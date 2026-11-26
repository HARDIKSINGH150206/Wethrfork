# 14. Folder structure: every file, its job, its owner

Legend: **[S]** scanned as inference code by the judge (keep pristine), **[C]** committed, **[G]** gitignored,
owner P1/P2/P3. Files marked "stub" exist in the scaffold as placeholders with a docstring describing the job; the
implementation is written during the hackathon.

```
wethrfork/                                   repo root
├── README.md                          [C] P3  how to train and run (required by the track and the scan)
├── AGENTS.md                          [C] all rules for coding agents
├── CLAUDE.md                          [C] Claude Code guide
├── CODEX.md                           [C] Codex guide
├── LICENSE                            [C]     MIT
├── Makefile                           [C] P2  targets listed in docs/DEVELOPMENT.md
├── requirements.txt                   [C] P2  serve-time deps (judge-allowed only)
├── requirements-dev.txt               [C] P2  training, evaluation, tests
├── .gitignore                         [C] P2
├── serve.py                           [S][C] P2  judge entrypoint; the ONLY file with the route string
│
├── wethrfork/                         inference package
│   ├── __init__.py                    [S][C] version string
│   ├── physics.py                     [S][C] P1  constants: grid, channel indices, clamp bounds, Earth radius, Omega
│   ├── io.py                          [S][C] P2  decode_array (lists or b64), encode helpers
│   ├── climatology.py                 [S][C] P1  doy from sin/cos, slot arithmetic, climatology access
│   ├── normalize.py                   [S][C] P1  anomaly and normalization, log rain transforms
│   ├── model.py                       [S][C] P1  SpeedLimitNet: bounded advection + local CNN; rollout()
│   ├── ridge.py                       [S][C] P2  RidgeHead: apply per-cell, per-lead weights
│   ├── blend.py                       [S][C] P2  blend, damping, rain quantile map, clamp
│   └── engine.py                      [S][C] P2  Engine.load(), Engine.simulate(), simulate_parts(), nn_rollout_torch()
│
├── artifacts/                         [C] committed model files (written only by training/export_artifacts.py)
│   ├── manifest.json                  hashes, sizes, model name, self-grade summary
│   ├── nn.pt, nn_config.json          network weights and hyperparameters
│   ├── ridge.pt                       (14, 6, 21, 32, 36)
│   ├── climatology.npy                (366, 6, 32, 36)
│   ├── clim_std.npy                   (6, 32, 36)
│   ├── static.npy                     (2, 32, 36)
│   ├── stats.json, norm.json          normalization constants
│   ├── postproc.json                  blend weights, damping, rain maps
│   └── sigma_err.npy                  (14, 6, 32, 36) plus sigma_err_logtp.npy (14, 32, 36)
│
├── configs/                           [C] ALL dates live here
│   ├── data.yaml                      data path, splits (train, calib, grade)
│   ├── train.yaml                     network hyperparameters, curriculum, seed
│   ├── ridge.yaml                     lambdas, leads
│   ├── calib.yaml                     blend grid, damping floor, rain bias targets, fit/grade years
│   ├── eval.yaml                      validation windows: systematic, typed, shock_windows (by season)
│   ├── fuzz.yaml                      fuzz shock generator settings, seed
│   └── demo.yaml                      demo windows (ids, labels, dates) read by the lab
│
├── training/                          [C] P1/P2 never imported by serve.py
│   ├── __init__.py
│   ├── data.py                        netCDF loading, caching, sample building, splits
│   ├── build_climatology.py           climatology, clim_std, norms, static
│   ├── fit_ridge.py                   ridge skill head
│   ├── train_nn.py                    network training (loss.backward, optimizer.step)
│   ├── fit_blend.py                   blend weights on calib year
│   ├── fit_postproc.py                damping, rain quantile maps, bias
│   ├── compute_sigma_err.py           per-cell error maps on grade year
│   ├── export_artifacts.py            copy best files into artifacts/, write manifest
│   └── check_configs.py               validates YAML files
│
├── evaluation/                        [C] P2 (P1 for figures) never contains the route string
│   ├── __init__.py
│   ├── windows.py                     build init/truth windows from configs (uses dates from YAML)
│   ├── selfgrade.py                   kit scoring on validation windows
│   ├── causality_gate.py              per-season official shocks, stricter thresholds
│   ├── fuzz_gym.py                    random shocks, validity + causality, summary
│   ├── natural_experiment.py          warm-Bay composites vs model response
│   ├── regions.py                     region → cells mapping for impact cards
│   ├── scan_repo.py                   wraps monsoon_r1.repo_scan.scan with pass/fail
│   └── report.py                      brief figures (matplotlib allowed here)
│
├── lab/                               [C] P2 dashboard science backend (port 8001)
│   ├── __init__.py
│   ├── lab_server.py                  FastAPI: meta, windows, verdict, sensitivity, fuzz, natural-experiment
│   └── windows_store.py               reads data/*.nc per configs/demo.yaml (never ships data)
│
├── dashboard/                         [C] P3 React + Vite + TypeScript (see docs/06-frontend-plan.md)
│   ├── package.json, index.html, vite.config.ts, tsconfig.json
│   ├── public/ (india_outline.geojson, regions.json, selfgrade.json, figures/)
│   └── src/ (api/, lib/, state/, components/, styles/, App.tsx, main.tsx, config.ts)
│
├── tests/                             [C] P2 synthetic-only release gates (docs/10-testing-and-ci.md)
│   ├── conftest.py
│   ├── test_contract.py, test_null_shock.py, test_shock_added.py, test_validity.py
│   ├── test_lightcone.py, test_determinism.py, test_latency.py
│   ├── test_climatology_doy.py, test_no_dates.py, test_route_string.py
│   ├── test_repo_scan.py, test_artifacts.py, test_serve_http.py
│
├── docker/judge.Dockerfile            [C] P2 judge-like image (testing only)
├── scripts/demo.sh                    [C] P2 starts serve + lab + dashboard preview, warms up
├── brief/                             [C] P3 brief.md (or brief.typ), figures/, wethrfork-brief.pdf
├── vendor/                            [C] optional kit wheel (dev only)
├── docs/                              [C] foundation documents + STATUS.md
├── .github/workflows/ci.yml           [C] P2
├── data/                              [G] india_climate_train.nc, stats.json, cache.npz
└── runs/                              [G] training logs, checkpoints, self-grade JSON, fuzz output
```

## Import rules (enforced by review and `make scan`)
```
serve.py ──► wethrfork.*
lab.*    ──► wethrfork.*, monsoon_r1 (kit), evaluation.* (read-only helpers)
evaluation.* ──► wethrfork.*, training.data, monsoon_r1
training.* ──► wethrfork.* (model, normalize, climatology, physics), training.*
wethrfork.* ──► only wethrfork.* + torch, numpy (+ stdlib)
```
