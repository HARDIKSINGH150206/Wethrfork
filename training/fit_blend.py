"""Fit per-(lead, channel) blend weights between the network and the ridge head on the calibration year."""

from __future__ import annotations

import argparse
import json
import logging

import numpy as np

from training.data import ROOT, load_archive, load_config
from training.forecasts import collect, to_phys
from wethrfork.engine import Engine
from wethrfork.physics import MAX_STEPS, NC, lat_weights

log = logging.getLogger(__name__)


def fit_blend(fc, s, step: float = 0.05) -> np.ndarray:
    """Grid search w in [0,1] minimising latitude-weighted physical MSE. Returns [14,6]."""
    grid = np.round(np.arange(0.0, 1.0 + 1e-9, step), 4)
    wl = lat_weights()[None, :, None]
    out = np.full((MAX_STEPS, NC), 0.5, dtype=np.float32)
    for k in range(MAX_STEPS):
        tr = fc.truth_phys[:, k]
        for c in range(NC):
            errs = []
            for w in grid:
                z = w * fc.z_nn[:, k] + (1 - w) * fc.z_ridge[:, k]
                p = to_phys(z[:, None], fc.clim_tgt[:, k : k + 1], s)[:, 0]
                errs.append(float((wl * (p[:, c] - tr[:, c]) ** 2).mean()))
            out[k, c] = grid[int(np.argmin(errs))]
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/calib.yaml")
    ap.add_argument("--data-config", default="configs/data.yaml")
    ap.add_argument("--ship", action="store_true", help="refit on the shipping splits (calib + grade)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO)
    cfg = load_config(ROOT / args.config)
    dcfg = load_config(ROOT / args.data_config)
    arc = load_archive(dcfg)
    eng = Engine.load(warmup=False)
    splits = cfg["ship_refit_splits"] if args.ship else [cfg["fit_split"]]
    fc = collect(eng, arc, dcfg, splits)
    w = fit_blend(fc, eng.s, cfg["blend_grid_step"])
    path = ROOT / "artifacts" / "postproc.json"
    pp = json.loads(path.read_text()) if path.exists() else {}
    pp["blend_w"] = w.tolist()
    path.write_text(json.dumps(pp))
    log.info("blend weights by lead (mean over channels): %s", np.round(w.mean(axis=1), 2).tolist())
    log.info("by channel (mean over leads): %s", np.round(w.mean(axis=0), 2).tolist())


if __name__ == "__main__":
    main()
