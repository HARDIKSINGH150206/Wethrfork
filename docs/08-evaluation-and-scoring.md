# 08. Evaluation and scoring: how the judge scores us, and how we grade ourselves

Source of truth: the official kit `yug-monsoon-kit` v1.0.0 (`docs/R1_CONTRACT.md`, `monsoon_r1/scoring.py`,
`monsoon_r1/repo_scan.py`, `monsoon_r1/contract.py`, `monsoon_r1/client.py`, `monsoon_r1/stats.py`) and the Track 2
problem statement. Every threshold below is copied from that code. If the kit is updated, re-read it and update this file.

---

## 1. The funnel

| Stage | Who judges | What happens | Who advances |
| --- | --- | --- | --- |
| Stage 1 (Round 2 qualifier) | Automated grader + 1 human for the brief | 8 blind `/simulate` calls, repo scan, brief read | Top 10 qualifying teams by score |
| Stage 2 (desk review) | Organizing team | Live demo; judges apply a new shock on the spot; review impact extension; questions on design and limits | Top 2 |
| Round 3 (finals) | Official judging panel | Live presentation | Winners |

## 2. Stage 1 hard gate (fail any of these and nothing else matters)

1. Valid outputs on **all 8** requests. Validity per rollout (`scoring.validity`):
   - shape exactly `(steps, 6, 32, 36)`
   - all values finite (no NaN, no Inf)
   - `tp.min() >= -1e-6`
   - `t2m` within `[233.15, 333.15]` K
2. Beat "repeat yesterday" (persistence) at **day 4**.
3. A non-zero **localized** response to at least one shock.

Also: the HTTP call must succeed within 5.0 s, status 200, response under 80 MB, no redirects; `/health` must report
ready within 120 s (polled every 2 s). A failed or invalid window scores 0 for that window and is never skipped.

## 3. The 8 hidden calls

| # | Kind | Details |
| --- | --- | --- |
| 1-5 | Real windows | Dates after 2023-01-10 (never sent; only state grids and day of year). Window types: monsoon onset, heavy rain, heatwave, cyclone, winter disturbance. `steps = 10` |
| 6 | warm_ocean shock | On one real window: `+3.0 K` on t2m and `+15%` of the current tcwv over the Bay of Bengal box, lat 8..20, lon 82..94 |
| 7 | monsoon_stall shock | Same window: `-40%` of current u10 and v10 over the Arabian Sea box, lat 8..20, lon 65..75 |
| 8 | null shock | `perturbation` = zeros; output must equal the unperturbed call |

Box masks use cell centres: a cell is in the box if `lat_min <= LAT <= lat_max` and `lon_min <= LON <= lon_max`.
Bay of Bengal: lat 8.5..19.5 (12 rows), lon 82.5..93.5 (12 cols). Arabian Sea: lat 8.5..19.5 (12 rows), lon 65.5..74.5
(10 cols, touching the **western edge** of the grid).

Note: the warm_ocean +15% tcwv with +3 K is about 5% per K, close to Clausius-Clapeyron (about 7% per K). The judge's
shocks are physically sensible; ours in the dashboard should be too.

## 4. Points (100 total)

| Part | Points | Exact rule |
| --- | --- | --- |
| Forecast RMSE skill | 30 | `30 * clip(mean_ss / 0.12, 0, 1)` |
| Heavy-rain CSI skill | 15 | `15 * clip(mean_csi_skill / 0.10, 0, 1)` |
| Anti-blur | 10 | per channel `clip(r / 0.40, 0, 1) * (r <= 2.5)`, averaged over channels, times 10 |
| Perturbation causality | 15 | two shocks, 7.5 each, four checks each, chained; null failure halves the total |
| Repo scan | 15 | anti-cheat 8 + code health 7 |
| Brief | 15 | human |

### 4.1 Forecast RMSE skill (30)
- `rmse_lat(pred, true)`: latitude-weighted RMSE per channel. Weights `cos(lat)` normalized to mean 1, applied per
  row, mean over lat and lon, then square root; leading dimensions (windows, leads) averaged before the square root
  per channel.
- `SS = 1 - RMSE_model / min(RMSE_persistence, RMSE_climatology)` per channel.
- Evaluated at lead days 1, 4 and 8 (`rollout[0]`, `rollout[3]`, `rollout[7]`), all 6 channels, 5 windows.
- Persistence = the last input day repeated. Climatology = the kit's climatology for the target day (366 slots,
  15-day circular smoothing, built from training data).
- `mean_ss` is the mean over the per-window skill scores; full 30 points at `mean_ss >= 0.12`, linear below, 0 at or below 0.
- Interpretation: on average across channels, leads and windows, our RMSE must be 12% below the better of the two
  references. Day 1 is easy (persistence is weak for tp; climatology is weak for everything); day 8 is hard
  (climatology is strong). Our skill must come mostly from days 1 and 4, while day 8 must at least not be worse than
  climatology. This is why we damp toward climatology at long leads.

### 4.2 Heavy-rain CSI (15)
- Threshold 10 mm/day. `CSI = hits / (hits + misses + false alarms)` on `tp`.
- Reference: the better (max) of persistence CSI and climatology CSI. Skill `(CSI - ref) / (1 - ref)`.
- NaN when there are no events at all (winter, heatwave windows): those windows are ignored in the mean.
- Full 15 points at mean CSI skill 0.10.
- Trap: an MSE-trained model under-predicts rain intensity; by day 4 almost nothing exceeds 10 mm, CSI goes to 0 and
  skill goes negative against persistence. Our fix is per-lead rain quantile mapping (section 6 of `09-ml-plan.md`).
- Trap: climatology CSI is usually near 0 (smoothed climatology rarely exceeds 10 mm/day), so the reference is
  usually persistence, which is decent at day 1 and poor at day 4 and 8.

### 4.3 Anti-blur (10)
- `variance_ratio`: spatial variance of the predicted day-8 field divided by the true day-8 field, per channel,
  over the full field (not anomalies).
- Per channel: full credit at ratio 0.40 or more, linear below, **zero above 2.5** (noise injection is punished).
- Averaged over windows first, then channels.
- Insight: for t2m, msl and tcwv the climatological spatial gradient (north-south temperature, monsoon trough, moist
  ocean versus dry land) dominates the variance. Even a forecast equal to climatology keeps most of it. tp, u10 and v10
  are the channels at risk. Our post-processor keeps day-8 variance at 0.5 or more per channel.

### 4.4 Perturbation causality (15)
For each of warm_ocean and monsoon_stall: `d = rollout_shock - rollout_base`, with `std` from `stats.json`.
- `finite`: all of `d` finite.
- `nonzero`: `max |d/std| >= 1e-3`.
- `stable`: `max |d/std| <= 5.0` (anywhere, any lead).
- Energy per cell per day: `e[k] = sum over channels of (d/std)^2`.
- `localized`: day-1 near fraction `e[0][near].sum() / e[0].sum() >= 0.60`, where `near` is the box mask dilated 3
  times with 4-neighbour steps (Manhattan distance at most 3 from the box).
- `grows`: let `out_e[k] = e[k][~near].sum()`; `late = mean(out_e[3:8])`; requires `late > 1.5 * out_e[0] + 1e-12`
  **and** `late > 0.02 * max_k(e[k].sum())`.
- `no_teleport`: for every day k (0-based), the fraction of energy in cells farther than `3 + 8 * (k + 1)` cells
  (Euclidean distance to the nearest box cell) must be below 0.05.
- `propagates = grows and no_teleport`.
- Points per shock: 7.5 times (checks passed / 4), chained: no response gives 0; a response that is not localized
  earns only the nonzero quarter; stability and propagation count only if localized.
- Null: `max |a - b| / std <= 1e-3` between the null call and the unperturbed call; failure halves the whole 15.

What this means for design:
- A network with a global receptive field (U-Net, attention, global normalization) puts energy everywhere on day 1:
  fails `localized` and loses 3 of 4 quarters per shock.
- A model that damps the shock quickly fails `grows` (out-of-near energy over days 4-8 must be at least 1.5x day 1 and
  at least 2% of the peak total).
- `late` uses days 4-8, so we need `steps >= 8`; the judge uses 10.
- The Arabian Sea box touches the west edge: energy advected westward leaves the grid and is lost. Replicate padding
  avoids reflections; the gate must test monsoon_stall in every season.
- Our release gate is stricter than the judge's: near fraction at least 0.75 and growth ratio at least 3x, in every
  season, on validation windows.

### 4.5 Repo scan (15)
See `docs/11-repo-scan-hygiene.md` for the full mechanics. Summary:
- Anti-cheat (8): all 8 lost if any critical flag; 2 lost per warning. Critical: no file serves the route; an external
  weather source string in inference files; 5+ date literals or a date constructor call in an inference file; a
  multi-year archive array; no checkpoint. Warning: 3-4 date literals; any `.nc`, `.nc4`, `.grib`, `.grib2`, `.zarr`
  file anywhere in the repo.
- Code health (7): training pipeline detected outside inference files (3), server separate from UI (2), frontend
  present (1), README (0.5), checkpoint (0.5).

### 4.6 Brief (15)
Read by a person. Page 1: model design, how we prevent drift and blur, failure modes. Page 2: visualization and the
impact use case. See `docs/12-brief-outline.md`.

## 5. Stage 2 and finals (human)

- Judges apply a **new shock on the spot**. Expect: a different box, a different channel (msl, tp), a large amplitude,
  a cyclone-like vortex, a land shock (heatwave over Rajasthan), a negative moisture shock.
- They review the impact extension and ask about design and limits.
- What wins: speed and confidence on any shock, honest limits with numbers, a clear explanation of why the model is
  causal, a use case that matters to India.

## 6. Our self-grader (`evaluation/selfgrade.py`)

### 6.1 What it does
1. Loads validation windows from `configs/eval.yaml` (dates live there, never in Python).
2. For each window: builds `init_states` from the netCDF, calls `Engine.simulate()` directly (no HTTP), computes
   persistence and climatology exactly as the judge does, and calls the kit functions:
   `scoring.skill_vs_best_ref`, `scoring.csi`, `scoring.csi_skill`, `scoring.variance_ratio`,
   `scoring.anti_blur_points`, `scoring.forecast_points`.
3. For shock tests: `scoring.make_shock("warm_ocean" | "monsoon_stall" | "null", last_state, std)`, then
   `scoring.causality_checks`, `scoring.null_consistent`, `scoring.causality_points`.
4. Prints a table and writes `runs/selfgrade/<tag>.json`.

### 6.2 Honest splits
- Network and ridge are trained on 2005-2019.
- Calibrations (blend weights, post-processor, rain quantile map) are **fitted on 2020** and **graded on 2021**. The
  2021 number is the out-of-sample estimate we quote in the brief.
- For shipping, calibrations are refit on 2020-2021 (the network and ridge stay as trained).

### 6.3 Window sets in `configs/eval.yaml`
- `systematic`: every 5th day of 2021 as a start (about 70 windows) for stable statistics.
- `typed`: windows matching the judge's 5 types, chosen from 2020-2021 (candidates below; verify each in the data).
- `shock_windows`: one window per season (DJF, MAM, JJAS, ON) for the causality gate.

| Type | Candidate start (last input day) | Why |
| --- | --- | --- |
| Monsoon onset | 2021-06-01 | Onset over Kerala early June |
| Heavy rain | 2021-07-17 | Mumbai and west coast heavy rain spell mid July |
| Heatwave | 2020-05-22 | Severe north India heatwave late May 2020 |
| Cyclone | 2021-05-14 | Cyclone Tauktae in the Arabian Sea |
| Cyclone (alt) | 2020-05-16 | Cyclone Amphan in the Bay of Bengal |
| Winter disturbance | 2021-02-01 | Western disturbances in winter |

These candidates are from memory of real events and must be checked against the data before use; replace any that do
not show the expected signal.

### 6.4 Output (example layout)
```
SELF-GRADE  tag=v0.2  calib=fit2020/grade2021
skill  ch   d1     d4     d8    | mean_ss=0.153  -> 30.0/30
       t2m  0.41   0.18   0.02
       tp   0.35   0.12  -0.01
       ...
CSI@10 d1 0.31 (ref 0.22)  d4 0.14 (ref 0.07)  d8 0.06 (ref 0.03)  -> skill 0.09 -> 13.5/15
blur   ratio d8: t2m 0.97 tp 0.61 u10 0.72 v10 0.69 msl 0.93 tcwv 0.95 -> 10.0/10
shocks warm_ocean: nonzero Y localized Y(0.86) propagates Y(grow 4.1x, far 0.00) stable Y(max z 3.1)
       monsoon_stall: ...  null max|d|/std = 0.0  -> 15.0/15
total automated (excl. repo/brief): 68.5/70
```
(Numbers above are illustrative placeholders only.)

## 7. Release gates (CI and `make gate`)

| Gate | Threshold (ours, stricter than the judge where possible) |
| --- | --- |
| Validity | 100% over typed windows, shock windows and the fuzz set |
| Null | max difference exactly 0.0 |
| Localized | near fraction day 1 at least 0.75 for both official shocks in all 4 seasons |
| Grows | late out-of-near energy at least 3x day 1 and at least 2% of peak, all seasons |
| No teleport | far fraction below 0.01 |
| Stable | max z at most 4.0 |
| Skill | mean_ss on 2021 at least 0.12 (warn below), beats persistence at day 4 (fail below) |
| Anti-blur | day-8 ratio in [0.5, 2.0] for every channel |
| Latency | 10 steps under 1.5 s on 4 threads |
| Repo scan | 15/15, zero flags |
