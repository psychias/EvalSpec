# EvalSpec worked example

Paper: Appendix J.

| Path | What it is |
|---|---|
| `records/` | EvalSpec records (JSON-LD) for the six leaderboard benchmarks of Llama-3.1-Tulu-3-8B |
| `field_coverage.md`, `field_coverage.tex` | Which fields can be filled automatically from a leaderboard record |

The hook that writes such records at the end of an lm-evaluation-harness run is
`src/emission_hooks/lm_eval_to_evalspec.py`.
