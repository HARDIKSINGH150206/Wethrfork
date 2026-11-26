"""A separate dynamics network supplies the shock delta; the skill forecast and the null shock are unaffected."""

from __future__ import annotations

import numpy as np

from tests.conftest import build_test_artifacts
from wethrfork.engine import Engine


def test_dyn_head_changes_only_the_delta(tmp_path, state, doy):
    a = Engine.load(build_test_artifacts(tmp_path / "a"), warmup=False)
    b = Engine.load(build_test_artifacts(tmp_path / "b", with_dyn=True), warmup=False)
    assert b.dyn is not None and a.dyn is None
    p = np.zeros((6, 32, 36), np.float32)
    p[0, 8:16, 8:16] = 3.0
    assert np.array_equal(a.simulate(state, doy, 6, None), b.simulate(state, doy, 6, None))  # skill identical
    assert np.abs(a.simulate(state, doy, 6, p) - b.simulate(state, doy, 6, p)).max() > 0  # response differs
    z = np.zeros((6, 32, 36), np.float32)
    assert np.abs(b.simulate(state, doy, 6, z) - b.simulate(state, doy, 6, None)).max() == 0.0
