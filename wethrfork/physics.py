"""Physical constants, grid geometry, channel indices and clamp bounds. Single source of truth."""

from __future__ import annotations

import numpy as np

NLAT, NLON, NC = 32, 36, 6
T_IN = 3
MAX_STEPS = 14
LAT0, LON0, DEG = 6.5, 65.5, 1.0
LAT = LAT0 + DEG * np.arange(NLAT, dtype=np.float64)  # south -> north
LON = LON0 + DEG * np.arange(NLON, dtype=np.float64)  # west -> east

T2M, TP, U10, V10, MSL, TCWV = range(6)
CHANNELS = ("t2m", "tp", "u10", "v10", "msl", "tcwv")
UNITS = ("K", "mm/day", "m/s", "m/s", "Pa", "kg/m2")

EARTH_RADIUS_M = 6_371_000.0
OMEGA = 7.292e-5
DAY_S = 86400.0
CELL_NS_M = EARTH_RADIUS_M * np.deg2rad(DEG)  # ~111.2 km

# speed limit: displacement cap + bilinear + 3 conv layers of 3x3
DISP_CAP_CELLS = 4.0
N_CONV_BLOCKS = 3
MAX_REACH_PER_STEP = DISP_CAP_CELLS + 1.0 + N_CONV_BLOCKS  # 8 cells

# output clamp bounds (physical units)
T2M_MIN, T2M_MAX = 234.0, 332.0
MSL_MIN, MSL_MAX = 85000.0, 110000.0
WIND_ABS_MAX = 60.0
TCWV_MIN = 0.0
TP_MIN = 0.0

# kit stats are the fallback scale if artifacts/stats.json is missing
STD_DEFAULT = np.array([8.0, 8.0, 3.5, 2.5, 450.0, 20.0], dtype=np.float32)


def cell_size_ew_m(lat_deg: np.ndarray | float) -> np.ndarray | float:
    """East-west cell size in metres at the given latitude."""
    return CELL_NS_M * np.cos(np.deg2rad(lat_deg))


def lat_weights() -> np.ndarray:
    """cos(lat) weights normalised to mean 1, shape [NLAT]."""
    w = np.cos(np.deg2rad(LAT))
    return (w / w.mean()).astype(np.float32)
