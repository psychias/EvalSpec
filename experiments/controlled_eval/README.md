# Factorial grid and its follow-ups

Paper: Appendix M.1 and M.2, Table 19 (factorial grid, Exp1), §4. Design and results are
in [`../README.md`](../README.md).

| Path | What it is |
|---|---|
| `prompt_templates.md` | The three prompt formats and a fully rendered example |
| `0-shot-GSM8K/`, `5-shot-GSM8K/` | Per-question GSM8K logs (`samples_gsm8k*.jsonl`), one folder per model and format |
| `cross_extractor_results.csv` | The GSM8K outputs re-scored with other answer-extraction rules |
| `results/` | Raw records of the runs, one line per cell: the 312 grid runs, GPQA, the log-likelihood benchmarks and the `hf` backend control. `anova_per_benchmark.json` and `factorial_figure_stats.json` are written by the two scripts below |
| `scripts/compute_anova_per_benchmark.py` | One-way ANOVA per benchmark on prompt format, temperature and shot count (Tables 20 and 21) |
| `scripts/compute_factorial_figure_stats.py` | The numbers of Figures 3 and 4: bootstrap intervals and the mean score change when one setting differs. Run it after the script above |
| `scripts/rm_anova_loglik.py`, `scripts/analyze_powered_loglik.py` | Repeated-measures ANOVA and Friedman test on the five log-likelihood benchmarks |
| `scripts/rerun_*.py` | The log-likelihood benchmark cells on the `hf` backend (MMLU, GPQA, ARC-Challenge, WinoGrande, OpenBookQA) |
| `scripts/gsm8k_hf_control.py`, `scripts/gsm8k_hf_backend_check.py`, `scripts/analyze_gsm8k_hf_control.py` | GSM8K on the `hf` backend, to check the format effect is not specific to vLLM |
| `full_vs_limit200_qwen7b_gsm8k*.py`, `..._RESULT.txt` | One cell on the full GSM8K test set against the 200-problem subset |
| `analyse.py`, `figures/` | Sensitivity analysis and figures from the grid records |
| `factorial_grid.ipynb` | The Colab notebook that ran the grid of the paper: lm-evaluation-harness 0.4.11 on vLLM, 312 runs. Needs a GPU |
| `collision_model_results.jsonl` | 24 runs of Llama-3.1-Tulu-3-8B on BBH, GSM8K, MMLU and GPQA from an earlier design |

The `rerun_*.py` and `gsm8k_hf_*.py` scripts are written for one model per Colab
session: set `MODELS` at the top of the script. They print one `RESULT {json}` line per
cell; collect those lines into the file under `results/` that the analysis script reads.
