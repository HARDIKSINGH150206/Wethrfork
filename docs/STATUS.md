# STATUS (update at every gate)

| Field | Value |
| --- | --- |
| Current phase | Hardening done; submission candidate |
| Current tag | v1.1 (after this round of testing) |
| Model | `wethrfork-v1.1-speedlimit`: skill network + ridge (forecast), fine-tuned dynamics network (shock response) |

## Gates
| Gate | Status | Notes |
| --- | --- | --- |
| Gate 1: validator + scan 15/15 | pass | validator green; scan 15.0 / 15, no flags |
| v0.1: ridge qualifies | pass | ridge only: 2021 mean skill 0.099 |
| Gate 2: network passes causality, beats ridge | pass | all seasons, both official shocks |
| v0.2: calibrated, all release gates | pass | |
| Official-shock sweep (all 71 held-out windows) | pass | 15.00 / 15 causality points in every window (was 14.34 before the dynamics fine-tune) |
| Judge-like container (clean clone, no network, read-only, 4 CPUs, 6 GB) | pass | ready in 3 s, valid output, null difference 0.0 |
| Brief 2 pages | pass | `brief/wethrfork-brief.pdf` |

## Self-grade, 2021 (network and ridge never saw 2021)
| Metric | Day 1 | Day 4 | Day 8 | Mean / points |
| --- | --- | --- | --- | --- |
| RMSE skill vs best of persistence/climatology (calibration fitted on 2020) | 0.222 | 0.036 | -0.009 | 0.134 (30 / 30) |
| CSI skill at 10 mm/day | 0.092 | 0.019 | -0.013 | 0.075 (11.3 / 15) |
| Day-4 skill vs persistence, by channel (t2m, tp, u10, v10, msl, tcwv) | | 0.22, 0.26, 0.26, 0.30, 0.23, 0.24 | | beats persistence on every channel |
| Day-8 variance ratio (t2m, tp, u10, v10, msl, tcwv) | | | 1.01, 0.68, 0.71, 0.78, 0.85, 0.91 | anti-blur 10 / 10 |

Leakage check: the climatology and normalisation statistics are computed over 2005-2021 (like the judge's reference).
Rebuilding the climatology from 2005-2020 only and re-grading 2021 changes mean skill 0.1335 to 0.1326 and CSI skill
0.080 to 0.072 (shipped calibration). Negligible.

## Causality gate (per season, strict thresholds: near >= 0.75, growth >= 3x, far <= 0.01, max z <= 4)
| Season | warm_ocean near / growth / max z | monsoon_stall near / growth / max z |
| --- | --- | --- |
| DJF | 0.99 / 70 / 1.82 | 1.00 / 3423 / 2.04 |
| MAM | 1.00 / 79 / 1.47 | 1.00 / 202 / 0.29 |
| JJAS | 1.00 / 71 / 3.77 | 1.00 / 163 / 3.08 |
| ON | 1.00 / 23 / 3.55 | 1.00 / 20 / 1.30 |

Null shock: max difference exactly 0.0 in every season and in all 71 sweep windows.

## Engineering
| Check | Value |
| --- | --- |
| Tests | 79 pass (includes 40 HTTP edge cases: malformed bodies, wrong shapes, NaN/Inf, 1e30 values, odd steps, Feb 29 / Dec 31) |
| Malformed requests | clean 400/422 JSON errors (were 500 before this round) |
| Latency, 10 steps shocked | about 0.18 s wall with JSON; 8 concurrent shocked calls all succeed |
| Fuzz | 200 random shocks: validity 100%, causality 99.5% (rain shocks 94%, 40%-relative shocks 96% are the weakest) |
| Natural experiment (60 warm, moist Bay days, day 2) | rain pattern r = 0.31 (same sign in the Bay); pressure r = -0.07 (no match) |
| Monsoon-stall rain | same break-then-revival sequence as the data; dynamics network about 2x the observed size by day 8 |
| Repo scan | 15.0 / 15 |

## Open issues
| # | Issue | Status |
| --- | --- | --- |
| 1 | Pressure response does not match the natural-experiment composite | stated as a limit |
| 2 | Day-8 skill is about climatology | by design |
| 3 | Stall rain response about 2x observed after the dynamics fine-tune (was 1.4x); previous weights kept outside the repo for a revert | stated as a limit; Q&A 20 |
| 4 | Dashboard tested at 1500-1600 px wide; smaller screens only lightly handled | check on the demo laptop |
