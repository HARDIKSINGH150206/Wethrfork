# ARCHITECTURE: Wethrfork system overview

This is the map. Details live in `02-architecture-and-dataflow.md` (data flow), `03-model-and-physics-spec.md` (model),
`04-api-spec.md` (interfaces) and `06-frontend-plan.md` (dashboard).

---

## 1. Components

```
                          OFFLINE (build time, our laptop + RTX 4050)
  ┌──────────────────────────────────────────────────────────────────────────────────────┐
  │ data/india_climate_train.nc ─► training/data.py ─► build_climatology ─► fit_ridge     │
  │                                         │                                  │          │
  │                                         └──► train_nn (GPU) ──► fit_blend ─► fit_postproc
  │                                                                        │              │
  │                                              compute_sigma_err ◄───────┘              │
  │                                                     │                                 │
  │                              export_artifacts ──► artifacts/ (committed, ~20 MB)      │
  └──────────────────────────────────────────────────────────────────────────────────────┘
                                         │
                 RUNTIME (judge machine: CPU only)     RUNTIME (demo laptop)
  ┌──────────────────────────────────────┐   ┌──────────────────────────────────────────┐
  │ serve.py  :8000                       │   │ lab/lab_server.py  :8001                  │
  │   POST /health                        │   │   /meta /windows /verdict /sensitivity    │
  │   POST <route>  ──► wethrfork.Engine  │   │   /fuzz /natural-experiment               │
  │                       │               │   │     │ imports Engine directly (no HTTP)   │
  │   model.py  ridge.py  blend.py        │   │     │ imports monsoon_r1.scoring (kit)    │
  │   climatology.py normalize.py         │   │     │ reads data/*.nc (gitignored)        │
  └──────────────────────────────────────┘   └─────┼────────────────────────────────────┘
                 ▲                                   │
                 │ live forecasts (fetch)            │ verdicts, sensitivity, metadata
  ┌──────────────┴───────────────────────────────────▼──────────────────────────────────┐
  │ dashboard/ (React + Vite + TS, served locally, all assets bundled, works offline)    │
  │   Map canvas · Shock composer · Fork tree + side-by-side · Limits verdict · Impact    │
  └──────────────────────────────────────────────────────────────────────────────────────┘

  QUALITY (CI + local)
  tests/ (light cone, null, validity, latency, scan) · evaluation/ (selfgrade, gate, fuzz, natural experiment, figures)
```

## 2. Responsibilities

| Component | Does | Never does |
| --- | --- | --- |
| `serve.py` | HTTP, decoding, CORS, calls `Engine.simulate` | Any modelling logic, date handling, logging arrays |
| `wethrfork.engine` | Loads artifacts, runs both heads, applies the served formula and clamps | Imports from training, evaluation, lab, kit |
| `wethrfork.model` | The local network (advection + CNN) | Global operations, randomness at inference |
| `wethrfork.ridge` | Applies per-cell ridge weights for leads 1..14 | Shock deltas |
| `wethrfork.blend` | Blend, damping, rain quantile map, clamps | Touch the perturbation |
| `wethrfork.climatology` | doy from sin/cos, slot arithmetic, climatology by slot | Date objects |
| `training/*` | Everything that learns or fits | Get imported by `serve.py` |
| `evaluation/*` | Self-grade, gates, fuzz, natural experiment, brief figures | Contain the route string |
| `lab/*` | Science endpoints for the dashboard | Get imported by `serve.py`; ship data in the repo |
| `dashboard/*` | All visual and interactive features | Pre-render forecasts; fetch anything from the internet |

## 3. Key architectural decisions (see DECISIONS.md for the full list)
1. Two heads: skill head for the forecast, dynamics head for shock responses.
2. Local network with a tested reach bound of 8 cells per day along either axis.
3. Deterministic server; uncertainty comes from precomputed error maps.
4. Route string only in `serve.py`; science features in a separate lab process.
5. All dates in YAML configs; data never committed.
6. Climatology reproduced exactly from the kit method and shipped as a 366-day array.

## 4. Runtime budgets

| Path | Budget | Expected |
| --- | --- | --- |
| Server cold start to ready | 120 s (judge) | under 20 s |
| 10-step `/simulate`, no shock | 5 s (judge) | 0.3 to 0.8 s including JSON |
| 10-step `/simulate`, with shock | 5 s | 0.5 to 1.2 s (batch of 2) |
| Server memory | 6 GB | under 1.5 GB |
| Dashboard shock round trip | our target 3 s | 1 to 2 s |
| Verdict panel | our target 3 s | about 1 s |

## 5. Failure behaviour

| Failure | Behaviour |
| --- | --- |
| Artifact missing or hash mismatch | `/health` not ready with detail; never serve garbage |
| Exception inside the network | Ridge-only forecast + clamps (valid), logged |
| Non-finite input values | Replaced by climatology for those cells before simulating |
| `steps` outside 1..14 | Clipped to the range |
| Lab server down | Dashboard keeps forecast features, shows "lab offline", sensitivity falls back to finite differences |
| Data file absent on demo laptop | Lab offers a synthetic climatological start state; Timeline Prime hidden |
