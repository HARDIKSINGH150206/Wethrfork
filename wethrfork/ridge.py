"""Ridge skill head: one linear model per (lead, channel, cell) on 21 local features. Never used for shock deltas."""
from __future__ import annotations

import math

import torch

from .physics import MAX_STEPS, NC, NLAT, NLON, T_IN

N_FEAT = NC * T_IN + 3  # 18 anomalies + season sin/cos + bias = 21


class RidgeHead:
    def __init__(self, weights: torch.Tensor) -> None:
        """weights [14, 6, 21, H, W] float32."""
        assert tuple(weights.shape) == (MAX_STEPS, NC, N_FEAT, NLAT, NLON), tuple(weights.shape)
        self.w = weights.contiguous()

    @torch.no_grad()
    def predict(self, z_window: torch.Tensor, target_slots: torch.Tensor) -> torch.Tensor:
        """z_window [3,6,H,W] normalised anomalies (oldest first); target_slots [K] long -> z [K,6,H,W].

        Leads beyond 14 reuse lead 14's weights.
        """
        k = int(target_slots.shape[0])
        feats = z_window.reshape(T_IN * NC, NLAT, NLON)
        a = 2.0 * math.pi * target_slots.to(torch.float32) / 365.0
        outs = []
        for j in range(k):
            w = self.w[min(j, MAX_STEPS - 1)]  # [6,21,H,W]
            y = torch.einsum("cfij,fij->cij", w[:, : T_IN * NC], feats)
            y = y + w[:, T_IN * NC] * torch.sin(a[j]) + w[:, T_IN * NC + 1] * torch.cos(a[j]) + w[:, T_IN * NC + 2]
            outs.append(y)
        return torch.stack(outs, dim=0)


def design_features(z_window: torch.Tensor, target_slot: torch.Tensor) -> torch.Tensor:
    """Training-time feature builder. z_window [N,3,6,H,W], target_slot [N] -> X [H*W, N, 21]."""
    n = z_window.shape[0]
    f = z_window.reshape(n, T_IN * NC, NLAT * NLON).permute(2, 0, 1)  # [cells, N, 18]
    a = 2.0 * math.pi * target_slot.to(torch.float32) / 365.0
    extra = torch.stack([torch.sin(a), torch.cos(a), torch.ones_like(a)], dim=1)  # [N,3]
    return torch.cat([f, extra.unsqueeze(0).expand(NLAT * NLON, -1, -1)], dim=2)
