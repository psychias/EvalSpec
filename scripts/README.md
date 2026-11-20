# Scripts

Entry points for getting the dataset and recomputing the paper's numbers. Run them from
the repository root. None needs an API key.

| Script | What it does | Output |
|---|---|---|
| `fetch_data.py` | Downloads the published dataset from Hugging Face and lays it out under `data/` | `data/aggregated/`, `data/records/`, `data/annotations/`, `data/DATASET_CARD.md` |
| `reproduce_paper.py` | Recomputes the dataset totals, the metadata coverage (Tables 6 and 7), the collision counts, the score, harness and metadata audits (Tables 4 and 5) and the experiment numbers | `analysis_output/paper_numbers.json` and a printed report |
| `reproduce_case_studies.py` | Looks up every score quoted in the case studies of Section 5 and compares it with the paper | `PASS` / `FAIL` lines |
| `collision_prevalence.py` | Section 3.3: counts model and benchmark pairs reported by several sources, how often they disagree, and how often the harness is missing. Names are compared after lower-casing and dropping punctuation, with no alias table | printed report |
| `generate_evidence_file.py` | Writes the records behind each case study, with their harness and shot fields | `section5_evidence.txt` |
| `dataset_card_numbers.py` | Recomputes every number on the dataset card on Hugging Face; with `--check` it compares them with the card and fails when one is missing | printed report |
| `olv2_raw_scores.py` | Checks the Open LLM Leaderboard scores the paper quotes from the leaderboard's own table (the score before rescaling, such as 43.62 for Gemma-7B on BBH), which are not in the dataset. Reads the saved rows of the four models; with `--fetch` it downloads the table at a fixed revision and compares the saved rows with it, which needs `pip install -e ".[leaderboard]"` | printed report |
| `correct_olv2_labels.py` | Writes a copy of the dataset in which the Open LLM Leaderboard records carry the protocol labels the leaderboard documents: BBH, GPQA, MuSR and MMLU-Pro are multiple choice and not chain-of-thought. Scores are not changed, and the files under `data/records` and `data/aggregated` are left as they are | `data/corrected/`, with `comparison.json` (coverage and collision counts before and after) |
| `dataset_access.py` | Shared by the scripts above: finds the dataset on disk in either layout | |

```bash
python scripts/fetch_data.py
python scripts/reproduce_paper.py
python scripts/reproduce_case_studies.py
```

## Two layouts of `data/`

The scripts read the published dataset as `fetch_data.py` writes it: one CSV with every
result, and one JSONL file per source. They also read the working tree of the extraction
pipeline, which has one JSON file per record (`data/<source>/.../<uuid>.json`). When that
tree is present, `reproduce_paper.py` rebuilds `all_results.csv` from it first; pass
`--no-rebuild` to skip that.

The case-study scripts name single record files of the pipeline tree. On the published
dataset the same records are found in the JSONL files by paper, model and benchmark.

## Experiment numbers

`reproduce_paper.py` and `reproduce_case_studies.py` read the raw result files of the
experiments under `experiments/*/results/`, which are in the repository. If one is
removed, it is listed at the end of the report and the checks that need it are skipped.
The statistics that `reproduce_paper.py` does not print (the repeated-measures ANOVAs,
the figure numbers, the 8-judge and Vicuna-Bench studies, the temperature panel) come
from the analysis scripts listed in `experiments/README.md`; none of them needs a GPU or
an API key.
