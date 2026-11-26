PY ?= python
CFG ?= configs

.PHONY: setup artifacts climatology ridge train blend postproc sigma export selfgrade gate fuzz test scan serve validate judge lab dash demo status figures brief

setup:
	$(PY) -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt
	-pip install ./vendor/monsoon_r1_kit-1.0.0-py3-none-any.whl
	cd dashboard && npm install

climatology:
	$(PY) -m training.build_climatology --config $(CFG)/data.yaml
ridge:
	$(PY) -m training.fit_ridge --config $(CFG)/ridge.yaml
train:
	$(PY) -m training.train_nn --config $(CFG)/train.yaml
blend:
	$(PY) -m training.fit_blend --config $(CFG)/calib.yaml
postproc:
	$(PY) -m training.fit_postproc --config $(CFG)/calib.yaml
sigma:
	$(PY) -m training.compute_sigma_err --config $(CFG)/calib.yaml
export:
	$(PY) -m training.export_artifacts
artifacts: climatology ridge train blend postproc sigma export

selfgrade:
	$(PY) -m evaluation.selfgrade --config $(CFG)/eval.yaml
gate:
	$(PY) -m evaluation.causality_gate --config $(CFG)/eval.yaml
fuzz:
	$(PY) -m evaluation.fuzz_gym --config $(CFG)/fuzz.yaml
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
status:
	$(PY) -m training.export_artifacts --status
brief:
	@echo "render brief/brief.md to brief/wethrfork-brief.pdf (pandoc or typst)"
