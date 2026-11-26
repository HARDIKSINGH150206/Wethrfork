"""Judge entrypoint: python serve.py --port 8000

The only file that contains the route string. Loads the Engine once at import (artifacts, hash check, warm-up) and
serves POST /health and POST /simulate. Offline, CPU only, deterministic.
"""
import argparse
import time

import torch
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from wethrfork.engine import Engine
from wethrfork.io import decode_array, to_list

torch.set_num_threads(4)
try:
    torch.use_deterministic_algorithms(True)
except Exception:  # pragma: no cover
    pass

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["POST", "OPTIONS", "GET"], allow_headers=["*"])
ENGINE = Engine.load()


@app.post("/health")
def health():
    if ENGINE.ready:
        return {"status": "ready", "model_name": ENGINE.model_name}
    if ENGINE.error:
        return {"status": "error", "detail": ENGINE.error, "model_name": ENGINE.model_name}
    return {"status": "loading", "model_name": ENGINE.model_name}


@app.post("/simulate")
async def simulate_endpoint(request: Request):
    t0 = time.perf_counter()
    body = await request.json()
    init = decode_array(body["init_states"])
    pert = body.get("perturbation")
    pert = None if pert is None else decode_array(pert)
    steps = int(body.get("steps", 10))
    out = ENGINE.simulate(init, body["doy_sincos"], steps, pert)
    return {"rollout": to_list(out), "inference_ms": (time.perf_counter() - t0) * 1000.0}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    uvicorn.run(app, host="0.0.0.0", port=ap.parse_args().port, log_level="warning")
