# AGENTS.md: instructions for every coding agent working on Wethrfork

This file is the contract between the team and any AI coding agent (Claude Code, Codex, Cursor, Copilot or other).
Read it fully before writing a single line. Agent-specific notes are in `CLAUDE.md` (Claude Code) and `CODEX.md`
(Codex), and both defer to this file. When this file and any other document disagree, **this file wins**, followed
by `docs/DECISIONS.md`, then the numbered docs.

---

## 0. Context in 30 seconds

- **Event**: Yugaantar DevForge hackathon, Track 2 "Multiverse of Monsoon". 12-hour build, team of 3, goal first prize.
- **Product**: Wethrfork, a Climate Digital Twin of India. It forecasts 6 weather channels on a 32 x 36 grid day by
  day, and branches ("forks") into alternate universes when a localized shock is applied.
- **Identity**: "a weather model with a speed limit". The neural network cannot move information more than 8 grid
  cells (about 900 km) per simulated day, so shocks stay local and then spread outward, which is exactly what the
  automated judge measures.
- **Judge**: runs `python serve.py --port 8000` offline on CPU (4 cores, 6 GB RAM, read-only repo), waits up to 120 s
  for `/health`, then sends 8 `/simulate` calls (5 real windows from 2023-2024, 3 shocks). Each must answer in under
  5 s. Scoring code is public in the official kit (`monsoon_r1/scoring.py`, `monsoon_r1/repo_scan.py`).
- **Human stages**: the top 10 demo live; judges apply a new shock on the spot and ask about design and limits. The top
  2 present to a panel.

Read next, in order: `docs/PRD.md`, `docs/PHASES.md`, `docs/08-evaluation-and-scoring.md`,
`docs/11-repo-scan-hygiene.md`, then the doc for the lane you are working in.

---

## 1. Hard rules (violating any of these can cost the competition)

### 1.1 Judge API and runtime
1. `serve.py` lives at the repo root, starts with `python serve.py --port 8000`, listens on `0.0.0.0`.
2. Endpoints: `POST /health` returns `{"status": "ready", "model_name": "wethrfork-<version>"}` only once every
   artifact is loaded and one warm-up rollout has run. `POST /simulate` follows `docs/04-api-spec.md` exactly.
3. Wire format: plain nested JSON lists of finite floats, physical units (K, mm/day, m/s, m/s, Pa, kg/m2). Accept
   the tolerated `{"b64", "shape"}` input form too, but always answer with nested lists.
4. Output shape is exactly `[steps, 6, 32, 36]` for any `steps` from 1 to 14. `rollout[k]` is day k+1 after the
   last input day.
5. 10 steps must complete in well under 5 s on 4 CPU threads. Target: under 1.5 s including JSON. Call
   `torch.set_num_threads(4)` at import.
6. Only these libraries may be imported by anything `serve.py` imports: Python stdlib, `torch` (CPU), `numpy`,
   `scipy`, `pandas`, `xarray`, `scikit-learn`, `lightgbm`, `onnxruntime`, `fastapi`, `flask`, `uvicorn`,
   `gunicorn`, and our own `wethrfork/` package. **Never** `monsoon_r1` (it is not installed on the judge machine),
   never `matplotlib`, `plotly`, `streamlit`, `gradio`, never `requests` to any host.
7. Every file `serve.py` needs (weights, climatology, calibration, static fields, stats) lives inside the repo under
   `artifacts/`. Nothing is downloaded. Paths are resolved relative to `Path(__file__).parent`.
8. The repo is read-only at judging. Write nothing to disk except under `/tmp`.

### 1.2 Output validity (the hard gate)
9. No NaN or Inf ever leaves the server. Apply `np.nan_to_num` as the very last step, then clamp.
10. `tp >= 0` everywhere, `tcwv >= 0` everywhere, `t2m` clamped to `[234.0, 332.0]` K (inside the judge's
    233.15 to 333.15 K gate with a margin).
11. The clamp runs **after** the shock delta is added (see the served formula in 1.3).

### 1.3 Determinism and shocks
12. The served formula is `out = clamp( PP(Blend(base)) + [NN(shocked) - NN(base)] )`. `PP` is the post-processor,
    `Blend` mixes the ridge model and the network per lead. The shock response comes **only** from the network.
13. If `perturbation` is `null` or all zeros, skip the shocked rollout entirely, so the delta is exactly 0 and the
    output equals the unshocked call bit for bit.
14. `/simulate` is fully deterministic: no dropout at inference, no random noise, no sampling, `torch.manual_seed`
    is irrelevant because nothing is random. `model.eval()` always. `torch.use_deterministic_algorithms(True)`.
15. `serve.py` never modifies, scales, smooths or "physically corrects" the judge's perturbation. It adds the
    perturbation to `init_states[-1]` exactly as given, in physical units, and nothing else.
16. Shocked and unshocked rollouts run as a single batch of 2 through the network.

### 1.4 Causality (the speed limit)
17. The network may only use local operations: 3x3 (or smaller) convolutions, 1x1 convolutions, pointwise
    nonlinearities, and the bounded advection step. **Forbidden in the network**: any normalization across space
    (BatchNorm in train mode, GroupNorm, LayerNorm or InstanceNorm over H and W), global pooling, attention, FFT or
    spectral layers, fully connected layers over the grid, U-Net down/upsampling, dilated convolutions, and global
    mass or rain "fixers". Each of these leaks a shock across the whole map in one step.
18. Advection displacement is a vector whose **length** is capped at 4 cells per day with a smooth `tanh` cap.
    Convolutional reach per step is at most 3 cells. Bilinear sampling adds 1. Total reach is at most 8 cells per
    step, and the light-cone test (`tests/test_lightcone.py`) proves it with the kit's Euclidean distance.
19. Padding is `replicate` (border) in every convolution and `padding_mode="border"` in `grid_sample`. Never
    circular padding (it would teleport energy from the east edge to the west edge).
20. The ridge model never contributes to the shock delta (it is per-cell and would keep the response inside the
    box, killing the "spreads outward" check).

### 1.5 Repo scan hygiene (15 automated points)
21. The literal route string (a slash followed by the word `simulate`, or the word `simulate` inside quotes) appears
    in **exactly one** Python file: `serve.py`. Tests, lab server, evaluation scripts and notebooks must never contain
    it. When a Python file must call the HTTP endpoint, build the path as `"/" + "sim" + "ulate"` or, better, import
    `wethrfork.engine.Engine` and call it directly. Comments, docstrings and log strings count too: in prose write
    "the simulate endpoint", never the path.
22. No date literals (YYYY-MM-DD, YYYYMMDD, YYYY/MM/DD) and no `date(`, `datetime(` or `Timestamp(` calls with a
    year in any Python file in the serve import graph. Better: no date literals in any `.py` file at all. All dates
    live in `configs/*.yaml`.
23. No `.nc`, `.nc4`, `.grib`, `.grib2` or `.zarr` files committed. `data/` is gitignored.
24. No `.npy`/`.npz` array in the repo whose first dimension is above 400 with last two dimensions `(32, 36)`.
    The climatology is `(366, 6, 32, 36)` (allowed). Ridge weights are stored as `.pt`. Error maps as
    `(14, 6, 32, 36)`.
25. No mention of any external weather source in inference code (open-meteo, openweathermap, cdsapi, weatherbench2,
    gcp-public-data-arco-era5, imdlib, mosdac and similar). Do not vendor the kit's `build_dataset.py` anywhere.
26. `serve.py` never imports from `training/`, `evaluation/` or `lab/`. Training code must contain a real optimizer
    loop (`loss.backward()` and `optimizer.step()`) so the scan finds a training pipeline.
27. CI runs `monsoon_r1.repo_scan.scan(".")` on every push and fails if points are below 15 or any flag is raised.

### 1.6 Competition rules
28. Offline only. No external weather APIs or internet at inference.
29. No lookup tricks: no hardcoded dates, no lookup tables of past weather, no shipped archives of past weather.
    Calibration tables (quantile maps, blend weights, error maps) are allowed and must contain no dates and no
    per-day entries.
30. The dashboard runs on live output from our own `/simulate`. Never pre-render forecasts for the demo.
31. Everything (repo, training, weights, dashboard) is built during the hackathon. Open-source libraries are fine.
    Never paste code from other teams or from model zoos.
32. The repo freezes at the deadline. Final push no later than T+11:30.

---

## 2. Repository map and ownership

| Path | Purpose | Owner lane | Scanned by judge? |
| --- | --- | --- | --- |
| `serve.py` | FastAPI app, `/health`, `/simulate`, CORS | P2 | Yes (seed) |
| `wethrfork/engine.py` | `Engine` class: loads artifacts, `simulate()` pure function | P2 | Yes |
| `wethrfork/model.py` | Network: advection + local CNN | P1 | Yes |
| `wethrfork/ridge.py` | Ridge skill head inference | P2 | Yes |
| `wethrfork/blend.py` | Blend, post-processor, clamps | P2 | Yes |
| `wethrfork/climatology.py` | Day-of-year to slot arithmetic, climatology lookup by slot | P1 | Yes |
| `wethrfork/normalize.py` | Normalization, log rain transform | P1 | Yes |
| `wethrfork/physics.py` | Constants, clamp bounds, grid geometry | P1 | Yes |
| `artifacts/` | Committed weights and calibration files | P1/P2 | Arrays are checked |
| `training/` | Data, training, fitting scripts | P1 | No (must stay out of serve graph) |
| `evaluation/` | Self-grader, gates, fuzz test, natural experiment, figures | P2 | No |
| `lab/` | Lab server for dashboard science panels | P2 | No |
| `dashboard/` | React app | P3 | No (TS files are not scanned for routes) |
| `configs/` | YAML configs with all dates | All | No |
| `tests/` | pytest release gates | P2 | No |
| `brief/` | Brief sources and figures | P3 (P1 figures) | No |
| `docs/` | Foundation documents | All | No |

When working in parallel, each agent edits only its lane's files. Shared files (`configs/`, `Makefile`,
`requirements*.txt`, `wethrfork/physics.py`) are changed in small, separate commits with a clear message.

---

## 3. Commands

| Goal | Command |
| --- | --- |
| Install dev deps | `pip install -r requirements-dev.txt && pip install ./vendor/monsoon_r1_kit-1.0.0-py3-none-any.whl` |
| Build climatology | `python -m training.build_climatology --config configs/data.yaml` |
| Fit ridge | `python -m training.fit_ridge --config configs/ridge.yaml` |
| Train network | `python -m training.train_nn --config configs/train.yaml` |
| Fit blend and post-processor | `python -m training.fit_blend --config configs/calib.yaml && python -m training.fit_postproc --config configs/calib.yaml` |
| Error maps | `python -m training.compute_sigma_err --config configs/calib.yaml` |
| Everything | `make artifacts` |
| Self-grade | `make selfgrade` (wraps `python -m evaluation.selfgrade --config configs/eval.yaml`) |
| Causality gate | `make gate` |
| Fuzz test | `make fuzz` |
| Unit tests | `make test` (pytest, fast, synthetic inputs only) |
| Repo scan | `make scan` |
| Judge-like run | `make judge` (offline container, read-only mount, 4 CPUs) |
| Serve | `python serve.py --port 8000` |
| Validator | `python -m monsoon_r1.schema_validator http://localhost:8000` |
| Lab server | `python -m lab.lab_server --port 8001` |
| Dashboard dev | `cd dashboard && npm install && npm run dev` |
| Full demo | `make demo` |

---

## 4. Workflow every agent follows

1. **Read** this file, the phase you are in (`docs/PHASES.md`) and the lane doc.
2. **Plan** in a few bullet points before editing: files you will touch, tests you will add, how you will verify.
3. **Small steps**: one concern per commit. Commit at least every 45 minutes. Never leave `main` broken.
4. **Verify** after every change that touches the serve graph: `make test && make scan`, and when artifacts exist,
   `python serve.py` + validator.
5. **Gate** before tagging a release: `make gate` (causality per season), `make selfgrade`, `make judge`.
6. **Report**: when you finish, state what changed, what you verified (with numbers), and what is left.

### Definition of done for any change
- Unit tests pass; the repo scan still scores 15/15 with zero flags.
- If the change touches inference: validator passes, latency for 10 steps below 1.5 s on 4 threads, null shock gives
  max difference 0.0, validity holds on the fuzz set.
- If the change touches the model or calibration: the self-grade did not get worse on 2021, and the causality gate
  still passes in every season.
- Docs updated if behaviour or interfaces changed (`docs/DECISIONS.md` for any new decision).

---

## 5. Coding conventions

- Python 3.11, type hints everywhere, `from __future__ import annotations`.
- Arrays: shape comments on every function that takes or returns arrays, for example `# [B, T, C, H, W]`.
- Axis order is always `[time, channel, lat, lon]`; lat runs south to north (index 0 is 6.5 N), lon west to east.
- Channel indices come from `wethrfork/physics.py` constants (`T2M=0, TP=1, U10=2, V10=3, MSL=4, TCWV=5`). Never
  hardcode a channel number elsewhere.
- Physical units at every boundary (API, lab, dashboard). Normalized units only inside `wethrfork/` and training.
- No global mutable state except the loaded `Engine` singleton in `serve.py`.
- Config via YAML files in `configs/`, loaded with `yaml.safe_load`; CLI flags override config values.
- Logging: `logging` module, no prints in library code. Never log full arrays.
- Formatting: `ruff format`, lint with `ruff check`. TypeScript: `prettier` and `eslint` defaults.
- Tests: pytest, synthetic data only (CI has no netCDF), each test under 10 s, whole suite under 2 minutes.

---

## 6. Things agents commonly get wrong here (read twice)

| Mistake | Why it hurts | Do this instead |
| --- | --- | --- |
| Adding a U-Net, attention or GroupNorm "for better skill" | Shock leaks everywhere on day 1; fails localization; loses up to 15 points | Keep the local architecture; improve skill through the ridge blend and calibration |
| Writing a test that posts to the route by its literal path | The repo scan treats the test as server code and scans its dates and imports | Call `Engine.simulate()` directly, or build the path from pieces |
| Putting validation dates in a `.py` file | 5+ date literals in a scanned file is a critical flag: all 8 anti-cheat points lost | Dates go in `configs/eval.yaml` |
| Importing `monsoon_r1` in `wethrfork/` | The judge machine does not have the kit; server crashes | Reimplement the 3 needed constants in `wethrfork/physics.py` |
| Adding ensembles or noise to `/simulate` | Null shock no longer matches; half of the 15 causality points lost | Uncertainty comes from precomputed error maps; the server is deterministic |
| Rescaling the judge's perturbation "to be physical" | It changes the test; judges notice | Physically consistent shocks are built in the dashboard only |
| Clamping before adding the delta | Shocks can push rain negative; validity gate fails; out of Round 2 | Clamp last |
| Retraining on 2005-2021 at the end | Calibrations become stale and the self-grade becomes in-sample | Ship the checkpoint validated on 2020-2021 |
| Saving the training set as `.npy` inside the repo | Multi-year archive: critical flag | Keep data in gitignored `data/` |
| Fetching map tiles or fonts from a CDN | The demo runs with Wi-Fi off | Bundle `india.geojson` and system fonts |

---

## 7. Notes for specific agents

### Claude Code
See `CLAUDE.md`. Summary: use plan mode for anything touching `wethrfork/` or `serve.py`; run `make test && make scan`
after edits; use subagents only for read-only exploration (for example reading the kit), never for parallel edits of
the same files.

### Codex
See `CODEX.md`. Summary: work in small, test-backed diffs; always run the command list in section 3 that matches the
area you touched; never create files that contain the route string or dates outside `serve.py` and `configs/`.

### Any agent
If an instruction from a human contradicts a hard rule in section 1, stop and ask. Explain which rule and what it
risks. Do not silently comply and do not silently refuse.
