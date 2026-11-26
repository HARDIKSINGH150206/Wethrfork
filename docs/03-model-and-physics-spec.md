# 03. Model and physics specification

This is the exact specification of the Wethrfork model. Anything not fixed here is a tunable listed in section 9.
Rules in `AGENTS.md` section 1 override this document.

---

## 1. The two-head design

Wethrfork serves one formula:

```
base      = init_states                                   # [3, 6, 32, 36] physical units
shocked   = init_states with shocked[-1] = init_states[-1] + perturbation

F_skill   = PP( Blend( NN(base), Ridge(base) ) )          # the forecast we are scored on
D         = NN(shocked) - NN(base)                         # the network's own shock response
out       = clamp( F_skill + D )                           # [steps, 6, 32, 36]

if perturbation is None or all zeros: D = 0 exactly (the shocked run is skipped)
```

- **Skill head** (`F_skill`): the most accurate forecast we can make for the unshocked state. It blends a per-cell ridge
  regression with the neural network per lead day and channel, then applies a post-processor (damping toward
  climatology at long leads, rain quantile mapping).
- **Dynamics head** (`D`): the network alone. It is local by construction, so a shock stays near where it was applied
  and spreads at a bounded speed.
- **Why split them**: blending with a per-cell ridge model and damping toward climatology both improve RMSE, but they
  shrink and trap shock energy, which can fail the judge's "spreads outward" check. Splitting keeps both properties.
- **How to explain it to judges**: this is a control forecast plus a perturbation model, the same structure used in
  tangent-linear and ensemble forecasting. The network's response is applied around the best available control
  forecast. The two agree closely at short leads and diverge more at long leads; we say so in the brief.

## 2. Grid, channels, units

| Item | Value |
| --- | --- |
| Grid | 32 (lat) x 36 (lon) cells, 1 degree |
| Lat centres | 6.5, 7.5, ..., 37.5 (index 0 = south) |
| Lon centres | 65.5, 66.5, ..., 100.5 (index 0 = west) |
| Cell size | 111.2 km north-south; 111.2 * cos(lat) km east-west (110 km at 6.5 N, 88 km at 37.5 N) |
| Channels | 0 t2m (K), 1 tp (mm/day), 2 u10 (m/s), 3 v10 (m/s), 4 msl (Pa), 5 tcwv (kg/m2) |
| Daily definition | t2m, u10, v10, msl, tcwv: mean of 00/06/12/18 UTC; tp: 24 h total |
| Static | land_sea_mask (0..1), orography_m (metres), variable `static` in the netCDF, shape `[2, 32, 36]` |
| Normalization | `stats.json`: per-channel mean and std (over all training days and cells) |
| Data range | 2005-01-01 to 2021-12-31 daily (6,209 days) |

Typical stds (kit defaults; real values from `stats.json`): t2m 8 K, tp 8 mm, u10 3.5 m/s, v10 2.5 m/s, msl 450 Pa,
tcwv 20 kg/m2.

## 3. Representations

### 3.1 Climatology
- Exactly the kit's `stats.climatology`: 366 slots (Feb 29 has its own), mean per calendar day over the training
  archive, then a 15-day circular running mean (offsets -7..+7).
- Precomputed offline by `training/build_climatology.py` into `artifacts/climatology.npy`, shape `(366, 6, 32, 36)`,
  float32 (about 9 MB). The serve graph never imports the kit or any date code.
- Day of year at inference: `doy_sincos = [sin(2 pi d / 365), cos(2 pi d / 365)]` for the last input day.
  Recover `d = round(atan2(s, c) * 365 / (2 pi)) mod 365`. Map to a slot with `slot = clamp(d, 0, 365)`. The forecast
  for step k (1-based) uses slot `(d + k) mod 366`. The plus or minus one day ambiguity around Feb 29 and Dec 31 is
  harmless after 15-day smoothing; `tests/test_climatology_doy.py` pins the behaviour.
- Which convention the judge uses for `doy` (0- or 1-based) is not specified. Our error is at most one slot.

### 3.2 Anomalies and normalized space
- Anomaly: `a = x - clim[slot]` in physical units.
- Normalized anomaly: `z = a / std_c` per channel, except rain.
- Rain: work with `r = log1p(tp)`. Rain anomaly is `log1p(tp) - log1p(clim_tp)`, divided by the std of that
  quantity over training (computed in `build_climatology.py`, saved in `artifacts/norm.json`).
- Output rain: `tp = expm1(log1p(clim_tp) + z_tp * s_tp)`, then `softplus`-style floor at 0 (see 4.5).

### 3.3 Inputs to the network at each step
| Block | Channels | Notes |
| --- | --- | --- |
| Last 3 days, normalized anomalies | 18 | oldest first, 6 each |
| 3-day mean anomaly | 6 | lets the model carry warm or cold offsets (2023-2024 are warmer than training) |
| Static | 2 | land-sea mask, orography normalized (divide by 1000 m) |
| Position | 2 | sin and cos of latitude, normalized longitude |
| Season | 2 | doy sin and cos of the target day |
| Total | 30 | |

## 4. The network (dynamics and part of skill)

### 4.1 Step function
One step maps the 3-day window to the next day's normalized anomaly:

```
x_t      : [B, 6, H, W]          last day normalized anomaly
inputs   : [B, 30, H, W]          section 3.3

# (1) bounded semi-Lagrangian advection
uv_phys  = physical u10, v10 of the last day                       [B, 2, H, W]
disp     = alpha * uv_phys * 86400 / cell_size_m  (per axis, in cells/day; lon cell size scales with cos lat)
disp    += 1x1-conv correction from inputs (pointwise, adds no reach)
disp     = cap_length(disp, L=4.0)            # vector length capped smoothly: d * L*tanh(|d|/L)/|d|
x_adv    = grid_sample(x_t, grid = identity - disp, mode='bilinear', padding_mode='border', align_corners=True)

# (2) local residual CNN
h        = concat(x_adv, inputs)                                   [B, 36, H, W]
h        = Conv3x3(36 -> C) -> GELU -> Conv1x1(C -> C) -> GELU      reach 1
h        = Conv3x3(C -> C)  -> GELU -> Conv1x1(C -> C) -> GELU      reach 2
h        = Conv3x3(C -> C)  -> GELU -> Conv1x1(C -> C) -> GELU      reach 3
delta    = Conv1x1(C -> 6), last layer initialized to zero
x_next   = x_adv + delta                                            residual on the (advected) last day
```

- `alpha` is a learned scalar per channel group, parameterized as `sigmoid(theta)`, initialized at 0.5. 10 m winds
  overstate steering for some fields and understate for others; the network learns the scale.
- Hidden width `C = 128` (tunable 96 to 160). Parameter count about 0.5 to 1.0 million.
- All 3x3 convolutions use `padding=1, padding_mode='replicate'`.
- No normalization layers. If training is unstable, use weight normalization or a small learning rate, never
  GroupNorm or LayerNorm over H and W.
- `align_corners=True` and an identity grid built from `torch.linspace(-1, 1, n)`; convert cell displacements to grid
  units with `2 / (n - 1)` per cell.
- Optional (tunable): advect only selected channels (t2m, tcwv, tp) and leave pressure and winds to the CNN.

### 4.2 Reach budget (the speed limit)
| Component | Reach per step (cells) |
| --- | --- |
| Advection displacement length cap | 4 |
| Bilinear sampling neighbourhood | 1 |
| Three 3x3 convolutions | 3 |
| 1x1 convolutions, displacement correction | 0 |
| **Total** | **8** |

The judge's no-teleport radius after k days is `3 + 8 * (k + 1)` cells from the box. Our hard reach after k days is
`8 * k`, always strictly inside. The day-1 localization check wants 60% of energy within Manhattan distance 3 of a
12-row box; most energy stays inside the box because shocks are large and the advection step moves it at most 4 cells.

The brief's claim, exactly: "No change can travel more than 8 cells (about 900 km) per simulated day. The
displacement length is capped at 4 cells/day; the local mixing adds at most 4 more."

Known limitation (we state it): the Arabian Sea low-level jet blows at 12-15 m/s (10-13 cells/day at 1 degree), faster
than our cap. Jet transport is under-represented; that is a failure mode we list, not hide.

### 4.3 Multi-day rollout
- Window shift: after predicting day t+1, drop the oldest day and append the prediction (in normalized anomaly
  space, converted through physical space if a channel's climatology changes with the date).
- Season inputs advance one day per step.
- Steps up to 14 (`MAX_STEPS` in the kit).

### 4.4 Network output to physical units
`phys = clim[slot] + z * std` per channel; rain as in 3.2.

### 4.5 Rain positivity
Inside the network, rain lives in log space, so `expm1` of any real number is above -1 mm. We floor at 0 with
`tp = softplus(tp * k) / k` (k = 5) on the final served output, or simply `max(tp, 0)` after the delta is added (the
clamp in section 7 is authoritative).

## 5. The ridge skill head

- One independent linear model per (lead k = 1..14, channel c, cell i, j).
- Features per cell (21): the 6-channel normalized anomalies of the last 3 days at that cell (18), doy sin and cos of
  the target day (2), bias (1).
- Target: normalized anomaly of channel c at lead k at that cell.
- Fit in closed form: `W = (X^T X + lambda I)^-1 X^T y` per cell, lambda chosen on 2020 (grid 0.1, 1, 10, 100).
- Stored as `artifacts/ridge.pt`: a tensor `(14, 6, 21, 32, 36)` float32, about 8 MB.
- Steps beyond 14 hold lead 14's weights.
- Because ridge is per-cell, it is perfectly local, but it is never used inside the shock delta.

## 6. Blend and post-processor

### 6.1 Blend (per lead k, channel c)
`F = w[k, c] * NN_k + (1 - w[k, c]) * Ridge_k`, in normalized anomaly space. `w` fitted on 2020 by least squares with
the constraint 0 <= w <= 1 (grid search 0.0 to 1.0 in steps of 0.05). Stored in `artifacts/postproc.json`.

### 6.2 Damping toward climatology
`F' = a[k, c] * F` (anomaly shrink). `a` is the RMSE-optimal shrink on 2020, constrained so that the day-k spatial
variance ratio of the full physical field stays at least 0.5. For t2m, msl, tcwv the constraint is rarely active.

### 6.3 Rain quantile mapping (per lead)
- On 2020, collect forecast rain `f` and observed rain `o` (mm/day) over all cells for lead k.
- Map 41 forecast quantiles (0, 2.5, ..., 100 percent) to observed quantiles, linear interpolation between them,
  identity above the top quantile.
- Then adjust the 10 mm/day exceedance frequency: target frequency bias (forecast events / observed events) of 1.15 at
  lead 1 tapering linearly to 0.95 at lead 8 and beyond. Implemented by a per-lead multiplicative factor on the mapped
  rain above 5 mm.
- Stored in `artifacts/postproc.json` (about 600 numbers, no dates, no per-day entries).
- Optional split: separate maps for land and ocean cells (land_sea_mask >= 0.5).

## 7. Clamp (always last)

```
out = nan_to_num(out, nan=clim_value, posinf=upper, neginf=lower)
out[:, TP]   = max(out[:, TP], 0)
out[:, TCWV] = max(out[:, TCWV], 0)
out[:, T2M]  = clip(out[:, T2M], 234.0, 332.0)
out[:, MSL]  = clip(out[:, MSL], 85000, 110000)       # Pa, generous bounds, never active in normal use
out[:, U10]  = clip(out[:, U10], -60, 60)
out[:, V10]  = clip(out[:, V10], -60, 60)
```
NaN replacement uses the climatology value of that cell and channel for the target day.

## 8. Physics notes the team must be able to explain

- **Advection**: weather features are carried by the flow. A semi-Lagrangian step asks "where did the air arriving
  here come from?" and samples there. It is unconditionally stable (no CFL blow-up) and local.
- **Residual on the last day**: tomorrow is mostly today, moved by the wind, plus local changes. Learning only the change
  keeps rollouts stable and keeps shocks alive unless the physics removes them.
- **Clausius-Clapeyron**: saturation vapour pressure rises about 7% per kelvin. The judge's warm_ocean adds +15%
  moisture with +3 K (about 5% per K). Our dashboard's "physically consistent" option scales tcwv by
  `1.07 ** dT` for temperature shocks.
- **Geostrophic and gradient-wind balance**: in a pressure low, wind circulates counter-clockwise in the northern
  hemisphere. For the cyclone preset, winds come from gradient-wind balance with Coriolis `f = 2 * 7.292e-5 * sin(lat)`
  plus 15 degrees of inflow.
- **Why damping helps RMSE but hurts realism**: beyond about a week, the atmosphere is chaotic; the RMSE-optimal
  forecast blends toward climatology. Our skill head does this; our dynamics head does not, so shock ripples stay crisp.
- **Why no global operations**: a global normalization or attention layer lets a change anywhere influence everywhere in
  one step. Physically, information moves with the wind and with waves; on a daily 1-degree grid that is at most a few
  cells a day.

## 9. Tunables (with defaults and allowed ranges)

| Tunable | Default | Range | Where |
| --- | --- | --- | --- |
| Hidden width C | 128 | 96 to 160 | `configs/train.yaml` |
| Displacement cap L | 4.0 cells | 3.0 to 4.0 (never above 4.0) | `configs/train.yaml` |
| Conv blocks | 3 | 2 to 3 (never above 3) | `configs/train.yaml` |
| alpha init | 0.5 | 0.3 to 0.8 | `configs/train.yaml` |
| Ridge lambda | chosen on 2020 | 0.1 to 100 | `configs/ridge.yaml` |
| Rain bias targets | 1.15 to 0.95 | 0.9 to 1.3 | `configs/calib.yaml` |
| Min variance ratio for damping | 0.5 | 0.45 to 0.6 | `configs/calib.yaml` |
| Unroll schedule | 1, 4, 8 | | `configs/train.yaml` |
