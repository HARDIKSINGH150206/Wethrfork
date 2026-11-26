# 04. API specification

Two servers, two very different contracts:

| Server | Port | Who calls it | Scanned by judge | Contract owner |
| --- | --- | --- | --- | --- |
| Judge server (`serve.py`) | 8000 | Automated grader, our dashboard, our tests (via `Engine`) | Yes | The kit (`R1_CONTRACT.md`); we may not change it |
| Lab server (`lab/lab_server.py`) | 8001 | Our dashboard only | No | Us |

---

## 1. Judge server

### 1.1 Startup
- Command: `python serve.py --port 8000` (argparse `--port`, default 8000).
- Host: `0.0.0.0`. Log level `warning`.
- At import: `torch.set_num_threads(4)`, `torch.use_deterministic_algorithms(True)`, construct the `Engine` singleton,
  which loads every artifact listed in `artifacts/manifest.json`, verifies their SHA-256, and runs one warm-up rollout
  of 10 steps on a synthetic climatological input.
- If any artifact fails to load, `/health` must **not** report ready (return `{"status": "loading"}` or
  `{"status": "error", "detail": "..."}`) so the failure is obvious in the validator.

### 1.2 `POST /health`
Request: no body (ignore any body).
Response `200`:
```json
{"status": "ready", "model_name": "wethrfork-v1.0-speedlimit"}
```
Any other `status` means not ready. Keep it cheap: no computation, just a flag.

### 1.3 `POST /simulate`
Request body (JSON):
```json
{
  "init_states": [[[[...36 floats...] x32] x6] x3],
  "doy_sincos": [0.42, -0.91],
  "steps": 10,
  "perturbation": null
}
```

| Field | Type | Shape | Units | Notes |
| --- | --- | --- | --- | --- |
| `init_states` | nested list of floats, or `{"b64": str, "shape": [3,6,32,36]}` | `[3, 6, 32, 36]` | physical | 3 consecutive days, oldest first |
| `doy_sincos` | list of 2 floats | `[2]` | none | `[sin(2 pi doy/365), cos(2 pi doy/365)]` of the **last** input day |
| `steps` | int | | days | 1 to 14; the judge uses 10 |
| `perturbation` | null, nested list, or b64 dict | `[6, 32, 36]` | physical delta | added to `init_states[-1]` before simulating |

Response `200`:
```json
{"rollout": [[[[...]]]], "inference_ms": 142.5}
```

| Field | Shape | Notes |
| --- | --- | --- |
| `rollout` | `[steps, 6, 32, 36]` | `rollout[k]` is day k+1 after the last input day; always nested lists of finite floats |
| `inference_ms` | float | server-side time from request parsed to response built |

Size: 10 x 6 x 32 x 36 = 69,120 numbers, about 1 MB of JSON. Serialize with `np.asarray(out, dtype="f4").tolist()`.
For speed, consider `orjson` only if it is in the allowed library list; otherwise standard `json` via FastAPI is fine
(about 0.2 s).

### 1.4 Validation and error handling
- Decode with a tolerant `_arr()` (lists or b64), cast to float32.
- Check shapes: `init_states` must be `(3, 6, 32, 36)`, `perturbation` must be `(6, 32, 36)` if present, `steps` in
  1..14 (clip silently to that range rather than erroring; the judge always sends 10).
- Non-finite inputs: replace with climatology for that cell before simulating (never crash).
- Any exception inside `simulate()`: log it, fall back to the **ridge-only** forecast plus clamps (still valid), and
  never return a 500. A valid mediocre answer beats an error that scores 0.
- CORS: `CORSMiddleware(allow_origins=["*"], allow_methods=["POST", "OPTIONS"], allow_headers=["*"])` so the browser
  dashboard can call it. This adds no UI import.

### 1.5 `serve.py` skeleton (shape, not final code)
```python
# serve.py  (the ONLY file containing the route string)
import argparse, time
import numpy as np
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from wethrfork.engine import Engine, decode_array

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
ENGINE = Engine.load()            # loads artifacts, warm-up rollout; sets ENGINE.ready

@app.post("/health")
def health():
    return {"status": "ready" if ENGINE.ready else "loading", "model_name": ENGINE.model_name}

@app.post("/simulate")
async def simulate_endpoint(request: Request):
    t0 = time.perf_counter(); body = await request.json()
    init = decode_array(body["init_states"]); pert = body.get("perturbation")
    pert = None if pert is None else decode_array(pert)
    out = ENGINE.simulate(init, body["doy_sincos"], int(body["steps"]), pert)
    return {"rollout": out.astype("f4").tolist(), "inference_ms": (time.perf_counter() - t0) * 1000.0}

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--port", type=int, default=8000)
    uvicorn.run(app, host="0.0.0.0", port=ap.parse_args().port, log_level="warning")
```

### 1.6 `Engine` interface (`wethrfork/engine.py`)
```python
class Engine:
    model_name: str
    ready: bool
    @classmethod
    def load(cls, artifacts_dir: Path | None = None) -> "Engine": ...
    def simulate(self, init_states: np.ndarray,        # [3,6,32,36] physical
                 doy_sincos: Sequence[float],           # [2]
                 steps: int,
                 perturbation: np.ndarray | None,       # [6,32,36] physical delta
                 ) -> np.ndarray: ...                   # [steps,6,32,36] physical, clamped
    # used by lab and evaluation, never by the judge path:
    def simulate_parts(self, init_states, doy_sincos, steps, perturbation) -> dict:
        """returns {'skill': F_skill, 'nn_base': ..., 'nn_shocked': ..., 'delta': D, 'out': out}"""
    def nn_rollout_torch(self, init_states_t: torch.Tensor, doy_sincos, steps) -> torch.Tensor: ...
        # differentiable network rollout for sensitivity maps
```
`decode_array` lives in `wethrfork/io.py` (a small reimplementation of the kit's `decode_array`; the kit is not
importable on the judge machine).

## 2. Lab server (dashboard science backend)

Separate process, not imported by `serve.py`, so the judge never scans it. It imports `wethrfork.engine.Engine`
directly (no HTTP to the judge server, no route string) and the kit (`monsoon_r1.scoring`) for the verdict panel.

Base URL `http://localhost:8001`. All arrays as nested lists in physical units. CORS open.

### 2.1 `GET /meta`
Everything static the dashboard needs.
```json
{
  "lat": [6.5, ...], "lon": [65.5, ...],
  "channels": ["t2m","tp","u10","v10","msl","tcwv"],
  "units": ["K","mm/day","m/s","m/s","Pa","kg/m2"],
  "std": [...6], "mean": [...6],
  "land_sea_mask": [[...]], "orography_m": [[...]],
  "sigma_err": [[[[...]]]],            // [14,6,32,36] per-cell forecast RMSE by lead (2021)
  "regions": [{"id":"kerala","name":"Kerala","cells":[[i,j],...]}, ...],
  "speed_limit_cells_per_day": 8,
  "model_name": "wethrfork-v1.0-speedlimit"
}
```

### 2.2 `GET /windows`
Demo start states available locally (read from the gitignored netCDF; never shipped in the repo).
```json
[{"id": "w01", "label": "Monsoon active spell", "season": "JJAS", "doy": 197}, ...]
```
Labels avoid calendar years in the UI if possible; the brief explains the data source.

### 2.3 `GET /windows/{id}`
```json
{"id":"w01","init_states":[...3x6x32x36],"doy_sincos":[s,c],"truth":[...10x6x32x36]}
```
`truth` is included only for held-out windows (2021) so Timeline Prime can show model versus reality.

### 2.4 `POST /verdict`
Runs the official causality checks on any shock.
Request:
```json
{"init_states": [...], "doy_sincos": [s,c], "perturbation": [...6x32x36], "box": [lat_min, lat_max, lon_min, lon_max] | null, "steps": 10}
```
If `box` is null, the server derives the shock's bounding box from cells where `|perturbation/std|` exceeds 1% of its max.
Response:
```json
{
  "checks": {"finite": true, "nonzero": true, "localized": true, "propagates": true, "stable": true},
  "near_frac_day1": 0.86, "far_frac_max": 0.002, "max_z": 3.1, "growth_ratio": 4.2,
  "ood": {"max_abs_z_vs_clim_std": 3.4, "level": "inside" | "edge" | "extrapolating"},
  "fuzz_similar": {"n": 9, "pass_rate": 0.89},
  "elapsed_ms": 820
}
```
- OOD meter: `max |(shocked_last - clim) / clim_std_cell|`. Levels: inside (< 3), edge (3 to 5), extrapolating (> 5).
  `clim_std_cell` is the per-cell standard deviation of daily anomalies, precomputed (`artifacts/clim_std.npy`,
  shape `(6, 32, 36)`; small, allowed).
- `fuzz_similar`: nearest fuzz-test entries by channel, amplitude bucket, box size bucket and season.

### 2.5 `POST /sensitivity`
Where does a target come from?
Request:
```json
{"init_states": [...], "doy_sincos": [s,c], "target": {"cells": [[i,j],...], "channel": "tp", "lead": 5}}
```
Response:
```json
{"grad": [...6x32x36], "top_channel": "tcwv", "elapsed_ms": 410}
```
Computed with autograd through `Engine.nn_rollout_torch` (network only; labelled "network sensitivity"). Fallback if
the lab is down: the dashboard computes a coarse finite-difference map by calling `/simulate` with small bumps on a
4x4-cell block grid (81 calls, cached).

### 2.6 `GET /fuzz`
Fuzz-test summary for the heatmap and the failure-modes panel.
```json
{"n": 60, "validity": 1.0, "pass_rate": 0.88, "by_channel": {...}, "by_amplitude": {...}, "by_season": {...}, "cases": [...]}
```

### 2.7 `GET /natural-experiment`
Precomputed composite (computed offline by `evaluation/natural_experiment.py`, cached as small JSON in `runs/`,
read by the lab; not committed if it contains per-day data).
```json
{"observed_composite": {"d_tp": [...4x32x36], "d_msl": [...]}, "model_response": {...}, "pattern_corr": {"tp": 0.52, "msl": 0.61}, "n_events": 37}
```

## 3. Dashboard to server call patterns

| UI action | Calls | Expected time |
| --- | --- | --- |
| Load app | `GET /meta`, `GET /windows` | under 300 ms |
| Pick a start window | `GET /windows/{id}`, `POST :8000/simulate` (base) | under 1.5 s |
| Apply a shock / fork | `POST :8000/simulate` (shocked) + `POST /verdict` in parallel | under 3 s |
| Click a city | `POST /sensitivity` | under 1 s |
| Open limits panel | `GET /fuzz` (cached) | instant |

## 4. Error contract for the lab server

- `4xx` with `{"error": "..."}` for bad shapes.
- Never block the dashboard: every lab call has a 5 s client timeout; the UI shows "lab offline" and keeps the judge
  server features working.
