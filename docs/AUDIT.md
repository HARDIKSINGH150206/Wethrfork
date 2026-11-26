# AUDIT: QA remediation and brutal test report

Scope: the QA review of the v1.1 code base, every fix made in response, and a brutal re-test of the whole product with edge-case
data. Everything below was run on the final artifacts (`wethrfork-v1.1-speedlimit`); commands to reproduce are at the end.

## 1. QA findings and what was done

| # | Finding | Verdict | Action |
| --- | --- | --- | --- |
| 1 | "Causal by construction" overstates what is established | Agreed | Wording replaced everywhere (README, AGENTS, docs, brief, dashboard) by: a hybrid forecasting system with bounded local responses and measured limits (D40) |
| 1b | API perturbation differs from adding the same perturbation to the last input day | **Confirmed and larger than reported.** Over all 71 held-out windows the largest rainfall difference has median **14.5 mm/day** for the warm-ocean shock (p95 36.3, **max 104.9**), median 4.4 for the monsoon stall (max 27.7). By design (skill forecast of the unshocked state plus the dynamics network's response) | Not a bug, a design property. Measured (`evaluation/equivalence_check.py`), documented (D41), added to Q&A 21, the brief's failure modes and the dashboard About tab |
| 2 | Euclidean light-cone test allowed an extra day | **Confirmed.** The test used `3 + 8 (k + 1)` with k = number of days; the judge's 0-based index gives `3 + 8 k` | Fixed. Tests now assert (a) max-axis reach <= 8 per step, (b) the honest Euclidean bound 4 + 4 sqrt(2) = 9.66 per step, (c) the judge radius `3 + 8 d` |
| 2b | Internal gate could pass while the official `propagates` flag is false | **Confirmed.** `passes()` checked only numeric thresholds | Fixed: the gate now also requires the official `localized`, `propagates` and `stable` flags; unit-tested (`tests/test_gate_rules.py`) |
| 3 | `make demo` ran a commented stub | **Confirmed** | Real launcher (`scripts/demo.sh`): preflight, starts forecast server, lab server and dashboard, waits for readiness, runs live checks, opens the browser; `demo.sh stop`. New `scripts/preflight.py` (also `make preflight`) |
| 3b | Dashboard needs the lab server and the local dataset | **Confirmed.** Lab returned 500 / dashboard went blank | Lab has `/status` and answers 503 with instructions when the dataset is missing; the dashboard shows a clear banner. **Not done by me: a rehearsal on the presentation laptop** (see section 6) |
| 4 | Rebuild instructions do not match the shipped model | **Confirmed.** `make artifacts` trained one network; the exporter kept stale weights silently | `make artifacts` now trains skill, dynamics and the dynamics fine-tune, copies weights *before* calibration, then calibrates and writes the manifest with lineage. The exporter fails if a checkpoint is missing unless `--keep-existing` is explicit; the manifest check rejects an incomplete calibration |
| 4b | Rain calibration selects shrink, floor and scale but saves only the scale | **Confirmed, and worse:** the saved scale was also smoothed after tuning, so the shipped calibration differed from the tuned one | Saver now writes shrink, floor and the unsmoothed scale. **Regraded before adopting** (calibrated on 2020, graded on 2021): mean skill 0.1351 (was 0.1342), CSI skill 0.0734 (was 0.0754). Equivalent; adopted. Shipping refit on 2020+2021 redone |
| 5 | Impact panel is thin | Agreed | Replaced by **Rainfall exposure**: 3-day accumulated rainfall and the share of land *area* above a declared threshold (25 / 50 / 100 mm), control against scenario, by region and for all land. No flood probability, no crop loss. Cross-checked against an independent Python computation (identical) |

## 2. Defects found by this audit (beyond the QA list) and fixed

| Defect | How it was found | Fix |
| --- | --- | --- |
| `/status` crashed (500) when the dataset path is outside the repo | New test | Safe path display helper |
| Two forks in the same millisecond got the same id and overwrote each other | Code review, then confirmed in the browser (fork spam) | Sequential ids |
| Switching start state while a run was in flight let the old window's result overwrite the new window | Code review | Epoch token: results from an older epoch are dropped (forks, control run, sensitivity) |
| A failed verdict call was swallowed; the panel said "computing…" forever | Lab killed mid-session | Explicit "verdict unavailable" state |
| Shock form accepted an empty, zero or non-finite amount and boxes outside the domain | Hostile-form test | Validation with a visible reason |
| Error banner read "TypeFailed to fetch" | Browser test | Proper message cleanup |
| `npm install vitest` failed on a peer-dependency conflict (would have broken CI) | Clean `npm ci` check | Pinned a compatible version |
| Float32 overflow warnings flooded the log on absurd (1e20) inputs | Extreme fuzz | Quiet numpy error state around the engine call (the final clamp already handles the values) |
| Malformed requests returned 500 (previous round) | Probe | 400/422 with messages; 40 permanent tests |

## 3. Test results

### 3.1 Judge criteria (held-out 2021, calibration fitted on 2020, network and ridge never saw 2021)

| Criterion | Result |
| --- | --- |
| Valid outputs on every request | 100%: 6,206 archive start days (null), 4,138 shocked forecasts, 71 held-out windows, 200 fuzz shocks, 500 hostile inputs |
| Beat persistence at day 4 | Yes on all 6 channels: 0.22, 0.26, 0.26, 0.30, 0.23, 0.24 |
| RMSE skill | **0.135** mean over 71 windows (day 1: 0.223, day 4: 0.038, day 8: -0.009); full marks at 0.12 |
| Heavy-rain CSI skill | 0.073 (day 1: 0.087, day 4: 0.016, day 8: -0.011); 11.0 of 15 points |
| Anti-blur | day-8 variance ratio 1.01, 0.68, 0.71, 0.78, 0.85, 0.90; 10 of 10 |
| Null shock equals no shock | exactly 0.0 in every one of 6,206 + 71 windows |
| Causality, official shocks | 15.00 / 15 in all 71 held-out windows (every season); 99.76% of 4,138 shocked forecasts over the whole archive pass all four checks (see 5) |
| Speed | sequential p50 184 ms, p99 259 ms, max 262 ms with JSON (limit 5000 ms) |
| Repo scan | 15.0 / 15, no flags |

### 3.2 Brutal tests

| Test | Result |
| --- | --- |
| pytest | 101 pass |
| Dashboard unit tests (vitest) | 16 pass (units, date labels, sampling, rainfall exposure, view clamping) |
| Dataset audit (`evaluation/dataset_audit.py`) | 21 / 21: 6,209 contiguous days, no NaN, ranges physical, stats.json matches, our climatology equals the kit's reference implementation exactly (difference 0.0), no split leakage (train 5,462 / calibration 350 / grading 349 samples) |
| Archive-wide stress (`stress_archive.py`): every start day, 14 steps | 6,206 windows, 0 invalid, 0 negative moisture, 0 null mismatches; 4,138 shocked forecasts, 0 invalid; latency p50 37 ms, p99 96 ms, max 924 ms (first-call spike) |
| Locality through the full served formula (`stress_locality.py`): 150 random shocks, 6 channels, signs, 0.5 to 8 std, patches, corners and edges | Largest change outside the reach: **0.0**; farthest changed cell per day 6, 12, 17, 21, 25, 28, 32, 35, 35, 35 against limits 8, 16, 24 ... 80; tiny shocks continuous (1e-3 K gives 2e-4 std, 1e-6 and below give 0); 3 fresh processes give bit-identical checksums |
| Extreme-input fuzz (`stress_extreme.py`): 500 hostile cases (extremes, checkerboards, 1e20, NaN/Inf, wrong steps and dates, absurd shocks) | 0 failures; all finite, valid, deterministic; zero shock equals no shock |
| API edge cases (pytest, 40 cases) | pass: malformed gets 400/422, extreme gets a valid forecast |
| HTTP load and abuse (`stress_http.py`) | 16 threads x 12 mixed calls: 160 x 200, 32 x 422 (exactly the malformed ones), p99 2.4 s; health under load max 1.2 s; GET/PUT 405, truncated JSON 400, empty 400, binary 400, 5000-deep JSON 422, 20 MB body 200; still ready afterwards; memory 816 MB, +12 MB over 300 calls (no leak) |
| Browser (Playwright, 27 checks) | all pass: fork spam, start-state switching mid-run, lab down at load and mid-session, forecast server down, hostile form input, tiny and out-of-domain boxes, 5 viewports from phone to 4K, hostile search strings, extreme zoom/pan/toggles/playback, 30 forks in a row (heap 19 to 44 MB), no console errors |
| Exposure panel vs independent Python recomputation | identical (all land 29 to 29 mm, Kerala 40 to 55 mm and 33% to 56% of land area above 50 mm) |
| Preflight (`scripts/preflight.py`) | 13 / 13 static checks, live checks pass |
| Judge-like container from a fresh clone (no network, read-only, 4 CPUs, 6 GB) | see 3.3 |

### 3.3 Judge-like container
Run after the final push on a fresh clone of `main`; the result is appended in section 7.

## 4. Dataset: was it fitted before use?

The archive itself is used as released (ERA5 averaged to daily values on a 1 degree grid, 2005 to 2021) and is only *checked*, never
altered: no NaN, contiguous days, physical ranges, statistics identical to the organisers' `stats.json`. What we *compute* from it:

| Quantity | Years used | Consequence |
| --- | --- | --- |
| Climatology (366 slots, 15-day smoothing), per-cell anomaly std, normalisation constants | 2005 to 2021 (the judge's reference does the same) | Includes the grading year. Rebuilding from 2005 to 2020 only and re-grading 2021 changes skill 0.1335 to 0.1326 and CSI skill 0.080 to 0.072: negligible |
| Network and ridge weights | 2005 to 2019 | |
| Ridge strength, checkpoint choice, blend, damping, rain calibration | 2020 | |
| Reported skill | 2021 (held out) | Honest estimate |
| Final calibration shipped | 2020 + 2021 refit (weights unchanged) | In-sample on 2021, so we quote the held-out number |

Nothing is fitted to the judge's 2023 to 2024 windows (not in our data). The grading year is slightly warmer and moister than the
training mean (0.02 to 0.05 training std), a small shift.

## 5. Residual risks (stated, not hidden)

1. **Rare marginal causality misses.** Over every start day in the archive, 10 of 4,138 shocked forecasts (0.24%) fail the judge's
   `propagates` check, all marginally (far-field energy 1.3 to 2.0% of peak against the 2% bar, or growth 1.2 to 3.1 against 1.5).
   Expected cost per judging window about 0.01 point. Not retrained at the last minute.
2. **API shock is not an edited input** (finding 1b): up to 105 mm/day rainfall difference.
3. **Responses are learned, not validated physics.** Natural experiment: rain agrees in sign (r = 0.31), pressure does not (r = -0.07).
   The monsoon-stall rain response follows the observed break-and-revival sequence but is about 2x the observed size by day 8.
4. **Skill beyond day 8 is about climatology**; heavy-rain skill is small (CSI skill 0.073).
5. **Rehearsal on the presentation laptop is not done.** `make preflight` and `make demo` exist to make it a two-minute job; the
   dashboard was tested at 800x600 up to 4K but not on your projector.
6. **Concurrency:** one process, so 16 simultaneous heavy calls queue (p99 2.4 s). The judge sends calls one at a time.
7. **Memory:** the server holds about 0.8 GB; the judge allows 6 GB.

## 6. Reproduce

```bash
make test                                   # pytest (101)
(cd dashboard && npm test)                  # vitest (16)
make scan                                   # repo scan, 15 / 15
make gate sweep fuzz                        # official shocks: seasons, all held-out windows, 60 random
python -m evaluation.dataset_audit          # dataset checks
make stress                                 # extreme fuzz, locality, archive-wide (about 12 min)
python serve.py --port 8000 & make audit-http
python -m evaluation.equivalence_check      # API shock vs edited input
make preflight && make demo                 # before the presentation
```
