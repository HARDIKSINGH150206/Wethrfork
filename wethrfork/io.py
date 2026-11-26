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
