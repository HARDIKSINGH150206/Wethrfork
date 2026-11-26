"""Grader side of the judge rehearsal (evaluation/judge_rehearsal.py).

Runs INSIDE the grader container, which shares the server container's network namespace (loopback only, no internet)
and has the official kit installed. Every scored forecast call goes through the kit's own client
(`monsoon_r1.client.call_simulate`: 5 s hard deadline, 80 MB cap, no redirects, no retries), in plan order, back to
back, after the kit's `wait_ready` (health polled every 2 s). Then a few contract probes and the kit's schema validator.

Input:  <work>/plan.json, <work>/windows.npz      Output: <work>/out.npz, <work>/results.json
Never imported by the server. The route path is built from pieces (the repo scan treats a file holding the literal
route as server code).
"""

from __future__ import annotations

import contextlib
import io
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

URL = "http://127.0.0.1:8000"
ROUTE = "/" + "sim" + "ulate"


def _health_probe(requests) -> dict:
    r = requests.post(URL + "/health", timeout=10, allow_redirects=False)
    js = r.json()
    return {"status_code": r.status_code, "body": js, "content_type": r.headers.get("content-type", "")}


def _contract_probes(requests, init: np.ndarray, doy: list[float]) -> list[dict]:
    """Every allowed steps value (1..14): exact shape, nested lists, a numeric inference_ms, JSON content type."""
    from monsoon_r1 import contract as C
    from monsoon_r1 import scoring as S

    out = []
    for steps in range(1, C.MAX_STEPS + 1):
        body = {"init_states": C.encode_list(init), "doy_sincos": doy, "steps": steps, "perturbation": None}
        t0 = time.perf_counter()
        r = requests.post(URL + ROUTE, json=body, timeout=C.TIME_LIMIT_S, allow_redirects=False)
        wall = time.perf_counter() - t0
        rec = {
            "steps": steps,
            "status": r.status_code,
            "wall_s": wall,
            "content_type": r.headers.get("content-type", ""),
        }
        try:
            js = r.json()
            rec["keys"] = sorted(js)
            rec["rollout_is_list"] = isinstance(js.get("rollout"), list)
            ms = js.get("inference_ms")
            rec["inference_ms_ok"] = isinstance(ms, (int, float)) and not isinstance(ms, bool) and math.isfinite(ms)
            arr = np.asarray(js["rollout"], dtype="f4")
            rec["shape"] = list(arr.shape)
            rec["validity"] = S.validity(arr, steps)
        except Exception as e:  # recorded, judged on the host
            rec["error"] = f"{type(e).__name__}: {str(e)[:120]}"
        out.append(rec)
    return out


def main() -> int:
    import requests
    from monsoon_r1 import contract as C
    from monsoon_r1 import schema_validator
    from monsoon_r1.client import call_simulate, wait_ready

    work = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/work")
    plan = json.loads((work / "plan.json").read_text())
    z = np.load(work / "windows.npz")
    inits, perts = z["inits"], z["perts"]
    res: dict = {"grader_start_epoch": time.time()}

    ok, why = wait_ready(URL, float(plan["ready_limit_s"]), allow_private=True)
    res["ready"], res["ready_why"], res["ready_epoch"] = ok, why, time.time()
    if not ok:
        (work / "results.json").write_text(json.dumps(res))
        return 1
    res["health"] = _health_probe(requests)

    enc = {"list": C.encode_list, "b64": C.encode_array}
    rollouts = np.zeros((len(plan["calls"]), C.SCORE_STEPS, C.NC, C.NLAT, C.NLON), "f4")
    calls = []
    for n, c in enumerate(plan["calls"]):
        e = enc[c["enc"]]
        payload = {
            "init_states": e(inits[c["win"]]),
            "doy_sincos": c["doy"],
            "steps": C.SCORE_STEPS,
            "perturbation": None if c["pert"] < 0 else e(perts[c["pert"]]),
        }
        r = call_simulate(URL, payload, allow_private=True)
        if r.ok:
            rollouts[n] = r.out
        calls.append({"id": c["id"], "ok": r.ok, "wall_s": r.wall_s, "server_ms": r.server_ms, "error": r.error})
    res["calls"] = calls

    first = plan["calls"][0]
    res["probes"] = _contract_probes(requests, inits[first["win"]], first["doy"])

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = schema_validator.main([URL])
    res["validator_rc"], res["validator_log"] = rc, buf.getvalue()

    np.savez_compressed(work / "out.npz", rollouts=rollouts)
    (work / "results.json").write_text(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
