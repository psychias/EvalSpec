#!/usr/bin/env python3
"""Builds the site.

    python source/build.py                       reads the sample bundled in datastore/
    python source/build.py --datastore PATH      reads a copy of the full datastore (tools/fetch_datastore.py makes one)

Reads   config.json, spec/fields.json, source/pages/*.html and a folder of EEE files.
Writes  the pages (*.html), the data they load (data/*.js, data/model/*.js), the downloads
        (data/*.csv, data/stats.json) and the JSON Schema (spec/evalspec-<version>.schema.json).

The result is plain static files. It can be served by any web server or opened from disk.
"""
from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import json
import math
import pathlib
import re
import shutil
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import blocks  # noqa: E402
import figs    # noqa: E402
import ingest  # noqa: E402

E = ingest.E
esc = blocks.esc
PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")
NAV = [("registry.html", "Registry"), ("spec.html", "Spec"), ("submit.html", "Submit"),
       ("statistics.html", "Statistics"), ("data.html", "Data"), ("article.html", "Article")]
EXAMPLES = {            # worked examples: file in spec/examples/ -> label on the Submit page
    "required-generation.json": "a record at the Required tier",
    "required-judge.json": "a judged score",
    "hook-output.json": "what the released hook writes",
    "predicted.json": "a predicted record",
    "full-tier.eee.json": "a datastore file at the Full tier",
}
RECORDS_PER_SHARD = 300


# ---------------------------------------------------------------- small helpers

def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def js(name: str, value) -> str:
    """A data file the pages load with a script tag, so that they also work when opened from disk."""
    return f"window.{name} = {json.dumps(value, ensure_ascii=False, separators=(',', ':'))};\n"


def versioned(path: str) -> str:
    """The path with a short hash of the file, so that a browser never pairs a new page with an old script."""
    return f"{path}?v={hashlib.sha1((ROOT / path).read_bytes()).hexdigest()[:8]}"


def fill(template: str, values: dict, name: str) -> str:
    """Replaces {{key}} in one pass. A key without a value stops the build."""
    unknown = sorted(set(PLACEHOLDER.findall(template)) - set(values))
    if unknown:
        sys.exit(f"{name}: no value for {', '.join('{{' + k + '}}' for k in unknown)}")
    return PLACEHOLDER.sub(lambda m: str(values[m.group(1)]), template)


def long_date(day: datetime.date) -> str:
    return f"{day.day} {day:%B %Y}"


# ---------------------------------------------------------------- what the pages load

def featured_cell(cfg: dict, reg: dict) -> dict | None:
    """The model and benchmark shown on the home page: the configured pair, or the pair with the most sources."""
    want = (cfg.get("home") or {}).get("featured") or {}
    key = (ingest.model_key(want.get("model_id", "")), ingest.benchmark(want.get("benchmark_id", ""))[0])
    cells = {(c["model"], c["bench"]): c for c in reg["cells"]}
    cell = cells.get(key) or max(reg["cells"], key=lambda c: (c["sources"], c["spread"] or 0), default=None)
    return {"model": cell["model"], "bench": cell["bench"]} if cell else None


def write_data(cfg: dict, reg: dict, meta: dict) -> dict:
    """Writes data/ and returns the facts about it that the pages need."""
    spec = E.SPEC
    shards = max(1, min(512, math.ceil(len(reg["records"]) / RECORDS_PER_SHARD)))
    # the registry file carries no date, so that it changes only when the records do
    full = ingest.payload(reg, {k: meta[k] for k in ("snapshot", "datastore")})
    build_id = hashlib.sha1(json.dumps(full, sort_keys=True).encode("utf-8")).hexdigest()[:8]

    write("data/registry.js", js("EVALSPEC_REGISTRY", full))
    shutil.rmtree(ROOT / "data" / "model", ignore_errors=True)
    for n in range(shards):
        keys = {m["key"] for m in reg["models"] if ingest.shard_of(m["key"], shards) == n}
        write(f"data/model/{n}.js", f"window.EVALSPEC_SHARDS = window.EVALSPEC_SHARDS || {{}};\n"
                                    f"window.EVALSPEC_SHARDS[{n}] = {json.dumps(ingest.payload(ingest.subset(reg, keys), {}), ensure_ascii=False, separators=(',', ':'))};\n")
    # the lookup index: [id, records, sources, benchmarks, other spellings]
    write("data/models.js", js("EVALSPEC_MODELS", [[m["id"], m["n"], m["sources"], m["benches"], m["names"]] for m in full["models"]]))
    write("data/examples.js", js("EVALSPEC_EXAMPLES", {name: json.loads(read(f"spec/examples/{name}")) for name in EXAMPLES}))
    site = {
        "name": cfg["site"]["name"], "built": meta["built"], "build": build_id, "sample": meta["snapshot"].get("kind") == "sample",
        "datastore": meta["datastore"], "shards": shards, "featured": featured_cell(cfg, reg),
        "model_aliases": {k: ingest.flat(v) for k, v in ingest.ALIASES["models"].items()},
        "counts": {k: reg["stats"][k] for k in ("records", "models", "benches", "sources")},
    }
    write("data/spec.js", js("EVALSPEC_SPEC", spec) + js("EVALSPEC_SITE", site))

    write("data/records.csv", ingest.records_csv(reg))
    write("data/board.csv", ingest.board_csv(reg))
    write("data/stats.json", json.dumps({"built": meta["built"], "datastore": meta["datastore"], "snapshot": meta["snapshot"],
                                         **reg["stats"]}, indent=2, ensure_ascii=False) + "\n")
    write(f"spec/evalspec-{spec['version']}.schema.json", json.dumps(E.json_schema(cfg["site"]["url"]), indent=2) + "\n")
    return site


# ---------------------------------------------------------------- the frame every page shares

MARK = ('<svg viewBox="0 0 22 22" aria-hidden="true"><rect x="1" y="2.5" width="20" height="4.6" rx="1" fill="#fff"/>'
        '<rect x="1" y="8.7" width="20" height="4.6" rx="1" fill="#fff" opacity=".55"/>'
        '<rect x="1.6" y="15.5" width="18.8" height="3.4" rx="1" fill="none" stroke="#fff" stroke-width="1.2" stroke-dasharray="2.4 1.8"/></svg>')


def frame(cfg: dict, meta: dict, page: str, title: str, description: str, body: str,
          scripts=(), styles=(), current: str | None = None, head: str = "") -> str:
    site, paper, links = cfg["site"], cfg["paper"], cfg["links"]
    here = ' aria-current="page"'
    nav = "".join(f'<li><a href="{href}"{here if href == (current or page) else ""}>{label}</a></li>' for href, label in NAV)
    css = "".join(f'<link rel="stylesheet" href="{versioned(s)}">\n' for s in ("assets/css/site.css", *styles))
    js_tags = "".join(f'<script src="{versioned(s)}" defer></script>\n' for s in ("data/spec.js", "assets/js/site.js", *scripts))
    address = site["url"] + ("" if page == "index.html" else page)
    stats = meta["stats"]
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{esc(address)}">
<meta property="og:type" content="{"article" if page == "article.html" else "website"}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{esc(address)}">
<meta property="og:image" content="{esc(site["url"])}assets/img/{"og.png" if page == "article.html" else "og-site.png"}">
<meta name="twitter:card" content="summary_large_image">
{head}<link rel="icon" href="favicon.svg" type="image/svg+xml">
{css}</head>
<body id="top">
<a class="skip" href="#main">Skip to the content</a>
<header class="es-top">
  <div class="es-top-in">
    <a class="es-brand" href="index.html"{' aria-current="page"' if page == "index.html" else ""}>{MARK}{esc(site["name"])}</a>
    <nav aria-label="Site"><ul class="es-nav">{nav}</ul></nav>
    <form class="es-find" action="model.html" method="get" role="search" aria-label="Find a model" data-lookup>
      <label class="sr" for="find">Hugging Face id of a model</label>
      <input id="find" name="id" type="search" placeholder="organisation/model" autocomplete="off" spellcheck="false">
      <button type="submit">Find reports</button>
    </form>
  </div>
</header>
{body}
<footer class="es-foot">
  <div class="es-foot-in">
    <div>
      <p><b>{esc(site["name"])} {esc(E.SPEC["version"])}</b></p>
      <p>{esc(site["tagline"])}, proposed in "{esc(paper["title"])}" ({esc(paper["venue"])}).</p>
      <p>Built on {esc(meta["built_long"])} from {blocks.num(stats["records"])} records. No tracking, no external requests.</p>
    </div>
    <ul>
      <li>{blocks.paper_link(cfg)}</li>
      <li><a href="article.html">Interactive article</a></li>
      <li><a href="{esc(links["code"])}">Code</a></li>
      <li><a href="{esc(meta["datastore"]["url"])}">{esc(meta["datastore"]["name"])} datastore</a></li>
    </ul>
    <ul>
      <li><a href="index.html#paper">Cite</a></li>
      <li><a href="{esc(links["issues"])}">Report a problem</a></li>
      <li><a href="{esc(links["eee"])}">Every Eval Ever</a></li>
      <li><a href="data.html#cite">Licences</a></li>
    </ul>
  </div>
</footer>
{js_tags}</body>
</html>
'''


# ---------------------------------------------------------------- the article

def figure_html(template: str) -> str:
    return re.sub(r"<!--FIG:(\w+)-->", lambda m: figs.FIGS[m.group(1)](), template)


def render_article(template: str) -> tuple[str, int, int]:
    """<cite k="a,b"></cite> becomes numbered citation markers, in order of first use; <fn>text</fn> becomes a numbered
    footnote whose text is collected in the appendix; <!--FOOTNOTES--> and <!--REFERENCES--> receive the lists."""
    refs = {r["key"]: r for r in json.loads(read("source/refs.json"))}
    order, notes = [], []

    def cite(m):
        nums = []
        for key in (k.strip() for k in m.group(1).split(",")):
            if key not in refs:
                sys.exit(f"article: unknown citation key {key}")
            if key not in order:
                order.append(key)
            nums.append(order.index(key) + 1)
        label = ", ".join(map(str, nums))
        return (f'<a class="cite-ref" href="#ref-{nums[0]}" data-refs="{",".join(map(str, nums))}" '
                f'aria-label="Reference {label}">[{label}]</a>')

    def note(m):
        notes.append(m.group(1).strip())
        n = len(notes)
        return f'<a class="fn-ref" id="fnref-{n}" href="#fn-{n}" data-fn="{n}" aria-label="Footnote {n}">{n}</a>'

    # one pass over both, so that footnotes and citations are numbered in reading order
    out = re.sub(r'<fn>(.*?)</fn>|<cite k="([^"]+)"></cite>',
                 lambda m: note(m) if m.group(1) is not None else cite(re.match(r'<cite k="([^"]+)"></cite>', m.group(0))),
                 figure_html(template), flags=re.S)
    notes = [re.sub(r'<cite k="([^"]+)"></cite>', cite, text) for text in notes]
    footnotes = "\n".join(f'  <li id="fn-{i}">{text} <a class="backlink" href="#fnref-{i}" aria-label="Back to text">[&#8617;]</a></li>'
                          for i, text in enumerate(notes, 1))

    def reference(i, r):
        link = f' <a href="{esc(r["url"])}">[link]</a>' if r["url"] else ""
        tail = ", ".join(esc(x) for x in (r["authors"], r["venue"], r["year"]) if x)
        return f'  <li id="ref-{i}"><span class="title">{esc(r["title"])}</span>{link}<br>{tail}.</li>'

    references = "\n".join(reference(i, refs[k]) for i, k in enumerate(order, 1))
    out = out.replace("<!--FOOTNOTES-->", f'<ol class="footnotes">\n{footnotes}\n</ol>')
    out = out.replace("<!--REFERENCES-->", f'<ol class="references">\n{references}\n</ol>')
    return out, len(notes), len(order)


def article_figures(template: str, ids) -> str:
    """Figures of the article, reused as they are on the Statistics page."""
    out = []
    for fid in ids:
        m = re.search(rf'<figure class="[^"]*" id="{fid}">.*?</figure>', template, flags=re.S)
        if not m:
            sys.exit(f"statistics: the article has no figure {fid}")
        out.append(re.sub(r"<fn>.*?</fn>|<cite k=\"[^\"]+\"></cite>", "", figure_html(m.group(0)), flags=re.S))
    return "\n".join(out)


def scholar_tags(cfg: dict) -> str:
    """Bibliographic meta tags for the article, as indexing services read them."""
    paper = cfg["paper"]
    tags = [("citation_title", paper["title"]), ("citation_conference_title", paper["venue_long"]),
            ("citation_publication_date", paper["year"])]
    for a in paper["authors"]:
        given, _, family = a["name"].partition(" ")
        tags += [("citation_author", f"{family}, {given}"), ("citation_author_institution", a["affiliation"])]
    if paper.get("pdf_url"):
        tags.append(("citation_pdf_url", paper["pdf_url"]))
    return "".join(f'<meta name="{k}" content="{esc(v)}">\n' for k, v in tags)


# ---------------------------------------------------------------- page contents

def common(cfg: dict, meta: dict) -> dict:
    """Values every template may use."""
    ds, paper, links, lic = meta["datastore"], cfg["paper"], cfg["links"], cfg["licences"]
    return {
        "datastore_name": esc(ds["name"]), "datastore_url": esc(ds["url"]), "hf_repo": esc(ds["hf_repo"]),
        "revision": esc(ds["revision"]), "data_dir": esc(ds["data_dir"]),
        "paper_title": esc(paper["title"]), "paper_venue": esc(paper["venue"]), "paper_status": esc(paper["status"]),
        "bibtex": esc(paper["bibtex"]), "cite_short": esc(paper["cite_short"]),
        "code_url": esc(links["code"]), "issues_url": esc(links["issues"]), "eee_url": esc(links["eee"]),
        "data_licence": esc(lic["data"]["name"]), "data_licence_url": esc(lic["data"]["url"]),
        "code_licence": esc(lic["code"]["name"]), "code_licence_url": esc(lic["code"]["url"]),
        "spec_version": esc(E.SPEC["version"]), "eee_version": esc(E.SPEC["extends"]["version"]),
        "sample_note": blocks.sample_note(meta), "provenance_key": blocks.provenance_key(),
        "built": esc(meta["built_long"]),
    }


def home(cfg, reg, meta, base):
    paper = cfg["paper"]
    button = (f'<a class="es-btn" href="{esc(paper["url"])}">Read the paper</a>' if paper.get("url")
              else '<span class="es-pending" title="The link will be added when the paper is online">Paper (link pending)</span>')
    full = ingest.payload(reg, {})
    return {**base, "try_links": blocks.try_links(full["models"]), "tier_columns": blocks.tier_columns(E.SPEC),
            "registry_sentence": blocks.registry_sentence(reg["stats"]), "board_preview": blocks.board_preview(reg["sources"]),
            "authors": blocks.authors(cfg), "paper_button": button}


def spec_page(cfg, reg, meta, base):
    spec = E.SPEC
    shown = [
        ("A record at the Required tier", "A flat record for a score obtained by generation. Eleven Required fields apply to it.", "required-generation.json"),
        ("A judged score", "When a judge produces the score, <code>judge_prompt_hash</code> and <code>judge_score_rule</code> apply as well.", "required-judge.json"),
        ("What the released hook writes", "The record printed in the paper, with its hash written in full. The hook names the benchmark in <code>benchmark</code> "
         "and leaves out two Required fields and the range of the score.", "hook-output.json"),
        ("A predicted record", "Read from a publication by a language model. One field was added from documentation and is tagged on its own.", "predicted.json"),
        ("A datastore file", "The EEE form of a record at the Full tier. Fields without an EEE slot sit in <code>generation_config.additional_details</code>.",
         "full-tier.eee.json"),
    ]
    examples = "".join(blocks.example(title, note, json.loads(read(f"spec/examples/{name}")), name) for title, note, name in shown)
    extra = ["prompt-template.txt", "judge-prompt.txt"]
    return {**base, "field_tables": blocks.field_tables(spec), "record_keys": blocks.record_keys(spec),
            "scoring_modes": blocks.definition_list(spec["scoring_modes"]),
            "provenance_tags": blocks.definition_list(spec["provenance_tags"]),
            "tracks": blocks.definition_list(spec["tracks"], key="label"), "examples": examples,
            "example_links": ", ".join(f'<a href="spec/examples/{n}">{n}</a>' for n in [*(s[2] for s in shown), *extra])}


def submit(cfg, reg, meta, base):
    predicted = json.dumps(json.loads(read("spec/examples/predicted.json")), indent=2, ensure_ascii=False)
    return {**base, "example_buttons": blocks.example_buttons(EXAMPLES), "predicted_example": esc(predicted)}


def statistics(cfg, reg, meta, base):
    stats, spec = reg["stats"], E.SPEC
    article = read("source/pages/article.src.html")

    def rows(track):
        if track != "all" and not stats["tracks"][track]:
            return f'<p class="es-small">No {track} records in the datastore yet.</p>'
        return blocks.field_rows(stats["fields"][track], spec)

    with open(ROOT / "data/paper/sources.csv", encoding="utf-8", newline="") as f:
        paper_rows = list(csv.DictReader(f))
    tags = {t["id"]: f'{t["id"]} ({t["class"].replace("llm", "read by an LLM")})' for t in spec["provenance_tags"]}
    return {**base, "files": blocks.num(stats["files"]), "tiles": blocks.tiles(stats),
            "field_rows_all": rows("all"), "field_rows_author": rows("author-reported"), "field_rows_predicted": rows("predicted"),
            "mode_rows": blocks.count_rows(stats["modes"], stats["records"]),
            "tag_rows": blocks.count_rows(stats["tags"], stats["records"], tags),
            "tier_rows": blocks.count_rows(stats["tiers"], stats["records"], blocks.TIER_LABEL),
            "overlap": blocks.overlap(stats), "top_models": blocks.top_models(ingest.payload(reg, {})["models"]),
            "paper_sources": blocks.paper_sources(paper_rows),
            "paper_figures": '<div class="d-article es-plain">' + article_figures(article, ["fig-coverage", "fig-overlap"]) + "</div>"}


def data_page(cfg, reg, meta, base):
    spec, ds, links = E.SPEC, meta["datastore"], cfg["links"]
    v, eee = spec["version"], spec["extends"]["version"]
    data, code = (f'<a href="{base[k + "_licence_url"]}">{base[k + "_licence"]}</a>' for k in ("data", "code"))
    stats = reg["stats"]
    rows = [
        (f'{ds["name"]} datastore', "the home of every submission",
         "One Every Eval Ever file per record, author-reported and predicted. New records arrive as pull requests.",
         f"EEE {esc(eee)} with eight added fields<br>{data}",
         [("Datastore on Hugging Face", ds["url"]), (f'The {blocks.num(stats["records"])} records on this site as CSV', "data/records.csv"),
          ("The board as CSV", "data/board.csv"), ("Counts as JSON", "data/stats.json")]),
        ("The paper's corpus", "frozen",
         "46,559 records from 12 sources, harmonized for the paper: ten leaderboards and structured repositories, 100 arXiv papers "
         "read by a language model, and Papers With Code. It is the set of predicted records the datastore starts from.",
         f"As analysed in the paper<br>{data}",
         [("In the datastore", ds["url"]), ("Sources table as CSV", "data/paper/sources.csv"), ("Coverage table as CSV", "data/paper/coverage.csv")]),
        (f"EvalSpec {v}", "the specification",
         "The 21 fields with their tiers, types and EEE paths; the JSON Schema of a flat record; the EEE schema the datastore follows; worked examples.",
         f"Version {esc(v)}<br>{data}",
         [("Specification", "spec.html"), ("fields.json", "spec/fields.json"), ("JSON Schema", f"spec/evalspec-{v}.schema.json"),
          ("EEE schema", f"spec/eee-{eee}-extended.schema.json"), ("Changes", "spec/CHANGELOG.md")]),
        ("Validator", "",
         "Checks a record, reports its tier and coverage, and converts it into a datastore file. One Python file without dependencies; "
         "the same rules run in the browser on the Submit page.",
         code, [("evalspec.py", "tools/evalspec.py"), ("evalspec.js", "assets/js/evalspec.js"), ("Check a record in the browser", "submit.html#check")]),
        ("Emission hook", "for lm-evaluation-harness",
         "Writes one record per task from the objects the harness returns at the end of a run.",
         code, [("lm_eval_to_evalspec.py", f'{links["code"]}/blob/main/src/emission_hooks/lm_eval_to_evalspec.py'), ("How to use it", "submit.html#route-run")]),
        ("Code and experiment records", "",
         "The extraction and analysis pipeline, and the logs of the controlled experiments on prompt format, temperature, scoring mode, "
         "harness version and judges.",
         f"{code} (code)<br>{data} (records)", [("Code repository", links["code"])]),
        ("Tables behind the article", "",
         "The numbers drawn in the figures of the interactive article.",
         data, [(n, f"data/paper/{n}") for n in ("case_studies.csv", "coverage.csv", "sources.csv", "single_setting_change.csv",
                                                  "judge_sensitivity.csv", "evalspec_fields.json")]),
        ("The paper", "", f'{esc(cfg["paper"]["title"])}. {esc(cfg["paper"]["venue"])}. {esc(cfg["paper"]["status"])}.', "",
         [(blocks.paper_link(cfg), ""), ("Interactive article", "article.html")]),
    ]
    path, shortened = example_file(reg)
    doc = json.loads((meta["root"] / path).read_text(encoding="utf-8-sig"))
    if len(doc["evaluation_results"]) > 1:
        doc["evaluation_results"], shortened = doc["evaluation_results"][:1], True
    caption = f'The file <code>{esc(path)}</code> of the datastore this site was built from' + (", shortened to its first result." if shortened else ".")
    return {**base, "releases": blocks.releases(rows), "file_example": esc(json.dumps(doc, indent=2, ensure_ascii=False)),
            "file_example_caption": caption}


def example_file(reg) -> tuple[str, bool]:
    """A datastore file to show on the Data page: an author-reported one when there is one."""
    recs = sorted(reg["records"], key=lambda r: (r["report"]["track"] != "author-reported", -r["report"]["coverage"]["required"]["have"], r["file"]))
    return recs[0]["file"], False


def article(cfg, reg, meta, base):
    link = blocks.paper_link(cfg, "Paper")
    return {**base, "paper_link_byline": link}


NOT_FOUND = '''<main id="main" class="es-page">
<div class="es-wrap">
  <header class="es-head">
    <h1>This page does not exist</h1>
    <p class="es-lead">The address may be out of date. To find the evaluation reports for a model, enter its Hugging Face id.</p>
  </header>
  <form class="es-lookup" action="model.html" method="get" role="search" aria-label="Evaluation reports for a model" data-lookup>
    <label class="es-label" for="lookup">Find the evaluation reports for a model</label>
    <div class="es-lookup-row">
      <input class="es-input" id="lookup" name="id" type="search" placeholder="Hugging Face id, for example google/gemma-2-9b" autocomplete="off" spellcheck="false">
      <button class="es-btn" type="submit">Find reports</button>
    </div>
  </form>
  <p class="es-actions" style="margin-top:24px"><a class="es-btn is-plain" href="index.html">Home</a> <a class="es-btn is-plain" href="registry.html">Registry</a></p>
</div>
</main>'''


# ---------------------------------------------------------------- build

def build(datastore: pathlib.Path | None, today: datetime.date) -> dict:
    cfg = json.loads(read("config.json"))
    ds = cfg["datastore"]
    url = f"https://huggingface.co/datasets/{ds['hf_repo']}"
    bundled = datastore is None
    root = ROOT / "datastore" if bundled else datastore.resolve()
    if not root.is_dir():
        sys.exit(f"no datastore folder at {root}")
    snapshot = json.loads(read("datastore/snapshot.json")) if bundled else {"kind": "full", "name": f'{ds["name"]} datastore'}
    file_base = "datastore/" if bundled else f"{url}/blob/{ds['revision']}/"

    reg = ingest.build(root, file_base, ds["data_dir"])
    if not reg["records"]:
        sys.exit(f"no EEE records under {root}")
    meta = {"snapshot": snapshot, "built": today.isoformat(),
            "datastore": {"name": ds["name"], "hf_repo": ds["hf_repo"], "revision": ds["revision"], "data_dir": ds["data_dir"],
                          "url": url, "file_base": file_base}}
    site = write_data(cfg, reg, meta)
    meta.update({"built_long": long_date(today), "stats": reg["stats"], "root": root})   # used by the templates only

    base = common(cfg, meta)
    name, paper = cfg["site"]["name"], cfg["paper"]
    reg_js = ["data/registry.js", "assets/js/registry.js"]
    pages = [   # file, template, values, title, description, scripts, styles, nav entry, extra head
        ("index.html", "home.html", home, f'{name}: {cfg["site"]["tagline"][0].lower()}{cfg["site"]["tagline"][1:]}',
         "EvalSpec names the 21 fields a published benchmark score has to carry so that a reader can tell what was measured. "
         "Look up the evaluation reports for a model, check a record, or submit your own.", ["assets/js/home.js"], [], None, ""),
        ("registry.html", "registry.html", lambda *a: a[3], f"{name} registry",
         "Every record in the EvalSpec datastore: which sources report their own evaluation procedure, the records field by field, "
         "and the model and benchmark pairs that more than one source reports.", reg_js, [], None, ""),
        ("model.html", "model.html", lambda *a: a[3], "Evaluation reports for a model",
         "The published evaluation results for one model, with the procedure each source reports for them.",
         ["assets/js/model.js"], [], "registry.html", ""),
        ("spec.html", "spec.html", spec_page, f'{name} {E.SPEC["version"]} specification',
         "The EvalSpec fields, their tiers, types and rules, the scoring-mode vocabulary, provenance tags, conformance, "
         "and how a record maps onto an Every Eval Ever file.", [], [], None, ""),
        ("submit.html", "submit.html", submit, f"Submit a report to {name}",
         "Write an EvalSpec record, check it in the browser, convert it into a datastore file and open a pull request.",
         ["assets/js/evalspec.js", "data/examples.js", "assets/js/submit.js"], [], None, ""),
        ("statistics.html", "statistics.html", statistics, f"{name} statistics",
         "What the records in the EvalSpec datastore say about how scores were produced, and the frozen figures of the paper's corpus.",
         ["assets/js/article.js"], ["assets/css/article.css"], None, ""),
        ("data.html", "data.html", data_page, f"{name} data and releases",
         "The EvalSpec datastore, the paper's corpus, the specification files, the validator, the code and the experiment records.",
         [], [], None, ""),
        ("article.html", "article.src.html", article, paper["title"],
         "An interactive article. The same model on the same benchmark is published at 34.10 by a leaderboard and at 68.20 by its developers. "
         "What goes into a benchmark score, what 46,559 published records keep of it, and which fields a published result would need to carry.",
         ["assets/js/article.js"], ["assets/css/article.css"], None, scholar_tags(cfg)),
    ]
    for page, template, values, title, description, scripts, styles, current, head in pages:
        body = fill(read(f"source/pages/{template}"), values(cfg, reg, meta, base), template)
        if page == "article.html":
            body, notes, refs = render_article(body)
            print(f"  article: {notes} footnotes, {refs} references")
        write(page, frame(cfg, meta, page, title, description, body, scripts, styles, current, head))
    # GitHub Pages shows 404.html for any missing address, also below the root: there its links need the root as their base
    root_path = "/" + cfg["site"]["url"].split("://", 1)[-1].partition("/")[2]
    base_tag = ('<script>if (location.protocol !== "file:" && location.pathname.indexOf("%s") === 0 && location.pathname.slice(%d).indexOf("/") >= 0) '
                '{ document.write(\'<base href="%s">\'); }</script>\n' % (root_path, len(root_path), root_path))
    write("404.html", frame(cfg, meta, "404.html", "Page not found", "This page does not exist.", NOT_FOUND, head=base_tag))
    write("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          + "".join(f'  <url><loc>{esc(cfg["site"]["url"] + ("" if p[0] == "index.html" else p[0]))}</loc><lastmod>{today.isoformat()}</lastmod></url>\n'
                    for p in pages if p[0] != "model.html") + "</urlset>\n")
    return {"registry": reg, "site": site}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build the EvalSpec site.")
    ap.add_argument("--datastore", type=pathlib.Path, help="folder holding a copy of the datastore; default: the bundled sample")
    ap.add_argument("--date", type=datetime.date.fromisoformat, default=datetime.date.today(), help="build date, YYYY-MM-DD (default: today)")
    args = ap.parse_args(argv)
    out = build(args.datastore, args.date)
    s = out["registry"]["stats"]
    print(f'built from {s["files"]:,} files: {s["records"]:,} records, {s["models"]:,} models, {s["benches"]:,} benchmarks, '
          f'{s["sources"]:,} sources; {s["tracks"]["author-reported"]:,} author-reported, {s["tracks"]["predicted"]:,} predicted; '
          f'{out["site"]["shards"]} per-model file(s)')
    skipped = out["registry"]["skipped"]
    if skipped:
        print(f"  {len(skipped):,} file(s) or result(s) left out, for example: {skipped[0]['file']} ({skipped[0]['reason']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
