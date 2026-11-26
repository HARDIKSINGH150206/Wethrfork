from __future__ import annotations

import numpy as np
import pytest


def _shock(ch, val, box=(8, 20, 8, 20)):
    p = np.zeros((6, 32, 36), np.float32)
    p[ch, box[0] : box[1], box[2] : box[3]] = val
    return p


@pytest.mark.parametrize(
    "ch,val",
    [(0, 20.0), (0, -60.0), (1, -500.0), (1, 500.0), (5, -100.0), (5, 100.0), (4, -5000.0), (2, 80.0), (3, -80.0)],
)
def test_extreme_shocks_stay_valid(engine, state, doy, ch, val):
    out = engine.simulate(state, doy, 10, _shock(ch, val))
    assert out.shape == (10, 6, 32, 36)
    assert np.isfinite(out).all()
    assert out[:, 1].min() >= 0.0 and out[:, 5].min() >= 0.0
    assert out[:, 0].min() >= 233.15 and out[:, 0].max() <= 333.15


def test_random_shocks_valid(engine, state, doy):
    rng = np.random.default_rng(5)
    for _ in range(6):
        p = (rng.standard_normal((6, 32, 36)) * np.array([5, 10, 5, 5, 800, 15])[:, None, None]).astype(np.float32)
        out = engine.simulate(state, doy, 10, p)
        assert np.isfinite(out).all() and out[:, 1].min() >= 0
