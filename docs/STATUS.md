# STATUS (update at every gate)

| Field | Value |
| --- | --- |
| Current phase | Phase 4 complete (calibrated model), dashboard and brief in progress |
| Current tag | v0.2 |
| Last updated | v0.2 release (automated session) |

## Gates
| Gate | Target time | Status | Notes |
| --- | --- | --- | --- |
| Gate 1: validator + scan 15/15 | T+2:00 | pass | validator green, scan 15.0 / 15 with the dashboard committed |
| v0.1: ridge qualifies | T+3:00 | pass | tag v0.1 (ridge only: 2021 mean skill 0.099) |
| Gate 2: network passes causality, beats ridge | T+5:00 | pass | all 4 seasons, both official shocks, strict thresholds |
| v0.2: calibrated, all release gates | T+7:00 | pass | tag v0.2 |
| Freeze | T+10:00 | pending | |
| Gate 4: brief 2 pages | T+11:00 | pass | `brief/wethrfork-brief.pdf`, 2 pages, source `brief/brief.html` |
| Submitted | T+11:30 | pending | |

## Latest self-grade (2021, out-of-sample; calibration fitted on 2020)
| Metric | Day 1 | Day 4 | Day 8 | Mean / points |
| --- | --- | --- | --- | --- |
| RMSE skill (mean over channels) | 0.222 | 0.036 | -0.009 | mean_ss 0.134 (30.0 / 30) on 71 windows; typed windows 0.173 |
| CSI skill (10 mm/day) | | | | 0.075 (11.3 / 15); typed 0.157 |
| Variance ratio day 8 by channel (t2m, tp, u10, v10, msl, tcwv) | | | [1.01, 0.68, 0.71, 0.78, 0.85, 0.9] | anti-blur 10.0 / 10 |

Note: the held-out 2021 numbers are the honest estimate. Windows are every 5th day; per-window skill follows the kit.

## Causality gate (per season, strict thresholds: near >= 0.75, growth >= 3x, far <= 0.01, max z <= 4)
| Season | warm_ocean near / growth / max z | monsoon_stall near / growth / max z |
| --- | --- | --- |
| DJF | 0.99 / 78.7 / 1.69 | 1.00 / 464 / 2.18 |
| MAM | 1.00 / 69.0 / 3.51 | 1.00 / 41.6 / 0.38 |
| JJAS | 1.00 / 72.2 / 3.67 | 1.00 / 60.6 / 2.98 |
| ON | 1.00 / 18.8 / 3.38 | 1.00 / 12.2 / 1.19 |

Null shock: max difference exactly 0.0 in every season.

## Engineering
| Check | Value |
| --- | --- |
| Repo scan | 15.0 / 15, no flags |
| Latency 10 steps (shocked, with JSON, local) | about 0.18 s wall, 121 ms in server |
| Fuzz validity / causality pass | 1.00 / 0.95 over 60 shocks |
| Artifact sizes | ridge 8.1 MB, climatology 10.1 MB, two networks 1.6 MB each |
| Natural experiment (warm and moist Bay days, day 2) | 60 events; rain response same sign as the observed composite (pattern corr 0.28); pressure: model falls, observed composite about zero (corr -0.04). Reported as is. |

## Architecture as shipped
Skill: PP(Blend(skill network, ridge)). Shock delta: limiter(dynamics network(shocked) - dynamics network(base)). See
DECISIONS D31 to D35.

## Open issues
| # | Issue | Owner | Status |
| --- | --- | --- | --- |
| 1 | Natural-experiment pressure response does not match the composite | P1 | reported, not tuned |
| 2 | Day-8 skill is about climatology by design | P1 | accepted |
| 3 | Dashboard: Timeline Prime, Validation tab, sensitivity overlay not built | P3 | open |
| 4 | Brief: team name is a placeholder ("Team Wethrfork"); render with headless Chrome from `brief/brief.html` | P3 | open |
| 5 | Monsoon-stall fork raises west-coast rain in one monsoon window; unexplained, expect a judge question | P1 | open |
