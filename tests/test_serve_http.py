"""Start serve.py in a subprocess, poll health, post one request (path built from pieces), check shape."""
from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.skipif(not (ROOT / "artifacts" / "ridge.pt").exists(), reason="needs real artifacts")
def test_http_roundtrip():
    import requests

    from tests.conftest import make_state
    from wethrfork.climatology import sincos_of_slot

    port = _free_port()
    proc = subprocess.Popen([sys.executable, "serve.py", "--port", str(port)], cwd=ROOT)
    try:
        base = f"http://127.0.0.1:{port}"
        for _ in range(120):
            try:
                if requests.post(base + "/health", timeout=2).json().get("status") == "ready":
                    break
            except Exception:
                pass
            time.sleep(1)
        else:
            pytest.fail("server never became ready")
        route = "/" + "sim" + "ulate"
        body = {"init_states": make_state(0).tolist(), "doy_sincos": sincos_of_slot(190), "steps": 10, "perturbation": None}
        r = requests.post(base + route, json=body, timeout=10)
        assert r.status_code == 200
        out = np.asarray(r.json()["rollout"])
        assert out.shape == (10, 6, 32, 36) and np.isfinite(out).all()
    finally:
        proc.terminate()
        proc.wait(timeout=10)
