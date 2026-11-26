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
from wethrfork.physics import MAX_STEPS, NC, TP

log = logging.getLogger(__name__)


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
    eng = Engine.load(warmup=False)
    splits = cfg["ship_refit_splits"] if args.ship else [cfg["fit_split"]]
    fc = collect(eng, arc, dcfg, splits)
    proc = PostProc({"blend_w": pp["blend_w"]})
    blended = np.stack([proc.blend(fc.z_nn[i], fc.z_ridge[i]) for i in range(len(fc.z_nn))])
    damp = fit_damping(fc, blended, eng.s, cfg["damping"]["min_variance_ratio"], tuple(cfg["damping"]["clip"]))
    log.info("damping by lead (mean over channels): %s", np.round(damp.mean(axis=1), 2).tolist())
    z = np.stack([PostProc({"damp": damp}).damp_z(blended[i]) for i in range(len(blended))])
    phys = to_phys(z, fc.clim_tgt, eng.s)
    src, dst, scale = [], [], []
    bias_t = cfg["rain"]["bias_target_by_lead"]
    for k in range(MAX_STEPS):
        s_k, d_k = fit_rain(phys[:, k, TP], fc.truth_phys[:, k, TP], cfg["rain"]["quantiles"])
        src.append(s_k)
        dst.append(d_k)
        tmp = PostProc({"rain_src": [s_k] * MAX_STEPS, "rain_dst": [d_k] * MAX_STEPS})
        mapped = tmp.map_rain(phys[:, k, TP][:, None].repeat(MAX_STEPS, axis=1))[:, 0]  # lead-independent map
        obs = fc.truth_phys[:, k, TP]
        n_obs = max(int((obs > 10).sum()), 1)
        best, best_c = 1.0, -1.0
        for f in np.arange(0.8, 1.81, 0.05):
            m = np.where(mapped > 5, 5 + (mapped - 5) * f, mapped)
            c = csi(m, obs)
            c = 0.0 if np.isnan(c) else c
            if c > best_c:
                best_c, best = c, float(f)
        m = np.where(mapped > 5, 5 + (mapped - 5) * best, mapped)
        log.info(
            "lead %d: rain scale %.2f csi %.3f freq bias %.2f (prior target %.2f)",
            k + 1,
            best,
            best_c,
            (m > 10).sum() / n_obs,
            bias_t[k],
        )
        scale.append(best)
    sm = np.convolve(np.pad(scale, 1, mode="edge"), np.ones(3) / 3, mode="valid")
    pp.update(
        {"damp": damp.tolist(), "rain_src": src, "rain_dst": dst, "rain_scale": sm.tolist(), "rain_scale_above": 5.0}
    )
    path.write_text(json.dumps(pp))
    log.info("wrote %s", path)


if __name__ == "__main__":
    main()
