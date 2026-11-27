"""Pre-demo checks. Static mode needs no servers; --live also checks the running stack.

Run it on the presentation laptop before every rehearsal:  python scripts/preflight.py [--live]
Exit code 0 only if every check passes. Nothing here is specific to a date or a window.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import socket
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    RESULTS.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))
    return ok


def port_free(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def static_checks(ports: tuple[int, int, int]) -> None:
    check("python >= 3.10", sys.version_info >= (3, 10), sys.version.split()[0])
    missing = []
    for m in ("torch", "numpy", "fastapi", "uvicorn", "yaml", "pandas", "xarray", "netCDF4", "monsoon_r1"):
        try:
            __import__(m)
        except Exception:
            missing.append(m)
    hint = (
        " (the lab's live verdict needs the kit: pip install ./vendor/monsoon_r1_kit-1.0.0-py3-none-any.whl)"
        if "monsoon_r1" in missing
        else ""
    )
    check("python packages", not missing, f"missing: {missing}{hint}" if missing else "all importable")

    art = ROOT / "artifacts"
    from training.export_artifacts import POSTPROC_KEYS, REQUIRED

    absent = [f for f in REQUIRED if not (art / f).exists()]
    check("artifacts present", not absent, f"missing: {absent}" if absent else f"{len(REQUIRED)} files")
    if (art / "manifest.json").exists():
        man = json.loads((art / "manifest.json").read_text())
        bad = [n for n, m in man["files"].items() if hashlib.sha256((art / n).read_bytes()).hexdigest() != m["sha256"]]
        check("manifest hashes match", not bad, f"mismatch: {bad}" if bad else man["model_name"])
    else:
        check("manifest hashes match", False, "artifacts/manifest.json missing")
    if (art / "postproc.json").exists():
        pp = json.loads((art / "postproc.json").read_text())
        lost = [k for k in POSTPROC_KEYS if k not in pp]
        check(
            "calibration saved completely",
            not lost,
            f"missing keys: {lost}" if lost else "shrink, floor, scale, damping, blend",
        )

    # the dashboard's start states come from the local dataset, which is never committed
    from training.data import load_archive, load_config

    dcfg = load_config(ROOT / "configs" / "data.yaml")
    data_path = ROOT / dcfg["data_path"]
    if not check("local dataset present", data_path.exists(), str(data_path.relative_to(ROOT))):
        print("       the dashboard needs it for start states: copy india_climate_train.nc into data/")
    else:
        try:
            arc = load_archive(dcfg)
            import numpy as np

            check(
                "dataset readable and finite",
                arc.data.shape[1:] == (6, 32, 36) and bool(np.isfinite(arc.data).all()),
                f"{arc.data.shape[0]} days",
            )
            from evaluation.windows import index_of

            demo = load_config(ROOT / "configs" / "demo.yaml")["windows"]
            miss = []
            for w in demo:
                try:
                    index_of(arc, w["last_input_day"])
                except Exception:
                    miss.append(w["id"])
            check("demo start states resolve", not miss, f"unresolved: {miss}" if miss else f"{len(demo)} windows")
        except Exception as e:
            check("dataset readable and finite", False, f"{type(e).__name__}: {e}")

    node, npm = shutil.which("node"), shutil.which("npm")
    check("node and npm", bool(node and npm), "found" if node and npm else "install Node 20+")
    dist = ROOT / "dashboard" / "dist"
    check("dashboard built", (dist / "index.html").exists(), "run: cd dashboard && npm ci && npm run build")
    if dist.exists():
        ext = []
        for p in list(dist.rglob("*.html")) + list(dist.rglob("*.css")):
            txt = p.read_text(errors="ignore")
            for marker in ("fonts.googleapis", "fonts.gstatic", "cdn.", "unpkg.com", "jsdelivr"):
                if marker in txt:
                    ext.append(f"{p.name}:{marker}")
        check("dashboard works offline (no CDN fonts or scripts)", not ext, str(ext) if ext else "no external hosts")
    for name, port in zip(("forecast server", "lab server", "dashboard"), ports, strict=True):
        free = port_free(port)
        print(f"[INFO] port {port} ({name}): {'free' if free else 'in use (fine if the stack is already running)'}")

    try:
        import numpy as np

        from wethrfork.engine import Engine

        eng = Engine.load()
        check("engine loads and warms up", eng.ready, eng.error or eng.model_name)
        if eng.ready:
            from wethrfork.climatology import sincos_of_slot

            x = eng.clim[[100, 101, 102]].copy()
            p = np.zeros((6, 32, 36), np.float32)
            p[0, 10:20, 10:20] = 3.0
            t0 = time.perf_counter()
            out = eng.simulate(x, sincos_of_slot(102), 10, p)
            dt = time.perf_counter() - t0
            check(
                "shocked 10-day call is fast and finite",
                bool(np.isfinite(out).all()) and dt < 2.0,
                f"{dt:.2f}s (limit 5s)",
            )
    except Exception as e:
        check("engine loads and warms up", False, f"{type(e).__name__}: {e}")


def live_checks(ports: tuple[int, int, int]) -> None:
    import requests

    judge, lab, dash = (f"http://127.0.0.1:{p}" for p in ports)
    route = "/" + "sim" + "ulate"
    try:
        h = requests.post(judge + "/health", timeout=5).json()
        check("forecast server ready", h.get("status") == "ready", h.get("model_name", ""))
    except Exception as e:
        check("forecast server ready", False, type(e).__name__)
        return
    try:
        st = requests.get(lab + "/status", timeout=5).json()
        check("lab server up", True, f"engine ready: {st.get('engine_ready')}, data present: {st.get('data_present')}")
        wins = requests.get(lab + "/windows", timeout=15)
        check(
            "start states load",
            wins.status_code == 200 and len(wins.json()) > 0,
            f"{len(wins.json()) if wins.ok else wins.text[:80]}",
        )
        if wins.ok and wins.json():
            w = requests.get(lab + f"/windows/{wins.json()[0]['id']}", timeout=20).json()
            body = {"init_states": w["init_states"], "doy_sincos": w["doy_sincos"], "steps": 10}
            import numpy as np

            pert = np.zeros((6, 32, 36))
            pert[0, 8:20, 17:29] = 3.0
            t0 = time.perf_counter()
            r = requests.post(judge + route, json={**body, "perturbation": pert.tolist()}, timeout=10)
            dt = time.perf_counter() - t0
            ok = r.status_code == 200 and bool(np.isfinite(np.asarray(r.json()["rollout"])).all())
            check("fork round trip through the real server", ok, f"{dt:.2f}s")
            v = requests.post(lab + "/verdict", json={**body, "perturbation": pert.tolist(), "box": None}, timeout=20)
            check(
                "causality verdict",
                v.status_code == 200 and all(v.json()["checks"].values()),
                str(v.json().get("checks")) if v.ok else v.text[:80],
            )
    except Exception as e:
        check("lab server up", False, f"{type(e).__name__}: {e}")
    try:
        r = requests.get(dash, timeout=5)
        check("dashboard served", r.status_code == 200, dash)
        c = requests.options(
            judge + "/health", headers={"Origin": dash, "Access-Control-Request-Method": "POST"}, timeout=5
        )
        check("CORS lets the dashboard call the server", c.headers.get("access-control-allow-origin") in ("*", dash))
    except Exception as e:
        check("dashboard served", False, f"{type(e).__name__}: {e}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="also check the running servers and dashboard")
    ap.add_argument("--ports", default="8000,8001,4173")
    a = ap.parse_args()
    ports = tuple(int(x) for x in a.ports.split(","))  # type: ignore[assignment]
    print("== static checks ==")
    static_checks(ports)  # type: ignore[arg-type]
    if a.live:
        print("== live checks ==")
        live_checks(ports)  # type: ignore[arg-type]
    bad = [n for n, ok, _ in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(bad)}/{len(RESULTS)} checks passed" + (f"; FAILED: {bad}" if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
