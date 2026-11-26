"""Lab server (port 8001): science backend for the dashboard. Imports the Engine directly; no HTTP to the judge server."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from lab.windows_store import WindowsStore
from wethrfork.engine import Engine
from wethrfork.physics import CHANNELS, UNITS

ROOT = Path(__file__).resolve().parent.parent
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
ENGINE = Engine.load()
STORE = WindowsStore()
KIT_STATS = json.loads((ROOT / "artifacts" / "stats.json").read_text())
STD = np.array(KIT_STATS["std"], dtype=np.float32)
MEAN = np.array(KIT_STATS["mean"], dtype=np.float32)


def _json_file(rel: str) -> dict:
    p = ROOT / rel
    return json.loads(p.read_text()) if p.exists() else {"available": False}


@app.get("/meta")
def meta() -> dict:
    static = np.load(ROOT / "artifacts" / "static.npy")
    sig = ROOT / "artifacts" / "sigma_err.npy"
    return {
        "lat": [6.5 + i for i in range(32)],
        "lon": [65.5 + j for j in range(36)],
        "channels": list(CHANNELS),
        "units": list(UNITS),
        "std": STD.tolist(),
        "mean": MEAN.tolist(),
        "land_sea_mask": static[0].tolist(),
        "orography_m": static[1].tolist(),
        "sigma_err": np.load(sig).tolist() if sig.exists() else None,
        "speed_limit_cells_per_day": 8,
        "model_name": ENGINE.model_name,
    }


@app.get("/windows")
def windows() -> list[dict]:
    return STORE.listing()


@app.get("/windows/{wid}")
def window(wid: str) -> dict:
    w = STORE.get(wid)
    if w is None:
        raise HTTPException(404, {"error": "unknown window"})
    return w


def _derive_box(pert: np.ndarray) -> list[float]:
    z = np.abs(pert / STD[:, None, None]).max(axis=0)
    ii, jj = np.where(z > 0.01 * max(z.max(), 1e-12))
    if len(ii) == 0:
        return [8.0, 8.0, 65.0, 65.0]
    return [6.5 + float(ii.min()), 6.5 + float(ii.max()), 65.5 + float(jj.min()), 65.5 + float(jj.max())]


@app.post("/verdict")
def verdict(body: dict) -> dict:
    from monsoon_r1 import scoring as S

    t0 = time.perf_counter()
    try:
        init = np.asarray(body["init_states"], dtype=np.float32).reshape(3, 6, 32, 36)
        pert = np.asarray(body["perturbation"], dtype=np.float32).reshape(6, 32, 36)
    except Exception as e:
        raise HTTPException(400, {"error": f"bad shape: {e}"}) from e
    steps = int(body.get("steps", 10))
    doy = body["doy_sincos"]
    box = body.get("box") or _derive_box(pert)
    base = ENGINE.simulate(init, doy, steps, None)
    shock = ENGINE.simulate(init, doy, steps, pert)
    res = S.causality_checks(base, shock, tuple(box), STD)
    d = shock - base
    e = S._energy(d, STD)
    near = S.near_mask(tuple(box))
    out_e = np.array([e[k][~near].sum() for k in range(e.shape[0])])
    late = out_e[3:8].mean() if steps >= 8 else out_e[-1]
    growth = float(late / max(out_e[0], 1e-12))
    shocked_last = init[-1] + pert
    slot0 = ENGINE.clim.shape[0] and int(round(np.arctan2(doy[0], doy[1]) * 365 / (2 * np.pi))) % 365
    clim_std = ENGINE.clim_std if ENGINE.clim_std is not None else np.broadcast_to(STD[:, None, None], (6, 32, 36))
    ood = float(np.abs((shocked_last - ENGINE.clim[slot0]) / np.maximum(clim_std, 1e-6)).max())
    level = "inside" if ood < 3 else ("edge" if ood < 5 else "extrapolating")
    fuzz = _json_file("runs/fuzz/summary.json")
    return {
        "checks": {k: bool(res[k]) for k in ("finite", "nonzero", "localized", "propagates", "stable")},
        "near_frac_day1": float(res.get("near_frac_day1", 0.0)),
        "far_frac_max": float(res.get("far_frac_max", 0.0)),
        "max_z": float(np.abs(d / STD[None, :, None, None]).max()),
        "growth_ratio": growth,
        "ood": {"max_abs_z_vs_clim_std": ood, "level": level},
        "fuzz_similar": {"n": fuzz.get("n", 0), "pass_rate": fuzz.get("pass_rate")},
        "elapsed_ms": (time.perf_counter() - t0) * 1000.0,
    }


@app.post("/sensitivity")
def sensitivity(body: dict) -> dict:
    t0 = time.perf_counter()
    if ENGINE.net is None:
        raise HTTPException(503, {"error": "no network loaded"})
    init = torch.tensor(np.asarray(body["init_states"], dtype=np.float32).reshape(1, 3, 6, 32, 36), requires_grad=True)
    tgt = body["target"]
    ch = CHANNELS.index(tgt["channel"])
    lead = int(tgt["lead"])
    out = ENGINE.nn_rollout_torch(init, body["doy_sincos"], lead)
    loss = sum(out[0, lead - 1, ch, i, j] for i, j in tgt["cells"]) / max(len(tgt["cells"]), 1)
    loss.backward()
    g = init.grad[0, -1].numpy()
    scaled = np.abs(g) * STD[:, None, None]
    return {
        "grad": g.tolist(),
        "top_channel": CHANNELS[int(scaled.sum(axis=(1, 2)).argmax())],
        "elapsed_ms": (time.perf_counter() - t0) * 1000.0,
    }


@app.get("/fuzz")
def fuzz() -> dict:
    return _json_file("runs/fuzz/summary.json")


@app.get("/natural-experiment")
def natural() -> dict:
    return _json_file("runs/natural/summary.json")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8001)
    uvicorn.run(app, host="0.0.0.0", port=ap.parse_args().port, log_level="warning")
