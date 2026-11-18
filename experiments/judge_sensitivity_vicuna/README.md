# Judge model on a second dataset

Paper: Appendix M.6. The same five contestants and eight judges on the 80 questions of
Vicuna-Bench.

    python experiments/judge_sensitivity_vicuna/run_judge_vicuna.py

Needs `OPENROUTER_API_KEY`. Summary statistics are in `judge_vicuna_stats.json`.
The answers and the ratings are in `results/`; with `--analyze` the script recomputes
the statistics from them and calls no model.
