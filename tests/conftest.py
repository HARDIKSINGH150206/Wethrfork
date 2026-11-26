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


def build_test_artifacts(d: Path, with_nn: bool = True, with_ridge: bool = True, seed: int = 1) -> Path:
    """Write tiny random artifacts (never committed) so engine tests run without data or training."""
    import json

    import torch

    from wethrfork.model import NetConfig, SpeedLimitNet
    from wethrfork.ridge import N_FEAT

    rng = np.random.default_rng(seed)
    d.mkdir(parents=True, exist_ok=True)
    mean = np.array([295.0, 4.0, 1.0, 0.5, 100800.0, 30.0], np.float32)[None, :, None, None]
    sd = np.array([4.0, 2.0, 1.0, 1.0, 200.0, 8.0], np.float32)[None, :, None, None]
    season = np.sin(np.linspace(0, 2 * np.pi, 366))[:, None, None, None].astype(np.float32)
    clim = mean + sd * season + 0.1 * sd * rng.standard_normal((1, 6, 32, 36)).astype(np.float32)
    clim[:, 1] = np.abs(clim[:, 1])
    clim[:, 5] = np.abs(clim[:, 5])
    np.save(d / "climatology.npy", clim.astype(np.float32))
    np.save(d / "clim_std.npy", np.broadcast_to(sd[0], (6, 32, 36)).astype(np.float32).copy())
    static = np.stack([rng.random((32, 36)), 500 * rng.random((32, 36))]).astype(np.float32)
    np.save(d / "static.npy", static)
    (d / "norm.json").write_text(json.dumps({"anom_std": [3.0, 0.8, 2.0, 2.0, 400.0, 6.0]}))
    if with_ridge:
        w = 0.01 * torch.randn(14, 6, N_FEAT, 32, 36, generator=torch.Generator().manual_seed(seed))
        torch.save(w, d / "ridge.pt")
    if with_nn:
        torch.manual_seed(seed)
        net = SpeedLimitNet(NetConfig(hidden=16))
        with torch.no_grad():
            torch.nn.init.normal_(net.head.weight, std=0.05)
            torch.nn.init.normal_(net.disp_corr.weight, std=0.05)
        torch.save(net.state_dict(), d / "nn.pt")
        (d / "nn_config.json").write_text(json.dumps(net.cfg.to_dict()))
    return d


@pytest.fixture(scope="session")
def engine(tmp_path_factory):
    from wethrfork.engine import Engine

    d = build_test_artifacts(tmp_path_factory.mktemp("artifacts"))
    eng = Engine.load(d, warmup=True)
    assert eng.ready, eng.error
    return eng
