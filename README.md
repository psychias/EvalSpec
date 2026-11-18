# LLM Evaluation Discrepancies And How To Prevent Them

Code, experiment records and paper sources for the paper of the same name, by
Stylianos Psychias, Hanna Hubarava, Juri Opitz, Pius von Däniken and Andrianos
Michail. Accepted to Findings of EACL 2027, to appear.

- EvalSpec site: https://psychias.github.io/EvalSpec/
- Interactive article: https://psychias.github.io/EvalSpec/article.html
- Dataset: https://huggingface.co/datasets/Hermeneia/EvalSpec_Dataset

## Quick start

```bash
git clone https://github.com/psychias/EvalSpec.git && cd EvalSpec
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

huggingface-cli login                 # the dataset is gated: accept its terms on its page first
python scripts/fetch_data.py          # downloads the dataset into data/
python scripts/reproduce_paper.py     # recomputes the paper's numbers
pytest                                # 102 tests
```

`reproduce_paper.py` prints the dataset totals, the metadata coverage and the audit
results, and writes everything to `analysis_output/paper_numbers.json`.

The repository is built around Every Eval Ever (EEE), a JSON schema (v0.2.1) for
LLM evaluation results, and a pipeline that collects published results into it.
The collected dataset has 46,559 records from 12 sources, covering 7,398 models
and 1,954 benchmarks. The sources are public leaderboards, HuggingFace model
cards, Papers With Code, and results extracted by an LLM from 100 arXiv papers.

## What the paper shows

A score such as "MMLU = 68" can be compared across models only if it was
produced the same way each time. Usually it was not. The same model and
benchmark get scored with different harnesses, shot counts, prompt formats,
temperatures and scoring modes (log-likelihood or generation), and these choices
can move a score by more than the gap between two models on a leaderboard. The
paper puts 46,559 published records into one schema, checks which of these
settings each record keeps, and measures how much the settings matter.

### Dataset

| | Records | Models | Benchmarks |
|---|---|---|---|
| Full dataset (12 sources) | 46,559 | 7,398 | 1,954 |
| Leaderboard subset (10 sources) | 28,755 | 5,301 | 174 |
| ArXiv extraction (100 papers) | 17,228 | 1,726 | 1,806 |
| Papers With Code | 576 | 383 | 16 |

### Sources rarely evaluate the same thing

Sources cover almost entirely different model and benchmark pairs. Open LLM
Leaderboard v2 (OLv2) alone has 26,790 records and shares almost no models with
the other sources. Most leaderboards cannot be checked against each other
because they do not measure the same pairs.

### The settings that move scores are the ones least often recorded

Share of records with a documented value for each field:

| Field | Full dataset | Leaderboard subset |
|---|---|---|
| n-shot | 80.5% | 98.0% |
| harness | 63.2% | 93.2% † |
| chain-of-thought | 50.0% | 77.7% |
| prompt template | 14.1% | 0.0% |
| temperature | 3.1% | 0.0% |

† No leaderboard API exposes the harness. The pipeline attaches it from each
platform's documentation. Prompt template and temperature have no coverage at
all in the leaderboard subset.

### Disagreements cannot be traced to a cause

When several sources do report the same model on the same benchmark, the scores
often disagree. Section 5 of the paper works through BBH, GSM8K, TruthfulQA,
Belebele and HellaSwag. With the settings missing from the records, a reader
cannot tell which setting produced the gap. Some agreements between sources
that look independent are one pipeline reported twice: OLv2 and SEA-LION match
to two decimals on Gemma-2-9B BBH.

### Extraction audit

The arXiv extraction was checked by hand against the source papers.

- Scores: 2,027 extracted scores from 10 papers were compared with the papers.
  1,976 matched, a precision of 97.5%. Recall is 81.4%: the pipeline picks up
  the main tables and skips many secondary ones.
- Harness: five papers name a harness (817 rows). In 368 of those rows the
  paper attributes a harness to the result, and the extractor named it
  correctly in 263 (71.5%). It missed the other 105 and never named a wrong
  one. It abstained on all 449 rows with no attributed harness, and on all 869
  rows from five papers that name no harness.

### EvalSpec

EvalSpec is the reporting specification the paper proposes: 13 Required
fields, 5 Recommended and 3 Full. A record that follows it either states the
settings that drive score differences or shows that they were left out.

The [EvalSpec site](https://psychias.github.io/EvalSpec/) holds the
specification, a registry of the dataset's records with a page per model, a
form that writes and checks a record for submission, and the interactive
article. Its sources and build script are on the `gh-pages` branch of this
repository.

## Experiments

The controlled experiments measure how far each unrecorded setting moves a score.
[`experiments/README.md`](experiments/README.md) has the design, the results and the
commands for each one, and says which raw result files are in the repository.

| Experiment | Result |
|---|---|
| Factorial grid: 4 models, BBH, GSM8K and MMLU, 3 prompt formats, 2 temperatures, 2 shot counts, 312 runs | Prompt format explains about 27% of GSM8K score variance, temperature 0.25% |
| Exp1: GSM8K under three prompt formats | 58.5%, 57.0% and 2.5%: the answer parser fails on chain-of-thought output |
| Prompt format on five log-likelihood benchmarks | Significant on four of five, a few points in size |
| Exp2: MMLU by log-likelihood and by generation | At most 0.21 pp apart |
| Exp3: lm-evaluation-harness 0.4.3 against 0.4.11 | At most 1.97 pp, below the spread between seeds (2.81 pp) |
| Judge model: the same answers under 4 and 8 judges | Mean rating moves by up to 1.35 points of 10 and the ranking changes |
| Temperature panel | 2.2% of GSM8K variance, 0.66% of judged MT-Bench variance |

## Repository layout

```
src/eee_eval/            the pipeline, as a Python package
  extraction/            arXiv extraction by a language model; leaderboard and model-card fetchers
  scrapers/              one scraper per leaderboard
  converters/            lm-evaluation-harness, Inspect AI and HELM logs to EEE records
  analysis/              aggregate_results (all_results.csv) and coverage_audit
  validation/            schema validation and data-quality checks
  eval_types.py          Pydantic models of the schema
src/emission_hooks/      writes EvalSpec records at the end of an lm-evaluation-harness run
eval.schema.json         the EEE JSON Schema, v0.2.1

scripts/                 fetch the dataset, recompute the paper's numbers
experiments/             the controlled experiments, one folder each, with their records
configs/                 paper lists for the extraction, experiment settings
figures/                 the figures, and in figures/scripts/ the scripts that draw them
tests/                   unit and integration tests

data/                    the dataset, written by scripts/fetch_data.py (not in git)
analysis_output/         numbers written by the reproduction scripts (not in git)
```

The EvalSpec site, with the specification, the registry and the submission form, is
built from the `gh-pages` branch, which has its own README.

## Installation

Python 3.10 or newer; the code was tested on 3.10.

```bash
python -m venv .venv
source .venv/bin/activate          # Linux/macOS
# .venv\Scripts\Activate.ps1       # Windows PowerShell
pip install -e ".[dev]"            # the package, pytest and ruff
pip install -r requirements.txt    # optional: the exact versions the paper was run with
```

With the environment active, `make install`, `make data`, `make repro`, `make figures`
and `make test` run the same steps.

## The dataset

`python scripts/fetch_data.py` downloads
[Hermeneia/EvalSpec_Dataset](https://huggingface.co/datasets/Hermeneia/EvalSpec_Dataset)
and lays it out where the scripts read it:

```
data/aggregated/all_results.csv     one row per source, model, benchmark and score (46,559 rows)
data/records/<source>.jsonl         the full records of each of the 12 sources, one per line
data/annotations/*.csv              the hand-checked audit sets (scores, harness, metadata fields)
data/eval.schema.json               the record schema
```

The dataset is gated, so the download needs a HuggingFace account that has accepted its
terms. With a copy already on disk, run `python scripts/fetch_data.py --from <folder>`.

## Reproducing the paper's numbers

```bash
python scripts/reproduce_paper.py          # dataset totals, coverage, audits, experiment numbers
python scripts/reproduce_case_studies.py   # the case studies of Section 5, as PASS/FAIL checks
python scripts/collision_prevalence.py     # model and benchmark pairs reported by several sources
python scripts/generate_evidence_file.py   # writes section5_evidence.txt: the records behind each case
```

None of these needs an API key. From the published dataset they reproduce the dataset
totals (46,559 records, 7,398 models, 1,954 benchmarks), the coverage tables, the
collision counts (41,999 pairs, 291 in two or more sources), the score audit (97.5%
precision, 81.4% recall), the harness and metadata audits and the case-study scores.

```bash
make figures      # redraws every file in figures/ from the data and the experiment logs
```

### What reproduces from a clone

| Part | Status |
|---|---|
| Dataset totals, per-source counts, metadata coverage | Reproduces from the published dataset |
| Collision counts of Section 3.3 | Reproduces from the published dataset (`scripts/collision_prevalence.py`) |
| Score, harness and metadata audits | Reproduces from the audit files of the dataset |
| Case-study scores of Section 5 | Reproduces: 25 of 25 checks pass |
| Figures in `figures/` | Redrawn by `make figures` |
| Exp2 (scoring mode) | Reproduces from `experiments/scoring_mode_eval/scoring_mode_results.jsonl` |
| Factorial grid, Exp1, Exp3, judge model, temperature panel | Reproduces from the raw result files under `experiments/*/results/`, without a GPU or an API key |
| BBH re-run | The score of the re-run is recorded in `experiments/bbh_protocol/`; its log was not kept |
| Re-running the experiments | Scripts are in `experiments/`; they need a GPU or an OpenRouter key |

[`experiments/README.md`](experiments/README.md) lists the command that recomputes each
experiment's numbers and the result file it reads.

## Using the pipeline

### Collecting records

Copy `.env.example` to `.env` and fill in the keys you need:

| Variable | Needed for |
|---|---|
| `OPENROUTER_API_KEY` | `eee_eval.extraction.extract_paper` (extraction from arXiv papers), and the judge and temperature experiments |
| `HF_TOKEN` | `eee_eval.extraction.add_leaderboard_records`, `hf_model_card_fetcher`, and gated models in the GPU experiments |
| `REQUESTS_CA_BUNDLE` | optional: a custom CA bundle if TLS verification fails |

```bash
python -m eee_eval.extraction.add_leaderboard_records     # leaderboards (needs HF_TOKEN)
python -m eee_eval.extraction.hf_model_card_fetcher       # HuggingFace model cards (needs HF_TOKEN)
python -m eee_eval.extraction.pwc_fetcher                 # Papers With Code
python -m eee_eval.extraction.extract_paper --paper-list configs/papers/general_llm_papers.txt

python -m eee_eval.validation.validate_outputs            # check records against the schema
python -m eee_eval.analysis.aggregate_results             # write data/aggregated/all_results.csv
python -m eee_eval.analysis.coverage_audit                # metadata coverage per field
```

These write one JSON file per record under `data/<source>/`. Raw downloads go to
`data/raw/`.

### Converting evaluation logs

```bash
python -m eee_eval.converters.lm_eval --log_path <results.json>
python -m eee_eval.converters.inspect --log_path <eval.log>
python -m eee_eval.converters.helm --log_path <run_dir/>
```

Each converter lists its flags with `--help`.

### Emitting EvalSpec records from a run

```python
from lm_eval import simple_evaluate
from emission_hooks.lm_eval_to_evalspec import emit_evalspec

out = simple_evaluate(model=lm, tasks=["gsm8k"], num_fewshot=5)
records = emit_evalspec(out, model_args={"pretrained": "meta-llama/Llama-3.1-8B"})
```

The hook reads the scoring mode from the task's output type and records a hash of the
prompt template. The [Submit page](https://psychias.github.io/EvalSpec/submit.html) of
the site checks such records and turns them into a dataset file.

## EEE schema (v0.2.1)

Each evaluation record has four blocks:

| Block | Fields |
|---|---|
| `model_info` | name, developer, parameter count, release date |
| `eval_library` | harness name, version |
| `source_metadata` | source URL, source type, evaluator relationship |
| `evaluation_results` | benchmark name, score, metric, generation config (shots, temperature, prompt template, chain-of-thought) |

The schema is defined in [`eval.schema.json`](eval.schema.json). The Pydantic
models are in [`src/eee_eval/eval_types.py`](src/eee_eval/eval_types.py).

## Citation

```bibtex
@inproceedings{psychias2027discrepancies,
  title     = {{LLM} Evaluation Discrepancies And How To Prevent Them},
  author    = {Psychias, Stylianos and Hubarava, Hanna and Opitz, Juri and von D{\"a}niken, Pius and Michail, Andrianos},
  booktitle = {Findings of the Association for Computational Linguistics: EACL 2027},
  year      = {2027},
  note      = {To appear}
}
```

## Licence

MIT, see [`LICENSE`](LICENSE).
