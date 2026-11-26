from __future__ import annotations

import torch

from wethrfork.normalize import from_z, to_z


def test_roundtrip():
    torch.manual_seed(0)
    x = torch.rand(2, 6, 4, 5) * 10 + 1
    clim = torch.rand(6, 4, 5) * 10 + 1
    s = torch.tensor([1.0, 0.8, 2.0, 2.0, 100.0, 5.0])
    z = to_z(x, clim, s)
    y = from_z(z, clim, s)
    assert torch.allclose(x, y, atol=1e-3, rtol=1e-4)


def test_rain_never_negative():
    clim = torch.ones(6, 3, 3)
    s = torch.ones(6)
    z = torch.full((1, 6, 3, 3), -50.0)
    assert from_z(z, clim, s)[:, 1].min() >= 0.0
