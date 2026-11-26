from __future__ import annotations

import numpy as np


def test_repeat_calls_identical(engine, state, doy):
    p = np.zeros((6, 32, 36), np.float32)
    p[0, 5:15, 5:15] = 2.0
    a = engine.simulate(state, doy, 10, p)
    b = engine.simulate(state, doy, 10, p)
    assert np.array_equal(a, b)


def test_reload_identical(tmp_path, state, doy):
    from tests.conftest import build_test_artifacts
    from wethrfork.engine import Engine

    d = build_test_artifacts(tmp_path)
    a = Engine.load(d, warmup=False).simulate(state, doy, 5, None)
    b = Engine.load(d, warmup=False).simulate(state, doy, 5, None)
    assert np.array_equal(a, b)
