PYTHON ?= .venv/bin/python
PIP ?= .venv/bin/pip

.PHONY: help venv install doctor init list-sources fetch pipeline pipeline-skip test clean-output

help:
	@echo "Available commands:"
	@echo "  make venv           Create the project virtual environment"
	@echo "  make install        Install Python dependencies"
	@echo "  make doctor         Validate repository setup"
	@echo "  make init           Initialize state files"
	@echo "  make list-sources   Show configured sources"
	@echo "  make fetch          Fetch RootData raw cache"
	@echo "  make pipeline       Run the full pipeline"
	@echo "  make pipeline-skip  Rebuild outputs from existing cache"
	@echo "  make test           Run lightweight automated tests"
	@echo "  make clean-output   Remove generated output artifacts"

venv:
	python3 -m venv .venv

install:
	$(PIP) install -r requirements.txt

doctor:
	$(PYTHON) scripts/doctor.py

init:
	$(PYTHON) scripts/init.py

list-sources:
	$(PYTHON) scripts/cli.py list-sources

fetch:
	$(PYTHON) scripts/cli.py fetch --source rootdata_projects

pipeline:
	$(PYTHON) scripts/cli.py run --source rootdata_projects

pipeline-skip:
	$(PYTHON) scripts/cli.py run --source rootdata_projects --skip-fetch

test:
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py'

clean-output:
	rm -rf output/normalized output/merged output/scored output/context output/briefs output/project-theses output/project-dossiers.json output/ranked-opportunities.md output/raw-opportunities.md
