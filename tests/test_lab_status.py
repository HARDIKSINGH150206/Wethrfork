"""The lab server says clearly when the local dataset is missing, instead of failing with a 500."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not (ROOT / "artifacts" / "nn.pt").exists(), reason="needs real artifacts")


@pytest.fixture(scope="module")
def lab():
    from fastapi.testclient import TestClient

    import lab.lab_server as ls

    return ls, TestClient(ls.app)


def test_status_reports_engine_and_data(lab):
    ls, c = lab
    s = c.get("/status").json()
    assert s["engine_ready"] is True and "data_present" in s and s["model_name"].startswith("wethrfork-")


def test_missing_dataset_gives_503_with_instructions(lab, monkeypatch, tmp_path):
    ls, c = lab
    monkeypatch.setattr(ls, "DATA_PATH", tmp_path / "nope" / "india_climate_train.nc")
    for url in ("/windows", "/windows/w01"):
        r = c.get(url)
        assert r.status_code == 503
        d = r.json()["detail"]
        assert "dataset is missing" in d["error"] and "india_climate_train.nc" in d["detail"]
    assert c.get("/status").json()["data_present"] is False
    assert c.get("/meta").status_code == 200  # static artifacts still work


def test_unknown_window_is_404(lab):
    ls, c = lab
    if ls.DATA_PATH.exists():
        assert c.get("/windows/does-not-exist").status_code == 404
