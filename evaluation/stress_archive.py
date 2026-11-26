"""Brutal archive-wide check: every start day in the archive, 14 steps, null forecast, plus both official shocks on a stride.

For each window: kit validity (shape, finite, rain >= 0, t2m inside the judge's range), tcwv >= 0, null-shock consistency,
and for shocks the four causality checks. Reports pass counts, the worst offenders and latency percentiles."""

from __future__ import annotations

import argparse
import json
import time

import numpy as np

from training.data import ROOT, load_archive, load_config
from wethrfork.climatology import sincos_of_slot
from wethrfork.engine import Engine


def main() -> int:
    from monsoon_r1 import contract as C
    from monsoon_r1 import scoring as S

    ap = argparse.ArgumentParser()
    ap.add_argument("--shock-stride", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0, help="debug: only the first N windows")
    a = ap.parse_args()
    arc = load_archive(load_config(ROOT / "configs" / "data.yaml"))
    eng = Engine.load()
    assert eng.ready, eng.error
    std = np.array(json.loads((ROOT / "artifacts" / "stats.json").read_text())["std"], dtype=np.float32)
    slots = arc.slots()
    n = len(arc.dates)
    starts = list(range(2, n - 1))
    if a.limit:
        starts = starts[: a.limit]
    bad_valid, bad_tcwv, bad_null, lat_ms = [], [], [], []
    shock_n, shock_fail = 0, {"nonzero": 0, "localized": 0, "propagates": 0, "stable": 0, "finite": 0}
    shock_validity_fail = []
    pts = []
    zeros = np.zeros((6, 32, 36), np.float32)
    t_start = time.time()
    for k, t in enumerate(starts):
        init = arc.data[t - 2 : t + 1]
        doy = sincos_of_slot(int(slots[t]))
        t0 = time.perf_counter()
        out = eng.simulate(init, doy, 14, None)
        lat_ms.append((time.perf_counter() - t0) * 1000)
        if S.validity(out, 14):
            bad_valid.append(str(arc.dates[t].date()))
        if out[:, 5].min() < 0:
            bad_tcwv.append(str(arc.dates[t].date()))
        if k % a.shock_stride == 0:
            if np.abs(eng.simulate(init, doy, 14, zeros) - out).max() != 0.0:
                bad_null.append(str(arc.dates[t].date()))
            base10 = out[:10]
            res = []
            for name, box in (("warm_ocean", C.BOX_BAY_OF_BENGAL), ("monsoon_stall", C.BOX_ARABIAN_SEA)):
                sh = eng.simulate(init, doy, 10, S.make_shock(name, init[-1], std))
                if S.validity(sh, 10) or sh[:, 5].min() < 0:
                    shock_validity_fail.append((str(arc.dates[t].date()), name))
                r = S.causality_checks(base10, sh, box, std)
                res.append(r)
                for c in shock_fail:
                    shock_fail[c] += int(not r[c])
            shock_n += 2
            pts.append(S.causality_points(res, True))
        if (k + 1) % 500 == 0:
            print(f"  {k + 1}/{len(starts)} windows, {time.time() - t_start:.0f}s", flush=True)
    lat = np.array(lat_ms)
    pts = np.array(pts)
    print(f"\nwindows (every start day in the archive): {len(starts)}")
    print(
        f"  invalid forecasts (kit validity): {len(bad_valid)}   negative tcwv: {len(bad_tcwv)}   null-shock mismatches: {len(bad_null)}"
    )
    print(
        f"  shocked forecasts: {shock_n}   invalid: {len(shock_validity_fail)}   failed official checks: {shock_fail}"
    )
    print(
        f"  causality points per window: mean {pts.mean():.3f}/15, min {pts.min():.2f}, windows below 15: {int((pts < 14.99).sum())}/{len(pts)}"
    )
    print(
        f"  null 14-day forecast latency ms: p50 {np.percentile(lat, 50):.0f}  p95 {np.percentile(lat, 95):.0f}  p99 {np.percentile(lat, 99):.0f}  max {lat.max():.0f}"
    )
    out = ROOT / "runs" / "stress"
    out.mkdir(parents=True, exist_ok=True)
    (out / "archive.json").write_text(
        json.dumps(
            {
                "windows": len(starts),
                "invalid": bad_valid[:20],
                "neg_tcwv": bad_tcwv[:20],
                "null_mismatch": bad_null[:20],
                "shocked": shock_n,
                "shock_invalid": shock_validity_fail[:20],
                "shock_fail": shock_fail,
                "points_mean": float(pts.mean()),
                "points_min": float(pts.min()),
                "below_15": int((pts < 14.99).sum()),
                "latency_ms": {
                    "p50": float(np.percentile(lat, 50)),
                    "p95": float(np.percentile(lat, 95)),
                    "p99": float(np.percentile(lat, 99)),
                    "max": float(lat.max()),
                },
            },
            indent=1,
        )
    )
    ok = not (bad_valid or bad_tcwv or bad_null or shock_validity_fail)
    print("RESULT:", "PASS (validity and null)" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
