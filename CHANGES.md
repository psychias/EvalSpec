# What changed from the previous site

The previous site was one page: the interactive article, with links to the code and the
dataset. This site is built around the standard. The article is one of its eight pages.

| | Previous site | This site |
|---|---|---|
| Purpose | Present the paper | Host EvalSpec as a reporting standard: specify it, look records up, take submissions, show what has been submitted. The paper is the evidence for it |
| Home page | The article | What EvalSpec is, a lookup by Hugging Face id, three findings of the paper, the ways to report a result, the citation |
| EvalSpec | A section and a figure in the article | A specification page: version, field tables with types and rules, scoring modes, provenance tags, conformance, the mapping onto Every Eval Ever, JSON Schema, worked examples, open questions |
| Relation to EEE | Mentioned in the article | Stated on the home page and the Spec page: EvalSpec is an extended version of the EEE schema, and every record is an EEE file |
| Records | Not shown; a link to the dataset | A registry: every record with its fields and who filled each one in, and a page for each model |
| Lookup | None | By Hugging Face id, with suggestions while typing. `organisation/name` and `name` find the same model |
| Leaderboard | None | A transparency board. Sources are ranked by how much of their procedure they report first-hand. Scores are never ranked |
| Author-reported and predicted | Not distinguished | Two tracks, derived from the provenance tag of each record and shown separately on every page |
| Submission | None | Form, check in the browser, conversion into a datastore file, pull-request instructions; a route for runs (the hook), for corrections of predicted records, and for records read by a language model |
| Validator | None | `tools/evalspec.py` on the command line and `assets/js/evalspec.js` in the browser, with the same rules, tested against each other |
| Statistics | Fixed figures inside the article | A page with counts recomputed from the datastore at every build, next to the paper's figures, which stay frozen |
| Releases | Three links in the top bar | A Data page that lists every release, with licences and the commands to rebuild the site |
| Name of the datastore | Linked as `EEE_datastore` | Called "EvalSpec". The Hugging Face address is one setting in `config.json` |
| Build | `source/build.py` wrote one page | `source/build.py` writes all pages from `config.json`, `spec/fields.json`, the templates and a folder of EEE files |
| Appearance | The article template | The article as it was. The new pages use a plainer style of their own: Atkinson Hyperlegible, a blue top bar, and one visual rule for provenance (solid: first-hand, grey: read by a language model, hatched: inferred, dashed outline: not on record) |

## What did not change

- The article's text, figures, footnotes and references. Three short sentences were added
  that point to the Spec, Registry and Data pages; nothing else was reworded.
- The article's script and styles, apart from the top bar and footer, which are now the
  site's own, and the typeface.
- The six tables behind the article's figures.

## What moved

- The article is at `article.html`. The address of the site now shows the new home page.
  A link to a section of the article written for the old address, such as `…/#audit`,
  is passed on to `article.html#audit`.
- The six tables are in `data/paper/` (they were in `data/`). `data/` now holds what the
  build writes.
- `source/article.src.html` is `source/pages/article.src.html`, and holds the body of the
  article only; the frame of the page comes from the build.
- The dates and links that were marked `EDIT` in the old page are settings in `config.json`.
