"""Day-of-year arithmetic and climatology lookup by slot (366 slots, Feb 29 has its own)."""
from __future__ import annotations

from typing import Sequence

import numpy as np

N_SLOTS = 366


def doy_from_sincos(doy_sincos: Sequence[float]) -> int:
    """Recover the integer day-of-year index from [sin, cos] with period 365."""
    s, c = float(doy_sincos[0]), float(doy_sincos[1])
    if not (np.isfinite(s) and np.isfinite(c)):
        return 0
    d = int(round(np.arctan2(s, c) * 365.0 / (2.0 * np.pi))) % 365
    return d


def slot_of_doy(d: int) -> int:
    """Clamp a day-of-year index to a climatology slot."""
    return int(min(max(d, 0), N_SLOTS - 1))


def slots_for_steps(doy_sincos: Sequence[float], steps: int) -> np.ndarray:
    """Slots of the target days k=1..steps after the last input day."""
    d = doy_from_sincos(doy_sincos)
    return np.array([(slot_of_doy(d) + k) % N_SLOTS for k in range(1, steps + 1)], dtype=np.int64)


def slot_of_last_day(doy_sincos: Sequence[float]) -> int:
    return slot_of_doy(doy_from_sincos(doy_sincos))


def sincos_of_slot(slot: int) -> list[float]:
    """Inverse of the above: the [sin, cos] pair the judge would send for a given slot."""
    a = 2.0 * np.pi * float(slot) / 365.0
    return [float(np.sin(a)), float(np.cos(a))]


def lookup(clim: np.ndarray, slots: np.ndarray) -> np.ndarray:
    """clim [366,6,H,W], slots [K] -> [K,6,H,W]."""
    return clim[np.asarray(slots) % N_SLOTS]
