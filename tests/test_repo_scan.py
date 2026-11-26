from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_official_scan_has_no_flags():
    rs = pytest.importorskip("monsoon_r1.repo_scan")
    res = rs.scan(ROOT)
    assert not [f for f in res["flags"] if f["level"] == "critical"], res["flags"]
    assert res["health"]["training_pipeline"] and res["health"]["frontend_present"]
    assert set(res["inference_files"]) <= {
        "serve.py",
        "wethrfork/__init__.py",
        "wethrfork/engine.py",
        "wethrfork/model.py",
        "wethrfork/ridge.py",
        "wethrfork/blend.py",
        "wethrfork/climatology.py",
        "wethrfork/normalize.py",
        "wethrfork/physics.py",
        "wethrfork/io.py",
    }, res["inference_files"]
