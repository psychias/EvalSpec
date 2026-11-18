# BBH protocols and the Gemma-2-9B re-run

Paper: §5.1 and §5.3.

| Path | What it is |
|---|---|
| `sealion_provenance/rerun_gemma2_9b_bbh.py` | Runs the leaderboard's `leaderboard_bbh` configuration on Gemma-2-9B (3-shot multiple-choice log-likelihood), and the chain-of-thought protocol for comparison. Needs a GPU and access to `google/gemma-2-9b` |
| `sealion_provenance/olv2_gemma2_9b_bbh.json` | The leaderboard's own record for that model |
| `build_E1_notebook.py` | Writes the notebook that runs BBH under four protocols (log-likelihood, direct generation, chain-of-thought on 23 and on 18 tasks) |

The re-run reproduces the leaderboard's unrescaled score to within 0.11 pp (53.88
against 53.77). Both values are in `sealion_provenance/olv2_gemma2_9b_bbh.json`, which
`scripts/reproduce_paper.py` reads; the log of the re-run itself was not kept, so the
script above has to be run again to check the 53.88 independently.
