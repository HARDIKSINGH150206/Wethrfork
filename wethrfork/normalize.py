"""Anomaly normalisation with a log transform for rain. All functions are differentiable torch ops.

Normalised anomaly: z = (x - clim) / s for every channel except rain, where
z = (log1p(tp) - log1p(clim_tp)) / s_tp. `s` comes from artifacts/norm.json ("anom_std", length 6).
"""

from __future__ import annotations

import torch

from .physics import TP


def _split_tp(x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """x [..., 6, H, W] -> (before-tp, tp, after-tp) channel groups."""
    return x[..., :TP, :, :], x[..., TP : TP + 1, :, :], x[..., TP + 1 :, :, :]


def to_z(x: torch.Tensor, clim: torch.Tensor, s: torch.Tensor) -> torch.Tensor:
    """Physical field -> normalised anomaly. x, clim: [..., 6, H, W]; s: [6]. Returns [..., 6, H, W]."""
    s = s.view(*([1] * (x.dim() - 3)), -1, 1, 1)
    a, b, c = _split_tp(x)
    ca, cb, cc = _split_tp(clim)
    sa, sb, sc = _split_tp(s.expand(*x.shape[:-3], -1, 1, 1))
    za = (a - ca) / sa
    zb = (torch.log1p(b.clamp(min=0.0)) - torch.log1p(cb.clamp(min=0.0))) / sb
    zc = (c - cc) / sc
    return torch.cat([za, zb, zc], dim=-3)


def from_z(z: torch.Tensor, clim: torch.Tensor, s: torch.Tensor) -> torch.Tensor:
    """Normalised anomaly -> physical field (rain floored at 0)."""
    s = s.view(*([1] * (z.dim() - 3)), -1, 1, 1)
    a, b, c = _split_tp(z)
    ca, cb, cc = _split_tp(clim)
    sa, sb, sc = _split_tp(s.expand(*z.shape[:-3], -1, 1, 1))
    xa = ca + a * sa
    xb = torch.expm1(torch.log1p(cb.clamp(min=0.0)) + b * sb).clamp(min=0.0)
    xc = cc + c * sc
    return torch.cat([xa, xb, xc], dim=-3)
