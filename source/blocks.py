"""HTML fragments built from the spec, the config and the ingested datastore.

Each function returns a string. Everything that comes from a record or from the
config goes through esc(), so a model name can never inject markup.
"""
from __future__ import annotations

import html
import json
import math

import ingest

E = ingest.E
TIER_LABEL = {"none": "Below Required", "required": "Required", "recommended": "Recommended", "full": "Full"}
TYPE_LABEL = {"string": "text", "string_or_null": "text or null", "enum": "one of four values", "integer": "integer",
              "number": "number", "integer_or_list": "integer or list", "sha256": "sha256:&lt;64 hex digits&gt;",
              "timestamp": "ISO 8601 date or date-time", "url": "http(s) address"}
APPLIES = {"generation": "when scoring_mode is generation", "judge": "when a judge produces the score"}


def esc(text) -> str:
    return html.escape(str(text), quote=True)


def path(text) -> str:
    """An EEE path that may wrap after each dot."""
    return esc(text).replace(".", ".<wbr>")


def wrap_name(text) -> str:
    """A field name that may wrap after each underscore."""
    return esc(text).replace("_", "_<wbr>")


def num(n) -> str:
    return f"{n:,}"


def share(part, whole) -> float:
    return 100.0 * part / whole if whole else 0.0


def pct(part, whole) -> str:
    """A percentage for display: no decimals, but never '0%' or '100%' for a value that is not exactly that."""
    v = share(part, whole)
    if 0 < v < 1:
        return "under 1%"
    if 99 < v < 100:
        return "over 99%"
    return f"{math.floor(v + 0.5)}%"            # halves round up, as Math.round does in the browser


def meter(cov, thin=False) -> str:
    """Stacked bar: first-hand, read by an LLM, inferred. The empty rest is what is not on record."""
    of = cov["of"]
    parts = [("is-first", cov["first_hand"], "first-hand"), ("is-llm", cov["llm"], "read by an LLM"), ("is-inferred", cov["inferred"], "inferred")]
    label = ", ".join(f"{pct(n, of)} {name}" for _, n, name in parts if n) or "nothing on record"
    tip = "; ".join(f"{name}: {num(n)} of {num(of)}" for _, n, name in parts) + f"; not on record: {num(of - cov['have'])} of {num(of)}"
    segs = "".join(f'<i class="{cls}" style="width:{share(n, of):.2f}%"></i>' for cls, n, _ in parts if n)
    return (f'<span class="es-meter{" is-thin" if thin else ""}" role="img" tabindex="0" aria-label="{esc(label)}" '
            f'data-tip="{esc(tip)}">{segs}</span>')


def provenance_key(with_missing=True) -> str:
    items = [("is-first", "reported first-hand"), ("is-llm", "read from the source by an LLM"), ("is-inferred", "inferred by a pipeline")]
    if with_missing:
        items.append(("is-missing", "not on record"))
    return '<ul class="es-key">' + "".join(f'<li><span class="es-mark {c}"></span>{t}</li>' for c, t in items) + "</ul>"


# ---------------------------------------------------------------- home

def tier_columns(spec) -> str:
    out = []
    for tier in spec["tiers"]:
        fields = [f for f in spec["fields"] if f["tier"] == tier["id"]]
        items = "".join(f'<li>{esc(f["name"])}' + (f'<small>{esc(APPLIES[f["applies"]])}</small>' if f["applies"] != "always" else "") + "</li>"
                        for f in fields)
        out.append(f'<div><h3>{esc(tier["label"])} <span class="es-small">{len(fields)} fields</span></h3>'
                   f'<p>{esc(tier["description"])}</p><ul>{items}</ul></div>')
    return '<div class="es-tiers">' + "".join(out) + "</div>"


def board_rows(sources, limit=None) -> str:
    rows = []
    for s in sources[:limit]:
        cov = s["cov"]
        ref = f'<span class="es-sub">{esc(s["kind"])}{", " + esc(s["ref"]) if s["ref"] else ""}</span>'
        rows.append(f'<tr><td class="es-rank">{s["rank"]}</td><td>{esc(s["label"])}{ref}</td>'
                    f'<td class="es-num">{num(s["n"])}</td><td>{meter(cov)}</td>'
                    f'<td class="es-num">{pct(cov["first_hand"], cov["of"])}</td><td class="es-num">{pct(cov["have"], cov["of"])}</td></tr>')
    return "".join(rows)


def board_preview(sources, limit=5) -> str:
    return ('<div class="es-scroll"><table class="es-table"><thead><tr><th scope="col">Rank</th><th scope="col">Source</th>'
            '<th scope="col" class="es-num">Records</th><th scope="col">Procedure fields on record</th>'
            '<th scope="col" class="es-num">First-hand</th><th scope="col" class="es-num">On record</th></tr></thead>'
            f'<tbody>{board_rows(sources, limit)}</tbody></table></div>' + provenance_key(False))


def registry_sentence(stats) -> str:
    t = stats["tracks"]
    return (f'The registry holds <b>{num(stats["records"])}</b> records for <b>{num(stats["models"])}</b> models and '
            f'<b>{num(stats["benches"])}</b> benchmarks, from <b>{num(stats["sources"])}</b> sources. '
            f'{num(t["author-reported"])} are author-reported and {num(t["predicted"])} are predicted.')


def sample_note(meta) -> str:
    snap = meta.get("snapshot") or {}
    if snap.get("kind") != "sample":
        return ""
    return (f'<div class="es-note"><p>This build reads the sample bundled with the site: {num(snap.get("records", 0))} records that the paper and its '
            f'code repository quote in full. The full corpus of the paper has 46,559 records and lives in the '
            f'<a href="{esc(meta["datastore"]["url"])}">{esc(meta["datastore"]["name"])} datastore</a>; '
            f'the <a href="data.html#rebuild">Data page</a> says how to build the site from it.</p></div>')


def try_links(models, limit=3) -> str:
    best = sorted(models, key=lambda m: (-m["sources"], -m["n"], m["id"]))[:limit]
    return ", ".join(f'<a href="model.html?id={esc(m["id"])}">{esc(m["id"])}</a>' for m in best)


def authors(cfg) -> str:
    return '<ul class="es-authors">' + "".join(
        f'<li><a href="{esc(a["url"])}">{esc(a["name"])}</a> <small>{esc(a["affiliation"])}</small></li>' for a in cfg["paper"]["authors"]) + "</ul>"


def paper_link(cfg, label="Paper") -> str:
    url = cfg["paper"].get("url")
    if url:
        return f'<a href="{esc(url)}">{esc(label)}</a>'
    return f'<span class="es-pending" title="The link will be added when the paper is online">{esc(label)} (link pending)</span>'


# ---------------------------------------------------------------- statistics

def tiles(stats) -> str:
    t, o = stats["tracks"], stats["overlap"]
    items = [(num(stats["records"]), "records"), (num(stats["models"]), "models"), (num(stats["benches"]), "benchmarks"),
             (num(stats["sources"]), "sources"), (num(t["author-reported"]), "author-reported records"),
             (num(t["predicted"]), "predicted records"),
             (num(stats["tiers"]["required"] + stats["tiers"]["recommended"] + stats["tiers"]["full"]), "records at the Required tier or above")]
    return '<ul class="es-tiles">' + "".join(f"<li><b>{v}</b><span>{esc(k)}</span></li>" for v, k in items) + "</ul>"


def field_rows(fields, spec) -> str:
    """Meter list: one row per EvalSpec field, grouped by tier."""
    out = []
    for tier in spec["tiers"]:
        rows = []
        for f in fields:
            if f["tier"] != tier["id"]:
                continue
            cov = {"of": f["applies"], "have": f["have"], "first_hand": f["first_hand"], "llm": f["llm"], "inferred": f["inferred"]}
            rows.append(f'<dt>{esc(f["name"])}</dt><dd>{meter(cov)}</dd>'
                        f'<dd class="es-num">{num(f["have"])} of {num(f["applies"])}</dd>')
        out.append(f'<p class="es-rowhead">{esc(tier["label"])}</p><dl class="es-rows">{"".join(rows)}</dl>')
    return "".join(out)


def count_rows(counts: dict, total: int, labels=None) -> str:
    """Ranked bars for a small set of counts."""
    top = max(counts.values(), default=0)
    out = []
    for key, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        label = (labels or {}).get(key, key)
        out.append(f'<dt class="is-plain">{esc(label)}</dt><dd><div class="es-bar" role="img" aria-label="{num(n)} of {num(total)}">'
                   f'{f"""<i style="width:{share(n, top):.2f}%"></i>""" if n else ""}</div></dd><dd class="es-num">{num(n)} <span class="es-small">({pct(n, total)})</span></dd>')
    return '<dl class="es-rows">' + "".join(out) + "</dl>"


def overlap(stats) -> str:
    o = stats["overlap"]
    b = o["bands"]
    total = o["cells"]
    if not total:
        return '<p class="es-small">No model and benchmark pair in the datastore is reported by more than one source.</p>'
    parts = [("is-b1", b["within1"], "within 1 pp"), ("is-b2", b["within5"], "1 to 5 pp apart"), ("is-b3", b["over5"], "more than 5 pp apart"),
             ("is-b4", b["unscaled"], "on scales that cannot be compared")]
    bar = "".join(f'<i class="{c}" style="width:{share(n, total):.2f}%" title="{num(n)} {esc(t)}">{num(n) if share(n, total) >= 6 else ""}</i>'
                  for c, n, t in parts if n)
    key = "".join(f'<li><span class="es-mark" style="background:var(--{v})"></span>{num(n)} {esc(t)}</li>'
                  for (c, n, t), v in zip(parts, ("blue-2", "gold-2", "gold", "track")) if n)
    return (f'<p>{num(total)} of {num(stats["pairs"])} model and benchmark pairs ({pct(total, stats["pairs"])}) are reported by more than one source.</p>'
            f'<div class="es-bands" role="img" aria-label="How far apart the sources are">{bar}</div><ul class="es-key">{key}</ul>')


def top_models(models, limit=10) -> str:
    best = sorted(models, key=lambda m: (-m["sources"], -m["n"], m["id"]))[:limit]
    rows = "".join(f'<tr><td class="es-id"><a href="model.html?id={esc(m["id"])}">{esc(m["id"])}</a></td>'
                   f'<td class="es-num">{num(m["sources"])}</td><td class="es-num">{num(m["n"])}</td><td class="es-num">{num(m["benches"])}</td></tr>'
                   for m in best)
    return ('<div class="es-scroll"><table class="es-table"><thead><tr><th scope="col">Model</th><th scope="col" class="es-num">Sources</th>'
            f'<th scope="col" class="es-num">Records</th><th scope="col" class="es-num">Benchmarks</th></tr></thead><tbody>{rows}</tbody></table></div>')


# ---------------------------------------------------------------- spec

def field_tables(spec) -> str:
    out = []
    for tier in spec["tiers"]:
        fields = [f for f in spec["fields"] if f["tier"] == tier["id"]]
        rows = []
        for f in fields:
            when = f'<span class="es-when">{esc(APPLIES[f["applies"]])}</span>' if f["applies"] != "always" else ""
            new = '<span class="es-new">no EEE path: added by EvalSpec</span>' if f.get("new_in_evalspec") else ""
            why = f'<span class="es-why">In the paper: {esc(f["because"])}</span>' if f.get("because") else ""
            kind = TYPE_LABEL[f["type"]]
            if f["type"] == "enum":
                kind = "<br>".join(f"<code>{esc(v)}</code>" for v in f["enum"])
            rows.append(f'<tr id="field-{esc(f["name"])}"><td><code>{wrap_name(f["name"])}</code>{when}</td>'
                        f'<td>{esc(f["description"])}. {esc(f["guidance"])}{why}</td>'
                        f'<td class="es-type">{kind}</td>'
                        f'<td class="es-path"><code>{path(f["eee_path"])}</code>{new}</td></tr>')
        out.append(f'<table class="es-fieldtable"><caption>{esc(tier["label"])} <small>For {esc(tier["purpose"])}. {esc(tier["description"])} '
                   f'{len(fields)} fields.</small></caption><thead><tr><th scope="col">Field</th><th scope="col">Meaning</th>'
                   f'<th scope="col">Value</th><th scope="col">Where it lives in an EEE file</th></tr></thead><tbody>{"".join(rows)}</tbody></table>')
    return "".join(out)


def definition_list(items, key="id", text="definition") -> str:
    return '<dl class="es-deflist">' + "".join(f"<dt>{esc(i[key])}</dt><dd>{esc(i[text])}</dd>" for i in items) + "</dl>"


def example(title, note, obj, name) -> str:
    code = esc(json.dumps(obj, indent=2, ensure_ascii=False))
    (report,) = [E.check(v) for v in E.views(obj)]
    c = report["coverage"]["required"]
    tier = "below the Required tier" if report["tier"] == "none" else f'{TIER_LABEL[report["tier"]]} tier'
    tall = ' class="is-tall"' if code.count("\n") > 32 else ""
    return (f'<div class="es-example"><h3>{esc(title)}</h3><p>{note}</p>'
            f'<pre tabindex="0" aria-label="{esc(title)}"{tall}><code>{code}</code></pre>'
            f'<p class="es-small">Validator result: {tier}, {c["have"]} of {c["of"]} Required fields that apply. '
            f'<a href="spec/examples/{esc(name)}">Download</a>, or <a href="submit.html?example={esc(name)}#check">open it in the validator</a>.</p></div>')


def record_keys(spec) -> str:
    rows = "".join(f'<tr><td><code>{wrap_name(k["name"])}</code></td><td>{esc(k["description"])}</td><td class="es-type">{esc(k["value"])}</td>'
                   f'<td class="es-path"><code>{path(k["eee_path"])}</code></td></tr>' for k in spec["record_keys"])
    return ('<table class="es-fieldtable"><thead><tr><th scope="col">Key</th><th scope="col">Meaning</th><th scope="col">Value</th>'
            f'<th scope="col">Where it lives in an EEE file</th></tr></thead><tbody>{rows}</tbody></table>')


# ---------------------------------------------------------------- submit, data

def example_buttons(names: dict) -> str:
    """names: file name -> label. Each button loads one worked example into the validator."""
    return ", ".join(f'<button class="es-expander" type="button" data-example="{esc(n)}">{esc(label)}</button>' for n, label in names.items()) + "."


def releases(rows) -> str:
    """rows: (name, note, what it holds, version and licence, [(label, href)])."""
    out = []
    for name, note, holds, version, links in rows:
        items = "".join(f'<li><a href="{esc(href)}">{esc(label)}</a></li>' if href else f"<li>{label}</li>" for label, href in links)
        out.append(f'<tr><td>{esc(name)}{f"<small>{esc(note)}</small>" if note else ""}</td><td>{holds}</td><td>{version}</td><td><ul>{items}</ul></td></tr>')
    return "".join(out)


def paper_sources(rows) -> str:
    """The frozen source table of the paper (data/paper/sources.csv)."""
    out = []
    for r in rows:
        total = r["source"] in ("Leaderboard subtotal", "Total")
        cells = "".join(f'<td class="es-num">{num(int(r[k]))}</td>' for k in ("records", "models", "benchmarks"))
        name = f"<b>{esc(r['source'])}</b>" if total else esc(r["source"])
        out.append(f"<tr><td>{name}</td>{cells}</tr>")
    return "".join(out)
