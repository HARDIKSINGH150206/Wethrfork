# 02. Architecture and data flow

How a number travels from the netCDF file to a pixel on the judge's screen, and from the judge's request to the score.

---

## 1. Build-time flow (offline, our laptop)

```
data/india_climate_train.nc  (time 6209, channel 6, lat 32, lon 36) + static (2, 32, 36)
   │
   ├─► training/data.py ─────────────► data/cache.npz (gitignored) + split indices from configs/data.yaml
   │
   ├─► training/build_climatology.py ─► artifacts/climatology.npy (366,6,32,36)
   │                                   artifacts/clim_std.npy (6,32,36)
   │                                   artifacts/norm.json, artifacts/static.npy, artifacts/stats.json
   │
   ├─► training/fit_ridge.py ─────────► artifacts/ridge.pt (14,6,21,32,36)          [train 2005-2019, lambda on 2020]
   │
   ├─► training/train_nn.py (GPU) ────► runs/<name>/best.pt ─► artifacts/nn.pt + nn_config.json
   │
   ├─► training/fit_blend.py ─────────► artifacts/postproc.json: blend_w (14,6)      [fit 2020]
   ├─► training/fit_postproc.py ──────► artifacts/postproc.json: damping a (14,6), rain maps per lead
   │                                   [fit 2020, grade 2021, then refit 2020-2021 for shipping]
   ├─► training/compute_sigma_err.py ─► artifacts/sigma_err.npy (14,6,32,36)         [2021]
   │
   └─► training/export_artifacts.py ──► artifacts/manifest.json (hashes, sizes, model name, self-grade numbers)
```

## 2. Inference flow (judge machine)

```
HTTP POST (≈1 MB JSON)
  │ serve.py: parse JSON → decode_array → float32
  ▼
Engine.simulate(init [3,6,32,36], doy_sincos [2], steps, pert [6,32,36] | None)
  │
  ├─ sanitize: non-finite → climatology; steps → clip(1, 14)
  ├─ d = doy_from_sincos(doy_sincos)                       # integer day 0..365
  ├─ slots = [(d + k) % 366 for k in 1..steps]
  │
  ├─ base window W0 = init (physical)
  ├─ if pert is not None and any(pert != 0):
  │      W1 = init.copy(); W1[-1] += pert                   # exactly as given
  │      batch = stack(W0, W1)                              # [2,3,6,32,36]
  │  else:
  │      batch = W0[None]                                   # [1,3,6,32,36]
  │
  ├─ NN rollout (torch, CPU, no grad): batch → [B, steps, 6, 32, 36] physical
  ├─ Ridge (numpy or torch): W0 → [steps, 6, 32, 36] physical
  ├─ Skill head: F = PP(Blend(NN[0], Ridge)) in anomaly space → physical
  ├─ Delta: D = NN[1] - NN[0] if shocked else 0
  ├─ out = clamp(nan_to_num(F + D))
  ▼
serve.py: {"rollout": out.tolist(), "inference_ms": ...}
```

### 2.1 Inside one network step
```
window [B,3,6,H,W] physical
  → anomalies vs climatology of each window day (slots d-2, d-1, d for the first step)
  → normalized (std per channel; rain via log1p)
  → features [B,30,H,W]: 18 window + 6 mean anomaly + 2 static + 2 position + 2 season
  → displacement from u10,v10 of the last day (physical m/s → cells/day, cos-lat for east-west), alpha scale,
    + 1x1 correction, length cap 4 cells
  → grid_sample(last day normalized anomaly) along -displacement (border padding)
  → local CNN (3 x [3x3 conv → GELU → 1x1 conv → GELU]) → delta
  → next normalized anomaly = advected + delta
  → physical = climatology(slot d+1) + anomaly * std (rain via expm1)
  → window shifts: drop oldest, append new day
```

### 2.2 Where each scoring property is enforced
| Property | Enforced at |
| --- | --- |
| No NaN/Inf | `nan_to_num` in the final clamp; sanitize on input |
| Rain ≥ 0 | final clamp (after delta) |
| t2m within bounds | final clamp |
| Zero shock exact | `Engine.simulate` skips the shocked run |
| Locality day 1 | network reach (cap 4 + bilinear 1 + convs 3) |
| Outward growth | residual-on-last-day network; delta not damped by post-processor |
| No teleport | hard reach 8k after k days versus judge radius 3+8(k+1) |
| Stability (≤ 5 std) | local network trained with unroll + noise; tested by fuzz |
| Skill | ridge + network blend, damping, calibrated rain |
| Anti-blur | damping floor keeps variance ratio ≥ 0.5; rain quantile mapping |
| Latency | ~1M parameter network, batch of 2, 4 threads |

## 3. Dashboard flow (demo laptop)

```
Browser (localhost:5173 in dev, or built files served by `make demo`)
  │
  ├─ on load: GET lab/meta, GET lab/windows
  ├─ pick window: GET lab/windows/{id} → init_states, doy_sincos, (truth)
  ├─ base universe: POST serve/<route> {init, doy, steps 10, perturbation null}
  ├─ user composes a shock in the UI (pure TS: box or Gaussian, channel, amplitude, optional CC moisture coupling,
  │  or cyclone preset) → perturbation [6,32,36] physical
  ├─ fork: POST serve/<route> {..., perturbation}  ∥  POST lab/verdict {..., perturbation}
  ├─ render: base map, shocked map, delta map (full), stipple where |delta| > sigma_err[lead]; speed-limit ring
  │  around the shock box with radius 8 x lead cells
  ├─ impact card: per region, P(exceed) for base and shocked using sigma_err → shift in probability
  └─ click a city: POST lab/sensitivity → overlay
```

All arrays arrive as nested lists; the dashboard converts them once to `Float32Array` per channel per day
(10 x 6 x 1,152 values) and renders on a `<canvas>` grid. No WebGL needed.

## 4. Evaluation flow (CI and local)

```
configs/eval.yaml (all dates) ──► evaluation/selfgrade.py ──► Engine.simulate (direct call, no HTTP)
                                         │                         │
                                         └── kit scoring.py ◄──────┘  skill, CSI, blur, causality, null
                                                   │
                                                   ▼
                              runs/selfgrade/<tag>.json + console table + docs/STATUS.md (manual paste)

tests/ (synthetic only, CI) ──► light cone, null exactness, validity, latency, climatology doy, repo scan
evaluation/fuzz_gym.py ──► runs/fuzz/summary.json + heatmap PNG (brief) + lab /fuzz
evaluation/natural_experiment.py ──► runs/natural/composite.json + figure (brief) + lab endpoint
```

## 5. Process and port layout for the demo

| Process | Command | Port |
| --- | --- | --- |
| Judge server | `python serve.py --port 8000` | 8000 |
| Lab server | `python -m lab.lab_server --port 8001` | 8001 |
| Dashboard | `npm run preview -- --port 5173` (built) | 5173 |

`make demo` starts all three, waits for `/health` ready and `lab /meta`, issues one warm-up fork, then opens the browser.
