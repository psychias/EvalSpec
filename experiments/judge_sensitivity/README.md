# Judge model, four judges

Paper: Appendix M.6, Table 19. Five contestant models answer the 80 MT-Bench turn-1
questions once; four judges score the same answers.

    python experiments/judge_sensitivity/run_judge_sensitivity.py

Needs `OPENROUTER_API_KEY`. Writes `results/responses.jsonl` and
`results/judge_runs.jsonl`, and the summary `judge_sensitivity_report.txt`. All three are
in the repository; with `--analyze` the script rebuilds the summary from them and calls
no model. Contestants and judges are the lists at the top of the script.
