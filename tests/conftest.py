"""Shared fixtures: synthetic states and a tiny set of random artifacts so CI works before training."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def make_state(seed: int = 0) -> np.ndarray:
    """[3,6,32,36] physical-unit synthetic window, close to the kit validator."""
    rng = np.random.default_rng(seed)
    base = np.array([295.0, 4.0, 2.0, 1.0, 100500.0, 35.0], dtype=np.float32)[None, :, None, None]
    noise_sd = np.array([3.0, 3.0, 2.0, 1.5, 300.0, 8.0], dtype=np.float32)[None, :, None, None]
    x = base + noise_sd * rng.standard_normal((3, 6, 32, 36)).astype(np.float32)
    x[:, 1] = np.abs(x[:, 1])
    x[:, 5] = np.abs(x[:, 5])
    return x.astype(np.float32)


@pytest.fixture
def state() -> np.ndarray:
    return make_state(0)


@pytest.fixture
def doy() -> list[float]:
    from wethrfork.climatology import sincos_of_slot

    return sincos_of_slot(190)
