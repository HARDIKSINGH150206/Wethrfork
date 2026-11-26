from __future__ import annotations

import numpy as np

from wethrfork.io import decode_array, encode_array


def test_shapes_for_all_steps(engine, state, doy):
    for steps in (1, 10, 14):
        out = engine.simulate(state, doy, steps, None)
        assert out.shape == (steps, 6, 32, 36) and out.dtype == np.float32


def test_steps_clipped(engine, state, doy):
    assert engine.simulate(state, doy, 99, None).shape[0] == 14
    assert engine.simulate(state, doy, 0, None).shape[0] == 1


def test_b64_roundtrip(state):
    assert np.array_equal(decode_array(encode_array(state)), state)
    assert np.array_equal(decode_array(state.tolist()), state)


def test_decode_rejects_bad():
    import pytest

    with pytest.raises(ValueError):
        decode_array({"b64": "AAAA", "shape": [3, 6, 32, 36]})
    with pytest.raises(ValueError):
        decode_array([1.0, 2.0], expect_shape=(3,))


def test_nonfinite_input_does_not_crash(engine, state, doy):
    bad = state.copy()
    bad[0, 0, 0, 0] = np.nan
    bad[2, 4, 5, 5] = np.inf
    out = engine.simulate(bad, doy, 5, None)
    assert np.isfinite(out).all()
