# 09. ML plan: data, training, fitting, calibration

This document is the recipe P1 (model) and P2 (calibration) follow. The architecture itself is in
`03-model-and-physics-spec.md`. Every script reads a YAML config from `configs/`; every date lives in those configs.

---

## 1. Data

### 1.1 Files
| File | Where | Committed? | Contents |
| --- | --- | --- | --- |
| `india_climate_train.nc` | `data/` | **Never** | variable `data (time, channel, lat, lon)` float32, 2005-01-01..2021-12-31 daily; variable `static (static_channel, lat, lon)` with `land_sea_mask`, `orography_m`; coords `time`, `channel`, `lat`, `lon` |
| `stats.json` | `data/` and copied to `artifacts/` | Yes (artifacts copy) | `{"channels": [...], "mean": [6], "std": [6]}` |
| kit wheel | `vendor/` | Optional | `monsoon_r1_kit-1.0.0-py3-none-any.whl` from the kit Releases page |

Download both data files from the kit's Releases page (tag v1.0.0) **before** the event.

### 1.2 Loading (`training/data.py`)
```python
ds = xr.open_dataset(cfg.data_path)            # data/india_climate_train.nc
X = ds["data"].values.astype("float32")        # [N, 6, 32, 36]
dates = pd.to_datetime(ds["time"].values)      # dates are allowed here: training/ is not in the serve graph
static = ds["static"].values.astype("float32") # [2, 32, 36]
```
- Check: no NaN, N = 6,209, lat ascending 6.5..37.5, lon ascending 65.5..100.5, channel order matches the contract.
- Cache to `data/cache.npz` for fast reloads (gitignored).
- `training/` may use dates freely. Keep the year boundaries in `configs/data.yaml`:
  ```yaml
  data_path: data/india_climate_train.nc
  splits:
    train: ["2005-01-01", "2019-12-31"]
    calib: ["2020-01-01", "2020-12-31"]   # fit blend, damping, rain map, ridge lambda
    grade: ["2021-01-01", "2021-12-31"]   # out-of-sample self-grade
  ```

### 1.3 Samples
- A sample is `(x[t-2], x[t-1], x[t]) -> (x[t+1], ..., x[t+K])` with K up to 8 during training (14 for ridge).
- A sample belongs to a split by the date of `x[t]`. Drop samples whose targets cross a split boundary.
- Train: about 5,470 samples. Calib: about 360. Grade: about 355.

## 2. Artifacts built before any model

`training/build_climatology.py` writes:
| Artifact | Shape | Notes |
| --- | --- | --- |
| `artifacts/climatology.npy` | (366, 6, 32, 36) float32 | exact kit method (366 slots, 15-day circular mean), built from **all 2005-2021** data, like the judge |
| `artifacts/clim_std.npy` | (6, 32, 36) float32 | per-cell std of daily anomalies (for the OOD meter and rain normalization) |
| `artifacts/norm.json` | small | per-channel std of normalized anomalies; rain log-anomaly std |
| `artifacts/static.npy` | (2, 32, 36) float32 | land-sea mask and orography |
| `artifacts/stats.json` | small | copy of the kit stats |

Caveat to record: the climatology uses all years including 2020-2021, matching what the judge most likely uses for its
climatology reference. It is a 366-day mean, not an archive; the network is still trained only on 2005-2019 targets.

Verification (`tests/test_climatology_doy.py`, needs the kit): our climatology equals `monsoon_r1.stats.climatology`
on the same data within 1e-4.

## 3. Ridge skill head (`training/fit_ridge.py`), P2, hour 1-2

1. Features per cell: normalized anomalies of the last 3 days (18), doy sin and cos of the target day (2), bias (1).
2. Targets: normalized anomaly at lead k = 1..14 for each channel.
3. For each lambda in [0.1, 1, 10, 100]: fit on train, score RMSE on calib; pick lambda per (lead, channel).
4. Refit on train with the chosen lambdas. Save `artifacts/ridge.pt`, tensor `(14, 6, 21, 32, 36)`.
5. Vectorized implementation: build `X` as `[cells, samples, 21]` and solve batched normal equations with
   `torch.linalg.solve` (1,152 cells x 14 leads x 6 channels, tiny).
6. Expected: beats persistence at every lead for t2m, msl, tcwv; strong at day 1 for tp. Gate v0.1 at hour 3: ridge
   alone (with clamps) beats persistence at day 4 on calib.

## 4. Network training (`training/train_nn.py`), P1, hour 1-5

### 4.1 Setup
- Device: CUDA (RTX 4050, 6 GB). Mixed precision `torch.autocast("cuda", dtype=torch.bfloat16)` if supported, else fp16
  with GradScaler. Keep `grid_sample` in fp32 if precision issues appear.
- Seed: `configs/train.yaml: seed: 17`.
- Optimizer AdamW, lr 1e-3 with cosine decay to 1e-5, weight decay 1e-4, grad clip 1.0.
- Batch size 32 (fits easily: 30x32x36 inputs, 128 channels).
- Data on GPU entirely (6,209 x 6 x 32 x 36 x 4 bytes = 172 MB).

### 4.2 Loss
- Latitude-weighted MSE in normalized anomaly space, averaged over channels with weights
  `t2m 1, tp 1, u10 1, v10 1, msl 1, tcwv 1` (tunable).
- Heavy-rain weight: cells where observed tp exceeds 10 mm/day get weight 3 on the tp term.
- No variance-matching or spectral loss (decided; costs RMSE for points that are mostly free).

### 4.3 Curriculum
| Stage | Unroll K | Epochs | Approx time on RTX 4050 | Exit criterion |
| --- | --- | --- | --- | --- |
| A | 1 | 15 | 3 to 6 min | val day-1 RMSE below ridge for t2m and msl |
| B | 4 | 10 | 5 to 10 min | 30-day free rollout finite; day-4 skill above ridge on 2 channels |
| C | 8 | 8 | 8 to 15 min | causality gate passes on calib shock windows |
(times are estimates; measure in hour 2 and adjust epochs)

- In unrolled stages, the loss is the mean over all K steps (equal weights), with gradients flowing through the
  rollout (backprop through time). If memory is tight, detach every 4 steps.
- Input noise in stages B and C: add Gaussian noise with std 0.05 (normalized units) to the initial window to make the
  model robust to its own errors.
- Shock-robustness augmentation (stage C, optional): with probability 0.2, add a random smooth bump (Gaussian blob,
  radius 2 to 6 cells, amplitude up to 1.5 std) to the **last** input day only, and add a penalty on the bump's
  response energy outside the light cone at day 1. Teaches the model not to discard a last-day-only change.

### 4.4 Checkpoint selection
- Every epoch in stages B and C: run the fast self-grade on calib (20 windows) plus the causality gate on the 4 shock
  windows. Keep the best checkpoint by mean skill **among those passing the gate**.
- Save `runs/<name>/best.pt` plus a JSON with metrics. Export to `artifacts/nn.pt` (state_dict only, plus a
  `config.json` with architecture hyperparameters).

### 4.5 Things to watch
| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Free rollout drifts warm or cold | anomaly bias accumulates | add the 3-day mean anomaly input; stage B noise; lower lr |
| NaN during training | grid_sample in fp16, exploding unroll | fp32 for grid_sample; grad clip; shorter unroll |
| Shock decays to zero by day 3 | residual not carrying the last day; over-smoothing | check `x_next = x_adv + delta` init (delta zero); augmentation |
| Shock leaks far on day 1 | a global op slipped in; displacement cap wrong | run `tests/test_lightcone.py` |
| tp all near drizzle | MSE averaging | heavy-rain weight; quantile map fixes most of it later |

## 5. Blend (`training/fit_blend.py`), P2, hour 4-5

- Inputs: NN and ridge forecasts on calib (2020) for leads 1..14, in normalized anomaly space.
- For each (lead, channel): grid search `w` in 0.00..1.00 step 0.05 minimizing latitude-weighted MSE.
- Save to `artifacts/postproc.json` under `"blend_w": [[...6] x14]`.

## 6. Post-processor (`training/fit_postproc.py`), P2, hour 5-6

1. Anomaly damping `a[k, c]`: closed-form RMSE-optimal shrink `a = <F, O> / <F, F>` on calib, clipped to [0.3, 1.0],
   then increased if needed until the full-field day-k variance ratio is at least 0.5 on calib.
2. Rain quantile map per lead (section 6.3 of the model spec), optional land/ocean split.
3. Frequency-bias adjustment per lead toward the targets in `configs/calib.yaml`.
4. Save into `artifacts/postproc.json`.
5. Grade on 2021 with the kit scoring functions. Record the numbers in `docs/STATUS.md`.
6. For shipping: refit steps 1-3 on 2020 plus 2021 (the network and ridge stay as they are). Re-run the causality gate
   (the post-processor does not touch the delta, but the clamps do).

## 7. Error maps (`training/compute_sigma_err.py`), P1, hour 6-7

- `sigma_err[k, c, i, j]` = RMSE of the **served** forecast (skill head) at lead k for channel c at cell (i, j) over
  2021 start dates. Shape `(14, 6, 32, 36)`, saved as `artifacts/sigma_err.npy` (allowed: first dimension 14).
- Used by the dashboard for stippling and the impact card's exceedance probabilities, never by `/simulate`.

## 8. Artifact manifest

`artifacts/manifest.json`:
```json
{
  "model_name": "wethrfork-v1.0-speedlimit",
  "files": {
    "nn.pt": {"sha256": "...", "bytes": 0},
    "nn_config.json": {"sha256": "..."},
    "ridge.pt": {"sha256": "..."},
    "climatology.npy": {"sha256": "..."},
    "clim_std.npy": {"sha256": "..."},
    "static.npy": {"sha256": "..."},
    "stats.json": {"sha256": "..."},
    "norm.json": {"sha256": "..."},
    "postproc.json": {"sha256": "..."},
    "sigma_err.npy": {"sha256": "..."}
  },
  "trained_on": "train split from configs/data.yaml",
  "selfgrade": {"mean_ss_2021": null, "csi_skill_2021": null}
}
```
Written by `training/export_artifacts.py`. `Engine.load()` verifies the hashes.

Expected total size: nn.pt 2 to 4 MB, ridge.pt 8 MB, climatology 9 MB, sigma_err 0.4 MB, rest tiny. About 20 MB. No LFS
needed (GitHub warns at 50 MB per file).

## 9. Compute budget (one RTX 4050, 6 GB)

| Job | Estimate |
| --- | --- |
| Build climatology and norms | under 1 min (CPU) |
| Ridge fit | 1 to 2 min |
| Network stage A+B+C | 20 to 40 min |
| Blend + post-processor fit | under 2 min |
| Fuzz test (60 shocks, CPU) | 2 to 4 min |
| Self-grade (70 windows) | 1 to 2 min |

Everything fits several times over in 12 hours; the bottleneck is people, not the GPU. Run training in the background
and keep working.

## 10. What we deliberately do not do
- No foundation models or pretrained weights (rules: weights trained during the event; also CPU and 5 s limits).
- No final refit on all years (keeps the self-grade honest and calibrations valid).
- No ensembles at inference (null shock determinism).
- No global layers (causality).
- No variance-matching loss (costs RMSE).
