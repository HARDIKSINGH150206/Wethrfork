"""Build init/truth windows from configs/eval.yaml (dates live in YAML, never here)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from training.data import Archive
from wethrfork.climatology import sincos_of_slot


def _window(arc: Archive, i: int, steps: int, wid: str, label: str = "") -> dict | None:
    if i - 2 < 0 or i + steps >= len(arc.dates):
        return None
    slot0 = int(arc.slots()[i])
    return {
        "id": wid,
        "label": label or wid,
        "last_idx": i,
        "slot0": slot0,
        "doy_sincos": sincos_of_slot(slot0),
        "init": arc.data[i - 2 : i + 1].copy(),
        "truth": arc.data[i + 1 : i + 1 + steps].copy(),
    }


def index_of(arc: Archive, day: str) -> int:
    return int(arc.dates.get_loc(pd.Timestamp(day)))


def systematic(arc: Archive, cfg: dict) -> list[dict]:
    s = cfg["systematic"]
    steps = cfg.get("steps", 10)
    lo, hi = index_of(arc, s["start"]), index_of(arc, s["end"])
    out = []
    for i in range(lo, hi + 1, int(s["every_days"])):
        w = _window(arc, i, steps, f"sys{i}")
        if w:
            out.append(w)
    return out


def typed(arc: Archive, cfg: dict) -> list[dict]:
    steps = cfg.get("steps", 10)
    out = []
    for t in cfg["typed"]:
        w = _window(arc, index_of(arc, t["last_input_day"]), steps, t["type"], t["type"])
        if w:
            out.append(w)
    return out


def shock_windows(arc: Archive, cfg: dict) -> dict[str, dict]:
    steps = cfg.get("steps", 10)
    return {
        season: _window(arc, index_of(arc, day), steps, season, season) for season, day in cfg["shock_windows"].items()
    }


def stack(ws: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    return np.stack([w["init"] for w in ws]), np.stack([w["truth"] for w in ws])
