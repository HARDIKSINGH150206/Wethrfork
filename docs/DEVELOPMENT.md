# DEVELOPMENT: environment, commands, conventions

## 1. Environments

| Machine | Purpose | Requirements |
| --- | --- | --- |
| Training laptop (RTX 4050, 6 GB) | Training, fitting | Python 3.11, CUDA PyTorch (2.x), 16 GB RAM recommended |
| Dev laptops | Server, evaluation, lab, dashboard | Python 3.11, CPU PyTorch, Node 20 |
| Judge (simulated) | `make judge` | Docker; image with Python 3.11 + only the allowed libraries |

### 1.1 Python dependencies
`requirements.txt` (what `serve.py` needs; all on the judge's allowed list):
```
torch            # CPU build at judging
numpy
fastapi
uvicorn
```
`requirements-dev.txt`:
```
-r requirements.txt
xarray
netCDF4
pandas
scipy
pyyaml
pytest
ruff
requests
matplotlib       # evaluation/report.py only; never in the serve graph
```
Plus the kit wheel (`vendor/monsoon_r1_kit-1.0.0-py3-none-any.whl`), dev only.

Pin exact versions once installed (`pip freeze > requirements-lock.txt`) and record the judge-compatible torch version
in the README. Save weights as `state_dict` (no pickled classes) so a different torch minor version loads them.

### 1.2 Node
`dashboard/package.json` dependencies: `react`, `react-dom`, `zustand`, `echarts`; dev: `vite`, `typescript`,
`@vitejs/plugin-react`, `eslint`, `prettier`. No map libraries, no UI kits that pull fonts from CDNs.

## 2. Makefile targets

| Target | Does |
| --- | --- |
| `make setup` | create venv, install dev deps and kit wheel, `npm install` in dashboard |
| `make artifacts` | climatology → ridge → train → blend → postproc → sigma_err → export (each step skips if up to date) |
| `make train` | network training only (reads `configs/train.yaml`) |
| `make selfgrade` | `python -m evaluation.selfgrade --config configs/eval.yaml` |
| `make gate` | `python -m evaluation.causality_gate --config configs/eval.yaml` |
| `make fuzz` | `python -m evaluation.fuzz_gym --config configs/fuzz.yaml` |
| `make test` | `pytest -q tests/` |
| `make scan` | `python -m evaluation.scan_repo` (wraps `monsoon_r1.repo_scan.scan`, fails below 15 or on any flag) |
| `make serve` | `python serve.py --port 8000` |
| `make validate` | start server, wait ready, run the kit schema validator, stop server |
| `make judge` | docker run with `--network none --cpus 4 --memory 6g -v $PWD:/sub:ro`, then validator from host |
| `make lab` | `python -m lab.lab_server --port 8001` |
| `make dash` | `cd dashboard && npm run dev` |
| `make demo` | build dashboard, start serve + lab + preview, wait, warm up, open browser |
| `make status` | print artifacts present, their hashes, last self-grade, last gate result |
| `make figures` | `python -m evaluation.report` (brief figures into `brief/figures/`) |
| `make brief` | render `brief/brief.md` (or `.typ`) to `brief/wethrfork-brief.pdf` |

## 3. Conventions

### 3.1 Python
- Package layout: `wethrfork/` (inference), `training/`, `evaluation/`, `lab/` are packages (`__init__.py`).
- Imports: `serve.py` → `wethrfork.*` only. `training`, `evaluation`, `lab` may import `wethrfork`. Nothing imports
  `training` except `training` itself and `evaluation` (for data loading).
- Config: `configs/*.yaml`, loaded once; every script has `--config` and `--smoke` (tiny subset, under 1 minute).
- Arrays: float32 everywhere; `[T, C, H, W]` ordering; lat index 0 is south.
- Naming: `x` physical state, `a` anomaly, `z` normalized anomaly, `F` skill-head forecast, `D` shock delta.
- Randomness: only in training and fuzz generation, seeded from config.

### 3.2 Git
- Commit messages: `<lane>: <imperative summary>` for example `p2: clamp after delta in engine`.
- Never commit: `data/`, `runs/`, `.venv/`, `node_modules/`, `dashboard/dist/`, `*.nc`, large `.npy` outside `artifacts/`.
- `artifacts/` is committed only through `training/export_artifacts.py` so the manifest stays in sync.

### 3.3 `.gitignore` essentials
```
data/
runs/
.venv/
__pycache__/
*.nc
*.nc4
*.grib
*.grib2
*.zarr
node_modules/
dashboard/dist/
.DS_Store
```

### 3.4 Status file
`docs/STATUS.md` is updated at every gate: current tag, artifacts and hashes, self-grade table, gate results, latency,
open issues, owner of each issue.

## 4. Debugging recipes

| Problem | Check |
| --- | --- |
| Validator says not ready | `curl -X POST localhost:8000/health`; check artifact hashes; server log |
| Timeout | `inference_ms` in the response versus wall time; JSON size; torch threads; accidental grad mode |
| Negative rain | clamp order in `engine.py` (must be last) |
| Null shock mismatch | the zero check uses `np.any(pert != 0)`; no randomness; same thread count |
| Scan flag | `make scan` prints `inference_files`; look for unexpected files and their imports |
| Shock leaks far | `pytest tests/test_lightcone.py -s` prints measured reach |
| Shock vanishes | causality gate prints growth ratio per season; check residual path and damping |
| Dashboard CORS error | `serve.py` CORS middleware; correct port in `dashboard/src/config.ts` |
