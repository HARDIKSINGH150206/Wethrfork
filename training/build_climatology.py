"""Build climatology, per-cell anomaly std, normalisation constants and static fields (kit method, 366 slots)."""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import numpy as np

from training.data import ROOT, Archive, load_archive, load_config

log = logging.getLogger(__name__)


def climatology(data: np.ndarray, slots: np.ndarray, smooth_days: int = 15) -> np.ndarray:
    """[N,6,H,W] daily fields + slot index per day -> [366,6,H,W]: slot mean then circular running mean."""
    clim = np.zeros((366,) + data.shape[1:], dtype=np.float64)
    cnt = np.zeros(366)
    for k in range(366):
        m = slots == k
        cnt[k] = m.sum()
        if cnt[k]:
            clim[k] = data[m].mean(axis=0, dtype=np.float64)
    h = smooth_days // 2
    out = np.zeros_like(clim)
    for k in range(366):
        out[k] = np.mean([clim[(k + o) % 366] for o in range(-h, h + 1)], axis=0)
    return out.astype(np.float32)


def anomaly_stats(arc: Archive, clim: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Per-cell std of daily anomalies [6,H,W] and per-channel std of normalised-space anomaly [6] (rain in log space)."""
    slots = arc.slots()
    a = arc.data - clim[slots]
    cell_std = a.std(axis=0).astype(np.float32)
    la = np.log1p(np.maximum(arc.data[:, 1], 0)) - np.log1p(np.maximum(clim[slots][:, 1], 0))
    s = a.std(axis=(0, 2, 3)).astype(np.float64)
    s[1] = la.std()
    return cell_std, s.astype(np.float32)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/data.yaml")
    ap.add_argument("--out", default="artifacts")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO)
    cfg = load_config(ROOT / args.config)
    arc = load_archive(cfg)
    lo, hi = cfg["climatology"]["years"]
    i0, i1 = arc.index_range(lo, hi)
    sub = Archive(arc.data[i0:i1], arc.dates[i0:i1], arc.static)
    clim = climatology(sub.data, sub.slots(), cfg["climatology"]["smooth_days"])
    cell_std, s = anomaly_stats(sub, clim)
    out = Path(ROOT / args.out)
    out.mkdir(parents=True, exist_ok=True)
    np.save(out / "climatology.npy", clim)
    np.save(out / "clim_std.npy", cell_std)
    np.save(out / "static.npy", arc.static.astype(np.float32))
    (out / "norm.json").write_text(json.dumps({"anom_std": [float(x) for x in s], "rain_log": True}, indent=1))
    stats_src = ROOT / cfg["stats_path"]
    if stats_src.exists():
        (out / "stats.json").write_text(stats_src.read_text())
    log.info("wrote artifacts to %s; anom_std=%s", out, s.tolist())


if __name__ == "__main__":
    main()
