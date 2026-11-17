# Experiments

The controlled experiments of the paper, one folder each. The corpus shows which
evaluation settings go unrecorded; these runs measure how far each setting moves a
score. Section and appendix numbers refer to the paper.

| Paper | What it tests | Folder | Needs |
|---|---|---|---|
| Factorial grid (App. M.1, Table 19) | Prompt format, temperature and shot count on BBH, GSM8K and MMLU | [`controlled_eval/`](controlled_eval/) | GPU |
| Exp1 (§4, Table 19) | GSM8K under three prompt formats: the answer parser fails on chain-of-thought output | [`controlled_eval/`](controlled_eval/) | GPU |
| Prompt format on five log-likelihood benchmarks (App. M.1) | Whether the format effect holds outside GSM8K | [`controlled_eval/scripts/`](controlled_eval/scripts/) | GPU |
| Backend control and full-set check (App. M.1) | GSM8K on the `hf` backend; 200-problem subset against the full test set | [`controlled_eval/`](controlled_eval/) | GPU |
| Exp2 (§5.1, App. M.4) | MMLU scored by log-likelihood and by generation | [`scoring_mode_eval/`](scoring_mode_eval/) | GPU |
| Exp3 (§5.3, App. M.5) | lm-evaluation-harness 0.4.3 against 0.4.11 on GSM8K | [`harness_reeval/version_compare/`](harness_reeval/version_compare/) | GPU |
| BBH re-run (§5.1, §5.3) | Reproducing the leaderboard's Gemma-2-9B BBH score under its own configuration | [`bbh_protocol/`](bbh_protocol/) | GPU |
| Judge model (App. M.6) | The same answers scored by different judge models | [`judge_sensitivity/`](judge_sensitivity/), [`judge_sensitivity_extended/`](judge_sensitivity_extended/), [`judge_sensitivity_vicuna/`](judge_sensitivity_vicuna/) | OpenRouter key |
| Temperature panel (App. M.7) | Temperature on GSM8K and on judged MT-Bench answers | [`temperature_panel/`](temperature_panel/) | OpenRouter key |
| EvalSpec worked example (App. J) | EvalSpec records for one model, and what a harness can fill in | [`evalspec_worked_example/`](evalspec_worked_example/) | none |

`harness_reeval/` also holds an earlier cross-harness comparison that the final
paper does not use; its README says which files belong to it.

Analysis scripts that need a result file which is not on disk stop with a message
naming the file.

## Running them

GPU experiments use lm-evaluation-harness 0.4.11, with vLLM for the factorial grid and
the `hf` backend elsewhere. They were run on Colab A100 runtimes, one model per
session. Gated models (Mistral, Gemma, the GPQA dataset) need `HF_TOKEN` set to a token
with access. The judge and temperature experiments need no GPU: they call models through
OpenRouter and read `OPENROUTER_API_KEY` from the environment or from `.env`.

Each script writes its raw records to a `results/` folder next to it and caches there, so
a second run only fills gaps. Analysis scripts read from the same folder.

```bash
# judge model, 4 judges, MT-Bench turn 1
python experiments/judge_sensitivity/run_judge_sensitivity.py
# the same with 8 judge families and per-category results, then the Friedman test
python experiments/judge_sensitivity_extended/run_judge_sensitivity_extended.py
python experiments/judge_sensitivity_extended/friedman_test.py
# second dataset
python experiments/judge_sensitivity_vicuna/run_judge_vicuna.py
# temperature
python experiments/temperature_panel/run_temperature_panel.py

# harness version: see harness_reeval/version_compare/README.md
# analysis of the grid
python experiments/controlled_eval/scripts/compute_anova_per_benchmark.py
python experiments/controlled_eval/scripts/rm_anova_loglik.py
```

## What is in the repository and what is not

The numbers in the paper come from the raw result files. Some of those are in the
repository, and for the others only the reports computed from them are.

| Experiment | In the repository | Not in the repository |
|---|---|---|
| Factorial grid | per-question GSM8K logs for 4 models and 3 formats (`controlled_eval/0-shot-GSM8K/`, `5-shot-GSM8K/`), `results/gpqa_results.jsonl`, figures | `results/controlled_eval_results.jsonl` (the 312 runs), `results/generalization_hf.jsonl`, `results/gsm8k_hf_control.jsonl` |
| Exp2 | `scoring_mode_results.jsonl`, `scoring_mode_summary.csv` | |
| Exp3 | `version_comparison_report.txt`, `version_pairs.csv` (first 200-problem run) | `results/full_version_runs.jsonl` (the full-set, two-seed runs the paper reports) |
| BBH re-run | the leaderboard's own record, `sealion_provenance/olv2_gemma2_9b_bbh.json` | `harness_reeval/version_compare/results/bbh_protocol_runs.jsonl` |
| Judge model | reports and summary statistics | `results/responses.jsonl`, `results/judge_runs.jsonl` of each study |
| Temperature panel | `temperature_panel_stats.json` | raw responses |

`scripts/reproduce_paper.py` recomputes the experiment numbers from these files. It
lists the files it could not find and leaves those numbers empty. To restore them, copy
each file to the path given above and commit it; `results/` folders are tracked.

Two more things to know before reusing the grid:

- `controlled_eval/run.py` is an earlier runner. Its defaults (models, temperatures,
  format names, benchmarks) are not those of the grid in the paper, which was run from
  a Colab notebook that is not in the repository. The design of the paper's grid is
  written out below, and the scripts in `controlled_eval/scripts/` use it. Notebooks
  under `experiments/` are tracked by git, so the grid notebook can be added next to
  `run.py`.
- The quantisation experiment (`configs/experiment/quantisation_e4.yaml`,
  `harness_reeval/version_compare/run_e4.sh`) was started and is not in the paper.

## Designs and results

### Factorial grid

Four instruction-tuned models (Qwen2.5-14B-Instruct, Qwen2.5-7B-Instruct,
Llama-3.1-8B-Instruct, Mistral-7B-Instruct-v0.3), three benchmarks (BBH, GSM8K, MMLU),
three prompt formats, two temperatures (0.0, 0.7), two shot counts (0 and 3 for BBH; 0
and 5 for GSM8K and MMLU) and three seeds (42, 123, 7). MMLU was cut to temperature 0.0
and one seed. That gives 312 runs: 144 BBH, 144 GSM8K, 24 MMLU, each on a 200-problem
subset. Six MMLU runs failed under vLLM and were re-scored on the `hf` backend; cells
run on both backends agree within 0.5 pp.

The three prompt formats differ only in the system message. `plain` uses the model's
default system prompt, `instruct` asks for a careful direct answer, and `cot` asks for
step-by-step reasoning before the answer. The few-shot body is the same in all three.
The exact prompts are in [`controlled_eval/prompt_templates.md`](controlled_eval/prompt_templates.md).

Prompt format, one-way ANOVA per benchmark on the 5-shot cells:

| Benchmark | `plain` | `instruct` | `cot` | format effect |
|---|---|---|---|---|
| GSM8K (n=24/cell) | 38.75 | 34.19 | 19.25 | η²≈27.4%, F=13.0, p=1.6×10⁻⁵ |
| MMLU (n=4/cell) | 65.67 | 65.87 | 51.95 | reported with the log-likelihood benchmarks below |

Temperature explains η²≈0.25% of GSM8K variance (F=0.18, p=0.68). A bootstrap over
cells gives a 95% interval of 14.4% to 44.9% for the format effect.

Shot count: on GSM8K η²≈65% (F=264.6, p<10⁻³⁰), but the models did not get better at
arithmetic. Every 0-shot cell scores exactly 0.0, because without worked examples the
models leave out the `####` delimiter that the GSM8K parser looks for. On MMLU the
effect is η²≈0.1% (F=0.03, p=0.87; 60.17 at 0-shot, 61.16 at 5-shot).

### Exp1: GSM8K under three prompt formats

Qwen2.5-14B-Instruct, GSM8K, 5-shot, temperature 0.0, lm-evaluation-harness 0.4.11,
200 problems.

| Prompt format | Accuracy |
|---|---|
| `plain` | 58.5% |
| `instruct` | 57.0% |
| `cot` | 2.5% |

The chain-of-thought answers often contain the right number and no `####` delimiter, so
the standard extractor records them as wrong. The per-question logs are in
`controlled_eval/5-shot-GSM8K/`. `controlled_eval/cross_extractor_results.csv` scores the
same outputs with other extraction rules.

### Prompt format on five log-likelihood benchmarks

Each benchmark is replicated over the unit its protocol allows: seeds (n=12) for
ARC-Challenge, WinoGrande and OpenBookQA, which draw few-shot examples at random, and
models (8 instruction-tuned models from 1.5B to 14B, 7 after one exclusion) for MMLU and
GPQA, which are deterministic for a given seed. All runs use the `hf` backend. Every
subject is scored under all three formats, so the test is a repeated-measures ANOVA
blocked on the subject, with the Friedman test as a check.

| Benchmark | replicated over | n | F | p |
|---|---|---|---|---|
| ARC-Challenge | seeds | 12 | F(2,22)=23.4 | <10⁻⁴ |
| WinoGrande | seeds | 12 | F(2,22)=16.2 | <10⁻⁴ |
| MMLU | models | 7 | F(2,12)=10.2 | 0.003 |
| OpenBookQA | seeds | 12 | F(2,22)=5.7 | 0.01 |
| GPQA | models | 7 | F(2,12)=1.98 | 0.18 |

The effect is significant on four of the five and is a few points in size, about a
tenth of what GSM8K shows. GPQA is the exception; the models score near its 25% chance
level. Phi-3.5 was dropped because its metric did not parse.

Scripts: `rerun_generalization_hf.py`, `rerun_generalization_multiseed.py`,
`rerun_mmlu_hf.py`, `rerun_mmlu_gpqa_multiseed.py`, `rerun_gpqa_hf.py`,
`rerun_gpqa_multiseed.py` run the cells; `rm_anova_loglik.py` and
`analyze_powered_loglik.py` analyse them.

### Backend control and full-set check

GSM8K was re-scored on the `hf` backend for all four models (one seed, full test set,
three formats; `gsm8k_hf_control.py`, `analyze_gsm8k_hf_control.py`). Both Qwen models
collapse under `cot` as they do on vLLM (7B from 37.0 to 7.0, 14B from 38.2 to 0.1),
and Mistral, whose chain-of-thought output keeps the delimiter, stays flat (38.4, 41.0,
40.4).

The Qwen2.5-7B `plain` and `cot` cells were also rerun on all 1,319 GSM8K questions
(`full_vs_limit200_qwen7b_gsm8k.py`, result in `full_vs_limit200_qwen7b_gsm8k_RESULT.txt`):

| format | 200 problems | full set | difference |
|---|---|---|---|
| plain | 17.00 | 17.29 | +0.29 |
| cot | 59.50 | 58.23 | −1.27 |

The subset tracks the full set within 1.3 pp. This rerun used the `hf` backend with a
fixed few-shot seed and a different batch size, and its absolute scores differ from the
vLLM grid (40.2 and 27.7 for the same cells). The inference backend is itself a setting
that moves scores.

### Exp2: scoring mode on MMLU

Four models on MMLU, 5-shot, `plain`, temperature 0.0, each scored by log-likelihood and
by generation.

| Model | log-likelihood | generation | difference |
|---|---|---|---|
| Mistral-7B-Instruct-v0.3 | 61.85 | 61.64 | 0.21 |
| Qwen2.5-7B-Instruct | 74.25 | 74.43 | 0.18 |
| Llama-3.1-8B-Instruct | 68.19 | 68.16 | 0.03 |
| Qwen2.5-14B-Instruct | 79.97 | 79.79 | 0.18 |

The largest gap is 0.21 pp, so scoring mode alone does not produce large gaps on a
multiple-choice benchmark. The large gap on BBH comes from BBH's chain-of-thought
structure meeting the leaderboard's log-likelihood scoring.

### Exp3: harness version

Qwen2.5-1.5B-Instruct and Qwen2.5-7B-Instruct on the full GSM8K test set, 5-shot, `hf`
backend, lm-evaluation-harness 0.4.3 against 0.4.11, seeds 42 and 123.

| Model | 0.4.3 (seed 42 / 123) | 0.4.11 (seed 42 / 123) |
|---|---|---|
| Qwen2.5-1.5B-Instruct | 32.83 / 33.74 | 33.06 / 33.36 |
| Qwen2.5-7B-Instruct | 75.06 / 76.35 | 75.51 / 78.32 |

The largest difference between versions at the same seed is 1.97 pp, smaller than the
spread between seeds within one version (up to 2.81 pp). The two versions need
different `transformers` stacks and cannot be installed together, which is why each
cell runs on its own machine.

### BBH re-run

`bbh_protocol/sealion_provenance/rerun_gemma2_9b_bbh.py` runs the leaderboard's
`leaderboard_bbh` configuration on Gemma-2-9B. It reproduces the unrescaled score to
within 0.11 pp (53.88 against the leaderboard's 53.77), so the published 34.10 is
reproducible under its own procedure and not comparable with the chain-of-thought score
of 68.20. `bbh_protocol/build_E1_notebook.py` generates the notebook that compares BBH
protocols (log-likelihood, direct generation, chain-of-thought generation).

### Judge model

Five contestant models each answer the 80 MT-Bench turn-1 questions once. The same
answers are then scored by four judges (GPT-4o-mini, Gemini-3.5-Flash,
Llama-3.1-70B-Instruct, Claude-Haiku-4.5) with the MT-Bench 1 to 10 rubric at
temperature 0.

| Contestant | GPT-4o-mini | Gemini-3.5 | Llama-70B | Claude-Haiku | spread |
|---|---|---|---|---|---|
| Gemma-3-4B | 8.24 | 7.96 | 8.31 | 7.26 | 1.04 |
| Qwen2.5-7B | 7.86 | 8.02 | 7.96 | 6.97 | 1.05 |
| Llama-3.1-8B | 8.04 | 7.61 | 8.22 | 6.87 | 1.35 |
| Ministral-8B | 8.44 | 7.54 | 8.62 | 7.51 | 1.11 |
| Qwen2.5-72B | 8.32 | 8.59 | 8.38 | 7.74 | 0.84 |

The spread across judges averages 1.08 points and reaches 1.35. The judge also changes
the ranking: Ministral-8B is first under GPT-4o-mini and Llama-70B and last under
Gemini, and the Spearman correlation between pairs of judges runs from +1.00 to −0.30.

With eight judge families (adding DeepSeek, Mistral, Qwen and Amazon) and results per
MT-Bench category, the mean spread is 1.66 and the maximum 1.80. Spearman correlation
over the 28 judge pairs runs from +1.00 to −0.10 with a mean of +0.61. Mean spread by
category is between 1.5 (writing) and 2.9 (coding).

On Vicuna-Bench, with the same contestants and judges, the spread is 1.84, the Friedman
test over 389 fully rated answers gives χ²(7)=908.5 (Kendall's W=0.33), and Spearman
correlation falls to −0.40.

### Temperature panel

Four models at temperatures 0.0, 0.7 and 1.0 with two samples each, on GSM8K (parsed
numeric answer) and on MT-Bench (answers scored by a fixed judge, GPT-4o-mini).
Temperature explains 2.2% of GSM8K accuracy variance (means 86.0, 87.0, 85.1) and 0.66%
of MT-Bench score variance (means 8.63, 8.61, 8.58).

### EvalSpec worked example

`evalspec_worked_example/records/` holds EvalSpec records for the six leaderboard
benchmarks of one model, and `field_coverage.md` lists which fields could be filled
automatically from a leaderboard record. The hook that writes EvalSpec records at the
end of an lm-evaluation-harness run is in `src/emission_hooks/lm_eval_to_evalspec.py`.
