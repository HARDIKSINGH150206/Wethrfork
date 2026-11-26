# 11. Repo scan hygiene: never lose a point to the static scanner

The judge's `monsoon_r1/repo_scan.py` reads our repo without executing it and awards 15 points (anti-cheat 8, code
health 7). This document explains exactly how it works and what we do about each rule.

---

## 1. How the scanner finds "inference files"
1. **Seeds**: every `.py` file (outside `.git`, `node_modules`, `__pycache__`, `.venv`, `venv`, `env`,
   `.ipynb_checkpoints`, `dist`, `build`) whose text matches
   `ROUTE_RE = [/'"]simulate['"]|/simulate\b`.
   That is: a quote or slash, then the word, then a quote; or a slash followed by the word. **Any** Python file,
   including tests, clients, notebooks (`.ipynb` code cells too) and scripts.
2. **Closure**: every local module imported by a seed, transitively. Imports resolve against the importing file's
   folder and the repo root (`import a.b`, `from a import b`, relative imports).
3. All checks marked "inference code" apply to this set.

Consequence: if `tests/test_api.py` contains the route path and imports `training.data`, then `training/data.py` becomes
an inference file, its dates get scanned, and it stops counting as training code.

**Our rule**: the route string exists in `serve.py` only. `tests/test_route_string.py` enforces it. The scanner reads raw
text, so comments, docstrings and log messages count too: write "the simulate endpoint" in prose, never the path.
Method names such as `Engine.simulate(` are safe (no slash or quote before the word).

## 2. Anti-cheat checks (8 points; any critical flag = 0 of 8; each warning = -2)

| Check | Applies to | Level | Our rule |
| --- | --- | --- | --- |
| No file serves the route | repo | critical | `serve.py` exists with the route |
| External weather or data source strings (open-meteo, openweathermap, api.weather, weatherapi, visualcrossing, tomorrow.io, api.met.no, meteomatics, worldweatheronline, power.larc.nasa, cdsapi, cds.climate.copernicus, gcp-public-data-arco-era5, weatherbench2, mosdac, noaa-gfs, imdlib, nomads.ncep, mausam.imd) | inference files | critical | Never write these anywhere in `wethrfork/` or `serve.py`; never vendor the kit's `build_dataset.py` |
| Date literals (`19xx` or `20xx` followed by month and day, with or without `-` or `/`) | inference files | 5+ critical, 3-4 warning | No date literals in any `.py` file; dates in YAML |
| `date(`, `datetime(` or `Timestamp(` called with a literal year | inference files | critical | Never in inference code; we never import `datetime` in `wethrfork/` |
| `.npy` or `.npz` array with first dim > 400 and last dims `(32, 36)` | whole repo | critical | Climatology is 366 long; ridge stored as `.pt`; error maps are 14 long; no caches committed |
| `.nc`, `.nc4`, `.grib`, `.grib2`, `.zarr` files | whole repo | warning | `data/` gitignored; never commit sample data |
| No checkpoint: no file with a weight extension (`.pt .pth .ckpt .safetensors .onnx .h5 .keras .joblib .pkl .pickle .npz .msgpack .bin`) larger than 1 KB, and no Hugging Face link | whole repo | critical | `artifacts/nn.pt` and `artifacts/ridge.pt` committed |

Beware of numbers that look like dates: `20210531` in a constant, or `2020-12-31` in a docstring inside `wethrfork/`.
Even comments count (the scanner reads raw text).

## 3. Code health checks (7 points)

| Check | Points | How it is detected | Our rule |
| --- | --- | --- | --- |
| Training pipeline | 3 | a code file **not** in the inference set containing `.backward(`, `optimizer.step`, `.fit(`, `model.fit`, `train_step`, `loss.backward`, `lightning` or `Trainer(` | `training/train_nn.py` has `loss.backward()` and `optimizer.step()`; `serve.py` never imports it |
| Server separate from UI | 2 | no inference file contains `streamlit`, `gradio`, `dash(`, `plotly`, `matplotlib.pyplot` | No plotting imports in `wethrfork/` or `serve.py`; figures live in `evaluation/report.py` |
| Frontend present | 1 | a file named `package.json`, `index.html`, `streamlit_app.py`, `app.js` or `dashboard.py`, or text mentioning streamlit, plotly or leaflet, among the first 400 matching files | `dashboard/package.json` and `dashboard/index.html` |
| README | 0.5 | a file at the repo root starting with `readme` | `README.md` |
| Checkpoint | 0.5 | as above | committed weights |

## 4. Human-judged rules that interact with files
- "No lookup tricks: hardcoded dates, lookup tables or shipped archives of past weather" lead to disqualification.
- Our calibration files are statistics, not weather: blend weights `(14, 6)`, damping `(14, 6)`, rain quantile maps per
  lead (41 points each), error maps `(14, 6, 32, 36)`, climatology `(366, 6, 32, 36)` (the kit's own method).
  None contain dates or per-day entries. The brief says so in one line.
- Demo windows for the dashboard are read at demo time from the gitignored netCDF. Never export them to the repo.
- `dashboard/public/selfgrade.json` holds aggregate numbers only (skill by lead), no fields.

## 5. Self-check commands
```bash
make scan                         # fails on < 15 points or any flag; prints inference_files
pytest tests/test_route_string.py tests/test_no_dates.py tests/test_artifacts.py -q
git ls-files | grep -E '\.(nc|nc4|grib|grib2|zarr)$'   # must print nothing
```
Expected `inference_files`: `serve.py`, `wethrfork/__init__.py`, `wethrfork/engine.py`, `wethrfork/model.py`,
`wethrfork/ridge.py`, `wethrfork/blend.py`, `wethrfork/climatology.py`, `wethrfork/normalize.py`,
`wethrfork/physics.py`, `wethrfork/io.py`. Anything else in that list is a bug.
