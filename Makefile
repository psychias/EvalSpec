# Task runner. One target per task.
#   make repro PYTHON=.venv/bin/python     use another interpreter
#   make repro EVALSPEC_DATA=/path/to/data  use another copy of the dataset
PYTHON ?= python
export EVALSPEC_DATA

.PHONY: install data repro card figures test lint format clean help

help:  ## list targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
	  awk 'BEGIN{FS=":.*?## "}{printf "  %-12s %s\n", $$1, $$2}'

install:  ## editable install + pinned runtime + dev tools (ruff, pytest)
	$(PYTHON) -m pip install -e ".[dev]" && $(PYTHON) -m pip install -r requirements.txt

data:  ## download the published dataset into data/ (no account needed)
	$(PYTHON) scripts/fetch_data.py

repro:  ## regenerate every paper number -> analysis_output/paper_numbers.json
	$(PYTHON) scripts/reproduce_paper.py

card:  ## recompute the numbers of the dataset card and compare them with the card
	$(PYTHON) scripts/dataset_card_numbers.py --check

figures:  ## redraw the figures in figures/ (run `make repro` first)
	$(PYTHON) figures/scripts/coverage_bars.py
	$(PYTHON) figures/scripts/case_studies.py
	$(PYTHON) figures/scripts/parser_flow.py
	$(PYTHON) experiments/scoring_mode_eval/draw_scoring_mode_figure.py
	$(PYTHON) figures/scripts/factorial.py

test:  ## run the test suite
	$(PYTHON) -m pytest -q

lint:  ## ruff check
	ruff check src tests scripts

format:  ## auto-format (ruff)
	ruff check --fix src tests scripts

clean:  ## remove caches and generated analysis outputs
	rm -rf .pytest_cache **/__pycache__ analysis_output/*.csv analysis_output/*.json
