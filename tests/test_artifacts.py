"""Committed artifacts: no multi-year archives and (when a manifest exists) matching hashes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

ART = Path(__file__).resolve().parent.parent / "artifacts"


def test_no_archive_arrays():
    for p in ART.glob("*.npy"):
        a = np.load(p, mmap_mode="r")
        if a.ndim >= 3 and a.shape[-2:] == (32, 36):
            assert a.shape[0] <= 400, (p.name, a.shape)


def test_manifest_hashes():
    mp = ART / "manifest.json"
    if not mp.exists():
        return
    for name, meta in json.loads(mp.read_text())["files"].items():
        if meta.get("sha256"):
            assert hashlib.sha256((ART / name).read_bytes()).hexdigest() == meta["sha256"], name
