PYTHON ?= .venv/bin/python
PIP ?= .venv/bin/pip

.PHONY: help venv install doctor init fetch pipeline pipeline-skip clean-output

help:
	@echo "Available commands:"
	@echo "  make venv           Create the project virtual environment"
	@echo "  make install        Install Python dependencies"
	@echo "  make doctor         Validate repository setup"
	@echo "  make init           Initialize state files"
	@echo "  make fetch          Fetch RootData raw cache"
	@echo "  make pipeline       Run the full pipeline"
	@echo "  make pipeline-skip  Rebuild outputs from existing cache"
	@echo "  make clean-output   Remove generated output artifacts"

venv:
	python3 -m venv .venv

install:
	$(PIP) install -r requirements.txt

doctor:
	$(PYTHON) scripts/doctor.py

init:
	$(PYTHON) scripts/init.py

fetch:
	$(PYTHON) scripts/fetch-rootdata.py

pipeline:
	$(PYTHON) scripts/cli.py run

pipeline-skip:
	$(PYTHON) scripts/cli.py run --skip-fetch

clean-output:
	rm -rf output/normalized output/merged output/scored output/context output/briefs output/project-theses output/project-dossiers.json output/ranked-opportunities.md output/raw-opportunities.md
