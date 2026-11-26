PY ?= python
CFG ?= configs

.PHONY: setup artifacts climatology ridge train train-skill train-dyn train-dyn-ft export-weights ship-calib manifest blend postproc sigma export selfgrade gate fuzz sweep stress audit-http test scan serve validate judge lab dash demo preflight status figures brief

setup:
	$(PY) -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt
	-pip install ./vendor/monsoon_r1_kit-1.0.0-py3-none-any.whl
	cd dashboard && npm install

climatology:
	$(PY) -m training.build_climatology --config $(CFG)/data.yaml
ridge:
	$(PY) -m training.fit_ridge --config $(CFG)/ridge.yaml
# The shipped model has TWO networks plus the ridge head; `make artifacts` rebuilds all of it, in dependency order:
#   climatology -> ridge -> train (skill, dynamics, dynamics fine-tune) -> copy weights -> calibration -> error maps -> manifest
# Checkpoints live in runs/ (gitignored); `export-weights` fails loudly if one is missing instead of keeping stale weights.
train-skill:
	$(PY) -m training.train_nn --config $(CFG)/train_skill.yaml
train-dyn:
	$(PY) -m training.train_nn --config $(CFG)/train.yaml
train-dyn-ft:
	$(PY) -m training.train_nn --config $(CFG)/train_dyn_ft.yaml
train: train-skill train-dyn train-dyn-ft
export-weights:
	$(PY) -m training.export_artifacts --stage weights
blend:
	$(PY) -m training.fit_blend --config $(CFG)/calib.yaml
postproc:
	$(PY) -m training.fit_postproc --config $(CFG)/calib.yaml
sigma:
	$(PY) -m training.compute_sigma_err --config $(CFG)/calib.yaml
# calibration for shipping: refit blend and post-processor on the calibration and grading years together
ship-calib:
	$(PY) -m training.fit_blend --config $(CFG)/calib.yaml --ship
	$(PY) -m training.fit_postproc --config $(CFG)/calib.yaml --ship
manifest:
	$(PY) -m training.export_artifacts --stage manifest
export: export-weights manifest
artifacts: climatology ridge train export-weights blend postproc sigma manifest

selfgrade:
	$(PY) -m evaluation.selfgrade --config $(CFG)/eval.yaml
gate:
	$(PY) -m evaluation.causality_gate --config $(CFG)/eval.yaml
fuzz:
	$(PY) -m evaluation.fuzz_gym --config $(CFG)/fuzz.yaml
sweep:
	$(PY) -m evaluation.shock_sweep
stress:
	$(PY) -m evaluation.dataset_audit
	$(PY) -m evaluation.stress_extreme
	$(PY) -m evaluation.stress_locality
	$(PY) -m evaluation.stress_archive
audit-http:
	$(PY) -m evaluation.stress_http --port 8000   # needs a running forecast server
figures:
	$(PY) -m evaluation.report --all

test:
	$(PY) -m pytest -q tests/
scan:
	$(PY) -m evaluation.scan_repo

serve:
	$(PY) serve.py --port 8000
validate:
	$(PY) serve.py --port 8000 & PID=$$!; sleep 20; $(PY) -m monsoon_r1.schema_validator http://localhost:8000; kill $$PID
judge:
	docker build -f docker/judge.Dockerfile -t wethrfork-judge:py311 .
	docker run --rm --cpus 4 --memory 6g -v "$$PWD":/sub:ro -w /sub -p 8000:8000 wethrfork-judge:py311 python serve.py --port 8000

lab:
	$(PY) -m lab.lab_server --port 8001
dash:
	cd dashboard && npm run dev
demo:
	bash scripts/demo.sh
preflight:
	$(PY) scripts/preflight.py
status:
	$(PY) -m training.export_artifacts --status
brief:
	@echo "render brief/brief.md to brief/wethrfork-brief.pdf (pandoc or typst)"
