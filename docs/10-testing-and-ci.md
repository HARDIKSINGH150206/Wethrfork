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
