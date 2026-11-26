"""Self-grade with the official kit scoring functions. Calls Engine.simulate directly (no HTTP)."""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path

import numpy as np

from evaluation import windows as W
from training.data import ROOT, load_archive, load_config
from wethrfork.engine import Engine

log = logging.getLogger(__name__)
LEADS = (0, 3, 7)  # days 1, 4, 8


def _refs(w: dict, clim: np.ndarray, steps: int) -> tuple[np.ndarray, np.ndarray]:
    persist = np.repeat(w["init"][-1][None], steps, axis=0)
    slots = [(w["slot0"] + k) % 366 for k in range(1, steps + 1)]
    return persist, clim[slots]


def grade(engine: Engine, wins: list[dict], steps: int = 10) -> dict:
    from monsoon_r1 import scoring as S

    clim = engine.clim
    ss_w, csi_w, ratios = [], [], []
    per_lead = {k: [] for k in LEADS}
    csi_lead = {k: [] for k in LEADS}
    valid = True
    t_ms = []
    for w in wins:
        t0 = time.perf_counter()
        pred = engine.simulate(w["init"], w["doy_sincos"], steps, None)
        t_ms.append((time.perf_counter() - t0) * 1000)
        valid &= not S.validity(pred, steps)
        persist, climr = _refs(w, clim, steps)
        idx = list(LEADS)
        sk = S.skill_vs_best_ref(pred[idx], w["truth"][idx], persist[idx], climr[idx])
        ss_w.append(float(np.nanmean(sk["ss"])))
        for k in LEADS:
            s_k = S.skill_vs_best_ref(pred[[k]], w["truth"][[k]], persist[[k]], climr[[k]])
            per_lead[k].append(s_k["ss"])
            c = S.csi_skill(
                S.csi(pred[k, 1], w["truth"][k, 1]),
                S.csi(persist[k, 1], w["truth"][k, 1]),
                S.csi(climr[k, 1], w["truth"][k, 1]),
            )
            csi_lead[k].append(c)
        csi_w.append(
            S.csi_skill(
                S.csi(pred[idx, 1], w["truth"][idx, 1]),
                S.csi(persist[idx, 1], w["truth"][idx, 1]),
                S.csi(climr[idx, 1], w["truth"][idx, 1]),
            )
        )
        ratios.append(S.variance_ratio(pred[7], w["truth"][7]))
    fp = S.forecast_points(ss_w, csi_w)
    ratios = np.array(ratios)
    blur_pts = S.anti_blur_points(ratios)
    ss_lead = {int(k) + 1: np.nanmean(np.array(v), axis=0).tolist() for k, v in per_lead.items()}
    return {
        "n_windows": len(wins),
        "valid": bool(valid),
        "mean_ss": fp["mean_ss"],
        "mean_csi_skill": fp["mean_csi_skill"],
        "rmse_pts": fp["rmse_pts"],
        "csi_pts": fp["csi_pts"],
        "blur_pts": blur_pts,
        "var_ratio_day8_mean": np.nanmean(ratios, axis=0).tolist(),
        "ss_by_lead_channel": ss_lead,
        "ss_lead_mean": {k: float(np.nanmean(v)) for k, v in ss_lead.items()},
        "csi_skill_by_lead": {
            int(k) + 1: float(np.nanmean(v)) if np.isfinite(v).any() else None for k, v in csi_lead.items()
        },
        "mean_ms": float(np.mean(t_ms)),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/eval.yaml")
    ap.add_argument("--data-config", default="configs/data.yaml")
    ap.add_argument("--tag", default="dev")
    ap.add_argument("--artifacts", default=None)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO)
    cfg = load_config(ROOT / args.config)
    arc = load_archive(load_config(ROOT / args.data_config))
    eng = Engine.load(Path(args.artifacts) if args.artifacts else None)
    assert eng.ready, eng.error
    res = {"systematic": grade(eng, W.systematic(arc, cfg)), "typed": grade(eng, W.typed(arc, cfg))}
    for name, r in res.items():
        print(
            f"[{name}] n={r['n_windows']} valid={r['valid']} mean_ss={r['mean_ss']:.4f} ({r['rmse_pts']:.1f}/30) "
            f"csi_skill={r['mean_csi_skill']:.4f} ({r['csi_pts']:.1f}/15) blur={r['blur_pts']:.1f}/10"
        )
        print("   ss by lead (mean over channels):", {k: round(v, 3) for k, v in r["ss_lead_mean"].items()})
        print("   day-8 variance ratio by channel:", [round(x, 2) for x in r["var_ratio_day8_mean"]])
    out = ROOT / "runs" / "selfgrade"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{args.tag}.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
