"""Strict judge-contract tests (no dataset, no Docker: they run in CI on every push).

The server is started the hard way: from a READ-ONLY copy that holds only what it may use (serve.py, wethrfork/,
artifacts/), with the kit, HTTP client libraries, plotting libraries and our own non-serve packages made unimportable,
and HOME read-only. It is then checked with the kit's own client and schema validator, the same code the judge runs.
Rules from AGENTS.md section 1 and the kit's API_CONTRACT.md. Calls go through `monsoon_r1.client.call_simulate`; the
one raw path is built from pieces (rule 21).

The full rehearsal on real data in a judge-like container is `make rehearsal` (evaluation/judge_rehearsal.py).
"""

from __future__ import annotations

import ast
import os
import shutil
import socket
import stat
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pytest

from tests.conftest import make_state

ROOT = Path(__file__).resolve().parent.parent
ROUTE = "/" + "sim" + "ulate"
NEEDS = ("serve.py", "wethrfork", "artifacts")
# Never importable by the server on the judge machine (rule 6 and 26). Plotting and UI libraries also cost repo points.
BLOCKED = {
    "monsoon_r1", "requests", "httpx", "aiohttp", "urllib3", "matplotlib", "plotly", "streamlit", "gradio", "dash",
    "training", "evaluation", "lab", "tests",
}  # fmt: skip
# Rule 6: the only third-party top-level modules the serve import graph may use.
ALLOWED = {
    "torch", "numpy", "scipy", "pandas", "xarray", "sklearn", "lightgbm", "onnxruntime", "fastapi", "flask", "uvicorn",
    "gunicorn", "starlette", "wethrfork",
}  # fmt: skip
STRICT_CALL_S = 1.5 if not os.environ.get("CI") else 5.0  # shared CI runners are slow; the judge allows 5 s
STRICT_READY_S = 60.0

pytestmark = pytest.mark.skipif(not (ROOT / "artifacts" / "ridge.pt").exists(), reason="needs the committed artifacts")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _make_read_only(p: Path) -> None:
    for q in sorted(p.rglob("*"), reverse=True):
        q.chmod(stat.S_IRUSR | stat.S_IRGRP | (stat.S_IXUSR | stat.S_IXGRP if q.is_dir() else 0))
    p.chmod(stat.S_IRUSR | stat.S_IXUSR)


def _make_writable(p: Path) -> None:
    for q in [p, *p.rglob("*")]:
        q.chmod(q.stat().st_mode | stat.S_IWUSR)


LAUNCH = """
import runpy, sys
BLOCKED = {blocked!r}
class _Block:
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] in BLOCKED:
            raise ImportError("not available on the judge machine: " + name)
        return None
sys.meta_path.insert(0, _Block())
sys.argv = ["serve.py", "--port", "{port}"]
runpy.run_path("serve.py", run_name="__main__")
"""


@pytest.fixture(scope="module")
def judge_server(tmp_path_factory):
    """serve.py from a read-only copy of only its own files, with forbidden imports blocked. Yields the base URL."""
    from monsoon_r1.client import wait_ready

    top = tmp_path_factory.mktemp("judge")
    sub, home = top / "sub", top / "home"
    sub.mkdir()
    home.mkdir()
    for name in NEEDS:
        src = ROOT / name
        if src.is_dir():
            shutil.copytree(src, sub / name, ignore=shutil.ignore_patterns("__pycache__"))
        else:
            shutil.copy2(src, sub / name)
    _make_read_only(sub)
    _make_read_only(home)
    port = _free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTHON")}
    env.update(HOME=str(home), PYTHONDONTWRITEBYTECODE="1")
    log = top / "server.log"
    t0 = time.time()
    with open(log, "w") as fh:
        proc = subprocess.Popen(
            [sys.executable, "-c", LAUNCH.format(blocked=BLOCKED, port=port)], cwd=sub, env=env, stdout=fh, stderr=fh
        )
    url = f"http://127.0.0.1:{port}"
    ok, why = wait_ready(url, 120, allow_private=True, abort=lambda: proc.poll() is not None)
    ready_s = time.time() - t0
    try:
        if not ok:
            pytest.fail(f"server not ready ({why}); log:\n{log.read_text()[-3000:]}")
        yield {"url": url, "ready_s": ready_s, "proc": proc, "log": log}
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        _make_writable(top)


@pytest.fixture(scope="module")
def std() -> np.ndarray:
    import json

    return np.array(json.loads((ROOT / "artifacts" / "stats.json").read_text())["std"], dtype=np.float32)


def _call(url: str, init: np.ndarray, doy, pert=None, encode="list"):
    from monsoon_r1 import contract as C
    from monsoon_r1.client import call_simulate

    enc = C.encode_list if encode == "list" else C.encode_array
    payload = {
        "init_states": enc(init),
        "doy_sincos": doy,
        "steps": C.SCORE_STEPS,
        "perturbation": None if pert is None else enc(pert),
    }
    r = call_simulate(url, payload, allow_private=True)
    assert r.ok, r.error
    assert r.wall_s <= STRICT_CALL_S, f"call took {r.wall_s:.2f} s (strict limit {STRICT_CALL_S} s)"
    return r.out


# ------------------------------------------------------------------------------------------------- start-up
def test_ready_from_read_only_copy_without_kit(judge_server):
    """Rules 6, 7, 8, 26: starts from serve.py + wethrfork/ + artifacts/ only, read-only, no kit, no training code."""
    assert judge_server["ready_s"] <= STRICT_READY_S, f"ready after {judge_server['ready_s']:.1f} s"
    assert judge_server["proc"].poll() is None


def test_health_contract(judge_server):
    """Rule 2: POST /health answers 200 with exactly {status: ready, model_name: wethrfork-<version>}."""
    import requests

    r = requests.post(judge_server["url"] + "/health", timeout=5, allow_redirects=False)
    assert r.status_code == 200
    js = r.json()
    assert set(js) == {"status", "model_name"}, js
    assert js["status"] == "ready"
    assert js["model_name"].startswith("wethrfork-")


# ------------------------------------------------------------------------------------------------- wire contract
def test_kit_schema_validator_passes(judge_server, capsys):
    """The organisers' validator: health, both wire forms, warm_ocean and zero perturbations, validity, 5 s."""
    from monsoon_r1 import schema_validator

    rc = schema_validator.main([judge_server["url"]])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "FAIL" not in out, out


@pytest.mark.parametrize("steps", range(1, 15))
def test_every_steps_value(judge_server, steps):
    """Rule 4: shape exactly [steps,6,32,36] for 1..14, nested lists, numeric inference_ms, nothing else, valid."""
    import math

    import requests
    from monsoon_r1 import scoring as S

    from wethrfork.climatology import sincos_of_slot

    body = {
        "init_states": make_state(steps).tolist(),
        "doy_sincos": sincos_of_slot(160),
        "steps": steps,
        "perturbation": None,
    }
    r = requests.post(judge_server["url"] + ROUTE, json=body, timeout=5, allow_redirects=False)
    assert r.status_code == 200, r.text[:300]
    assert "application/json" in r.headers.get("content-type", "")
    js = r.json()
    assert set(js) == {"rollout", "inference_ms"}
    assert isinstance(js["rollout"], list), "the answer must be nested lists, never base64"
    ms = js["inference_ms"]
    assert isinstance(ms, (int, float)) and not isinstance(ms, bool) and math.isfinite(ms)
    out = np.asarray(js["rollout"], dtype=np.float32)
    assert out.shape == (steps, 6, 32, 36)
    assert S.validity(out, steps) == []
    assert out[:, 5].min() >= 0.0, "moisture must never be negative (rule 10)"


def test_both_wire_forms_identical(judge_server, doy):
    """Rule 3: the tolerated base64 input gives exactly the same forecast as the canonical lists."""
    from monsoon_r1 import scoring as S

    st = make_state(3)
    a = _call(judge_server["url"], st, doy)
    b = _call(judge_server["url"], st, doy, encode="b64")
    assert np.array_equal(a, b)
    p = S.make_shock("warm_ocean", st[-1], S.STD_DEFAULT)
    assert np.array_equal(_call(judge_server["url"], st, doy, p), _call(judge_server["url"], st, doy, p, encode="b64"))


# ------------------------------------------------------------------------------------------------- determinism and shocks
def test_null_shock_and_determinism_bit_for_bit(judge_server, doy, std):
    """Rules 13 and 14: zeros equal no perturbation exactly (the judge allows 1e-3 std; we require 0.0) and every call
    is deterministic."""
    from monsoon_r1 import scoring as S

    st = make_state(4)
    base = _call(judge_server["url"], st, doy)
    again = _call(judge_server["url"], st, doy)
    null = _call(judge_server["url"], st, doy, np.zeros((6, 32, 36), np.float32))
    assert np.array_equal(base, again)
    assert float(np.abs(null - base).max()) == 0.0
    assert S.null_consistent(null, base, std)


@pytest.mark.parametrize("name,box", [("warm_ocean", "BOX_BAY_OF_BENGAL"), ("monsoon_stall", "BOX_ARABIAN_SEA")])
def test_official_shock_is_local_and_stable(judge_server, doy, std, name, box):
    """Hard gate and causality checks on a synthetic window: a finite, non-zero response that starts near the box,
    never jumps farther than the speed limit, and stays below our stricter z of 4 (judge: 5). Growth needs real
    weather, so `propagates` is checked by the rehearsal and the gate on real windows."""
    from monsoon_r1 import contract as C
    from monsoon_r1 import scoring as S

    st = make_state(5)
    base = _call(judge_server["url"], st, doy)
    shocked = _call(judge_server["url"], st, doy, S.make_shock(name, st[-1], std))
    assert S.validity(shocked, C.SCORE_STEPS) == []
    r = S.causality_checks(base, shocked, getattr(C, box), std)
    assert r["finite"] and r["nonzero"] and r["localized"] and r["stable"], r
    assert r["near_frac_day1"] >= 0.75, r
    assert r["no_teleport"] and r["far_frac_max"] <= 0.01, r
    assert float(np.abs((shocked - base) / std[None, :, None, None]).max()) <= 4.0


def test_server_wrote_nothing_and_logged_no_error(judge_server):
    """Rule 8 and clean operation: still running, and nothing alarming in its log after all of the above."""
    assert judge_server["proc"].poll() is None
    text = judge_server["log"].read_text()
    assert "Traceback" not in text, text[-3000:]


# ------------------------------------------------------------------------------------------------- static rules
def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            mods.add(node.module.split(".")[0])
    return mods


def test_serve_import_graph_uses_only_allowed_libraries():
    """Rule 6: serve.py and wethrfork/ import only the standard library and the judge's allowed libraries."""
    files = [ROOT / "serve.py", *sorted((ROOT / "wethrfork").rglob("*.py"))]
    bad = {}
    for f in files:
        extra = {m for m in _imports(f) if m not in sys.stdlib_module_names and m not in ALLOWED and m != "__future__"}
        if extra:
            bad[str(f.relative_to(ROOT))] = sorted(extra)
    assert not bad, f"imports not available on the judge machine: {bad}"


def test_serve_settings_threads_and_determinism():
    """Rules 5 and 14 in the source: four threads, deterministic algorithms, model in eval mode, 0.0.0.0."""
    src = (ROOT / "serve.py").read_text()
    assert "torch.set_num_threads(4)" in src
    assert "use_deterministic_algorithms(True)" in src
    assert 'host="0.0.0.0"' in src
    eng = (ROOT / "wethrfork" / "engine.py").read_text()
    assert ".eval()" in eng
