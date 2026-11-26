"""The rebuild instructions must match the shipped model, and the exporter must never keep stale weights silently."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

import training.export_artifacts as exp

ROOT = Path(__file__).resolve().parent.parent


def _cfg(name: str) -> dict:
    return yaml.safe_load((ROOT / "configs" / name).read_text())


def test_make_artifacts_builds_both_networks_in_dependency_order():
    mk = (ROOT / "Makefile").read_text()
    line = re.search(r"^artifacts:(.*)$", mk, re.M).group(1).split()
    assert (
        line.index("train")
        < line.index("export-weights")
        < line.index("blend")
        < line.index("postproc")
        < line.index("manifest")
    )
    train = re.search(r"^train:(.*)$", mk, re.M).group(1).split()
    assert train == ["train-skill", "train-dyn", "train-dyn-ft"]
    for tgt, cfg in (
        ("train-skill", "train_skill.yaml"),
        ("train-dyn", "train.yaml"),
        ("train-dyn-ft", "train_dyn_ft.yaml"),
    ):
        assert f"{cfg}" in re.search(rf"^{tgt}:\n\t(.*)$", mk, re.M).group(1)


def test_config_chain_matches_exporter_defaults():
    skill, dyn, ft = _cfg("train_skill.yaml"), _cfg("train.yaml"), _cfg("train_dyn_ft.yaml")
    assert ft["init_from"] == f"{dyn['out_dir']}/best.pt"  # the fine-tune starts from the dynamics run
    assert len({skill["out_dir"], dyn["out_dir"], ft["out_dir"]}) == 3
    import sys

    argv = sys.argv
    sys.argv = ["x"]
    try:
        import argparse

        ap = argparse.ArgumentParser()
        ap.add_argument("--skill-dir", default="runs/nn_skill")
        ap.add_argument("--dyn-dir", default="runs/nn_dyn_ft")
    finally:
        sys.argv = argv
    src = (ROOT / "training" / "export_artifacts.py").read_text()
    assert f'default="{skill["out_dir"]}"' in src and f'default="{ft["out_dir"]}"' in src


def test_missing_checkpoint_is_an_error(tmp_path, monkeypatch):
    art = tmp_path / "artifacts"
    art.mkdir()
    (art / "nn.pt").write_bytes(b"old")
    monkeypatch.setattr(exp, "ART", art)
    monkeypatch.setattr(exp, "ROOT", tmp_path)
    with pytest.raises(SystemExit) as e:
        exp.copy_weights(tmp_path / "runs" / "nope", tmp_path / "runs" / "nope2", keep_existing=False)
    assert "checkpoint missing" in str(e.value)
    assert (art / "nn.pt").read_bytes() == b"old"  # and nothing was touched


def test_keep_existing_must_be_explicit(tmp_path, monkeypatch, capsys):
    art = tmp_path / "artifacts"
    art.mkdir()
    (art / "nn.pt").write_bytes(b"old")
    (art / "nn_dyn.pt").write_bytes(b"old")
    monkeypatch.setattr(exp, "ART", art)
    monkeypatch.setattr(exp, "ROOT", tmp_path)
    exp.copy_weights(tmp_path / "x", tmp_path / "y", keep_existing=True)
    assert "WARNING" in capsys.readouterr().out


def test_checkpoints_are_copied_when_present(tmp_path, monkeypatch):
    art = tmp_path / "artifacts"
    art.mkdir()
    for d in ("a", "b"):
        (tmp_path / d).mkdir()
        (tmp_path / d / "best.pt").write_bytes(d.encode())
        (tmp_path / d / "nn_config.json").write_text("{}")
    monkeypatch.setattr(exp, "ART", art)
    monkeypatch.setattr(exp, "ROOT", tmp_path)
    exp.copy_weights(tmp_path / "a", tmp_path / "b", keep_existing=False)
    assert (art / "nn.pt").read_bytes() == b"a" and (art / "nn_dyn.pt").read_bytes() == b"b"


def test_incomplete_calibration_is_rejected(tmp_path, monkeypatch):
    art = tmp_path / "artifacts"
    art.mkdir()
    for f in exp.REQUIRED:
        (art / f).write_text("{}")
    (art / "postproc.json").write_text(
        json.dumps({"blend_w": [], "damp": [], "rain_scale": []})
    )  # the old, lossy format
    monkeypatch.setattr(exp, "ART", art)
    with pytest.raises(SystemExit) as e:
        exp.check_complete()
    assert "rain_shrink" in str(e.value) and "rain_floor" in str(e.value)


def test_shipped_artifacts_are_complete_and_calibration_is_saved_whole():
    art = ROOT / "artifacts"
    for f in exp.REQUIRED:
        assert (art / f).exists(), f
    pp = json.loads((art / "postproc.json").read_text())
    for k in exp.POSTPROC_KEYS:
        assert k in pp, k
    for k in ("rain_shrink", "rain_floor", "rain_scale", "damp"):
        assert len(pp[k]) == 14
    assert (
        all(0.0 < v <= 1.0 for v in pp["rain_shrink"])
        and all(v >= 0.0 for v in pp["rain_floor"])
        and all(0.5 <= v <= 4 for v in pp["rain_scale"])
    )
    man = json.loads((art / "manifest.json").read_text())
    assert "lineage" in man and set(man["files"]) >= {"nn.pt", "nn_dyn.pt", "postproc.json"}
