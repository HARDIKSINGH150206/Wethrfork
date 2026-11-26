# CODEX.md: Codex guide for Wethrfork

Codex reads `AGENTS.md` automatically. This file adds Codex-specific working rules. **`AGENTS.md` is the source of
truth**; if this file conflicts with it, follow `AGENTS.md`.

---

## 1. Before any task

1. Read `AGENTS.md` sections 0 to 6.
2. Read the current phase in `docs/PHASES.md` and the lane doc for the files you will touch.
3. Read `docs/STATUS.md` for the latest numbers and open issues.

## 2. Task sizing

Codex works best on tasks with a clear input, output and test. Good Codex tasks in this project:

| Task | Files | Acceptance test |
| --- | --- | --- |
| Reproduce the kit climatology | `training/build_climatology.py`, `wethrfork/climatology.py` | `tests/test_climatology_doy.py` passes; max diff vs kit function below 1e-4 |
| Ridge skill head | `training/fit_ridge.py`, `wethrfork/ridge.py` | Self-grade: ridge beats persistence at day 4 on 2021 |
| Light-cone test | `tests/test_lightcone.py` | Reach at most 8 cells per step, Euclidean |
| Clamp and served formula | `wethrfork/blend.py`, `wethrfork/engine.py` | `tests/test_null_shock.py`, `tests/test_validity.py` pass |
| Post-processor fit | `training/fit_postproc.py` | Variance ratio at day 8 at least 0.5 for every channel; CSI skill improves on 2021 |
| Fuzz test | `evaluation/fuzz_gym.py`, `configs/fuzz.yaml` | Writes `runs/fuzz/summary.json` and a heatmap; validity 100% |
| Dashboard component | one file in `dashboard/src/components/` | Storybook-free: renders with mock data in `npm run dev`; typecheck passes |

Avoid giving Codex tasks that span the network design and the calibration at once; split them.

## 3. Mandatory verification per area

| Area touched | Run before declaring done |
| --- | --- |
| `serve.py`, `wethrfork/` | `make test && make scan`; if artifacts exist, start the server and run the validator |
| `training/` | the script on a 30-day subset (`--smoke`), then `make test` |
| `evaluation/` | `make selfgrade --smoke` |
| `dashboard/` | `npm run typecheck && npm run build` |
| `configs/` | `python -m training.check_configs` |

## 4. Codex-specific guardrails

- Never create a Python file other than `serve.py` that contains the route string (slash + simulate, or the quoted
  word). Codex tends to write convenience HTTP clients in tests: use `wethrfork.engine.Engine` instead.
- Never write date literals in Python. If a test needs a date, use a day-of-year integer or read `configs/`.
- Never add dependencies to the serve graph beyond the allowed list in `AGENTS.md` section 1.1.
- Do not reformat files you did not change (keeps diffs reviewable by teammates during the event).
- Keep generated artifacts out of commits unless the task is "export artifacts". Then commit only files under
  `artifacts/` listed in `artifacts/manifest.json`.
- Use deterministic seeds in training (`configs/train.yaml: seed`) so reruns are comparable.

## 5. Output format when finishing a task

Report in this order:
1. What changed (files, one line each).
2. Verification run and its numbers (test counts, scan points, latency, self-grade deltas).
3. Anything skipped or uncertain.
4. Suggested next task from `docs/PHASES.md`.
