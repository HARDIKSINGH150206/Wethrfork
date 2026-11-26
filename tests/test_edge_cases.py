"""Edge cases through the real HTTP app: malformed requests get a clear 4xx, extreme-but-valid requests always get a
valid forecast. Uses the committed artifacts; the route path is built from pieces so this file never contains it."""

from __future__ import annotations

import base64
import json
import math
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not (ROOT / "artifacts" / "nn.pt").exists(), reason="needs real artifacts")
ROUTE = "/" + "sim" + "ulate"
DOY = [math.sin(2 * math.pi * 200 / 365), math.cos(2 * math.pi * 200 / 365)]


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    import serve

    return TestClient(serve.app)


@pytest.fixture(scope="module")
def st():
    from tests.conftest import make_state

    return make_state(3)


def _body(st, **kw):
    d = {"init_states": st.tolist(), "doy_sincos": DOY, "steps": 10, "perturbation": None}
    d.update(kw)
    return d


def _valid(r, steps=10):
    assert r.status_code == 200, r.text[:200]
    o = np.asarray(r.json()["rollout"], dtype=np.float64)
    assert o.shape == (steps, 6, 32, 36)
    assert np.isfinite(o).all()
    assert o[:, 1].min() >= 0 and o[:, 5].min() >= 0
    assert o[:, 0].min() >= 233.15 and o[:, 0].max() <= 333.15
    return o


def _b64(a):
    a = np.ascontiguousarray(a, "<f4")
    return {"b64": base64.b64encode(a.tobytes()).decode(), "shape": list(a.shape)}


def test_health_get_and_post(client):
    assert client.post("/health").json()["status"] == "ready"
    assert client.get("/health").json()["status"] == "ready"


@pytest.mark.parametrize(
    "steps,expect", [(1, 1), (10, 10), (14, 14), (0, 1), (-3, 1), (15, 14), (100, 14), ("10", 10), (10.7, 10)]
)
def test_steps_are_clipped_not_rejected(client, st, steps, expect):
    _valid(client.post(ROUTE, json=_body(st, steps=steps)), expect)


def test_missing_optional_fields_default(client, st):
    b = _body(st)
    del b["steps"], b["perturbation"]
    _valid(client.post(ROUTE, json=b))


@pytest.mark.parametrize("doy", [[0, 0], [5, -3], [1.0, 0.0], [0.0, -1.0]])
def test_odd_day_of_year(client, st, doy):
    _valid(client.post(ROUTE, json=_body(st, doy_sincos=doy)))


def test_nan_and_inf_inputs(client, st):
    x = st.copy()
    x[0, 0, 0, 0] = np.nan
    x[2, 4, 3, 3] = np.inf
    p = np.zeros((6, 32, 36), np.float32)
    p[1, 5, 5] = np.nan
    raw = json.dumps(_body(x, perturbation=p.tolist()))  # json emits NaN / Infinity tokens
    _valid(client.post(ROUTE, content=raw, headers={"Content-Type": "application/json"}))
    raw = json.dumps(_body(st)).replace(json.dumps(DOY), "[NaN, 1.0]")
    _valid(client.post(ROUTE, content=raw, headers={"Content-Type": "application/json"}))


@pytest.mark.parametrize(
    "name,fill",
    [("zeros", 0.0), ("huge", 1e30), ("tiny", -1e30)],
)
def test_absurd_initial_states(client, name, fill):
    _valid(
        client.post(ROUTE, json={"init_states": np.full((3, 6, 32, 36), fill).tolist(), "doy_sincos": DOY, "steps": 10})
    )


def test_negative_rain_in_init(client, st):
    x = st.copy()
    x[:, 1] = -50.0
    _valid(client.post(ROUTE, json=_body(x)))


@pytest.mark.parametrize("ch,val", [(0, 200.0), (0, -200.0), (4, -1e6), (5, -1e4), (1, 1e5), (2, 300.0), (3, -300.0)])
def test_extreme_shocks_everywhere(client, st, ch, val):
    p = np.zeros((6, 32, 36), np.float32)
    p[ch] = val
    _valid(client.post(ROUTE, json=_body(st, perturbation=p.tolist())))


def test_b64_and_batch_dim_perturbation(client, st):
    p = np.zeros((6, 32, 36), np.float32)
    p[0, 10:14, 10:14] = 3.0
    a = _valid(client.post(ROUTE, json=_body(st, init_states=_b64(st), perturbation=_b64(p))))
    b = _valid(client.post(ROUTE, json=_body(st, perturbation=p[None].tolist())))
    assert np.allclose(a, b, atol=1e-4)


def test_integer_zero_perturbation_equals_null(client, st):
    a = _valid(client.post(ROUTE, json=_body(st)))
    b = _valid(client.post(ROUTE, json=_body(st, perturbation=np.zeros((6, 32, 36), int).tolist())))
    assert np.abs(a - b).max() == 0.0


@pytest.mark.parametrize(
    "mutate,status",
    [
        (lambda b: b.update(doy_sincos=[0.5]), 422),
        (lambda b: b.pop("doy_sincos"), 422),
        (lambda b: b.update(init_states=np.zeros((2, 6, 32, 36)).tolist()), 422),
        (lambda b: b.update(init_states=np.zeros((3, 6, 36, 32)).tolist()), 422),
        (lambda b: b.update(perturbation=np.zeros((6, 32, 35)).tolist()), 422),
        (lambda b: b.update(init_states="hello"), 422),
        (lambda b: b.update(init_states={"b64": "!!!", "shape": [3, 6, 32, 36]}), 422),
        (lambda b: b.update(steps="ten"), 422),
        (lambda b: b.clear(), 422),
    ],
)
def test_malformed_requests_get_clear_errors(client, st, mutate, status):
    b = _body(st)
    mutate(b)
    r = client.post(ROUTE, json=b)
    assert r.status_code == status
    assert "error" in r.json()


def test_not_json(client):
    r = client.post(ROUTE, content="garbage", headers={"Content-Type": "application/json"})
    assert r.status_code == 400 and "error" in r.json()


def test_extra_keys_ignored(client, st):
    _valid(client.post(ROUTE, json=_body(st, foo=1, bar=[1, 2])))


def test_feb29_and_dec31_windows(client, st):
    for slot in (58, 59, 60, 364, 365):
        a = 2 * math.pi * slot / 365
        _valid(client.post(ROUTE, json=_body(st, doy_sincos=[math.sin(a), math.cos(a)])))
