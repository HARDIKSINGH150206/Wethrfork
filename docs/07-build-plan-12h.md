# 07. 12-hour build plan (3 people)

Hour-by-hour plan. Gates and phase logic are in `PHASES.md`. Rules: commit every 45 minutes, never break `main`, the
person who breaks CI fixes it first, feature freeze at T+10:00, submit by T+11:30.

| Hour | P1 Model | P2 Server + science | P3 Dashboard + story | Checkpoint |
| --- | --- | --- | --- | --- |
| 0:00-1:00 | Load netCDF, verify shapes and channel order, year splits from YAML, precompute climatology (exact kit method), clim_std, norms, static | Repo skeleton, kit installed, template `serve.py` with CORS, `Engine` placeholder, CI with validator, repo scan, date and archive checks | Vite + React + TS scaffold, India outline on canvas, mock rollout | Template server passes the validator |
| 1:00-2:00 | Local CNN v0 (no advection), training stage A on GPU in background | Ridge baseline per cell and lead; self-grader skeleton with kit scoring | Map, day scrubber, channel picker, legends | **Gate 1**: scan 15/15, validator green |
| 2:00-3:00 | Stage B unroll (K=4), rain in log space; watch free-rollout drift | Ridge wired into `serve.py`, clamps, null-shock and latency tests | Shock composer: draw box, channel, amplitude, presets | **v0.1 tagged**: ridge beats persistence at day 4 |
| 3:00-4:00 | Add bounded advection step; light-cone test | Causality gate (per season, both official shocks) | Swap mock for live judge server | Light-cone test passes |
| 4:00-5:00 | Stage C (K=8); checkpoint selection by self-grade among gate passers | Served formula (two heads), blend placeholder; natural-experiment sanity check | Fork view: 3 synced maps + speed-limit ring + universe list | **Gate 2**: network beats ridge, causality passes all seasons |
| 5:00-6:00 | Export weights; help P2 with calibration data | Blend + post-processor fit on 2020, grade on 2021, refit 2020-2021 | Cyclone preset and track | **v0.2 tagged** |
| 6:00-7:00 | `sigma_err` maps (and log-space rain error) | Fuzz test (~60 shocks) + summary | Stippling, impact cards (probability shifts, crop stress) | Fuzz pass rate known |
| 7:00-8:00 | Eval tables by lead for the brief | Lab server: meta, windows, verdict, fuzz | Limits verdict panel | Live verdict works |
| 8:00-9:00 | Natural-experiment full plot | Lab: natural-experiment endpoint, then sensitivity (cut first if late) | Validation tab, Timeline Prime, sensitivity overlay, polish | All features in |
| 9:00-10:00 | Brief page 1 figures: light cone, variance ratio by lead, fuzz heatmap | `make judge` (offline, read-only, 4 CPUs); `make demo` | README, screenshots, About/model card, brief page 2 | **Feature freeze** |
| 10:00-11:00 | Q&A drill; fix only what tests flag | Clean-clone run: serve + validator + scan; tag `v1.0` | Brief to PDF (2 pages) | **Gate 4**: brief is 2 pages |
| 11:00-12:00 | Demo rehearsal x2 | Final push before T+11:30 | Backup demo video | **Submit by 11:30** |

## Communication rhythm
- Every hour on the hour: 3-minute stand-up. Each person says: done, next, blocked. Update `docs/STATUS.md`.
- Blockers longer than 15 minutes are escalated immediately.
- Merges to `main` only with CI green.

## Branching
- `main` is always submittable after v0.1.
- Short-lived branches: `p1/<topic>`, `p2/<topic>`, `p3/<topic>`, merged by the owner after CI.
- Tags: `v0.1` (ridge), `v0.2` (full calibrated model), `v1.0` (final).

## Hand-offs between lanes
| From → To | What | When |
| --- | --- | --- |
| P1 → P2 | `artifacts/nn.pt` + `nn_config.json`, rollout function in `wethrfork/model.py` | T+4:00 (v0), T+5:00 (final) |
| P2 → P3 | Judge server running on the LAN or same laptop with CORS | T+3:00 |
| P2 → P3 | Lab endpoints `/meta`, `/windows`, `/verdict` | T+7:30 |
| P1 → P3 | `sigma_err.npy` (via lab `/meta`) | T+7:00 |
| P1/P2 → P3 | Figures and numbers for the brief | T+9:30 |

## Laptop layout
- Laptop A (RTX 4050): P1 trains; also runs the judge server for P3 during the day.
- Laptop B: P2 server, evaluation, lab.
- Laptop C: P3 dashboard. Final demo laptop: A or C with everything installed (decide by T+9:00).
