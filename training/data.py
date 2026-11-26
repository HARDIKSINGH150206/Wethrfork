"""Data loading, splits and sample building. Dates come from configs/*.yaml only."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent.parent


def load_config(path: str | Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def slot_of_dates(dates: pd.DatetimeIndex) -> np.ndarray:
    """Kit convention: 0..365 with Feb 29 owning slot 59 (index within a leap year)."""
    cum = np.array([0, 31, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335])
    return cum[dates.month.values - 1] + dates.day.values - 1


@dataclass
class Archive:
    data: np.ndarray  # [N, 6, 32, 36] physical
    dates: pd.DatetimeIndex
    static: np.ndarray  # [2, 32, 36]

    def index_range(self, lo: str, hi: str) -> tuple[int, int]:
        """Inclusive date range -> (start, stop) index pair."""
        i0 = int(self.dates.searchsorted(pd.Timestamp(lo), side="left"))
        i1 = int(self.dates.searchsorted(pd.Timestamp(hi), side="right"))
        return i0, i1

    def slots(self) -> np.ndarray:
        return slot_of_dates(self.dates)


def load_archive(cfg: dict) -> Archive:
    """Read the netCDF (cached to an npz under data/ for fast reloads)."""
    cache = ROOT / cfg.get("cache_path", "data/cache.npz")
    if cache.exists():
        z = np.load(cache, allow_pickle=False)
        return Archive(z["data"], pd.DatetimeIndex(z["dates"].astype("datetime64[ns]")), z["static"])
    import xarray as xr

    ds = xr.open_dataset(ROOT / cfg["data_path"])
    data = ds["data"].values.astype("float32")
    dates = pd.DatetimeIndex(pd.to_datetime(ds["time"].values))
    static = ds["static"].values.astype("float32")
    assert data.ndim == 4 and data.shape[1:] == (6, 32, 36), data.shape
    assert np.isfinite(data).all(), "archive contains non-finite values"
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez(cache, data=data, dates=dates.values.astype("datetime64[ns]").astype("int64"), static=static)
    log.info("cached archive to %s", cache)
    return Archive(data, dates, static)


def split_bounds(arc: Archive, cfg: dict, name: str) -> tuple[int, int]:
    lo, hi = cfg["splits"][name]
    return arc.index_range(lo, hi)


def sample_starts(i0: int, i1: int, horizon: int, t_in: int = 3) -> np.ndarray:
    """Indices t of the LAST input day such that inputs t-2..t and targets t+1..t+horizon all lie in [i0, i1)."""
    lo = i0 + t_in - 1
    hi = i1 - horizon
    return np.arange(lo, max(lo, hi), dtype=np.int64)
