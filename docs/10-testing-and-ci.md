# 10. Testing and CI

Tests are release gates, not decoration. CI has no netCDF data, so unit tests use synthetic inputs; data-dependent
checks (self-grade, causality gate, fuzz) run locally with `make` and their results go into `docs/STATUS.md`.

---

## 1. Test matrix

| Test file | What it proves | Data | Runs in CI |
| --- | --- | --- | --- |
| `tests/test_contract.py` | `Engine.simulate` returns `[steps,6,32,36]` float32 for steps 1, 10, 14; accepts lists and b64 | synthetic | yes |
| `tests/test_null_shock.py` | `perturbation=None` and zeros give identical output (max diff 0.0) | synthetic | yes |
| `tests/test_shock_added.py` | the perturbation is added to the last day exactly (monkeypatch the network to identity) | synthetic | yes |
| `tests/test_validity.py` | finite, tp ≥ 0, tcwv ≥ 0, t2m in range for random and extreme shocks (+20 K, -100% tcwv, -5000 Pa) | synthetic | yes |
| `tests/test_lightcone.py` | perturbing one cell changes nothing beyond Euclidean distance 8k after k steps (network only) | synthetic | yes |
| `tests/test_determinism.py` | two calls give identical output; restart gives identical output | synthetic | yes |
| `tests/test_latency.py` | 10 steps with shock under 1.5 s on 4 threads (skipped if CI runner is slower; logged) | synthetic | yes |
| `tests/test_climatology_doy.py` | doy recovery from sin/cos; slots for Jan 1, Feb 28, Feb 29, Dec 31; matches the kit climatology on a synthetic archive | synthetic | yes |
| `tests/test_no_dates.py` | no `.py` file in the repo matches the kit `DATE_RE` or `DATETIME_CALL` | repo files | yes |
| `tests/test_route_string.py` | exactly one `.py` file (`serve.py`) matches the kit `ROUTE_RE` | repo files | yes |
| `tests/test_repo_scan.py` | `monsoon_r1.repo_scan.scan(".")` returns 15 points and no flags | repo files | yes |
| `tests/test_artifacts.py` | manifest hashes match; array shapes allowed (first dim ≤ 400 for any `(…,32,36)` npy) | artifacts | yes |
| `tests/test_serve_http.py` | starts `serve.py` in a subprocess, polls health, posts one request using a path built from pieces, checks shape | synthetic | yes |

Data-dependent (local, `make`):
| Command | Gate |
| --- | --- |
| `make selfgrade` | mean skill, CSI skill, anti-blur ratios (thresholds in `08-evaluation-and-scoring.md` section 7) |
| `make gate` | per-season causality for both official shocks |
| `make fuzz` | validity 100%, causality pass rate recorded |
| `make validate` | kit schema validator against the running server |
| `make judge` | offline container run + validator |

## 2. Synthetic inputs
`tests/conftest.py` provides:
- `synthetic_state(seed)`: like the kit validator's `_state` (base values t2m 295 K, tp 4, u10 2, v10 1, msl 100500,
  tcwv 35, plus Gaussian noise), with tp made non-negative.
- `engine_fixture`: `Engine.load()` on real artifacts if present, else on tiny randomly initialized test artifacts
  generated in a temp dir (so CI works before training).

## 3. Light-cone test (detail)
```
for k in 1..4:
    x = synthetic window; x2 = x.copy(); x2[-1, c, i0, j0] += 1.0  (normalized units, centre cell)
    y  = network_rollout(x, k);  y2 = network_rollout(x2, k)
    changed = |y2 - y|.max(over channels) > 1e-6
    dist = Euclidean distance from (i0, j0) for every cell
    assert dist[changed].max() <= 8 * k + 1e-6
```
Also run with autograd: gradient of output cell (i, j) at step k with respect to all inputs is zero beyond 8k.
Print the measured reach for each k.

## 4. CI workflow (`.github/workflows/ci.yml`)
```yaml
name: ci
on: [push, pull_request]
jobs:
  python:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install torch --index-url https://download.pytorch.org/whl/cpu
      - run: pip install -r requirements-dev.txt
      - run: pip install ./vendor/monsoon_r1_kit-1.0.0-py3-none-any.whl || pip install "git+https://github.com/OfficialAbhinavSingh/yug-monsoon-kit"
      - run: ruff check .
      - run: pytest -q tests/
  dashboard:
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: dashboard } }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "20" }
      - run: npm ci
      - run: npm run typecheck
      - run: npm run build
```
The CI file is YAML, not Python, so URLs in it never reach the repo scan's Python checks.

## 5. Judge simulation (`make judge`)
```
docker run --rm --network none --cpus 4 --memory 6g \
  -v "$PWD":/sub:ro -w /sub -p 8000:8000 \
  wethrfork-judge:py311 python serve.py --port 8000
# then from the host:
python -m monsoon_r1.schema_validator http://localhost:8000
```
`wethrfork-judge:py311` is built from `docker/judge.Dockerfile` with only the allowed libraries (torch CPU, numpy,
scipy, pandas, xarray, scikit-learn, lightgbm, onnxruntime, fastapi, flask, uvicorn, gunicorn). Note that
`--network none` blocks the port mapping on some systems; if so, run the validator inside the container with
`docker exec`. The Dockerfile is for our testing only; the judge does not need it.

## 6. What "green" means before each tag
| Tag | Required |
| --- | --- |
| v0.1 | CI green, validator, scan 15/15, self-grade beats persistence at day 4 |
| v0.2 | v0.1 + light cone, causality gate all seasons, fuzz validity 100%, release gates in doc 08 |
| v1.0 | v0.2 + `make judge` + clean clone run + brief committed |

## 7. Strict judge testing (D43)

Three layers, each built on the organisers' own code (the kit's client, schema validator and scoring), with our margins
on top. Thresholds live in `configs/rehearsal.yaml` ("judge" = the organisers' limits, "strict" = ours).

| Layer | Command | Needs | What it proves |
| --- | --- | --- | --- |
| Judge-contract tests | `pytest tests/test_judge_contract.py` (part of `make test` and CI) | artifacts only | The server starts from a **read-only** copy of only `serve.py`, `wethrfork/`, `artifacts/`, with the kit, HTTP clients, plotting libraries and `training/`, `evaluation/`, `lab/` made unimportable and HOME read-only; the kit's schema validator passes; `/health` is exactly `{status, model_name}`; steps 1 to 14 give the exact shape, nested lists and a numeric `inference_ms`; base64 and lists give identical answers; null shock and repeated calls identical bit for bit; both official shocks local (near >= 0.75), no teleport, max z <= 4; the serve import graph uses only allowed libraries |
| Judge rehearsal | `make rehearsal` (`--worktree` for uncommitted code) | data + Docker | The organisers' procedure on a clean copy of git HEAD: server in `wethrfork-judge:py311` (Python 3.11, allowed libraries only, no kit) with **no network, read-only repo and root filesystem, 4 CPUs, 6 GB**; a grader container makes 120 calls with the kit's client (5 s deadline, no retries) over every held-out 2021 window, the judge's window types and one window per season, the three official shocks on 10 windows, both wire forms, steps 1 to 14, and the kit validator; scored with `monsoon_r1.scoring`. Also: ready time, peak memory, server log, determinism, container-versus-dev drift, and the day-of-year convention (counted from 0 or 1) |
| Release check | `make release-check` (`make release-check-quick` without data) | data + Docker + npm | lint, all tests, repo scan, preflight, causality gate, all-window sweep, fuzz (validity 100 %, pass rate >= 0.95), self-grade (valid, mean skill >= 0.12, CSI >= 0.05, day-8 ratio in [0.5, 2.0]), rehearsal, dashboard tests and build. Exit 0 only if every step passes; a skipped step gives exit 2 |

**The tests are proven to fail.** Five deliberately broken copies of the server (importing the kit, writing into the
repo at start-up, random noise on the answer, a 2 s delay, negative rain) were each rejected by the rehearsal, and the
four that break the contract also by the judge-contract tests. When you change a gate, re-run such a check: a gate that
cannot fail protects nothing.

Before every tag: `make release-check` must print `RELEASE CHECK: PASS`; paste the summary into `docs/STATUS.md`.

## 8. Browser tests (D44)

`e2e/` drives the real dashboard in Chromium with Playwright: `make e2e` (or `pytest -q e2e/`), and the `browser` job in
CI. Set-up: `pip install -r requirements-e2e.txt && python -m playwright install chromium`, then build the dashboard.
The fixture starts the forecast server, the lab server and the built dashboard (or reuses a running `make demo`).

| Test | What it proves |
| --- | --- |
| map loads | logo, map menu, rail, timeline, legend, coordinates, scale and the control run; the map canvas is not blank |
| layers | each of the five maps switches, renders and has its own legend unit |
| timeline | seek to day +5.5, play advances, back to day +1 |
| menu | collapses to the active map and back |
| preset fork | Warm Bay runs live; the audit shows the four official checks (all pass on real data) and the exposure table |
| difference, swipe, rings | the delta legend, a draggable divider, the ring toggle |
| draw a shock | drag a box, change the amount, fork: a new universe named after the shock |
| bad input | no box: a visible reason and a disabled fork button |
| point forecast | click readout, ten-day table, meteogram, close |
| search, settings | jump to Kolkata; units change; start states listed; servers ready |
| pages | Timeline Prime, Validation and About open and return to the map |
| layouts | 1280 x 720 and a 390 x 844 phone: every control on screen, no horizontal scroll |

Every test also fails on **any page or console error** and on **any request to a host other than our own local
servers** (the dashboard must work offline). Without the dataset (CI) the two start-state requests are answered from
the committed climatology; with it, the real demo windows are used. Proven to fail: an external web font is reported as a
request leaving the machine, and a crash on Play is reported as a page error and as "playback did not advance".
Failure screenshots go to `e2e-artifacts/` (uploaded by CI).
