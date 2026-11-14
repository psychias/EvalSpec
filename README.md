# LLM Evaluation Discrepancies And How To Prevent Them

Code, experiment records and paper sources for the paper of the same name, by
Stylianos Psychias, Hanna Hubarava, Juri Opitz, Pius von Däniken and Andrianos
Michail. Accepted to Findings of EACL 2027, to appear.

- Interactive article: https://psychias.github.io/eee-eval/
- Dataset: https://huggingface.co/datasets/evaleval/EEE_datastore

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
  1,976 matched, a precision of 97.5%. Recall is about 81%: the pipeline picks
  up the main tables and skips many secondary ones.
- Harness: on five papers that name a harness (817 rows), per-row precision is
  89.5% (731/817). Every harness the pipeline names is correct (263/263), so
  the errors are rows where it named none. On five papers that name no harness
  (869 rows), it abstained on every row.

### EvalSpec

EvalSpec is the reporting specification the paper proposes: 9 Required fields,
8 Recommended and 3 Full. A record that follows it either states the settings
that drive score differences or shows that they were left out.

## Experiment outcomes

The dataset shows which settings go unrecorded. The controlled experiments in
Appendix G of the paper measure how far each of those settings moves a score.
Runs use `lm-evaluation-harness` with vLLM unless stated otherwise.

### 1. Factorial grid

Setup: 4 instruction-tuned models (Qwen2.5-14B-Instruct, Qwen2.5-7B-Instruct,
Llama-3.1-8B-Instruct, Mistral-7B-Instruct-v0.3), 3 benchmarks (BBH, GSM8K,
MMLU), 3 prompt formats (`plain` few-shot, `instruct` with a system prompt,
`cot` chain-of-thought), 2 temperatures (0.0, 0.7), 2 shot counts (0 and 3 for
BBH; 0 and 5 for GSM8K and MMLU) and 3 seeds (42, 123, 7). MMLU was cut to
temperature 0.0 and one seed because of server limits. That gives 312
successful runs: 144 BBH, 144 GSM8K, 24 MMLU. GSM8K and MMLU use a 200-problem
subset; BBH uses the full suite. Six MMLU runs failed under vLLM and were
re-scored on the `hf` backend. Cells run on both backends agree within 0.5 pp.

Prompt format, one-way ANOVA per benchmark on the 5-shot cells:

| Benchmark | `plain` | `instruct` | `cot` | format effect |
|---|---|---|---|---|
| GSM8K (n=24/cell) | 38.75 | 34.19 | 19.25 | η²≈27.4%, F=13.0, p=1.6×10⁻⁵ |
| MMLU (n=4/cell) | 65.67 | 65.87 | 51.95 | η²≈35.1%, F=2.43, p=0.14 |

Prompt format explains 27.4% of GSM8K score variance, with a gap of 19.50 pp
between plain and cot. Temperature explains η²≈0.25% (F=0.18, p=0.68). The MMLU
estimate is larger, η²≈35.1%, but with four runs per cell it is underpowered
(p=0.14). The ordering of the formats is the same as on GSM8K.

Shot count, ANOVA pooled by shot count: on GSM8K η²≈65.1% (F=264.6, p<10⁻³⁰),
but the models did not get better at arithmetic. Every 0-shot cell scores
exactly 0.00, because instruction-tuned models leave out the `####` delimiter
that the GSM8K parser looks for. On MMLU η²≈0.1% (F=0.03, p=0.87; 60.17 at
0-shot, 61.16 at 5-shot), so shot count has almost no effect on this
log-likelihood benchmark.

### 2. E1: GSM8K prompt-format sensitivity

Setup: Qwen2.5-14B-Instruct on GSM8K, 5-shot, temperature 0.0, seeds 42, 123
and 7 (the run is deterministic, so the seeds give identical scores),
`limit=200`.

| Prompt format | Score |
|---|---|
| `plain` (direct-answer few-shot) | 58.5% |
| `instruct` (system prompt) | 57.0% |
| `cot` (chain-of-thought few-shot) | 2.5% |

Changing only the prompt format takes the score from 58.5% to 2.5%. The
chain-of-thought output has no `####` delimiter, so the standard extractor
returns nothing for nearly every item. At temperature 0.7 the scores are 58.67,
52.67 and 2.83.

### 3. E2: MMLU scoring-mode control

Setup: 4 models on MMLU, 5-shot, `plain`, temperature 0.0, each scored by
log-likelihood and by generation on the full 14,042-item test set, so both
modes see the same items.

| Model | log-likelihood | generation | \|Δ\| |
|---|---|---|---|
| Mistral-7B-Instruct-v0.3 | 61.85 | 61.64 | 0.21 |
| Qwen2.5-7B-Instruct | 74.25 | 74.43 | 0.18 |
| Llama-3.1-8B-Instruct | 68.19 | 68.16 | 0.03 |
| Qwen2.5-14B-Instruct | 79.97 | 79.79 | 0.18 |

The largest gap is 0.21 pp, so scoring mode barely matters on MMLU. The much
larger scoring-mode gap on BBH (case study in §5.1) is therefore particular to
BBH, whose chain-of-thought structure meets OLv2's multiple-choice
log-likelihood scoring. The paper separates that gap from the part caused by
OLv2's score normalisation.

### 4. E3: harness-version sensitivity

Setup: Qwen2.5-1.5B-Instruct and Qwen2.5-7B-Instruct on the full GSM8K test
set, 5-shot, `hf` backend, `lm-eval` 0.4.3 against 0.4.11, seeds 42 and 123,
all other settings fixed.

| Model | 0.4.3 (s42/s123) | 0.4.11 (s42/s123) |
|---|---|---|
| Qwen2.5-1.5B-Instruct | 32.83 / 33.74 | 33.06 / 33.36 |
| Qwen2.5-7B-Instruct | 75.06 / 76.35 | 75.51 / 78.32 |

The largest difference between versions at the same seed is 1.97 pp, which is
smaller than the spread between seeds within one version (up to 2.81 pp). The
two versions also need different `transformers` stacks and cannot be installed
together. This is why `harness_version` is a Required field in EvalSpec.

### 5. Judge-model sensitivity

Setup: 5 contestant models each answer the 80 MT-Bench turn-1 questions once.
The same answers are then scored by 4 judges (GPT-4o-mini, Gemini-3.5-Flash,
Llama-3.1-70B-Instruct, Claude-Haiku-4.5) with the MT-Bench 1 to 10 rubric at
temperature 0. Any difference in score comes from the judge.

| Contestant | GPT-4o-mini | Gemini-3.5 | Llama-70B | Claude-Haiku | spread |
|---|---|---|---|---|---|
| Gemma-3-4B | 8.24 | 7.96 | 8.31 | 7.26 | 1.04 |
| Qwen2.5-7B | 7.86 | 8.02 | 7.96 | 6.97 | 1.05 |
| Llama-3.1-8B | 8.04 | 7.61 | 8.22 | 6.87 | 1.35 |
| Ministral-8B | 8.44 | 7.54 | 8.62 | 7.51 | 1.11 |
| Qwen2.5-72B | 8.32 | 8.59 | 8.38 | 7.74 | 0.84 |

The judge changes the ranking as well as the level. Ministral-8B is first under
GPT-4o-mini and Llama-70B and last under Gemini. The spread across judges
averages 1.08 points (maximum 1.35), and the Spearman rank correlation between
pairs of judges runs from +1.00 down to −0.30. A score from an LLM judge cannot
be read without knowing which judge gave it.

The study was repeated with 8 judge families (adding DeepSeek, Mistral, Qwen
and Amazon) and broken down by MT-Bench task category
(`experiments/judge_sensitivity_extended/`). The effect is larger there: mean
spread 1.66, maximum 1.80. Spearman correlation over the 28 judge pairs runs
from +1.00 to −0.10 with a mean of +0.61. The spread is between 1.5 and 2.9
points in all 8 task categories and is largest on coding, extraction and math.

### 6. GSM8K on the full test set

The factorial grid scored GSM8K on 200 problems to save compute. To check that
the subset is representative, the Qwen2.5-7B plain and cot cells were rerun on
all 1,319 questions on a Colab A100
(`experiments/controlled_eval/full_vs_limit200_qwen7b_gsm8k.py`):

| format | limit=200 | full (1319) | Δ |
|---|---|---|---|
| plain | 17.00 | 17.29 | +0.29 |
| cot | 59.50 | 58.23 | −1.27 |

Both formats change by at most 1.3 pp, so the 200-problem subset stands in well
for the full set. The rerun used the `hf` backend of lm-eval, because the
current vLLM wheel targets CUDA 13 and Colab has CUDA 12. Its absolute scores
differ from the vLLM scores in the grid, which is a backend effect of its own.
The rerun checks the subset; it does not reproduce the vLLM numbers.

### 7. Prompt format on five log-likelihood benchmarks

Setup: to see whether prompt format matters outside generation-scored GSM8K, it
was measured on five log-likelihood benchmarks. Each is replicated over the
unit its protocol allows: seeds (n=12) for ARC-Challenge, WinoGrande and
OpenBookQA, which draw few-shot examples at random, and models (8 instruct
models from 1.5B to 14B) for MMLU and GPQA, which are deterministic for a given
seed. All runs use the `hf` backend. Each subject is scored under plain,
instruct and cot, so the test is a repeated-measures ANOVA blocked on the
subject, cross-checked with the Friedman test.

| Benchmark | replicated over | n | RM-ANOVA *p* | verdict |
|---|---|---|---|---|
| ARC-Challenge | seeds | 12 | <1e-4 | significant |
| WinoGrande | seeds | 12 | <1e-4 | significant |
| MMLU | models | 7 | 0.003 | significant |
| OpenBookQA | seeds | 12 | 0.010 | significant |
| GPQA | models | 7 | 0.18 | null (chance floor) |

Prompt format has a significant effect on 4 of the 5 benchmarks, and the
Friedman test agrees. GPQA is the exception; the models score near its 25%
chance level. The effects are a few points, about a tenth of what GSM8K shows
under generation scoring. Format matters most where the score depends on
parsing generated text. Phi-3.5 was excluded because its metric did not parse.
The Llama-3.1-8B mirror is flagged, and the conclusions hold without it.
(`experiments/controlled_eval/scripts/rm_anova_loglik.py`)

### 8. Further checks

- Judge effect on a second dataset, Vicuna-Bench: spread across judges 1.84,
  Friedman χ²(7)=908.5 (Kendall's *W*=0.33), Spearman correlation between
  judges as low as −0.4. (`experiments/judge_sensitivity_vicuna/`)
- Temperature panel through OpenRouter: temperature explains 2.2% of GSM8K
  variance and 0.66% of MT-Bench judged-quality variance.
  (`experiments/temperature_panel/`)
- EvalSpec emission hook: an adapter, with tests, that turns an existing
  lm-evaluation-harness run into EvalSpec-R records and fills 8 of 8
  Required fields, including `scoring_mode` and the prompt-template
  hash. (`src/emission_hooks/lm_eval_to_evalspec.py`)

## Repository layout

```
eval.schema.json                       EEE JSON Schema v0.2.1
src/eee_eval/eval_types.py             Pydantic models for the schema
src/eee_eval/instance_level_types.py   Instance-level schema types

scripts/reproduce_paper.py        Recompute every paper number → analysis_output/paper_numbers.json
scripts/reproduce_case_studies.py Re-derive the §5 case-study numbers from data/
scripts/generate_evidence_file.py Build section5_evidence.txt (raw-data provenance)

src/eee_eval/
├── extraction/               Ingestion: arXiv LLM extraction, leaderboard and model-card fetchers
├── analysis/                 aggregate_results (→ all_results.csv) and coverage_audit
├── converters/               Framework-log → EEE adapters (lm_eval, inspect, helm, common)
├── scrapers/                 Leaderboard-specific scrapers
├── validation/               Schema validation and output checks
└── utils/                    Shared helpers (I/O, schema validation)
src/emission_hooks/           lm-evaluation-harness → EvalSpec adapter

configs/                      Default config, experiment configs, arXiv paper lists
experiments/                  Controlled experiments and their records
LLM_Evaluation_Report/        Paper LaTeX sources and figure scripts
tests/                        Unit and integration tests
data/                         Aggregated EEE records per source (not tracked in git)
analysis_output/              Generated statistics, incl. paper_numbers.json (not tracked in git)
```

## Installation

Python 3.10 or newer. The code was tested on 3.10.

```bash
python -m venv .venv
source .venv/bin/activate          # Linux/macOS
# .venv\Scripts\Activate.ps1       # Windows PowerShell
pip install -r requirements.txt
```

## Environment variables

Copy `.env.example` to `.env` and fill in the keys you need:

| Variable | Needed for | Notes |
|---|---|---|
| `OPENROUTER_API_KEY` | `eee_eval.extraction.extract_paper` | LLM extraction of results from arXiv papers |
| `HF_TOKEN` | `eee_eval.extraction.add_leaderboard_records`, `hf_model_card_fetcher` | HuggingFace access token for the leaderboard and model-card fetchers |
| `REQUESTS_CA_BUNDLE` | optional | Custom CA bundle if TLS verification fails in your environment |

Reproducing the paper's numbers needs no keys.

## Reproducing the paper's numbers

The scripts read the aggregated records from `data/`. That directory is not
tracked in git; the records are published as the HuggingFace dataset linked at
the top.

`reproduce_paper.py` recomputes every number in the paper from the raw data
files and writes the results to `analysis_output/paper_numbers.json`:

```bash
python scripts/reproduce_paper.py              # recompute and write paper_numbers.json
python scripts/reproduce_paper.py --no-rebuild # reuse the existing data/aggregated/all_results.csv
# or: make repro
```

It covers the §3.2 dataset totals and per-source counts, the §4.1 score
extraction audit, the §4.2 harness audit, the §4.3 metadata coverage, the §5
factorial-grid ANOVA and the appendix experiments. Two more scripts give the
detail behind the case studies, down to the JSON paths and the harness and shot
fields of each record:

```bash
python scripts/reproduce_case_studies.py       # §5 case-study numbers
python scripts/generate_evidence_file.py       # writes section5_evidence.txt
```

## Rebuilding the dataset (optional)

To fetch the records again from their sources:

```bash
# Leaderboard records (needs HF_TOKEN)
python -m eee_eval.extraction.add_leaderboard_records

# HuggingFace model-card results (needs HF_TOKEN)
python -m eee_eval.extraction.hf_model_card_fetcher

# Papers With Code results
python -m eee_eval.extraction.pwc_fetcher

# Extract results from arXiv papers (needs OPENROUTER_API_KEY)
python -m eee_eval.extraction.extract_paper --paper-list configs/papers/general_llm_papers.txt

# Validate records against the EEE schema
python -m eee_eval.validation.validate_outputs

# Aggregate into a single CSV (data/aggregated/all_results.csv)
python -m eee_eval.analysis.aggregate_results
```

## Analysis and figures

```bash
# Metadata coverage audit (→ analysis_output/coverage_stats.csv)
python -m eee_eval.analysis.coverage_audit

# Regenerate the paper figures
python LLM_Evaluation_Report/figures/scripts/coverage_bars.py   # Figure 6 (§4.3)
python LLM_Evaluation_Report/figures/scripts/unified.py         # Figure 5 (§5)
python LLM_Evaluation_Report/figures/scripts/case1.py           # Figure 4 (§5.1)
```

## Converting evaluation-framework logs

Each converter has its own command-line interface. Run any of them with
`--help` for the full list of flags (`--output_dir`,
`--evaluator_relationship` and so on):

```bash
# lm-evaluation-harness
python -m eee_eval.converters.lm_eval --log_path <results.json>

# Inspect AI
python -m eee_eval.converters.inspect --log_path <eval.log>

# CRFM HELM
python -m eee_eval.converters.helm --log_path <run_dir/>
```

## Running the tests

```bash
pip install pytest
pytest
```

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
