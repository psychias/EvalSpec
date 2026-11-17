# Scripts

Entry points for getting the dataset and recomputing the paper's numbers. Run them from
the repository root. None needs an API key.

| Script | What it does | Output |
|---|---|---|
| `fetch_data.py` | Downloads the published dataset from Hugging Face and lays it out under `data/` | `data/aggregated/`, `data/records/`, `data/annotations/` |
| `reproduce_paper.py` | Recomputes the dataset totals, the metadata coverage, the score and harness audits and the experiment numbers | `analysis_output/paper_numbers.json` and a printed report |
| `reproduce_case_studies.py` | Looks up every score quoted in the case studies of Section 5 and compares it with the paper | `PASS` / `FAIL` lines |
| `collision_prevalence.py` | Counts model and benchmark pairs reported by several sources, and how often they disagree | printed report |
| `generate_evidence_file.py` | Writes the records behind each case study, with their harness and shot fields | `section5_evidence.txt` |
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
experiments under `experiments/*/results/`. Files that are not on disk are listed at the
end of the report, and the checks that need them are skipped. `experiments/README.md`
says which files those are.
