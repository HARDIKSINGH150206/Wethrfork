"""Official shocks on every systematic window (not just one per season): pass rate of each judge check and the
causality points the kit would award per window. Also checks day-4 skill against persistence on the same windows."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict

import numpy as np

from evaluation import windows as W
from training.data import ROOT, load_archive, load_config
from wethrfork.engine import Engine

CHECKS = ("finite", "nonzero", "localized", "propagates", "stable")


def main() -> int:
    from monsoon_r1 import contract as C
    from monsoon_r1 import scoring as S

    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/eval.yaml")
    ap.add_argument("--data-config", default="configs/data.yaml")
    args = ap.parse_args()
    cfg = load_config(ROOT / args.config)
    arc = load_archive(load_config(ROOT / args.data_config))
    eng = Engine.load()
    assert eng.ready, eng.error
    std = np.array(json.loads((ROOT / "artifacts" / "stats.json").read_text())["std"], dtype=np.float32)
    wins = W.systematic(arc, cfg)
    counts = defaultdict(int)
    pts, null_ok_all, d4 = [], True, []
    by_season = defaultdict(list)
    for w in wins:
        base = eng.simulate(w["init"], w["doy_sincos"], 10, None)
        null = eng.simulate(w["init"], w["doy_sincos"], 10, np.zeros((6, 32, 36), np.float32))
        null_ok = S.null_consistent(base, null, std)
        null_ok_all &= null_ok
        res = []
        for name, box in (("warm_ocean", C.BOX_BAY_OF_BENGAL), ("monsoon_stall", C.BOX_ARABIAN_SEA)):
            shock = eng.simulate(w["init"], w["doy_sincos"], 10, S.make_shock(name, w["init"][-1], std))
            r = S.causality_checks(base, shock, box, std)
            res.append(r)
            for c in CHECKS:
                counts[f"{name}.{c}"] += int(bool(r[c]))
        p = S.causality_points(res, null_ok)
        pts.append(p)
        month = int(arc.dates[w["last_idx"]].month)
        by_season[
            "DJF" if month in (12, 1, 2) else "MAM" if month in (3, 4, 5) else "JJAS" if month in (6, 7, 8, 9) else "ON"
        ].append(p)
        persist = np.repeat(w["init"][-1][None], 10, axis=0)
        d4.append(S.skill_vs_best_ref(base[[3]], w["truth"][[3]], persist[[3]], persist[[3]])["ss_persist"])
    n = len(wins)
    print(f"windows: {n}   null consistent in all: {null_ok_all}")
    for name in ("warm_ocean", "monsoon_stall"):
        print(f"  {name:14s}", "  ".join(f"{c} {counts[f'{name}.{c}'] / n:.0%}" for c in CHECKS))
    pts = np.array(pts)
    print(
        f"causality points per window: mean {pts.mean():.2f}/15, min {pts.min():.2f}, full marks in {np.mean(pts >= 14.99):.0%} of windows"
    )
    print("  by season:", {k: round(float(np.mean(v)), 2) for k, v in by_season.items()})
    d4 = np.array(d4)
    print(
        f"day-4 skill vs persistence, mean over windows by channel: {np.round(np.nanmean(d4, axis=0), 3).tolist()}  (positive = beats persistence)"
    )
    out = ROOT / "runs" / "sweep"
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(
        json.dumps(
            {
                "n": n,
                "points_mean": float(pts.mean()),
                "points_min": float(pts.min()),
                "checks": {k: v / n for k, v in counts.items()},
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
