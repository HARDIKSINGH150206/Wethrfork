"""Collect network and ridge forecasts on a split, in normalised and physical space, for calibration fitting."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import torch

from training.data import Archive, sample_starts, split_bounds
from wethrfork.engine import Engine
from wethrfork.model import rollout
from wethrfork.normalize import from_z, to_z
from wethrfork.physics import MAX_STEPS


@dataclass
class Forecasts:
    z_nn: np.ndarray  # [N,14,6,H,W]
    z_ridge: np.ndarray  # [N,14,6,H,W]
    truth_phys: np.ndarray  # [N,14,6,H,W]
    clim_tgt: np.ndarray  # [N,14,6,H,W]
    last_phys: np.ndarray  # [N,6,H,W]


@torch.no_grad()
def collect(engine: Engine, arc: Archive, dcfg: dict, split_names: list[str], leads: int = MAX_STEPS, stride: int = 1) -> Forecasts:
    ts = []
    for name in split_names:
        lo, hi = split_bounds(arc, dcfg, name)
        ts.append(sample_starts(lo, hi, horizon=leads))
    t = np.concatenate(ts)[::stride]
    slots_all = arc.slots()
    out = {k: [] for k in ("z_nn", "z_ridge", "truth", "clim", "last")}
    for i in range(0, len(t), 16):
        tb = t[i : i + 16]
        init = torch.from_numpy(np.stack([arc.data[j - 2 : j + 1] for j in tb]))
        slots = torch.from_numpy(np.stack([slots_all[j : j + leads + 1] for j in tb]))
        prev = torch.stack([(slots[:, 0] - 2) % 366, (slots[:, 0] - 1) % 366, slots[:, 0]], dim=1)
        z0 = to_z(init, engine.clim_t[prev], engine.s)
        zr = torch.stack([engine.ridge.predict(z0[b], slots[b, 1:]) for b in range(len(tb))])
        zn = (
            rollout(engine.net, z0, slots, engine.clim_t, engine.s, engine.static_t, leads)
            if engine.net is not None
            else zr.clone()
        )
        out["z_nn"].append(zn.numpy())
        out["z_ridge"].append(zr.numpy())
        out["truth"].append(np.stack([arc.data[j + 1 : j + 1 + leads] for j in tb]))
        out["clim"].append(engine.clim_t[slots[:, 1:]].numpy())
        out["last"].append(init[:, -1].numpy())
    return Forecasts(
        np.concatenate(out["z_nn"]),
        np.concatenate(out["z_ridge"]),
        np.concatenate(out["truth"]),
        np.concatenate(out["clim"]),
        np.concatenate(out["last"]),
    )


def to_phys(z: np.ndarray, clim: np.ndarray, s: torch.Tensor) -> np.ndarray:
    return from_z(torch.from_numpy(z), torch.from_numpy(clim), s).numpy()
