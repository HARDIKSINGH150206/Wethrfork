"""Per-season causality gate for both official shocks, with thresholds stricter than the judge's."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import numpy as np

from evaluation import windows as W
from training.data import ROOT, load_archive, load_config
from wethrfork.engine import Engine

log = logging.getLogger(__name__)
SHOCKS = {"warm_ocean": "BOX_BAY_OF_BENGAL", "monsoon_stall": "BOX_ARABIAN_SEA"}


def growth_ratio(base: np.ndarray, shock: np.ndarray, box, std: np.ndarray) -> float:
    from monsoon_r1 import scoring as S

    d = shock - base
    e = S._energy(d, std)
    near = S.near_mask(box)
    out_e = np.array([e[k][~near].sum() for k in range(e.shape[0])])
    late = out_e[3:8].mean() if e.shape[0] >= 8 else out_e[-1]
    return float(late / max(out_e[0], 1e-12))


def run_window(engine: Engine, w: dict, std: np.ndarray, steps: int = 10) -> dict:
    from monsoon_r1 import contract as C
    from monsoon_r1 import scoring as S

    base = engine.simulate(w["init"], w["doy_sincos"], steps, None)
    out = {}
    for name, box_name in SHOCKS.items():
        box = getattr(C, box_name)
        pert = S.make_shock(name, w["init"][-1], std)
        shocked = engine.simulate(w["init"], w["doy_sincos"], steps, pert)
        res = S.causality_checks(base, shocked, box, std)
        res["growth_ratio"] = growth_ratio(base, shocked, box, std)
        z = np.abs((shocked - base) / std[None, :, None, None])
        res["max_z"] = float(z.max())
        out[name] = res
    null = engine.simulate(w["init"], w["doy_sincos"], steps, np.zeros((6, 32, 36), np.float32))
    out["null_max_diff"] = float(np.abs(null - base).max())
    return out


def passes(res: dict, gate: dict) -> dict:
    ok = {}
    for name in SHOCKS:
        r = res[name]
        ok[name] = bool(
            r["finite"]
            and r["nonzero"]
            and r["localized"]  # the judge's own flags must pass as well as our stricter thresholds
            and r["propagates"]
            and r["stable"]
            and r.get("near_frac_day1", 0) >= gate["near_frac_min"]
            and r["growth_ratio"] >= gate["growth_min"]
            and r["far_frac_max"] <= gate["far_frac_max"]
            and r["max_z"] <= gate["max_z"]
        )
    ok["null"] = res["null_max_diff"] == 0.0
    return ok


def run_gate(engine: Engine, arc, cfg: dict) -> dict:
    std = np.array(json.loads((ROOT / "data" / "stats.json").read_text())["std"], dtype=np.float32)
    wins = W.shock_windows(arc, cfg)
    report = {}
    for season, w in wins.items():
        res = run_window(engine, w, std, cfg.get("steps", 10))
        report[season] = {"checks": res, "pass": passes(res, cfg["gate"])}
    report["all_pass"] = all(all(v["pass"].values()) for k, v in report.items() if k != "all_pass")
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/eval.yaml")
    ap.add_argument("--data-config", default="configs/data.yaml")
    ap.add_argument("--artifacts", default=None)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO)
    cfg = load_config(ROOT / args.config)
    arc = load_archive(load_config(ROOT / args.data_config))
    eng = Engine.load(Path(args.artifacts) if args.artifacts else None)
    assert eng.ready, eng.error
    rep = run_gate(eng, arc, cfg)
    print(f"{'season':6} {'shock':14} near1  grow  far    maxz  loc prop stab pass")
    for season, v in rep.items():
        if season == "all_pass":
            continue
        for name in SHOCKS:
            r = v["checks"][name]
            print(
                f"{season:6} {name:14} {r.get('near_frac_day1', 0):.2f}  {r['growth_ratio']:5.1f}  {r['far_frac_max']:.3f}  "
                f"{r['max_z']:.2f}  {int(r['localized'])}   {int(r['propagates'])}    {int(r['stable'])}    {int(v['pass'][name])}"
            )
        print(f"{season:6} null max diff {v['checks']['null_max_diff']}")
    print("GATE", "PASS" if rep["all_pass"] else "FAIL")
    out = ROOT / "runs" / "gate"
    out.mkdir(parents=True, exist_ok=True)
    (out / "latest.json").write_text(json.dumps(rep, indent=1, default=float))
    return 0 if rep["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
