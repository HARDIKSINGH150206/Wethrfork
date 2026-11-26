# CLAUDE.md: Claude Code guide for Wethrfork

Claude Code loads this file automatically. It is deliberately short on project facts and long on how to work,
because the facts live in `AGENTS.md` and `docs/`. **Read `AGENTS.md` in full at the start of every session.** Its hard
rules override anything here.

---

## 1. Start-of-session checklist

1. Read `AGENTS.md` (rules, repo map, commands, common mistakes).
2. Read `docs/PHASES.md` and find the current phase. If unsure, run `git log --oneline -15` and `make status`
   (prints which artifacts exist and which gates have passed).
3. Read the lane doc for the task:
   - model or training: `docs/03-model-and-physics-spec.md`, `docs/09-ml-plan.md`
   - server or evaluation: `docs/04-api-spec.md`, `docs/08-evaluation-and-scoring.md`, `docs/11-repo-scan-hygiene.md`
   - dashboard: `docs/06-frontend-plan.md`, `docs/05-demo-golden-path.md`
   - brief: `docs/12-brief-outline.md`
4. State a short plan (files, tests, verification) before editing anything in `serve.py` or `wethrfork/`.

## 2. Project facts you must never forget

- Grid 32 x 36, 1 degree, lat 6.5 to 37.5 (index 0 is south), lon 65.5 to 100.5. Channels in order:
  t2m K, tp mm/day, u10 m/s, v10 m/s, msl Pa, tcwv kg/m2.
- `/simulate` input: `init_states [3,6,32,36]` oldest first, `doy_sincos` for the LAST input day (period 365),
  `steps` (1..14, judge uses 10), `perturbation [6,32,36]` delta added to `init_states[-1]`, or null.
- Output: `rollout [steps,6,32,36]` physical units + `inference_ms`.
- Served formula: `clamp(PP(Blend(base)) + [NN(shocked) - NN(base)])`. Zero shock skips the shocked run.
- Network: residual on the last day; bounded advection (vector length at most 4 cells/day, tanh cap) then a local
  CNN (3 cells reach). Total reach at most 8 cells per day. Replicate padding. No global operations.
- Judge machine: CPU only, 4 cores, 6 GB RAM, offline, read-only repo, 5 s per call, 120 s to become ready.
- Route string only in `serve.py`. Dates only in `configs/*.yaml`. Data only in gitignored `data/`.

## 3. How to work in this repo with Claude Code

- **Plan mode** for: any change to the network, the served formula, the clamps, the calibration fitting, or the
  scoring reproduction. These are where silent point losses happen.
- **Direct edits** are fine for: dashboard components, docs, configs, tests, Makefile targets.
- **After every edit that touches `serve.py` or `wethrfork/`**, run:
  ```bash
  make test && make scan
  ```
  and, if artifacts exist:
  ```bash
  python serve.py --port 8000 &   # then
  python -m monsoon_r1.schema_validator http://localhost:8000
  ```
- **Before tagging** (`v0.1`, `v0.2`, `v1.0`): `make gate && make selfgrade && make judge`. Paste the numbers into
  `docs/STATUS.md`.
- **Long jobs** (training, fuzz test): run them in the background and keep working on something else; check the
  log file in `runs/<name>/train.log` rather than polling.
- **Subagents**: use them for read-only exploration (for example "read the kit's scoring.py and list every
  threshold") or for independent review ("critique this diff against AGENTS.md section 1"). Never have two agents
  edit the same file.
- **Never** run `git push --force`, never rewrite history on `main`, never commit `data/`, `runs/`, `.venv/` or
  `node_modules/`.

## 4. Prompts that work well for this project

Use these as starting points; each maps to a phase in `docs/PHASES.md`.

- Phase 1: "Create the repo skeleton from `docs/14-folder-structure.md`. Copy the kit's template server into
  `serve.py`, add CORS and a `/health` that reports not-ready until artifacts load. Add CI from
  `docs/10-testing-and-ci.md`. Run the validator and the repo scan and show me both outputs."
- Phase 2: "Implement `training/build_climatology.py` to reproduce the kit's `stats.climatology` exactly (366 slots,
  15-day circular smoothing). Add `tests/test_climatology_doy.py` covering Dec 31, Feb 29 and Jan 1."
- Phase 2: "Implement the ridge skill head per `docs/09-ml-plan.md` section 3, wire it into `Engine`, and show the
  self-grade versus persistence and climatology at days 1, 4 and 8."
- Phase 3: "Implement `wethrfork/model.py` per `docs/03-model-and-physics-spec.md` section 4, then
  `tests/test_lightcone.py`. Show me the measured reach per step."
- Phase 4: "Implement the served formula and clamps in `wethrfork/blend.py` and `engine.py`. Prove with tests that a
  zero shock gives max difference 0.0 and that every fuzz shock passes `scoring.validity`."
- Phase 5: "Build the Fork view per `docs/06-frontend-plan.md` section 5, calling our `/simulate` live."

## 5. Memory and notes

- Keep running notes in `docs/STATUS.md` (what is done, current self-grade, gate results, open issues). Update it at
  every phase exit. It is the hand-off between people and sessions.
- Add any new decision to `docs/DECISIONS.md` as a new numbered entry. Never edit an old decision; supersede it.

## 6. When you are unsure

Stop and ask the human. Quote the rule from `AGENTS.md` that is in tension, say what you would do and what it risks.
Guessing on anything in `AGENTS.md` section 1 is never acceptable.
