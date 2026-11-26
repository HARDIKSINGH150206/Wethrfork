"""Judge entrypoint: python serve.py --port 8000

The only file that contains the route string. Loads the Engine once at import (artifacts, hash check, warm-up) and
serves POST /health and POST /simulate. Offline, CPU only, deterministic.
"""

import argparse
import json
import logging
import time

import torch
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from wethrfork.engine import Engine
from wethrfork.io import RequestError, parse_request, to_list

torch.set_num_threads(4)
try:
    torch.use_deterministic_algorithms(True)
except Exception:  # pragma: no cover
    pass

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["POST", "OPTIONS", "GET"], allow_headers=["*"])
ENGINE = Engine.load()


@app.get("/health")
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
    try:
        body = json.loads(await request.body())
    except (ValueError, UnicodeDecodeError):
        return JSONResponse({"error": "body is not valid JSON"}, status_code=400)
    try:
        init, doy, steps, pert = parse_request(body)
    except RequestError as e:
        return JSONResponse({"error": str(e)}, status_code=422)
    try:
        out = ENGINE.simulate(init, doy, steps, pert)  # never raises for valid shapes: falls back to the ridge head
    except Exception as e:  # pragma: no cover - last resort, keep the answer machine-readable
        logging.exception("simulate failed")
        return JSONResponse({"error": f"internal error: {type(e).__name__}"}, status_code=500)
    return {"rollout": to_list(out), "inference_ms": (time.perf_counter() - t0) * 1000.0}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    uvicorn.run(app, host="0.0.0.0", port=ap.parse_args().port, log_level="warning")
