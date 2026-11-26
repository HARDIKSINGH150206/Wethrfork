"""Per-cell forecast error maps of the served skill head on the grading year (used by the dashboard, never by serving)."""

from __future__ import annotations

import argparse
import logging

import numpy as np

from training.data import ROOT, load_archive, load_config, sample_starts, split_bounds
from wethrfork.climatology import sincos_of_slot
from wethrfork.engine import Engine
from wethrfork.physics import MAX_STEPS

log = logging.getLogger(__name__)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/calib.yaml")
    ap.add_argument("--data-config", default="configs/data.yaml")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO)
    cfg = load_config(ROOT / args.config)
    dcfg = load_config(ROOT / args.data_config)
    arc = load_archive(dcfg)
    eng = Engine.load(warmup=False)
    lo, hi = split_bounds(arc, dcfg, cfg["grade_split"])
    ts = sample_starts(lo, hi, horizon=MAX_STEPS)
    slots = arc.slots()
    se = np.zeros((MAX_STEPS, 6, 32, 36), dtype=np.float64)
    se_log = np.zeros((MAX_STEPS, 32, 36), dtype=np.float64)
    for t in ts:
        pred = eng.simulate(arc.data[t - 2 : t + 1], sincos_of_slot(int(slots[t])), MAX_STEPS, None)
        tru = arc.data[t + 1 : t + 1 + MAX_STEPS]
        se += (pred - tru) ** 2
        se_log += (np.log1p(pred[:, 1]) - np.log1p(np.maximum(tru[:, 1], 0))) ** 2
    out = ROOT / "artifacts"
    np.save(out / "sigma_err.npy", np.sqrt(se / len(ts)).astype(np.float32))
    np.save(out / "sigma_err_logtp.npy", np.sqrt(se_log / len(ts)).astype(np.float32))
    log.info("saved error maps from %d start days", len(ts))


if __name__ == "__main__":
    main()
