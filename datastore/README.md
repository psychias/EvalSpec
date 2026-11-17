# The bundled sample

`data/` holds 98 Every Eval Ever files with 122 records. It is what the site is built
from when no other datastore is given, so that the site works as delivered.

It is a sample, not the datastore. The full corpus of the paper has 46,559 records and
lives on Hugging Face (see `datastore.hf_repo` in `config.json`). To build the site
from it:

    python tools/fetch_datastore.py
    python source/build.py --datastore datastore_cache

## What is in it

Every file names the origin of its numbers in
`source_metadata.additional_details.sample_origin`. The numbers are those quoted in the
paper or shipped in its code repository. The files were written by
`source/snapshot/build_snapshot.py` in the layout of the paper's pipeline; they are not
copies of the files on Hugging Face, and their `retrieved_timestamp` is the day the
sample was assembled.

| Folder | Records | Track | Origin |
|---|---|---|---|
| `open_llm_leaderboard_v2/` | 20 | predicted | Section 5.1 and Appendices E and G of the paper; `experiments/harness_reeval/all_harness_pairs.csv` |
| `hf_model_card/` | 16 | predicted | `experiments/harness_reeval/all_harness_pairs.csv`; `experiments/evalspec_worked_example/records` |
| `evalplus/` | 5 | predicted | `experiments/harness_reeval/all_harness_pairs.csv` |
| `papers_with_code/` | 1 | predicted | `experiments/harness_reeval/all_harness_pairs.csv` |
| `archiv_paper_extraction/` | 16 | predicted | Section 5 and Appendices G and H of the paper (results read from papers by a language model) |
| `evalspec_controlled_runs/` | 64 | author-reported | the paper's own experiments: prompt format and temperature (E1), scoring mode (E2), harness version (E3), the model grid, the judge panel, and the re-run of Gemma-2-9B on BBH |

The 64 author-reported records are the authors' own controlled runs, written as
EvalSpec records. They are the only records in the sample with first-hand fields, and
none of them reaches the Required tier: the experiment logs do not hold a prompt hash,
and most hold no run time.

To leave them out, delete `data/evalspec_controlled_runs/`, set `files` and `records`
in `snapshot.json` to the new counts, and build again.

## Changing the sample

Edit `source/snapshot/build_snapshot.py` and run it. It rewrites `data/` and
`snapshot.json`.
