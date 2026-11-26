"""SpeedLimitNet: bounded semi-Lagrangian advection followed by a local residual CNN.

Reach budget per step (cells, Chebyshev): displacement cap 4 + bilinear 1 + three 3x3 convs 3 = 8.
Nothing in here looks at the whole map: no normalisation over space, no pooling, no attention, no FFT, no dilation.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from .normalize import from_z, to_z
from .physics import (
    DAY_S,
    DISP_CAP_CELLS,
    LAT,
    LON,
    NC,
    NLAT,
    NLON,
    T_IN,
    U10,
    V10,
    cell_size_ew_m,
    CELL_NS_M,
)

N_INPUT = NC * T_IN + NC + 2 + 2 + 2  # 18 window + 6 mean + 2 static + 2 position + 2 season = 30


@dataclass
class NetConfig:
    hidden: int = 128
    conv_blocks: int = 3
    displacement_cap: float = DISP_CAP_CELLS
    alpha_init: float = 0.5

    def __post_init__(self) -> None:
        assert self.conv_blocks <= 3, "speed limit: at most 3 conv blocks"
        assert self.displacement_cap <= 4.0, "speed limit: displacement cap at most 4 cells"

    def to_dict(self) -> dict:
        return asdict(self)


def cap_length(d: torch.Tensor, cap: float) -> torch.Tensor:
    """Smoothly cap the length of displacement vectors. d [..., 2, H, W] (x, y) -> same shape, |d| < cap."""
    r = torch.sqrt((d * d).sum(dim=-3, keepdim=True) + 1e-12)
    return d * (cap * torch.tanh(r / cap) / r)


class SpeedLimitNet(nn.Module):
    def __init__(self, cfg: NetConfig | None = None) -> None:
        super().__init__()
        self.cfg = cfg or NetConfig()
        c = self.cfg.hidden
        # alpha scales how strongly the 10 m wind steers each channel (learned, in (0, 1))
        p = min(max(self.cfg.alpha_init, 1e-3), 1 - 1e-3)
        self.theta = nn.Parameter(torch.full((NC,), math.log(p / (1 - p))))
        # pointwise displacement correction (1x1, adds no reach), 2 components per channel
        self.disp_corr = nn.Conv2d(N_INPUT, 2 * NC, kernel_size=1)
        nn.init.zeros_(self.disp_corr.weight)
        nn.init.zeros_(self.disp_corr.bias)
        layers: list[nn.Module] = []
        cin = NC + N_INPUT
        for _ in range(self.cfg.conv_blocks):
            layers += [
                nn.Conv2d(cin, c, 3, padding=1, padding_mode="replicate"),
                nn.GELU(),
                nn.Conv2d(c, c, 1),
                nn.GELU(),
            ]
            cin = c
        self.body = nn.Sequential(*layers)
        self.head = nn.Conv2d(c, NC, 1)
        nn.init.zeros_(self.head.weight)
        nn.init.zeros_(self.head.bias)

        lat = torch.tensor(LAT, dtype=torch.float32)
        dx = torch.tensor(cell_size_ew_m(LAT), dtype=torch.float32)  # [H]
        self.register_buffer("inv_dx", (DAY_S / dx).view(1, 1, NLAT, 1))
        self.register_buffer("inv_dy", torch.tensor(DAY_S / CELL_NS_M, dtype=torch.float32))
        self.register_buffer("lat_n", ((lat - 22.0) / 16.0).view(1, 1, NLAT, 1).expand(1, 1, NLAT, NLON).clone())
        lon = torch.tensor(LON, dtype=torch.float32)
        self.register_buffer("lon_n", ((lon - 83.0) / 18.0).view(1, 1, 1, NLON).expand(1, 1, NLAT, NLON).clone())
        ys = torch.linspace(-1.0, 1.0, NLAT)
        xs = torch.linspace(-1.0, 1.0, NLON)
        gy, gx = torch.meshgrid(ys, xs, indexing="ij")
        self.register_buffer("base_grid", torch.stack([gx, gy], dim=-1))  # [H, W, 2] (x, y)

    @property
    def alpha(self) -> torch.Tensor:
        return torch.sigmoid(self.theta)

    def build_inputs(
        self, window: torch.Tensor, static: torch.Tensor, season: torch.Tensor
    ) -> torch.Tensor:
        """window [B,3,6,H,W] normalised anomalies (oldest first), static [2,H,W], season [B,2] -> [B,30,H,W]."""
        b = window.shape[0]
        flat = window.reshape(b, T_IN * NC, NLAT, NLON)
        mean = window.mean(dim=1)
        st = static.unsqueeze(0).expand(b, -1, -1, -1)
        pos = torch.cat([self.lat_n, self.lon_n], dim=1).expand(b, -1, -1, -1)
        sea = season.view(b, 2, 1, 1).expand(b, 2, NLAT, NLON)
        return torch.cat([flat, mean, st, pos, sea], dim=1)

    def advect(self, x_last: torch.Tensor, uv_phys: torch.Tensor, inputs: torch.Tensor) -> torch.Tensor:
        """Semi-Lagrangian advection with a length-capped displacement. x_last [B,6,H,W], uv_phys [B,2,H,W] m/s."""
        b = x_last.shape[0]
        dx = uv_phys[:, 0:1] * self.inv_dx  # cells/day east
        dy = uv_phys[:, 1:2] * self.inv_dy  # cells/day north
        base = torch.cat([dx, dy], dim=1).unsqueeze(1)  # [B,1,2,H,W]
        corr = self.disp_corr(inputs).view(b, NC, 2, NLAT, NLON)
        disp = self.alpha.view(1, NC, 1, 1, 1) * base + corr  # [B,6,2,H,W]
        disp = cap_length(disp, self.cfg.displacement_cap)
        gx = self.base_grid[..., 0] - disp[:, :, 0] * (2.0 / (NLON - 1))
        gy = self.base_grid[..., 1] - disp[:, :, 1] * (2.0 / (NLAT - 1))
        grid = torch.stack([gx, gy], dim=-1).reshape(b * NC, NLAT, NLON, 2)
        out = F.grid_sample(
            x_last.reshape(b * NC, 1, NLAT, NLON), grid, mode="bilinear", padding_mode="border", align_corners=True
        )
        return out.view(b, NC, NLAT, NLON)

    def step(
        self, window: torch.Tensor, uv_phys: torch.Tensor, static: torch.Tensor, season: torch.Tensor
    ) -> torch.Tensor:
        """One day ahead. Returns next-day normalised anomaly [B,6,H,W]."""
        inputs = self.build_inputs(window, static, season)
        x_adv = self.advect(window[:, -1], uv_phys, inputs)
        h = self.head(self.body(torch.cat([x_adv, inputs], dim=1)))
        return x_adv + h


def sincos_slots(slots: torch.Tensor) -> torch.Tensor:
    """slots [...] -> [..., 2] using the judge's period of 365 days."""
    a = 2.0 * math.pi * slots.to(torch.float32) / 365.0
    return torch.stack([torch.sin(a), torch.cos(a)], dim=-1)


def rollout(
    model: SpeedLimitNet,
    z0: torch.Tensor,
    slots: torch.Tensor,
    clim: torch.Tensor,
    s: torch.Tensor,
    static: torch.Tensor,
    steps: int,
    detach_every: int = 0,
) -> torch.Tensor:
    """Free-running rollout in normalised anomaly space.

    z0 [B,3,6,H,W]; slots [B,steps+1] long (index 0 = last input day, j = target day j); clim [366,6,H,W].
    Returns z [B,steps,6,H,W].
    """
    window = z0
    outs = []
    for j in range(1, steps + 1):
        last_phys = from_z(window[:, -1], clim[slots[:, j - 1]], s)
        uv = last_phys[:, U10 : V10 + 1]
        season = sincos_slots(slots[:, j])
        z_next = model.step(window, uv, static, season)
        outs.append(z_next)
        window = torch.cat([window[:, 1:], z_next.unsqueeze(1)], dim=1)
        if detach_every and j % detach_every == 0:
            window = window.detach()
    return torch.stack(outs, dim=1)


def rollout_physical(
    model: SpeedLimitNet,
    init_states: torch.Tensor,
    slots: torch.Tensor,
    clim: torch.Tensor,
    s: torch.Tensor,
    static: torch.Tensor,
    steps: int,
) -> torch.Tensor:
    """Physical in, physical out. init_states [B,3,6,H,W]; returns [B,steps,6,H,W] (unclamped)."""
    b = init_states.shape[0]
    clim_in = clim[slots[:, :1].expand(b, T_IN)]  # last-day clim approximates earlier days' clim for anomalies
    # earlier days use their own slots: slots of days -2,-1,0
    prev = torch.stack([(slots[:, 0] - 2) % 366, (slots[:, 0] - 1) % 366, slots[:, 0]], dim=1)
    clim_in = clim[prev]
    z0 = to_z(init_states, clim_in, s)
    z = rollout(model, z0, slots, clim, s, static, steps)
    return from_z(z, clim[slots[:, 1 : steps + 1]], s)


def count_parameters(model: nn.Module) -> int:
    return int(sum(p.numel() for p in model.parameters()))


def numpy_slots(slot0: int, steps: int) -> np.ndarray:
    return np.array([(slot0 + k) % 366 for k in range(steps + 1)], dtype=np.int64)
