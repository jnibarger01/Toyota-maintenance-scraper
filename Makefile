PYTHON  ?= python3
VENV    := .venv
PIP     := $(VENV)/bin/pip
PYTEST  := $(VENV)/bin/python

.PHONY: install test smoke lint run clean

install: ## Create .venv and install requirements
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r toyota-maintenance-scraper/requirements.txt

test: ## Run full unittest suite
	$(VENV)/bin/python -m unittest discover -s toyota-maintenance-scraper/tests -v

smoke: ## Quick offline smoke test
	$(VENV)/bin/python main.py --smoke-test --offline --no-resume --output-dir output_ci

lint: ## Syntax-check all Python files with py_compile
	find toyota-maintenance-scraper -name "*.py" -not -path "*/__pycache__/*" \
		-print0 | xargs -0 $(VENV)/bin/python -m py_compile
	$(VENV)/bin/python -m py_compile main.py
	@echo "Lint OK"

run: ## Full live scrape (makes network calls)
	$(VENV)/bin/python main.py

clean: ## Remove output dirs and __pycache__
	rm -rf output/ output_test/ output_ci/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
