"""Fit damping toward climatology, rain quantile maps and rain frequency scaling on the calibration year."""

from __future__ import annotations

import argparse
import json
import logging

import numpy as np

from training.data import ROOT, load_archive, load_config
from training.forecasts import collect, to_phys
from wethrfork.blend import PostProc
from wethrfork.engine import Engine
from wethrfork.physics import MAX_STEPS, NC, TP, lat_weights

log = logging.getLogger(__name__)
# competition points per unit: 30 pts for mean ss 0.12 over 6 channels x 3 leads; 15 pts for CSI skill 0.10 over 3 leads
RMSE_PTS_PER_SS = 30.0 / 0.12 / 18.0
CSI_PTS_PER_SKILL = 15.0 / 0.10 / 3.0


def csi(p: np.ndarray, o: np.ndarray, thr: float = 10.0) -> float:
    a, b = p > thr, o > thr
    h, m, f = (a & b).sum(), (~a & b).sum(), (a & ~b).sum()
    return float(h / (h + m + f)) if (h + m + f) else float("nan")


def fit_damping(fc, blended_z, s, floor: float, clip: tuple[float, float]) -> np.ndarray:
    """RMSE-optimal shrink a = <F,O>/<F,F> in normalised anomaly space, raised until the day-k variance ratio >= floor."""
    d = np.ones((MAX_STEPS, NC), dtype=np.float32)
    z_true = _truth_z(fc, s)
    for k in range(MAX_STEPS):
        for c in range(NC):
            f, o = blended_z[:, k, c].ravel(), z_true[:, k, c].ravel()
            a = float(np.clip((f * o).sum() / max((f * f).sum(), 1e-12), clip[0], clip[1]))
            while True:
                z = blended_z[:, k : k + 1].copy()
                z[:, :, c] *= a
                p = to_phys(z, fc.clim_tgt[:, k : k + 1], s)[:, 0, c]
                vt = fc.truth_phys[:, k, c].reshape(len(p), -1).var(axis=1)
                ratio = float(np.mean(p.reshape(len(p), -1).var(axis=1) / np.maximum(vt, 1e-12)))
                if ratio >= floor or a >= 1.0:
                    break
                a = min(1.0, a + 0.05)
            d[k, c] = a
    return d


def _truth_z(fc, s) -> np.ndarray:
    import torch

    from wethrfork.normalize import to_z

    return to_z(torch.from_numpy(fc.truth_phys), torch.from_numpy(fc.clim_tgt), s).numpy()


def fit_rain(tp_f: np.ndarray, tp_o: np.ndarray, nq: int) -> tuple[list, list]:
    q = np.linspace(0, 100, nq)
    src = np.percentile(tp_f, q)
    dst = np.percentile(tp_o, q)
    src = np.maximum.accumulate(src + 1e-9 * np.arange(nq))
    return src.tolist(), dst.tolist()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/calib.yaml")
    ap.add_argument("--data-config", default="configs/data.yaml")
    ap.add_argument("--ship", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO)
    cfg = load_config(ROOT / args.config)
    dcfg = load_config(ROOT / args.data_config)
    arc = load_archive(dcfg)
    path = ROOT / "artifacts" / "postproc.json"
    pp = json.loads(path.read_text())
    eng = Engine.load(warmup=False, verify=False)
    splits = cfg["ship_refit_splits"] if args.ship else [cfg["fit_split"]]
    fc = collect(eng, arc, dcfg, splits)
    proc = PostProc({"blend_w": pp["blend_w"]})
    blended = np.stack([proc.blend(fc.z_nn[i], fc.z_ridge[i]) for i in range(len(fc.z_nn))])
    damp = fit_damping(fc, blended, eng.s, cfg["damping"]["min_variance_ratio"], tuple(cfg["damping"]["clip"]))
    log.info("damping by lead (mean over channels): %s", np.round(damp.mean(axis=1), 2).tolist())
    z = np.stack([PostProc({"damp": damp}).damp_z(blended[i]) for i in range(len(blended))])
    phys = to_phys(z, fc.clim_tgt, eng.s)
    scale, shrink, floor = [], [], []
    wl = lat_weights()[None, :, None]
    for k in range(MAX_STEPS):
        raw0 = phys[:, k, TP]
        obs = fc.truth_phys[:, k, TP]
        clim_tp = fc.clim_tgt[:, k, TP]
        persist = fc.last_phys[:, TP]

        def rmse_w(x, obs=obs):  # per-window latitude-weighted RMSE, like the judge's per-window skill
            return np.sqrt((wl * (x - obs) ** 2).mean(axis=(1, 2)))

        ref = np.minimum(rmse_w(persist), rmse_w(clim_tp))
        c_ref = np.nanmax([csi(persist, obs), csi(clim_tp, obs)])
        best, best_j = (1.0, 0.0, 1.0), -1e9
        for a in (0.3, 0.5, 0.7, 0.85, 1.0):
            raw = clim_tp + a * (raw0 - clim_tp)
            for fl in (0.0, 0.5, 1.0, 2.0):
                for f in np.arange(0.8, 2.01, 0.1):
                    m = np.where(raw > 5, 5 + (raw - 5) * f, raw)
                    m = np.where(m < fl, 0.0, m)
                    c = csi(m, obs)
                    cs = 0.0 if np.isnan(c) else (c - c_ref) / (1 - c_ref)
                    ss_w = float(np.mean(1.0 - rmse_w(m) / np.maximum(ref, 1e-6)))
                    j = RMSE_PTS_PER_SS * ss_w + CSI_PTS_PER_SKILL * cs
                    if j > best_j:
                        best_j, best = j, (a, fl, float(f))
        shrink.append(best[0])
        floor.append(best[1])
        scale.append(best[2])
        log.info(
            "lead %d: shrink %.2f floor %.1f scale %.2f points-proxy %.2f", k + 1, best[0], best[1], best[2], best_j
        )
    sm = np.convolve(np.pad(scale, 1, mode="edge"), np.ones(3) / 3, mode="valid")
    pp.update({"damp": damp.tolist(), "rain_scale": sm.tolist(), "rain_scale_above": 5.0})
    path.write_text(json.dumps(pp))
    log.info("wrote %s", path)


if __name__ == "__main__":
    main()
