"""Network-only light-cone test: a one-cell change must not travel more than 8 cells per step."""

from __future__ import annotations

import numpy as np
import torch

from wethrfork.model import NetConfig, SpeedLimitNet, rollout
from wethrfork.physics import NC, NLAT, NLON

torch.manual_seed(3)


def _randomised_net() -> SpeedLimitNet:
    net = SpeedLimitNet(NetConfig(hidden=16)).eval()
    with torch.no_grad():  # zero-initialised layers would hide leaks; randomise them
        for m in (net.head, net.disp_corr):
            torch.nn.init.normal_(m.weight, std=0.3)
            torch.nn.init.normal_(m.bias, std=0.1)
    return net


def _setup():
    clim = torch.zeros(366, NC, NLAT, NLON)
    s = torch.ones(NC)
    static = torch.zeros(2, NLAT, NLON)
    return clim, s, static


def _reach(k: int, i0: int, j0: int, ch: int, with_wind: bool) -> tuple[float, float]:
    net = _randomised_net()
    clim, s, static = _setup()
    z = 0.2 * torch.randn(1, 3, NC, NLAT, NLON)
    if with_wind:  # strong westerly/southerly flow so the displacement cap is active
        z[:, :, 2] += 6.0
        z[:, :, 3] += 6.0
    z2 = z.clone()
    z2[0, -1, ch, i0, j0] += 3.0
    slots = torch.arange(k + 1).unsqueeze(0) + 100
    with torch.no_grad():
        y = rollout(net, z, slots, clim, s, static, k)
        y2 = rollout(net, z2, slots, clim, s, static, k)
    changed = ((y2 - y).abs().amax(dim=(0, 1, 2)) > 1e-6).numpy()
    ii, jj = np.indices((NLAT, NLON))
    cheb = np.maximum(abs(ii - i0), abs(jj - j0))
    euc = np.sqrt((ii - i0) ** 2 + (jj - j0) ** 2)
    if not changed.any():
        return 0.0, 0.0
    return float(cheb[changed].max()), float(euc[changed].max())


def test_chebyshev_reach_is_at_most_8_per_step():
    """The architectural bound: 4 (advection cap) + 1 (bilinear) + 3 (three 3x3 convolutions) cells along each axis."""
    for k in (1, 2, 3):
        for ch in (0, 1, 2, 4):
            cheb, euc = _reach(k, 16, 18, ch, with_wind=True)
            print(f"step {k} ch {ch}: chebyshev reach {cheb}, euclidean {euc:.2f}")
            assert cheb <= 8 * k + 1e-6


def test_euclidean_reach_bound_is_not_eight():
    """Chebyshev 8 per step is NOT a Euclidean 8: the worst diagonal case is 4 + sqrt(2) + 3 sqrt(2) = 9.66 cells per step.
    This test states the honest Euclidean bound and checks the measurement stays inside it."""
    bound = 4.0 + 4.0 * np.sqrt(2.0)
    for k in (1, 2, 3):
        _, euc = _reach(k, 16, 18, 0, with_wind=True)
        assert euc <= bound * k + 1e-6


def test_inside_judge_radius_after_k_days():
    """The judge allows 3 + 8 * (k + 1) cells for the 0-based day index k, i.e. 3 + 8 * d after d forecast days.
    (An earlier version of this test used d + 1 and so allowed one extra day of travel.)"""
    for days in (1, 2, 3):
        _, euc = _reach(days, 16, 18, 0, with_wind=True)
        assert euc <= 3 + 8 * days


def test_response_exists_nearby():
    cheb, _ = _reach(1, 16, 18, 0, with_wind=False)
    assert cheb >= 1
