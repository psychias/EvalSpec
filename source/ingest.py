"""Reads a datastore folder and builds everything the site shows about it.

  registry = ingest.build(pathlib.Path("datastore"), file_base="datastore/")

The datastore is a folder of EEE files (data/<source>/<developer>/<model>/<uuid>.json),
or of files with one EEE record per line (data/<source>.jsonl).
Each evaluation result becomes one record. Records are grouped three ways:
by source (the transparency board), by model (the lookup by Hugging Face id) and
by model and benchmark (cells, where sources can be compared).
"""
from __future__ import annotations

import collections
import csv
import io
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
import evalspec as E  # noqa: E402

ALIASES = json.loads((HERE / "aliases.json").read_text(encoding="utf-8"))
# arXiv id -> title, for papers the datastore names only by id (tools/paper_titles.py writes it)
TITLES = json.loads((HERE / "paper_titles.json").read_text(encoding="utf-8")) if (HERE / "paper_titles.json").exists() else {}
SKIP_DIRS = {"aggregated", "samples", "naive"}          # folders the paper's own pipeline leaves out
TIER_ORDER = ["none", *E.TIERS]
# the fields that decide whether two scores were produced the same way
PROCEDURE = [f["name"] for f in E.FIELDS if f["tier"] == "required" and f["name"] not in (*E.IDENTITY, "evaluation_timestamp")]
ARXIV = re.compile(r"arxiv\.org/(?:abs|pdf|html)/([0-9]{4}\.[0-9]{4,5})")
KEY_FIELDS = ["scoring_mode", "harness_name", "harness_version", "n_shot", "benchmark_variant", "judge_model", "evaluation_timestamp"]


def flat(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(text).lower().replace("+", "plus"))


def model_key(model_id: str) -> str:
    """Organisation prefix and punctuation removed. Suffixes such as -instruct are kept: they name different checkpoints."""
    tail = str(model_id).strip().split("/")[-1]
    key = flat(tail) or tail.lower()                    # a name without ASCII letters or digits keeps its own text
    return flat(ALIASES["models"].get(key, key)) or key


def benchmark(name: str) -> tuple[str, str]:
    """(key, label) of a benchmark name. A bracketed note such as (3-Shot) is ignored when the full name is not known."""
    name = str(name).strip()
    for candidate in (name, re.sub(r"\s*\(.*?\)", "", name).strip()):
        label = ALIASES["benchmarks"].get(flat(candidate))
        if label:
            return flat(label), label
    bare = re.sub(r"\s*\(.*?\)", "", name).strip() or name
    return flat(bare), bare


def source_of(doc: dict) -> dict:
    """Who published the score. For results read from a paper, the paper; otherwise the named source."""
    sm = doc.get("source_metadata") or {}
    details = sm.get("additional_details") or {}
    links = [u for u in (E._first_url(r) for r in doc.get("evaluation_results") or [] if isinstance(r, dict)) if u]
    if details.get("paper_title") or details.get("arxiv_id"):       # the layout of the paper's own extraction pipeline
        arxiv = details.get("arxiv_id")
        label = TITLES.get(str(arxiv)) or details.get("paper_title") or f"arXiv:{arxiv}"
        return {"key": flat(arxiv or label), "label": label, "kind": "Paper", "ref": f"arXiv:{arxiv}" if arxiv else "",
                "url": details.get("paper_url") or (f"https://arxiv.org/abs/{arxiv}" if arxiv else "")}
    label = sm.get("source_name") or "Unnamed source"
    kind = details.get("source_kind")
    if kind not in E.SPEC["source_kinds"]:                          # older files do not say: go by what they are
        kind = ("Evaluation run" if sm.get("source_type") == "evaluation_run"
                else "Model card" if "model card" in label.lower() else "Leaderboard")
    url = (links[0] if kind == "Paper" and links else sm.get("source_organization_url") or (links[0] if links else ""))
    url = url if E.URL.match(str(url)) else ""
    arxiv = ARXIV.search(url) if kind == "Paper" else None        # the same key as the extraction pipeline uses for this paper
    return {"key": flat(arxiv.group(1)) if arxiv else flat(label), "label": label, "kind": kind,
            "ref": f"arXiv:{arxiv.group(1)}" if arxiv else "", "url": url}


def read(root: pathlib.Path, data_dir: str = "data"):
    """(relative path, document) for every EEE file under root, plus what could not be read."""
    base = root / data_dir if (root / data_dir).is_dir() else root
    docs, skipped = [], []
    for path in sorted(base.rglob("*.json")):
        rel = path.relative_to(root).as_posix()
        if SKIP_DIRS & set(path.relative_to(base).parts):
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8-sig"))
        except (ValueError, OSError) as e:
            skipped.append({"file": rel, "reason": f"not valid JSON ({e})"})
            continue
        if not E.is_eee(doc):
            skipped.append({"file": rel, "reason": "not an EEE record"})
            continue
        docs.append((rel, doc))
    for path in sorted(base.rglob("*.jsonl")):               # one EEE record per line
        rel = path.relative_to(root).as_posix()
        if SKIP_DIRS & set(path.relative_to(base).parts):
            continue
        try:
            lines = path.read_text(encoding="utf-8-sig").splitlines()
        except OSError as e:
            skipped.append({"file": rel, "reason": f"could not be read ({e})"})
            continue
        for n, line in enumerate(lines, 1):
            if not line.strip():
                continue
            try:
                doc = json.loads(line)
            except ValueError as e:
                skipped.append({"file": rel, "reason": f"line {n} is not valid JSON ({e})"})
                continue
            if not E.is_eee(doc):
                skipped.append({"file": rel, "reason": f"line {n} is not an EEE record"})
                continue
            docs.append((rel, doc))
    return docs, skipped


def build(root: pathlib.Path, file_base: str = "", data_dir: str = "data") -> dict:
    docs, skipped = read(root, data_dir)
    records, sources, models, benches = [], {}, {}, {}
    for rel, doc in docs:
        structure = E.eee_structure_errors(doc)
        src = source_of(doc)
        for view in E.views_from_eee(doc):
            rep = E.check(view)
            if not view["values"].get("model_id") or not view["values"].get("benchmark_id") or E._number(view["context"]["score"]) is None:
                skipped.append({"file": rel, "reason": "a result without a model, a benchmark or a numeric score"})
                continue
            v, ctx = view["values"], view["context"]
            mk, (bk, blabel) = model_key(v["model_id"]), benchmark(v["benchmark_id"])
            source = sources.setdefault(src["key"], {**src, "records": []})
            model = models.setdefault(mk, {"key": mk, "ids": collections.Counter(), "records": []})
            bench = benches.setdefault(bk, {"key": bk, "label": blabel, "records": []})
            model["ids"][v["model_id"]] += 1
            rec = {"i": len(records), "file": rel, "eid": ctx.get("evaluation_id") or "", "model": mk, "bench": bk, "source": src["key"],
                   "values": v, "provenance": view["provenance"], "report": rep, "context": ctx,
                   "pct": E.score_percent(ctx), "structure": structure}
            for group in (source, model, bench):
                group["records"].append(rec)
            records.append(rec)
    # a source's predicted records stop counting once the source reports the same model and benchmark itself
    own = {(r["source"], r["model"], r["bench"]) for r in records if r["report"]["track"] == "author-reported"}
    for r in records:
        r["superseded"] = r["report"]["track"] == "predicted" and (r["source"], r["model"], r["bench"]) in own
    for m in models.values():
        # the id shown for a model: one with an organisation, in its original capitals, then the most frequent
        m["id"] = sorted(m["ids"], key=lambda i: ("/" not in i, i == i.lower(), -m["ids"][i], i))[0]
        m["names"] = sorted(i for i in m["ids"] if i != m["id"])
    cells = build_cells([r for r in records if not r["superseded"]])
    return {"records": records, "sources": rank_sources(sources), "models": sorted(models.values(), key=lambda m: m["id"].lower()),
            "benches": sorted(benches.values(), key=lambda b: b["label"].lower()), "cells": cells, "skipped": skipped,
            "stats": statistics(records, sources, models, benches, cells, len({rel for rel, _ in docs})), "file_base": file_base}


def coverage(recs, tier="required") -> dict:
    out = collections.Counter()
    for r in recs:
        out.update(r["report"]["coverage"][tier])
    return {k: out[k] for k in ("of", "have", "first_hand", "llm", "inferred")}


def field_class(rec, name) -> str:
    """Who filled in a field of a record: first-hand, llm, inferred. Empty when the field is not on record."""
    return E.TAG_CLASS.get(rec["provenance"][name].lower(), "inferred") if name in rec["values"] else ""


def procedure_coverage(recs) -> dict:
    """Coverage of the Required fields that describe the procedure, leaving out the two that only name model and benchmark."""
    out = collections.Counter()
    for r in recs:
        for f in r["report"]["fields"]:
            if f["tier"] != "required" or f["name"] in E.IDENTITY or f["status"] == "not_applicable":
                continue
            out["of"] += 1
            if f["status"] == "reported":
                out["have"] += 1
                out[field_class(r, f["name"]).replace("-", "_")] += 1
    return {k: out[k] for k in ("of", "have", "first_hand", "llm", "inferred")}


def per_field(recs) -> list[dict]:
    """For each field: how many records it applies to, and how many carry it, by who filled it in."""
    rows = {f["name"]: collections.Counter() for f in E.FIELDS}
    for r in recs:
        for f in r["report"]["fields"]:
            row = rows[f["name"]]
            if f["status"] == "not_applicable":
                continue
            row["applies"] += 1
            if f["status"] == "reported":
                row["have"] += 1
                row[E.TAG_CLASS.get(f["provenance"].lower(), "inferred").replace("-", "_")] += 1
            elif f["status"] == "invalid":
                row["invalid"] += 1
    return [{"name": n, "tier": E.FIELD[n]["tier"], **{k: c[k] for k in ("applies", "have", "first_hand", "llm", "inferred", "invalid")}}
            for n, c in rows.items()]


def rank_sources(sources: dict) -> list[dict]:
    """Sources ordered by the share of procedure fields they report first-hand; ties by what an LLM could read
    from the source, then by what a pipeline had to infer. Sources with the same three shares have the same rank."""
    out = []
    for s in sources.values():
        recs = s.pop("records")
        live = [r for r in recs if not r["superseded"]]
        tracks = collections.Counter(r["report"]["track"] for r in recs)
        tiers = collections.Counter(r["report"]["tier"] for r in recs)
        out.append({**s, "n": len(recs), "models": len({r["model"] for r in recs}), "benches": len({r["bench"] for r in recs}),
                    "author": tracks["author-reported"], "predicted": tracks["predicted"], "superseded": len(recs) - len(live),
                    "cov": procedure_coverage(live), "tiers": [tiers[t] for t in TIER_ORDER],
                    "fields": [f for f in per_field(live) if f["tier"] == "required" and f["name"] not in E.IDENTITY]})
    shares = lambda s: tuple(round(s["cov"][k] / s["cov"]["of"], 6) if s["cov"]["of"] else 0.0 for k in ("first_hand", "llm", "inferred"))
    out.sort(key=lambda s: (*(-x for x in shares(s)), -s["n"], s["label"].lower()))
    for i, s in enumerate(out):
        s["rank"] = out[i - 1]["rank"] if i and shares(out[i - 1]) == shares(s) else i + 1
    return out


def comparable(name, value) -> str:
    """A value in the form used to decide whether two records agree on a field."""
    if name == "harness_name":
        return ALIASES["harnesses"].get(flat(value), flat(value))
    return json.dumps(value, sort_keys=True)


def build_cells(records) -> list[dict]:
    """One cell per model and benchmark with two or more records: how far apart the scores are, and whether the records say why."""
    groups = collections.defaultdict(list)
    for r in records:
        groups[(r["model"], r["bench"])].append(r)
    always = [n for n in PROCEDURE if E.FIELD[n]["applies"] == "always"]
    cells = []
    for (mk, bk), recs in groups.items():
        if len(recs) < 2:
            continue
        differs, soft = [], []           # a difference is firm only between values that were not inferred by a pipeline
        for n in PROCEDURE:
            seen = [(comparable(n, r["values"][n]), field_class(r, n)) for r in recs if n in r["values"]]
            if len({v for v, _ in seen}) > 1:
                (differs if len({v for v, c in seen if c != "inferred"}) > 1 else soft).append(n)
        missing = [n for n in always if any(n not in r["values"] for r in recs)]
        inferred = [n for n in always if any(field_class(r, n) == "inferred" for r in recs)]
        pcts = [r["pct"] for r in recs if r["pct"] is not None]
        stamps = [r["values"].get("evaluation_timestamp") for r in recs]
        twins = len({round(p, 2) for p in pcts}) < len(pcts)
        cells.append({
            "model": mk, "bench": bk, "n": len(recs), "sources": len({r["source"] for r in recs}),
            "author": sum(r["report"]["track"] == "author-reported" for r in recs),
            "lo": min(pcts) if pcts else None, "hi": max(pcts) if pcts else None,
            "spread": round(max(pcts) - min(pcts), 2) if len(pcts) == len(recs) else None,
            "procedure": "different" if differs else ("same" if not (missing or soft or inferred) else "unknown"),
            "differs": differs, "soft": soft, "missing": missing,
            "independent": ("yes" if all(stamps) and len(set(stamps)) == len(stamps)
                            else "twins" if twins and not all(stamps) else "unknown"),
        })
    cells.sort(key=lambda c: (-(c["sources"] > 1), -(c["spread"] or -1), c["model"], c["bench"]))
    return cells


def statistics(records, sources, models, benches, cells, files) -> dict:
    tracks = collections.Counter(r["report"]["track"] for r in records)
    tiers = collections.Counter(r["report"]["tier"] for r in records)
    modes = collections.Counter(r["values"].get("scoring_mode", "not recorded") for r in records)
    tags = collections.Counter(r["report"]["default_tag"] for r in records)
    kinds = collections.Counter()
    for s in sources.values():
        kinds[s["kind"]] += 1
    multi = [c for c in cells if c["sources"] > 1]
    bands = collections.Counter("unscaled" if c["spread"] is None else "within1" if c["spread"] <= 1 else "within5" if c["spread"] <= 5 else "over5"
                                for c in multi)
    pairs = len({(r["model"], r["bench"]) for r in records})
    return {
        "records": len(records), "files": files, "models": len(models), "benches": len(benches), "sources": len(sources), "pairs": pairs,
        "tracks": {t: tracks[t] for t in ("author-reported", "predicted")},
        "tiers": {t: tiers[t] for t in TIER_ORDER},
        "modes": dict(modes.most_common()), "tags": dict(tags.most_common()), "kinds": dict(kinds.most_common()),
        "superseded": sum(r["superseded"] for r in records),
        "malformed": sum(not r["report"]["well_formed"] or bool(r["structure"]) for r in records),
        "fields": {"all": per_field(records),
                   "author-reported": per_field([r for r in records if r["report"]["track"] == "author-reported"]),
                   "predicted": per_field([r for r in records if r["report"]["track"] == "predicted"])},
        "coverage": {t: coverage(records, t) for t in E.TIERS},
        "overlap": {"cells": len(multi), "bands": {k: bands[k] for k in ("within1", "within5", "over5", "unscaled")},
                    "unexplained": sum(c["procedure"] != "different" for c in multi if c["spread"] is None or c["spread"] > 1)},
    }


# ---------------------------------------------------------------- what the pages load

class Strings:
    """String table: every repeated text is stored once and referred to by number. 0 means absent."""

    def __init__(self):
        self.items, self.index = [""], {"": 0}

    def __call__(self, text) -> int:
        if text is None or text == "":
            return 0
        text = text if isinstance(text, str) else json.dumps(text, ensure_ascii=False)
        if text not in self.index:
            self.index[text] = len(self.items)
            self.items.append(text)
        return self.index[text]


def subset(reg: dict, model_keys: set) -> dict:
    """The part of a registry that concerns some models, in the same shape. Used for the per-model files."""
    records = [r for r in reg["records"] if r["model"] in model_keys]
    benches, sources = {r["bench"] for r in records}, {r["source"] for r in records}
    return {"records": records, "models": [m for m in reg["models"] if m["key"] in model_keys],
            "benches": [b for b in reg["benches"] if b["key"] in benches],
            "sources": [s for s in reg["sources"] if s["key"] in sources],
            "cells": [c for c in reg["cells"] if c["model"] in model_keys], "skipped": [], "stats": {}, "file_base": reg["file_base"]}


def shard_of(key: str, shards: int) -> int:
    """Which per-model file holds a model. The same sum is computed in assets/js/site.js."""
    h = 5381
    for ch in key:
        h = (h * 33 + ord(ch)) & 0xFFFFFFFF
    return h % shards


STATUS_CODE = {"missing": 0, "first-hand": 1, "llm": 2, "inferred": 3, "invalid": 4, "not_applicable": 5}


def payload(reg: dict, meta: dict) -> dict:
    """The registry in the compact, column-wise form the pages read (data/registry.js)."""
    S = Strings()
    mi = {m["key"]: i for i, m in enumerate(reg["models"])}
    bi = {b["key"]: i for i, b in enumerate(reg["benches"])}
    si = {s["key"]: i for i, s in enumerate(reg["sources"])}
    cols = collections.defaultdict(list)
    for r in reg["records"]:
        rep, ctx, v = r["report"], r["context"], r["values"]
        cov = rep["coverage"]
        cols["model"].append(mi[r["model"]])
        cols["bench"].append(bi[r["bench"]])
        cols["source"].append(si[r["source"]])
        cols["mid"].append(S(v["model_id"]))
        cols["bname"].append(S(v["benchmark_id"]))
        cols["score"].append(ctx["score"])
        cols["pct"].append(r["pct"])
        cols["lo"].append(ctx.get("min_score"))
        cols["hi"].append(ctx.get("max_score"))
        cols["metric"].append(S(ctx.get("metric_name")))
        cols["raw"].append(S(ctx.get("raw_score")))
        cols["note"].append(S(ctx.get("note")))
        cols["track"].append(1 if rep["track"] == "author-reported" else 0)
        cols["sup"].append(1 if r["superseded"] else 0)
        cols["tag"].append(S(rep["default_tag"]))
        cols["tier"].append(TIER_ORDER.index(rep["tier"]))
        cols["ok"].append(0 if (rep["errors"] or r["structure"]) else 1)
        cols["have"].append(cov["required"]["have"])
        cols["of"].append(cov["required"]["of"])
        cols["first"].append(cov["required"]["first_hand"])
        cols["llm"].append(cov["required"]["llm"])
        cols["rec"].append(cov["recommended"]["have"])
        cols["full"].append(cov["full"]["have"])
        # one digit per field, in the order of the spec: who filled it in, or why it is empty
        cols["sig"].append(S("".join(str(STATUS_CODE[E.TAG_CLASS.get(f["provenance"].lower(), "inferred") if f["status"] == "reported" else f["status"]])
                                     for f in rep["fields"])))
        for name in KEY_FIELDS:
            cols[name].append(S("none" if name in v and v[name] is None else v.get(name)))
        rest = {k: x for k, x in v.items() if k not in KEY_FIELDS and k not in E.IDENTITY}
        cols["more"].append(S(rest) if rest else 0)
        cols["tags"].append(S({k: t for k, t in r["provenance"].items() if t != rep["default_tag"]}) if any(
            t != rep["default_tag"] for t in r["provenance"].values()) else 0)
        cols["file"].append(S(r["file"]))
        cols["errors"].append(S([f'{e["field"]}: {e["message"]}' for e in rep["errors"]] + r["structure"]) if (rep["errors"] or r["structure"]) else 0)
    return {
        "meta": meta, "stats": reg["stats"], "strings": S.items, "n": len(reg["records"]), "cols": dict(cols),
        "models": [{"key": m["key"], "id": m["id"], "names": m["names"], "n": len(m["records"]),
                    "benches": len({r["bench"] for r in m["records"]}), "sources": len({r["source"] for r in m["records"]}),
                    "author": sum(r["report"]["track"] == "author-reported" for r in m["records"])} for m in reg["models"]],
        "benches": [{"key": b["key"], "label": b["label"], "n": len(b["records"])} for b in reg["benches"]],
        "sources": reg["sources"],
        "cells": [{**c, "model": mi[c["model"]], "bench": bi[c["bench"]]} for c in reg["cells"]],
        "skipped": reg["skipped"][:200], "skipped_total": len(reg["skipped"]),
    }


def records_csv(reg: dict) -> str:
    """Every record as one row, for people who want the table."""
    labels = {b["key"]: b["label"] for b in reg["benches"]}
    ids = {m["key"]: m["id"] for m in reg["models"]}
    names = {s["key"]: s for s in reg["sources"]}
    head = ["model", "model_as_reported", "benchmark", "benchmark_as_reported", "source", "source_kind", "track", "evidence_source",
            "score", "min_score", "max_score", "metric_name", *[f["name"] for f in E.FIELDS if f["name"] not in E.IDENTITY],
            "required_reported", "required_applicable", "required_first_hand", "tier", "superseded", "file"]
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(head)
    for r in reg["records"]:
        v, ctx, rep = r["values"], r["context"], r["report"]
        cov = rep["coverage"]["required"]
        cell = lambda n: "none" if n in v and v[n] is None else ("" if n not in v else json.dumps(v[n]) if isinstance(v[n], list) else v[n])
        w.writerow([ids[r["model"]], v["model_id"], labels[r["bench"]], v["benchmark_id"], names[r["source"]]["label"], names[r["source"]]["kind"],
                    rep["track"], rep["default_tag"], ctx["score"], ctx.get("min_score", ""), ctx.get("max_score", ""), ctx.get("metric_name") or "",
                    *[cell(f["name"]) for f in E.FIELDS if f["name"] not in E.IDENTITY],
                    cov["have"], cov["of"], cov["first_hand"], rep["tier"], int(r["superseded"]), r["file"]])
    return out.getvalue()


def board_csv(reg: dict) -> str:
    """The transparency board as a table: one row per source."""
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(["rank", "source", "kind", "reference", "records", "models", "benchmarks", "author_reported", "predicted", "superseded",
                "procedure_fields_applicable", "procedure_fields_reported", "reported_first_hand", "read_by_llm", "inferred"])
    for s in reg["sources"]:
        c = s["cov"]
        w.writerow([s["rank"], s["label"], s["kind"], s["ref"], s["n"], s["models"], s["benches"], s["author"], s["predicted"], s["superseded"],
                    c["of"], c["have"], c["first_hand"], c["llm"], c["inferred"]])
    return out.getvalue()
