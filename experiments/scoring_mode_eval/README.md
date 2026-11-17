# Exp2: scoring mode on MMLU

Paper: §5.1, Appendix M.4, Table 19. Four models on MMLU, 5-shot, scored by
log-likelihood and by generation. Results are in [`../README.md`](../README.md).

| Path | What it is |
|---|---|
| `scoring_mode_results.jsonl` | One record per model, scoring mode and sample size |
| `scoring_mode_summary.csv` | The four rows of the paper's table |
| `e2_full_set_reruns.py` | Full-set log-likelihood runs for the three smaller models |
| `finish_missing_cells_e2_e3.py` | The 14B log-likelihood cell, and one missing cell of Exp3 |
| `gen_scoring_mode_figure.py` | Bar chart of the two modes per model |
