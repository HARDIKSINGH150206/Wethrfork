"""Rain post-processing applies shrink, then scale, then floor, exactly as the calibration tunes them."""

from __future__ import annotations

import numpy as np

from wethrfork.blend import PostProc


def _pp(**kw):
    return PostProc({"rain_scale_above": 5.0, **kw})


def test_identity_without_calibration():
    tp = np.random.default_rng(0).random((3, 4, 5)).astype(np.float32) * 30
    assert np.allclose(PostProc().map_rain(tp, np.zeros_like(tp)), tp)


def test_scale_only_above_threshold():
    tp = np.array([[[2.0, 5.0, 15.0]]], np.float32)
    out = _pp(rain_scale=[1.5] * 14).map_rain(tp, np.zeros_like(tp))
    assert np.allclose(out[0, 0], [2.0, 5.0, 5.0 + 10.0 * 1.5])


def test_shrink_moves_toward_climatology_before_scale():
    tp = np.array([[[20.0]]], np.float32)
    clim = np.array([[[10.0]]], np.float32)
    out = _pp(rain_shrink=[0.5] * 14, rain_scale=[2.0] * 14).map_rain(tp, clim)
    shrunk = 10.0 + 0.5 * 10.0  # 15
    assert np.allclose(out, 5.0 + (shrunk - 5.0) * 2.0)


def test_floor_removes_drizzle_after_scaling():
    tp = np.array([[[0.4, 0.9, 3.0]]], np.float32)
    out = _pp(rain_floor=[1.0] * 14).map_rain(tp, np.zeros_like(tp))
    assert np.allclose(out[0, 0], [0.0, 0.0, 3.0])


def test_every_saved_parameter_changes_the_output():
    """Regression for the lost-parameters bug: each calibration field must be live in the engine."""
    tp = np.full((2, 3, 3), 12.0, np.float32)
    clim = np.full_like(tp, 4.0)
    base = PostProc({}).map_rain(tp, clim)
    assert not np.allclose(_pp(rain_shrink=[0.6] * 14).map_rain(tp, clim), base)
    assert not np.allclose(_pp(rain_scale=[1.3] * 14).map_rain(tp, clim), base)
    assert not np.allclose(_pp(rain_floor=[20.0] * 14).map_rain(tp, clim), base)
