from __future__ import annotations

import numpy as np


def test_null_equals_none_exactly(engine, state, doy):
    a = engine.simulate(state, doy, 10, None)
    b = engine.simulate(state, doy, 10, np.zeros((6, 32, 36), np.float32))
    assert np.abs(a - b).max() == 0.0


def test_nonzero_shock_changes_output(engine, state, doy):
    p = np.zeros((6, 32, 36), np.float32)
    p[0, 10:20, 10:20] = 3.0
    a = engine.simulate(state, doy, 10, None)
    b = engine.simulate(state, doy, 10, p)
    assert np.abs(a - b).max() > 0
