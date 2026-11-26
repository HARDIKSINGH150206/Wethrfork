"""With the network replaced by identity, the delta equals the perturbation exactly (up to float error)."""

from __future__ import annotations

import numpy as np
import torch


def test_perturbation_added_to_last_day(engine, state, doy, monkeypatch):
    import wethrfork.engine as eng_mod

    def identity_rollout(net, z0, slots, clim, s, static, steps, **kw):
        return z0[:, -1:].expand(-1, steps, -1, -1, -1).contiguous()

    monkeypatch.setattr(eng_mod, "rollout", identity_rollout)
    p = np.zeros((6, 32, 36), np.float32)
    p[0, 10:14, 10:14] = 2.5
    p[4, 20:24, 5:9] = -300.0
    parts = engine.simulate_parts(state, doy, 4, p)
    d = parts["delta"]
    assert d.shape == (4, 6, 32, 36)
    # advected persistence of the shocked minus the base last day -> the perturbation itself
    assert np.allclose(d[0, 0], p[0], atol=1e-2)
    assert np.allclose(d[0, 4], p[4], atol=0.5)
    assert isinstance(torch.zeros(1), torch.Tensor)
