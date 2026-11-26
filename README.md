# Wethrfork: the monsoon toolkit

> **A weather model with a speed limit.**
> A physics-aware Climate Digital Twin of India that rolls the monsoon forward day by day, forks it into alternate
> universes when you shock it, with a locality bound that is tested on the code and a live audit of every shock.

Wethrfork is our entry for **Yugaantar DevForge, Track 2: "Multiverse of Monsoon"**. This repository holds:

- the **inference server** the judges run (`serve.py`, the only file that defines the API route),
- the **model package** it loads (`wethrfork/`),
- the **training, calibration and evaluation pipelines** (`training/`, `evaluation/`),
- the **lab server** that powers the dashboard's scientific panels (`lab/`),
- the **interactive dashboard** (`dashboard/`, React + Vite + TypeScript),
- the **2-page brief** sources (`brief/`),
- and the **foundation documents** (`docs/`) that describe every decision.

If you are an AI coding agent (Claude Code, Codex or any other), read **`AGENTS.md` first**, then `CLAUDE.md` or
`CODEX.md`, then `docs/PHASES.md`. Nothing in this project should be built without reading those three.

---

## 1. One-minute summary

| Question | Answer |
| --- | --- |
| What does the judge run? | `python serve.py --port 8000`, offline, CPU only, 4 cores, 6 GB RAM, read-only repo |
| What does the API do? | `POST /health` and `POST /simulate`: 3 past days of India's weather in, N future days out, optional shock |
| What is the grid? | 32 x 36 cells of 1 degree, lat 6.5 to 37.5 N, lon 65.5 to 100.5 E |
| What are the channels? | t2m (K), tp (mm/day), u10 (m/s), v10 (m/s), msl (Pa), tcwv (kg/m2), always in that order |
| What is the model? | A **skill head** (per-cell ridge regression + neural network, blended and calibrated) for the forecast, and a **dynamics head** (the neural network alone) for the shock response |
| What is the neural network? | Residual-on-last-day: bounded semi-Lagrangian advection (displacement capped at 4 cells/day) + a local 3x3 CNN (reach 3 cells). Total influence is at most 8 cells (about 900 km) per day |
| Why that design? | The automated judge rewards shocks that stay local on day 1 and spread outward at a bounded speed. Each daily update of the shock-response network is bounded to 8 cells along either axis (about 9.7 diagonally); unit tests check the bound and the judge's own checks pass on every held-out window we tried |
| What makes it stand out? | A bounded, tested locality limit (not a claim of correct physics), a live "limits verdict" panel that runs the official causality checks on any shock a judge applies, natural-experiment validation, and a shock fuzz test |
| Team | 3 people, 12 hours, one RTX 4050 laptop GPU (6 GB) for training |

---

## Current results (v0.2, held-out 2021; calibration fitted on 2020)

| Metric | Value |
| --- | --- |
| Mean RMSE skill vs best of persistence/climatology | 0.135 (full marks at 0.12) |
| Heavy-rain CSI skill | 0.073 |
| Day-8 variance ratio (min over channels) | 0.68 |
| Causality gate (4 seasons x 2 official shocks) | pass, strict thresholds; null shock differs by exactly 0.0 |
| Fuzz test (60 shocks) | 100% valid, 95% causal |
| Repo scan | 15 / 15 |
| 10-step shocked call | about 0.18 s |

Reproduce: `make artifacts` (needs `data/india_climate_train.nc` from the kit release), then `make selfgrade gate fuzz scan`.
The shipped model uses two networks of one architecture (a skill network and a dynamics network, `docs/DECISIONS.md` D34).
Full numbers and open issues: `docs/STATUS.md`.

---

## 2. Quick start (once the code exists)

```bash
# 1. environment (Python 3.11 recommended)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pip install ./vendor/monsoon_r1_kit-1.0.0-py3-none-any.whl   # official kit, dev only, never imported by serve.py

# 2. data (never committed; gitignored)
mkdir -p data && cp /path/to/india_climate_train.nc /path/to/stats.json data/

# 3. build artifacts (climatology, ridge, network, blend, post-processor, error maps)
make artifacts            # runs every step in training/ in order; see docs/09-ml-plan.md

# 4. self-grade with the judge's own scoring code
make selfgrade            # prints a Stage 1 estimate (out-of-sample on 2021)

# 5. run what the judge runs
python serve.py --port 8000
python -m monsoon_r1.schema_validator http://localhost:8000

# 6. run the full demo (server + lab + dashboard, pre-warmed)
make demo
```

---

## 3. Repository map

```
wethrfork/
├── serve.py                 judge entrypoint; the ONLY file containing the API route string
├── wethrfork/               inference package (scanned by the judge's repo scan; keep it clean)
├── artifacts/               committed model files: weights, climatology, calibration, error maps
├── training/                data loading, training and fitting scripts (never imported by serve.py)
├── evaluation/              self-grader, causality gate, fuzz test, natural experiment, brief figures
├── lab/                     lab server for the dashboard (sensitivity, limits verdict, demo windows)
├── dashboard/               React + Vite + TypeScript dashboard
├── configs/                 YAML configs; ALL dates live here, never in .py files
├── tests/                   pytest suite; release gates
├── brief/                   2-page brief sources and figures
├── docs/                    foundation documents (start with docs/PRD.md)
├── data/                    gitignored; india_climate_train.nc and stats.json live here locally
└── .github/workflows/       CI
```

Full detail: `docs/14-folder-structure.md`.

---

## 4. Documents

| File | What it holds |
| --- | --- |
| `AGENTS.md` | Rules and workflow for every coding agent; the single most important file |
| `CLAUDE.md` | Claude Code specifics |
| `CODEX.md` | Codex specifics |
| `docs/PRD.md` | Product requirements: users, goals, scope, success metrics |
| `docs/ARCHITECTURE.md` | System architecture overview |
| `docs/DECISIONS.md` | Every design decision with reasons and rejected alternatives |
| `docs/DEVELOPMENT.md` | Environment, commands, conventions, git workflow |
| `docs/PHASES.md` | Phase-wise development plan with entry and exit gates |
| `docs/01-problem-and-novelty.md` | The problem, the official track spec, what is novel |
| `docs/02-architecture-and-dataflow.md` | Data flow from netCDF to dashboard pixel |
| `docs/03-model-and-physics-spec.md` | Exact model specification and physics |
| `docs/04-api-spec.md` | Judge API and lab API, byte-level |
| `docs/05-demo-golden-path.md` | The live demo script, second by second, with fallbacks |
| `docs/06-frontend-plan.md` | Dashboard specification |
| `docs/07-build-plan-12h.md` | Hour-by-hour plan for 3 people |
| `docs/08-evaluation-and-scoring.md` | How the judge scores, line by line, and how we self-grade |
| `docs/09-ml-plan.md` | Training, fitting and calibration recipes |
| `docs/10-testing-and-ci.md` | Test matrix and CI |
| `docs/11-repo-scan-hygiene.md` | How to never lose a repo-scan point |
| `docs/12-brief-outline.md` | The 2-page brief, panel by panel |
| `docs/13-qa-prep-and-risks.md` | Judge questions, answers, risks and fallbacks |
| `docs/14-folder-structure.md` | Every folder and file, with responsibility and owner |
| `docs/GLOSSARY.md` | Terms used across the project |

---

## 5. Rules we never break

1. `serve.py` runs offline on CPU and answers 10 steps in under 5 seconds.
2. A zero shock returns exactly the unshocked forecast.
3. Rain is never negative; t2m stays inside -40 to +60 C; no NaN or Inf ever leaves the server.
4. No dates, no external weather sources, no plotting libraries, no data archives in anything `serve.py` imports.
5. The route string appears only in `serve.py`.
6. The dashboard always runs on live output from our own `/simulate`.
7. Repo, training, weights and dashboard are built during the hackathon. The repo freezes at the deadline.

## 6. Data licence

`india_climate_train.nc` and `stats.json` contain modified ERA5 reanalysis data (Copernicus Climate Change Service,
Hersbach et al. 2020, via WeatherBench 2, Rasp et al. 2024), licensed CC BY 4.0. The data file is never committed.
