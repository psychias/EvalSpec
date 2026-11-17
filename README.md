# EvalSpec site

The public site for EvalSpec, the minimum reporting standard for LLM evaluation results
proposed in "LLM Evaluation Discrepancies And How To Prevent Them" (Findings of EACL 2027).

The site holds the specification, a registry of the records in the EvalSpec datastore,
a page that writes and checks records for submission, statistics, the data releases and
the interactive article. It is static: plain files, no server-side code, no tracking and
no request to any other site.

## Look at it

Open `index.html` in a browser. Or serve the folder:

    python -m http.server 8000        # then http://localhost:8000

## Pages

| Page | What it is for |
|---|---|
| `index.html` | What EvalSpec is, the lookup by Hugging Face id, the paper's findings, the three ways to report a result |
| `registry.html` | The transparency board (sources ranked by how much of their procedure they report themselves), every record, and the model and benchmark pairs with more than one record |
| `model.html?id=<hf id>` | Every record for one model, benchmark by benchmark, with what each source says about its procedure |
| `spec.html` | EvalSpec 1.0: fields, scoring modes, provenance, conformance, record formats, relation to Every Eval Ever |
| `submit.html` | Write a record, check it in the browser, convert it into a datastore file, open a pull request |
| `statistics.html` | Counts recomputed from the datastore at each build, and the frozen figures of the paper's corpus |
| `data.html` | Every release in one place, and how to rebuild the site |
| `article.html` | The interactive article (the previous site), unchanged in content |

## Build

    python source/build.py                           # from the sample bundled in datastore/
    python -m unittest discover -s tests             # 47 tests

    python tools/fetch_datastore.py                  # copy the datastore from Hugging Face into datastore_cache/
    python source/build.py --datastore datastore_cache

The build needs Python 3.9 or later and nothing else (tested with 3.9, 3.11 and 3.13, which
write identical files). Optional:
`jsonschema` for the schema tests, `node` for the tests that compare the browser validator
with the Python one, `huggingface_hub` for the download.

The pages in this branch are built from the full datastore, `Hermeneia/EvalSpec_Dataset` on
Hugging Face: 12 files with one record per line, 46,559 results. The registry shows 45,705
of them; the other 854 are results read from arXiv papers that carry no numeric score, and
the build leaves those out. Without `--datastore` the build reads the bundled sample of 122
records instead and says so on its pages (see `datastore/README.md`).

The dataset is gated: downloading it needs a Hugging Face account that has accepted its
terms (`huggingface-cli login`).

## Settings: `config.json`

Everything that may change is in this one file.

- `datastore.hf_repo` is the Hugging Face dataset. When the dataset is renamed, change this
  value and build again: every link and every command on the site is derived from it.
  `datastore.name` is the name shown to readers ("EvalSpec").
- `paper.url` and `paper.pdf_url`: while empty, the site shows "Paper (link pending)".
- `site.url`: the address the site is served at, used for the canonical link, the preview
  image and the sitemap.
- `home.featured`: the model and benchmark shown in the box at the top of the home page.
- `links`, `licences`, `paper.authors`, `paper.bibtex`.

## How a record gets onto the site

1. Someone writes records: with the form on the Submit page, with the released hook for
   lm-evaluation-harness, or by having a language model read a publication.
2. They check them (Submit page, or `python tools/evalspec.py check records.json -v`) and
   convert them into a datastore file, `data/<source>-<id>.jsonl` with one record per line
   (Submit page, or `python tools/evalspec.py to-eee`).
3. They open a pull request on the Hugging Face dataset.
4. A maintainer checks the files of the pull request with `python tools/evalspec.py check`
   and merges it. A record has to be well formed; it does not have to reach a tier.
5. The site is rebuilt. `.github/workflows/rebuild.yml` does this once a day.

## How the registry reads the datastore

`source/ingest.py` reads a folder of Every Eval Ever files, either one record per `.json`
file or one record per line of a `.jsonl` file; `tools/evalspec.py` reads the 21 fields out
of each result.

- **Two tracks.** A record whose provenance tag is `source-reported` is shown as
  author-reported. Every other record is shown as predicted. The tag is read from
  `source_metadata.additional_details.evidence_source`; for files without one it is
  inferred from the kind of file (see "Provenance and tracks" on the Spec page).
- **Sources.** Records are grouped by source: a leaderboard, a model card, a run, or a
  paper. Each paper is its own source, keyed by its arXiv id, whoever uploads its records.
- **The board.** Sources are ordered by the share of procedure fields (the Required fields
  other than `model_id` and `benchmark_id`) they report first-hand, then by the share a
  language model read from the source, then by the share a pipeline inferred. Sources with
  equal shares share a rank. Scores are never ranked.
- **Superseded records.** Once a source has an author-reported record for a model and
  benchmark, its predicted records for that pair are still listed but no longer counted.
- **Name matching.** Models are matched by name without the organisation, benchmarks by
  the alias table in `source/aliases.json`, both as in the paper's pipeline.
- **Pairs.** For a model and benchmark with several records, the registry states whether
  the records say the scores were produced the same way, and whether they are independent
  measurements. A difference counts only between values that were not inferred.

## Deploy

The folder is the site. Serve it from the root of a GitHub Pages branch, as the previous
site was; `.nojekyll` is present. Commit the built files.

- `.github/workflows/check.yml` runs the tests on every push and pull request.
- `.github/workflows/rebuild.yml` copies the datastore, rebuilds, and commits the result
  when the records have changed. It needs permission to push to the branch.

Neither workflow has been run: they were written without access to GitHub Actions.

## What is where

    config.json                 settings
    index.html, registry.html … the built pages (written by the build)
    data/                       what the pages load (written by the build); data/paper/ holds the article's tables
    spec/fields.json            the 21 fields: tier, type, rule, EEE path. Validators, form, tables and schema follow it
    spec/examples/              worked examples
    tools/evalspec.py           the validator and converter (command line, no dependencies)
    tools/fetch_datastore.py    copies the datastore from Hugging Face
    assets/js/evalspec.js       the same validator for the browser
    assets/js/site.js           shared by all pages: data loading, lookup, drawing a record
    assets/js/registry.js, model.js, submit.js, home.js      one script per page
    assets/js/article.js, assets/css/article.css             the article and its figures
    assets/css/site.css         every other style
    source/build.py             the build
    source/ingest.py            datastore -> records, sources, models, pairs, statistics
    source/blocks.py            HTML fragments used by the templates
    source/pages/               page templates; article.src.html is the article
    source/figs.py, refs.json   the article's figures and references
    source/aliases.json         name normalisation
    source/snapshot/            writes the bundled sample
    datastore/                  the bundled sample
    tests/                      tests

## Changing things

- **A field, a tier or a description**: `spec/fields.json`. The form on the Submit page, the
  tables on the Spec page and the JSON Schema are generated from it.
- **A rule** (what counts as valid, when a field applies): `tools/evalspec.py` and
  `assets/js/evalspec.js`. The tests run both on the same inputs and fail when they disagree.
- **The text of a page**: `source/pages/<page>.html`, then build.
- **The article**: `source/pages/article.src.html`, `source/figs.py`, `source/refs.json`.
- **The look**: `assets/css/site.css`. Classes start with `es-`.

## Points to decide

These were settled in order to finish the site and are easy to change.

- **The paper's own runs as author-reported records.** The sample holds 64 records from the
  controlled experiments, written as EvalSpec records. `datastore/README.md` says how to
  leave them out.
- **EEE paths.** The paper fixes the path of `judge_model` only. The other paths in
  `spec/fields.json` are a reading, listed as an open question on the Spec page.
- **Review.** The Submit page says a maintainer runs the validator on each pull request.
- **Licences.** `config.json` states MIT for data and for code, as on the dataset card and
  in the code repository. The validator in `tools/` and the site's scripts are new files.
- **One id per model.** A model's page is headed by the id that includes an organisation,
  and lists the other spellings.
- **Superseded records.** That a source's predicted records stop counting once the source
  reports the same model and benchmark itself is a rule of this site, not of the paper.
- **`source_kind`.** A flat record may say whether its source is a paper, a leaderboard, a
  model card or an evaluation run. Files without it are classified by what they are.
- **The address.** `site.url` in `config.json` is the address of the previous site.

## What has and has not been checked

Checked: the 45 tests; every page in headless Chrome at desktop and phone width, with no
console error and no request to another site; the lookup, the registry views, the form,
the check, the conversion and the "Correct this record" route, driven by script; the board
drawn in the browser against the board computed by the build, on the sample and on the
synthetic datastore; the new pages with axe-core (WCAG 2.1 A and AA rules, no finding);
HTML parsing of every page.

Not checked: the two workflows and the pull-request steps on Hugging Face. The
article keeps eight accessibility findings it already had (for example `dt` and `dd`
outside a `dl` in one figure, and a faint footnote back-link); its markup was left as it is.

## Credits

The article's layout follows the open-source Distill article template (Apache-2.0, The
Distill Template Authors). The typefaces are Atkinson Hyperlegible Next and Atkinson
Hyperlegible Mono (SIL Open Font License 1.1, `assets/fonts/OFL.txt`), served from this
folder. EvalSpec is an extended version of the Every Eval Ever schema.
