# Task runner. One target per task.
.PHONY: install data repro card figures test lint format clean help

help:  ## list targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
	  awk 'BEGIN{FS=":.*?## "}{printf "  %-12s %s\n", $$1, $$2}'

install:  ## editable install + pinned runtime + dev tools (ruff, pytest)
	python -m pip install -e ".[dev]" && python -m pip install -r requirements.txt

data:  ## download the published dataset into data/ (needs a Hugging Face login)
	python scripts/fetch_data.py

repro:  ## regenerate every paper number -> analysis_output/paper_numbers.json
	python scripts/reproduce_paper.py

card:  ## recompute the numbers of the dataset card and compare them with the card
	python scripts/dataset_card_numbers.py --check

figures:  ## redraw the figures in figures/ (run `make repro` first)
	python figures/scripts/coverage_bars.py
	python figures/scripts/unified.py
	python figures/scripts/case1.py
	python experiments/scoring_mode_eval/gen_scoring_mode_figure.py
	python figures/scripts/factorial.py

test:  ## run the test suite
	python -m pytest -q

lint:  ## ruff check
	ruff check src tests scripts

format:  ## auto-format (ruff)
	ruff check --fix src tests scripts

clean:  ## remove caches and generated analysis outputs
	rm -rf .pytest_cache **/__pycache__ analysis_output/*.csv analysis_output/*.json
