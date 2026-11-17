# Judge model, eight judge families

Paper: Appendix M.6. The study in `../judge_sensitivity/` with four more judges and
results for each of the eight MT-Bench categories. It reuses the contestant answers of
the first study.

    python experiments/judge_sensitivity_extended/run_judge_sensitivity_extended.py
    python experiments/judge_sensitivity_extended/friedman_test.py

Needs `OPENROUTER_API_KEY`. The report and the summary statistics
(`judge_sensitivity_extended_report.txt`, `judge_sensitivity_extended_stats.json`) are in
the repository; `friedman_test.py` reads `results/judge_runs.jsonl`.
