# Harness comparisons

Two things live here.

**In the paper.** [`version_compare/`](version_compare/) is Exp3 (§5.3, Appendix M.5):
lm-evaluation-harness 0.4.3 against 0.4.11 on GSM8K. Its README explains how the runs
are launched. `negative_control_version.jsonl` holds the first attempt at the same
question, 48 GSM8K runs on a 200-problem subset.

**Not in the paper.** The other files are an earlier attempt to compare scores of the
same model and benchmark across harnesses, using pairs found in the corpus:

| Path | What it is |
|---|---|
| `all_harness_pairs.csv`, `cross_harness_pairs.csv` | Model and benchmark pairs reported under two harnesses |
| `harness_unknown_pairs*.json` | Pairs where one side names no harness |
| `harness_*_report.txt`, `harness_*_stats.json`, `harness_reeval_data.json`, `harness_statistics.json` | Statistics over those pairs |
| `reeval_configs.json`, `reeval_commands.json`, `reeval_scripts/`, `run_reeval.sh`, `run_reeval.ps1`, `reeval_protocol_report.txt` | Generated commands for re-running the pairs under each harness |
| `figures/` | Plots of the score differences |

The paper's statement that the harness is unknown for 98% of cross-source disagreements
comes from `scripts/collision_prevalence.py`, not from these files.
