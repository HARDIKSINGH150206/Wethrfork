# PHASES: phase-wise development plan

Seven phases, from pre-event preparation to submission. Each phase has an owner per lane, deliverables, an exit gate
and ready-to-use prompts for Claude Code or Codex. Times are hours from the start of the hackathon clock (T+0).
The hour-by-hour table for all three people is in `07-build-plan-12h.md`; this file is the gate logic.

Lanes: **P1 Model** (owns the GPU laptop), **P2 Server + science**, **P3 Dashboard + story**.

---

## Phase 0: Preparation (before the event; no repo code)

The rules say the repo, training, weights and dashboard are built during the hackathon. Before the clock starts we
only prepare knowledge and tools.

| Task | Owner |
| --- | --- |
| Download `india_climate_train.nc`, `stats.json` and the kit wheel from the kit Releases page (v1.0.0) | P1 |
| Install Python 3.11, CUDA PyTorch on the RTX 4050 laptop, Node 20 on the dashboard laptop | All |
| Read `AGENTS.md`, `PRD.md`, this file, and your lane doc | All |
| Verify the GPU works: `python -c "import torch; print(torch.cuda.is_available())"` | P1 |
| Prepare a simplified India outline GeoJSON (public domain source) | P3 |
| Agree roles for demo: driver P3, narrator P1, Q&A P2 | All |

Exit: everyone can run Python and Node; data is on the training laptop; docs read.

---

## Phase 1: Foundation (T+0:00 to T+2:00)

**Goal**: a repo that already passes the validator and the repo scan with a placeholder model, plus data loading,
climatology and the dashboard shell.

| Lane | Deliverables |
| --- | --- |
| P1 | `training/data.py`, `training/build_climatology.py` (exact kit method), `artifacts/climatology.npy`, `clim_std.npy`, `static.npy`, `norm.json`; `wethrfork/climatology.py`, `normalize.py`, `physics.py` |
| P2 | Repo skeleton (`14-folder-structure.md`), `serve.py` from the kit template with CORS, `wethrfork/engine.py` skeleton (persistence placeholder), `wethrfork/io.py` (decoder), CI workflow, `Makefile`, tests: contract, null, validity, scan; `training/fit_ridge.py` started |
| P3 | Vite + React + TS app, `MapCanvas` with India outline, mock rollout, channel picker, day scrubber |

**Exit gate (Gate 1, T+2:00)**:
- `python -m monsoon_r1.schema_validator http://localhost:8000` passes (placeholder model).
- `make scan` = 15/15 with zero flags (requires a placeholder checkpoint file > 1 KB in `artifacts/` and a training
  script with an optimizer loop; both exist by now).
- `tests/test_climatology_doy.py` passes.

Prompts:
- "Create the skeleton from docs/14-folder-structure.md. Put the kit template server in serve.py with CORS. Engine
  returns persistence for now. Add CI per docs/10-testing-and-ci.md. Run the validator and the scan."
- "Implement build_climatology.py reproducing monsoon_r1.stats.climatology exactly and save the artifacts listed in
  docs/09-ml-plan.md section 2. Add the doy tests."

---

## Phase 2: Baseline that qualifies (T+2:00 to T+3:00)

**Goal**: v0.1, a valid submission that passes the hard gate on its own.

| Lane | Deliverables |
| --- | --- |
| P1 | `wethrfork/model.py` v0 (local CNN without advection), `training/train_nn.py` stage A running on GPU |
| P2 | Ridge fitted (`artifacts/ridge.pt`), wired into `Engine` with clamps; `evaluation/selfgrade.py` working with the kit |
| P3 | Shock composer UI (box drawing, channel, amplitude), presets wired to `lib/shocks.ts` |

**Exit gate (v0.1 tag, T+3:00)**:
- Ridge-only server: validator passes; self-grade beats persistence at day 4 on 2021.
- Latency for 10 steps under 1.5 s.
- Tag `v0.1` and push. From now on a qualifying submission always exists.

Note: ridge alone responds to shocks only inside the box (no propagation). That is acceptable for v0.1 (the gate needs
only a non-zero localized response to one shock).

---

## Phase 3: The speed-limited network (T+3:00 to T+5:00)

**Goal**: the full network with bounded advection, trained through the unroll curriculum, passing the causality gate.

| Lane | Deliverables |
| --- | --- |
| P1 | Advection step with length cap; `tests/test_lightcone.py`; training stages B (K=4) and C (K=8); checkpoint selection by self-grade among gate-passing checkpoints |
| P2 | `evaluation/causality_gate.py` (per season, both official shocks, stricter thresholds); served formula in `wethrfork/blend.py` + `engine.py` (blend placeholder w = 0.5 until fitted); natural-experiment sanity check (sign and pattern of warm-Bay d_tp and d_msl versus the observed composite) |
| P3 | Live coupling: swap mock for the judge server; Fork view with three synced maps and the ring |

**Exit gate (Gate 2, T+5:00)**:
- Light-cone test passes (reach ≤ 8 cells per step, Euclidean).
- Causality gate passes in all four seasons for both official shocks.
- Null shock difference exactly 0.0.
- Self-grade: blended model beats ridge alone on 2021 mean skill.
- Natural-experiment sanity: model warm-Bay response has the same sign as the observed composite for tp and msl in the
  Bay region. If it does not, stop feature work and fix the model.

If the gate fails at T+5:00: ship the best passing checkpoint or ridge-only, and spend at most one more hour on the
model before moving on.

---

## Phase 4: Calibration and limits (T+5:00 to T+7:00)

**Goal**: maximize Stage 1 points and measure limits.

| Lane | Deliverables |
| --- | --- |
| P1 | Export the chosen checkpoint; `training/compute_sigma_err.py` |
| P2 | `training/fit_blend.py`, `training/fit_postproc.py` (fit 2020, grade 2021, then refit 2020-2021); `evaluation/fuzz_gym.py` (~60 shocks) and its summary |
| P3 | Cyclone preset and track; stippling from `sigma_err`; impact cards (probability shifts) |

**Exit gate (v0.2 tag, T+6:00 to T+7:00)**:
- Out-of-sample 2021 self-grade recorded in `docs/STATUS.md`.
- Anti-blur ratio in [0.5, 2.0] for all channels at day 8.
- Fuzz: validity 100%; causality pass rate recorded.
- All release gates in `08-evaluation-and-scoring.md` section 7 pass. Tag `v0.2` and push.

---

## Phase 5: Science features (T+7:00 to T+9:00)

| Lane | Deliverables |
| --- | --- |
| P1 | Evaluation tables by lead for the brief; natural-experiment full plot |
| P2 | `lab/lab_server.py`: `/meta`, `/windows`, `/verdict`, `/fuzz`, `/natural-experiment`, then `/sensitivity` (cut first if late) |
| P3 | Limits verdict panel, Validation tab, Timeline Prime, sensitivity overlay, polish |

**Exit**: all features in, or cut per the order in `DECISIONS.md` D30.

---

## Phase 6: Hardening and freeze (T+9:00 to T+10:00)

| Lane | Deliverables |
| --- | --- |
| P1 | Brief page 1 figures (light cone, variance ratio by lead, fuzz heatmap) |
| P2 | `make judge`: offline container, read-only mount, 4 CPUs, no network; clean-clone test; `make demo` script |
| P3 | README, screenshots, model card in the About tab, brief page 2 draft |

**Exit (feature freeze, T+10:00)**: no new features after this point. Only fixes for failing tests.

---

## Phase 7: Brief, rehearsal, submission (T+10:00 to T+11:30)

| Lane | Deliverables |
| --- | --- |
| P1 | Q&A drill (`13-qa-prep-and-risks.md`) |
| P2 | Final clean-clone run of server + validator + scan; tag `v1.0`; final push before T+11:30 |
| P3 | Brief to PDF (exactly 2 pages), backup demo video, two full rehearsals |

**Exit (submission, T+11:30)**: repo URL and brief PDF submitted. Buffer of 30 minutes kept for emergencies.

---

## Gate summary

| Gate | Time | Must be true | If not |
| --- | --- | --- | --- |
| Gate 1 | T+2:00 | Validator passes, scan 15/15 | Fix before anything else |
| v0.1 | T+3:00 | Ridge server qualifies | Debug ridge; keep persistence placeholder out of submission |
| Gate 2 | T+5:00 | Network passes light cone, causality (all seasons), null, beats ridge | Ship best passing checkpoint or ridge-only; 1 hour cap on fixes |
| v0.2 | T+7:00 | Calibrated, all release gates | Revert calibration to identity for failing channels |
| Freeze | T+10:00 | Features done | Cut in D30 order |
| Gate 4 | T+11:00 | Brief is 2 pages | Trim page 2 first |
| Submit | T+11:30 | Pushed and submitted | — |
