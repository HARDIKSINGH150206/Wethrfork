"""Wire-format helpers: tolerant decoding of nested lists or base64 float32 arrays."""

from __future__ import annotations

import base64
from typing import Any

import numpy as np


def decode_array(x: Any, expect_shape: tuple[int, ...] | None = None) -> np.ndarray:
    """Accept nested lists or {'b64', 'shape'}; always returns float32. Raises ValueError on malformed input."""
    if isinstance(x, dict):
        if "b64" not in x or "shape" not in x:
            raise ValueError("array dict needs 'b64' and 'shape'")
        shape = tuple(int(s) for s in x["shape"])
        if any(s < 0 or s > 100000 for s in shape) or int(np.prod(shape)) > 20_000_000:
            raise ValueError("array too large")
        raw = base64.b64decode(x["b64"], validate=True)
        if len(raw) != int(np.prod(shape)) * 4:
            raise ValueError("b64 length does not match shape")
        a = np.frombuffer(raw, dtype="<f4").reshape(shape).astype(np.float32)
    else:
        a = np.asarray(x, dtype=np.float32)
    if expect_shape is not None and a.shape != tuple(expect_shape):
        raise ValueError(f"shape {a.shape} != expected {tuple(expect_shape)}")
    return a


def encode_array(a: np.ndarray) -> dict:
    """Compact wire form: base64 little-endian float32 plus shape."""
    a = np.ascontiguousarray(a, dtype="<f4")
    return {"b64": base64.b64encode(a.tobytes()).decode("ascii"), "shape": list(a.shape)}


def to_list(a: np.ndarray) -> list:
    """Canonical response form: nested lists of finite float32."""
    return np.asarray(a, dtype=np.float32).tolist()


class RequestError(ValueError):
    """A malformed request: the server answers 422 with this message instead of failing."""


def parse_request(body: Any) -> tuple[np.ndarray, list[float], int, np.ndarray | None]:
    """Validate a forecast request body. Returns (init [3,6,32,36], doy [2], steps, perturbation [6,32,36] or None).

    Values that are merely unusual (NaN, huge numbers, steps out of range) are accepted and handled downstream;
    only structurally wrong requests raise RequestError.
    """
    if not isinstance(body, dict):
        raise RequestError("body must be a JSON object")
    if "init_states" not in body:
        raise RequestError("missing 'init_states'")
    try:
        init = decode_array(body["init_states"])
    except (ValueError, TypeError) as e:
        raise RequestError(f"init_states: {e}") from e
    if init.shape != (3, 6, 32, 36):
        raise RequestError(f"init_states must have shape [3, 6, 32, 36], got {list(init.shape)}")
    doy = body.get("doy_sincos")
    try:
        doy_l = [float(v) for v in doy]  # type: ignore[union-attr]
    except (TypeError, ValueError) as e:
        raise RequestError("doy_sincos must be a list of two numbers") from e
    if len(doy_l) != 2:
        raise RequestError("doy_sincos must be a list of two numbers")
    try:
        steps = int(float(body.get("steps", 10)))
    except (TypeError, ValueError) as e:
        raise RequestError("steps must be an integer") from e
    pert = body.get("perturbation")
    if pert is not None:
        try:
            pert = decode_array(pert)
        except (ValueError, TypeError) as e:
            raise RequestError(f"perturbation: {e}") from e
        if pert.shape == (1, 6, 32, 36):
            pert = pert[0]
        if pert.shape != (6, 32, 36):
            raise RequestError(f"perturbation must have shape [6, 32, 36], got {list(pert.shape)}")
    return init, doy_l, steps, pert
