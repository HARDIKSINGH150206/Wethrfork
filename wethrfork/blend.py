"""Blend, damping, rain quantile map and the final clamp. Calibration constants are statistics, never dates."""
from __future__ import annotations

import numpy as np

from .physics import (
    MAX_STEPS,
    MSL,
    MSL_MAX,
    MSL_MIN,
    NC,
    T2M,
    T2M_MAX,
    T2M_MIN,
    TCWV,
    TP,
    U10,
    V10,
    WIND_ABS_MAX,
)


class PostProc:
    """Per-lead calibration loaded from artifacts/postproc.json (identity when a field is missing)."""

    def __init__(self, cfg: dict | None = None) -> None:
        cfg = cfg or {}
        self.blend_w = np.asarray(cfg.get("blend_w", np.full((MAX_STEPS, NC), 0.5)), dtype=np.float32)
        self.damp = np.asarray(cfg.get("damp", np.ones((MAX_STEPS, NC))), dtype=np.float32)
        self.rain_src = cfg.get("rain_src")  # [14][Q] forecast quantiles
        self.rain_dst = cfg.get("rain_dst")  # [14][Q] observed quantiles
        self.rain_scale = np.asarray(cfg.get("rain_scale", np.ones(MAX_STEPS)), dtype=np.float32)
        self.rain_scale_above = float(cfg.get("rain_scale_above", 5.0))

    @staticmethod
    def _lead(k: int) -> int:
        return min(k, MAX_STEPS - 1)

    def blend(self, z_nn: np.ndarray | None, z_ridge: np.ndarray) -> np.ndarray:
        """z_* [K,6,H,W] normalised anomalies -> blended [K,6,H,W]."""
        if z_nn is None:
            return z_ridge
        out = np.empty_like(z_ridge)
        for k in range(z_ridge.shape[0]):
            w = self.blend_w[self._lead(k)][:, None, None]
            out[k] = w * z_nn[k] + (1.0 - w) * z_ridge[k]
        return out

    def damp_z(self, z: np.ndarray) -> np.ndarray:
        out = np.empty_like(z)
        for k in range(z.shape[0]):
            out[k] = self.damp[self._lead(k)][:, None, None] * z[k]
        return out

    def map_rain(self, tp: np.ndarray) -> np.ndarray:
        """tp [K,H,W] mm/day -> quantile-mapped and bias-adjusted."""
        out = np.array(tp, dtype=np.float32, copy=True)
        for k in range(out.shape[0]):
            j = self._lead(k)
            if self.rain_src is not None and self.rain_dst is not None:
                src = np.asarray(self.rain_src[j], dtype=np.float64)
                dst = np.asarray(self.rain_dst[j], dtype=np.float64)
                v = out[k].astype(np.float64)
                m = np.interp(v, src, dst)
                hi = v > src[-1]
                m[hi] = v[hi] - src[-1] + dst[-1]
                out[k] = m.astype(np.float32)
            f = float(self.rain_scale[j])
            if f != 1.0:
                a = self.rain_scale_above
                o = out[k]
                out[k] = np.where(o > a, a + (o - a) * f, o)
        return out


def clamp(out: np.ndarray, clim_fallback: np.ndarray | None = None) -> np.ndarray:
    """Final step. out [K,6,H,W] physical; replaces non-finite values then enforces physical bounds."""
    out = np.asarray(out, dtype=np.float32)
    if clim_fallback is not None:
        bad = ~np.isfinite(out)
        if bad.any():
            out = np.where(bad, clim_fallback, out)
    out = np.nan_to_num(out, nan=0.0, posinf=1e6, neginf=-1e6)
    out[:, TP] = np.maximum(out[:, TP], 0.0)
    out[:, TCWV] = np.maximum(out[:, TCWV], 0.0)
    out[:, T2M] = np.clip(out[:, T2M], T2M_MIN, T2M_MAX)
    out[:, MSL] = np.clip(out[:, MSL], MSL_MIN, MSL_MAX)
    out[:, U10] = np.clip(out[:, U10], -WIND_ABS_MAX, WIND_ABS_MAX)
    out[:, V10] = np.clip(out[:, V10], -WIND_ABS_MAX, WIND_ABS_MAX)
    return out
