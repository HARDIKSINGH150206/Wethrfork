"""Browser tests for the dashboard: shared set-up.

Starts what the demo runs (forecast server :8000, lab server :8001, built dashboard :4173) unless it is already
running, then drives the real dashboard with Playwright (Chromium). Every forecast, verdict and sensitivity map comes
from our own servers.

Start states: with the dataset (data/india_climate_train.nc) the lab serves the real demo windows. Without it (CI),
the two start-state requests alone are answered in the browser with a plausible state built from the committed
climatology (`STUB`); nothing else is stubbed. Set E2E_STUB=1 to force the stub.

    pip install -r requirements-e2e.txt && python -m playwright install chromium
    (cd dashboard && npm ci && npm run build)
    pytest -q e2e/                        # screenshots of failures go to e2e-artifacts/
"""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
JUDGE, LAB, DASH = "http://127.0.0.1:8000", "http://127.0.0.1:8001", "http://127.0.0.1:4173"
ARTIFACTS = ROOT / "e2e-artifacts"
LOCAL_HOSTS = {"localhost", "127.0.0.1"}
STUB_SLOT = 196  # mid July: a monsoon state from the climatology


def _up(url: str, method: str = "GET") -> bool:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method=method), timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def _wait(url: str, seconds: float, method: str, proc: subprocess.Popen, log: Path) -> None:
    t0 = time.time()
    while time.time() - t0 < seconds:
        if _up(url, method):
            return
        if proc.poll() is not None:
            raise RuntimeError(f"{url} exited early:\n{log.read_text()[-3000:]}")
        time.sleep(0.5)
    raise RuntimeError(f"{url} not ready after {seconds} s:\n{log.read_text()[-3000:]}")


@pytest.fixture(scope="session")
def stack(tmp_path_factory):
    """The three services, started here only if not already running (a running `make demo` is reused)."""
    logs = tmp_path_factory.mktemp("logs")
    started: list[subprocess.Popen] = []
    dist = ROOT / "dashboard" / "dist" / "index.html"
    if not dist.exists():
        subprocess.run(["npm", "run", "build"], cwd=ROOT / "dashboard", check=True, capture_output=True)
    services = [
        ("forecast server", JUDGE + "/health", "POST", [sys.executable, "serve.py", "--port", "8000"], ROOT, 120),
        ("lab server", LAB + "/status", "GET", [sys.executable, "-m", "lab.lab_server", "--port", "8001"], ROOT, 120),
        ("dashboard", DASH + "/", "GET", ["npx", "vite", "preview", "--host", "127.0.0.1", "--port", "4173", "--strictPort"], ROOT / "dashboard", 60),
    ]  # fmt: skip
    try:
        for name, url, method, cmd, cwd, limit in services:
            if _up(url, method):
                continue
            log = logs / f"{name.replace(' ', '_')}.log"
            with open(log, "w") as fh:
                p = subprocess.Popen(cmd, cwd=cwd, stdout=fh, stderr=fh, start_new_session=True)
            started.append(p)
            _wait(url, limit, method, p, log)
        with urllib.request.urlopen(LAB + "/status", timeout=5) as r:
            status = json.loads(r.read())
        yield {"stub": os.environ.get("E2E_STUB") == "1" or not status["data_present"], "status": status}
    finally:
        for p in started:
            try:
                os.killpg(p.pid, signal.SIGTERM)
                p.wait(timeout=10)
            except Exception:
                pass


@pytest.fixture(scope="session")
def stub_window() -> dict:
    """A start state taken from the committed climatology (no archive, no dates), the lab's window format."""
    from wethrfork.climatology import sincos_of_slot

    clim = np.load(ROOT / "artifacts" / "climatology.npy")  # [366, 6, 32, 36]
    s = STUB_SLOT
    return {
        "id": "stub",
        "init_states": clim[s - 2 : s + 1].round(3).tolist(),
        "doy_sincos": sincos_of_slot(s),
        "weekday": 0,
        "clim": clim[[(s + k) % 366 for k in range(1, 11)]].round(3).tolist(),
    }


@pytest.fixture(scope="session")
def browser_instance():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        exe = os.environ.get("E2E_CHROME")  # optional: a system Chrome or Chromium
        try:
            b = p.chromium.launch(headless=True, args=["--no-sandbox"], **({"executable_path": exe} if exe else {}))
        except Exception:  # Playwright's own Chromium not installed: fall back to a system browser
            exe = exe or next(
                (shutil.which(n) for n in ("google-chrome", "chromium", "chromium-browser") if shutil.which(n)), None
            )
            if not exe:
                raise
            b = p.chromium.launch(headless=True, args=["--no-sandbox"], executable_path=exe)
        yield b
        b.close()


@pytest.fixture
def app(request, stack, stub_window, browser_instance):
    """A fresh dashboard page with the control run loaded. After the test: no page or console errors, and no request
    to any host other than our own local servers (the dashboard must work offline)."""
    ctx = browser_instance.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    errors: list[str] = []
    external: list[str] = []
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    page.on("console", lambda m: m.type == "error" and errors.append(f"console: {m.text}"))
    page.on(
        "request",
        lambda r: (
            urlparse(r.url).hostname not in LOCAL_HOSTS and not r.url.startswith("data:") and external.append(r.url)
        ),
    )
    if stack["stub"]:
        listing = [{"id": "stub", "label": "Climatological July state (test stub)", "season": "JJAS", "doy": STUB_SLOT}]
        page.route(re.compile(r".*:8001/windows$"), lambda r: r.fulfill(json=listing))
        page.route(re.compile(r".*:8001/windows/[^/]+$"), lambda r: r.fulfill(json=stub_window))
    page.goto(DASH + "/")
    page.wait_for_selector(".models button.on small", timeout=60000)  # the control run has answered
    page.mouse.move(720, 120)
    yield page
    if request.node.rep_call.failed if hasattr(request.node, "rep_call") else False:
        ARTIFACTS.mkdir(exist_ok=True)
        page.screenshot(path=str(ARTIFACTS / f"{request.node.name}.png"))
    ctx.close()
    assert not errors, errors[:5]
    assert not external, f"requests left the machine: {external[:5]}"


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)
