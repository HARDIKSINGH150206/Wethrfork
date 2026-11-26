"""Fit the ridge skill head: closed-form per (lead, channel, cell), lambda chosen on the calibration split."""
from __future__ import annotations

import argparse
import logging
import time

import numpy as np
import torch

from training.data import ROOT, load_archive, load_config, sample_starts, split_bounds
from wethrfork.normalize import to_z
from wethrfork.physics import MAX_STEPS, NC, NLAT, NLON, T_IN
from wethrfork.ridge import N_FEAT, design_features

log = logging.getLogger(__name__)


def load_norm_inputs(art_dir):
    import json

    clim = torch.from_numpy(np.load(art_dir / "climatology.npy"))
    s = torch.tensor(json.loads((art_dir / "norm.json").read_text())["anom_std"], dtype=torch.float32)
    return clim, s


def build_z(arc, clim, s) -> torch.Tensor:
    """Whole archive in normalised anomaly space [N,6,H,W]."""
    slots = torch.from_numpy(arc.slots())
    return to_z(torch.from_numpy(arc.data), clim[slots], s)


def batched_ridge(x: torch.Tensor, y: torch.Tensor, lam: float) -> torch.Tensor:
    """x [cells,N,F], y [cells,N,C] -> W [cells,F,C] (float64 normal equations)."""
    xt = x.transpose(1, 2)
    g = xt @ x
    eye = torch.eye(x.shape[2], dtype=x.dtype).unsqueeze(0)
    return torch.linalg.solve(g + lam * eye, xt @ y)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/ridge.yaml")
    ap.add_argument("--data-config", default="configs/data.yaml")
    ap.add_argument("--leads", type=int, default=None)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO)
    cfg = load_config(ROOT / args.config)
    dcfg = load_config(ROOT / args.data_config)
    art = ROOT / "artifacts"
    arc = load_archive(dcfg)
    clim, s = load_norm_inputs(art)
    z = build_z(arc, clim, s)
    slots = torch.from_numpy(arc.slots())
    leads = args.leads or cfg["leads"]
    lambdas = cfg["lambdas"]

    tr = split_bounds(arc, dcfg, "train")
    ca = split_bounds(arc, dcfg, "calib")
    t_tr = torch.from_numpy(sample_starts(*tr, horizon=leads))
    t_ca = torch.from_numpy(sample_starts(*ca, horizon=leads))
    log.info("train samples %d, calib samples %d", len(t_tr), len(t_ca))

    def window(t):
        idx = torch.stack([t - 2, t - 1, t], dim=1)
        return z[idx]  # [N,3,6,H,W]

    w_tr, w_ca = window(t_tr), window(t_ca)
    weights = torch.zeros(MAX_STEPS, NC, N_FEAT, NLAT, NLON)
    best_lams = np.zeros((MAX_STEPS, NC))
    t0 = time.time()
    for k in range(1, leads + 1):
        x_tr = design_features(w_tr, slots[t_tr + k]).double()
        x_ca = design_features(w_ca, slots[t_ca + k]).double()
        y_tr = z[t_tr + k].reshape(len(t_tr), NC, -1).permute(2, 0, 1).double()  # [cells,N,6]
        y_ca = z[t_ca + k].reshape(len(t_ca), NC, -1).permute(2, 0, 1).double()
        errs = []
        sols = []
        for lam in lambdas:
            w = batched_ridge(x_tr, y_tr, lam)  # [cells,F,6]
            sols.append(w)
            errs.append(((x_ca @ w - y_ca) ** 2).mean(dim=(0, 1)))  # [6]
        errs_t = torch.stack(errs)  # [L,6]
        pick = errs_t.argmin(dim=0)
        for c in range(NC):
            wsel = sols[int(pick[c])][:, :, c]  # [cells,F]
            weights[k - 1, c] = wsel.T.reshape(N_FEAT, NLAT, NLON).float()
            best_lams[k - 1, c] = lambdas[int(pick[c])]
        log.info("lead %d done (%.1fs) calib mse by channel %s", k, time.time() - t0, errs_t.min(dim=0).values.tolist())
    for k in range(leads, MAX_STEPS):
        weights[k] = weights[leads - 1]
    out = ROOT / cfg["out"]
    out.parent.mkdir(parents=True, exist_ok=True)
    torch.save(weights, out)
    log.info("saved %s; lambdas by lead %s", out, best_lams[:leads].tolist())


if __name__ == "__main__":
    main()
