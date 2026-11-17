#!/usr/bin/env python3
"""EvalSpec reference tool. Standard library only.

  python tools/evalspec.py check PATH [PATH ...]     report tier and coverage of records
  python tools/evalspec.py flatten FILE              EEE file -> flat EvalSpec view(s)
  python tools/evalspec.py to-eee FILE -o DIR        flat record(s) -> EEE datastore file(s)
  python tools/evalspec.py hash FILE                 sha256 of a prompt template, as the hook computes it
  python tools/evalspec.py schema                    print the JSON Schema generated from spec/fields.json

A record is either an EEE file (the datastore format) or a flat EvalSpec record
(what the lm-evaluation-harness hook emits). Both are reduced to one "view" per
score, and every check runs on the view. spec/fields.json is the only place where
fields, types and EEE paths are defined; assets/js/evalspec.js reads the same file.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import pathlib
import re
import sys
import time
import uuid

ROOT = pathlib.Path(__file__).resolve().parent.parent
SPEC_FILE = next((f for f in (ROOT / "spec" / "fields.json", pathlib.Path(__file__).resolve().parent / "fields.json") if f.is_file()), None)
if SPEC_FILE is None:
    sys.exit("evalspec.py needs fields.json: keep it in ../spec/ or next to this file")
SPEC = json.loads(SPEC_FILE.read_text(encoding="utf-8"))
FIELDS = SPEC["fields"]
FIELD = {f["name"]: f for f in FIELDS}
TIERS = [t["id"] for t in SPEC["tiers"]]
TAG_CLASS = {t["id"].lower(): t["class"] for t in SPEC["provenance_tags"]}
TAG_NAME = {t["id"].lower(): t["id"] for t in SPEC["provenance_tags"]}
MODE_ALIAS = {a: m["id"] for m in SPEC["scoring_modes"] for a in [m["id"], *m["aliases"]]}
MISSING = set(SPEC["missing_values"])
IDENTITY = ("model_id", "benchmark_id")
NO_JUDGE = ("log-likelihood", "generation", "execution")    # scoring modes that involve no judge
# keys a flat record may carry besides the 21 fields; they map onto EEE when converting
CONTEXT = tuple(k["name"] for k in SPEC["record_keys"] if k["name"] != "evidence_source")

SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
TIMESTAMP = re.compile(r"^([0-9]{4})-([0-9]{2})-([0-9]{2})([T ][0-9]{2}:[0-9]{2}(:[0-9]{2}(\.[0-9]+)?)?(Z|[+-][0-9]{2}:?[0-9]{2})?)?$")
NUMBER = re.compile(r"^[+-]?([0-9]+(\.[0-9]*)?|\.[0-9]+)([eE][+-]?[0-9]+)?$")
URL = re.compile(r"^https?://\S+$")


def is_missing(v) -> bool:
    return v is None or (isinstance(v, str) and v.strip().lower() in MISSING)


# ---------------------------------------------------------------- reading records

def is_eee(obj) -> bool:
    return isinstance(obj, dict) and isinstance(obj.get("evaluation_results"), list) and "model_info" in obj


def _get(obj, parts):
    """Follow a path. A part ending in [] maps over a list and joins what it finds."""
    for i, part in enumerate(parts):
        if not isinstance(obj, dict):
            return None
        if part.endswith("[]"):
            items = obj.get(part[:-2])
            found = [_get(it, parts[i + 1:]) for it in items] if isinstance(items, list) else []
            found = [str(v) for v in found if not is_missing(v)]
            return ", ".join(found) if found else None
        obj = obj.get(part)
    return obj


def _read(doc, result, path):
    parts = path.split(".")
    return _get(result, parts[1:]) if parts[0] == "evaluation_results[]" else _get(doc, parts)


def _details(*objs):
    out = {}
    for o in objs:
        if isinstance(o, dict):
            out.update(o)
    return out


def _first_url(result):
    """The address a result was read from, when the file gives one."""
    urls = (result.get("source_data") or {}).get("url")
    return urls[0] if isinstance(urls, list) and urls and isinstance(urls[0], str) else None


def _legacy_tag(doc, result_details):
    """Records written before provenance tags existed: infer the tag from the record type."""
    sm = doc.get("source_metadata") or {}
    if sm.get("source_type") == "evaluation_run":
        return "source-reported"
    names = f'{sm.get("source_name", "")} {result_details.get("source", "")}'.lower()
    if "extraction_confidence" in result_details or "arxiv" in names or "archiv" in names:
        return "LLM-extracted"
    return "documentation-inferred"


def views_from_eee(doc: dict) -> list[dict]:
    """One view per evaluation result of an EEE file."""
    sm = doc.get("source_metadata") or {}
    file_details = sm.get("additional_details") or {}
    mi = doc.get("model_info") or {}
    out = []
    for index, result in enumerate(doc.get("evaluation_results") or []):
        gc = result.get("generation_config") or {}
        details = gc.get("additional_details") or {}
        args = gc.get("generation_args") or {}
        raw = {}
        for f in FIELDS:
            for path in [f["eee_path"], *f["eee_also"]]:
                v = _read(doc, result, path)
                if not is_missing(v):
                    raw[f["name"]] = v
                    break
        collected = "evaluation_timestamp" in raw and str(raw["evaluation_timestamp"]) == str(doc.get("retrieved_timestamp"))
        if collected:
            del raw["evaluation_timestamp"]
        prov = _details({k[16:]: v for k, v in file_details.items() if k.startswith("evidence_source.")},
                        {k[16:]: v for k, v in details.items() if k.startswith("evidence_source.")})
        explicit = details.get("evidence_source") or file_details.get("evidence_source")
        mc = result.get("metric_config") or {}
        context = {
            "score": (result.get("score_details") or {}).get("score"),
            "metric_name": mc.get("metric_name"), "min_score": mc.get("min_score"), "max_score": mc.get("max_score"),
            "lower_is_better": mc.get("lower_is_better"),
            "model_name": mi.get("name"), "developer": mi.get("developer"),
            "source_name": sm.get("source_name"), "source_organization_name": sm.get("source_organization_name"),
            "source_organization_url": sm.get("source_organization_url"),
            "source_type": sm.get("source_type"), "evaluator_relationship": sm.get("evaluator_relationship"),
            "source_kind": file_details.get("source_kind"), "source_url": _first_url(result),
            "extractor_model": file_details.get("extractor_model"), "extraction_date": file_details.get("extraction_date"),
            "evaluation_id": doc.get("evaluation_id"), "result_index": index,
            "chain_of_thought": args.get("chain_of_thought"), "prompt_template": args.get("prompt_template"),
            "note": details.get("note"), "raw_score": ((result.get("score_details") or {}).get("details") or {}).get("raw_score"),
        }
        out.append(_view(raw, explicit or _legacy_tag(doc, details), prov, context, tag_inferred=not explicit))
        if collected:
            out[-1]["notes"].append(("evaluation_timestamp", "equal to retrieved_timestamp: read as the date the record was collected, not the date of the run"))
    return out


def view_from_flat(rec: dict) -> dict:
    """A flat EvalSpec record, with older key names accepted and reported."""
    raw, notes = {}, []
    for f in FIELDS:
        name = f["name"]
        if name in rec:
            raw[name] = rec[name]
            continue
        for alias in f.get("aliases", []):
            v = _get(rec, alias.split("."))
            if v is not None or (alias in rec):
                raw[name] = v
                notes.append((name, f"written as '{alias}'; the field is called '{name}'"))
                break
    es = rec.get("evidence_source")
    prov = {k: v for k, v in es.items() if k != "default"} if isinstance(es, dict) else {}
    default = es.get("default") if isinstance(es, dict) else es
    context = {k: rec.get(k) for k in CONTEXT}
    if context["metric_name"] is None and isinstance(rec.get("metric"), str):
        context["metric_name"] = rec["metric"]         # the released hook writes 'metric'
    view = _view(raw, default, prov, context, tag_inferred=False, explicit_null=[k for k, v in raw.items() if v is None])
    notes += [(k, "written as text; use a number") for k, v in raw.items()
              if isinstance(v, str) and k in view["values"] and FIELD[k]["type"] in ("integer", "number", "integer_or_list")]
    view["notes"] += notes
    return view


def _view(raw, default_tag, prov, context, tag_inferred, explicit_null=()):
    """Normalise raw values into a view: values (populated fields only), provenance, context."""
    values, invalid, notes = {}, {}, []
    for name, v in raw.items():
        if is_missing(v) and not (name == "judge_model" and name in explicit_null):
            continue
        ok, value, msg = _coerce(FIELD[name], v)
        if ok:
            values[name] = value
            if msg:
                notes.append((name, msg))
        else:
            invalid[name] = msg
    if "judge_model" in values and isinstance(values["judge_model"], str) \
            and values["judge_model"].strip().lower() in ("none", "null", "n/a", "not applicable"):
        values["judge_model"] = None
    mode = values.get("scoring_mode")
    if "judge_model" not in values and "judge_model" not in invalid and mode in NO_JUDGE:
        values["judge_model"] = None        # a scoring mode without a judge implies there is none
    default = TAG_NAME.get(str(default_tag or "").lower())
    if default_tag and not default:
        notes.append(("evidence_source", f"'{default_tag}' is not one of the five provenance tags"))
    provenance = {}
    for name in values:
        tag = TAG_NAME.get(str(prov.get(name, "")).lower())
        if not tag and default and TAG_CLASS[default.lower()] == "inferred" and name in IDENTITY:
            tag = "API-exposed"             # a source always names the model and the benchmark itself
        if name == "judge_model" and values[name] is None and name not in raw:
            tag = provenance.get("scoring_mode") or tag
        provenance[name] = tag or default or "unspecified"
    return {"values": values, "invalid": invalid, "provenance": provenance, "default_tag": default or "unspecified",
            "tag_inferred": tag_inferred, "context": context, "notes": notes,
            "track": "author-reported" if default == "source-reported" else "predicted"}


def _number(v):
    """A finite number, or None. Text is accepted when it is written as a plain decimal."""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return v if v == v and abs(v) != float("inf") else None
    return float(v.strip()) if isinstance(v, str) and NUMBER.match(v.strip()) else None


def _coerce(f, v):
    """Return (ok, value, message). A message with ok=True is a note; with ok=False it is the error."""
    t = f["type"]
    if t in ("string", "string_or_null"):
        if v is None and t == "string_or_null":
            return True, None, None
        if isinstance(v, (dict, list, bool)):
            return False, None, "must be text"
        s = str(v).strip()
        if s.lower() in f.get("not_values", []):
            return False, None, f"'{s}' does not identify an immutable version"
        return True, s, None
    if t == "enum":
        s = str(v).strip().lower()
        if s in MODE_ALIAS:
            canon = MODE_ALIAS[s]
            return True, canon, (None if s == canon else f"written as '{v}'; the value is '{canon}'")
        return False, None, f"'{v}' is not one of: {', '.join(f['enum'])}"
    if t in ("integer", "number"):
        n = _number(v)
        if n is None or (t == "integer" and n != int(n)):
            return False, None, "must be an integer" if t == "integer" else "must be a number"
        n = int(n) if t == "integer" else n
        if "min" in f and n < f["min"]:
            return False, None, f"must be at least {f['min']}"
        if "exclusive_min" in f and n <= f["exclusive_min"]:
            return False, None, f"must be greater than {f['exclusive_min']}"
        if "max" in f and n > f["max"]:
            return False, None, f"must be at most {f['max']}"
        return True, n, None
    if t == "integer_or_list":
        items = v if isinstance(v, list) else re.split(r"[,\s]+", str(v).strip().strip("[]"))
        nums = [_number(x) for x in items if str(x) != ""]
        if not nums or any(n is None or n != int(n) for n in nums):
            return False, None, "must be an integer or a list of integers"
        nums = [int(n) for n in nums]
        return True, (nums[0] if len(nums) == 1 else nums), None
    s = str(v).strip()
    if t == "sha256":
        if SHA256.match(s.lower()):
            return True, s.lower(), None
        return False, None, "must be 'sha256:' followed by 64 hexadecimal digits"
    if t == "timestamp":
        m = TIMESTAMP.match(s)
        try:
            if m:
                datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                return True, s, None
        except ValueError:
            pass
        return False, None, "must be an ISO 8601 date or date-time, for example 2026-07-03T10:00:00Z"
    if t == "url":
        return (True, s, None) if URL.match(s) else (False, None, "must be an http or https address")
    raise ValueError(f"unknown field type {t}")


# ---------------------------------------------------------------- checking a view

def applies(f, values) -> bool:
    if f["applies"] == "generation":
        return values.get("scoring_mode") == "generation"
    if f["applies"] == "judge":
        return values.get("scoring_mode") == "preference" or isinstance(values.get("judge_model"), str)
    return True


def score_percent(context):
    """The score on a 0 to 100 scale when the record states a 0-1 or 0-100 range, else None."""
    s, lo, hi = _number(context.get("score")), _number(context.get("min_score")), _number(context.get("max_score"))
    if s is None or lo != 0 or hi not in (1, 100):
        return None
    return round(s * 100 / hi, 4)


def check(view: dict) -> dict:
    """Tier, coverage and messages for one view."""
    values, invalid, ctx = view["values"], view["invalid"], view["context"]
    errors = [{"field": k, "message": m} for k, m in invalid.items()]
    warnings = [{"field": k, "message": m} for k, m in view["notes"]]
    for key in IDENTITY:
        if key not in values and key not in invalid:
            errors.append({"field": key, "message": "is required to identify the record"})
    if _number(ctx.get("score")) is None:
        errors.append({"field": "score", "message": "a numeric score is required"})
    elif score_percent(ctx) is None and (ctx.get("min_score") is None or ctx.get("max_score") is None):
        warnings.append({"field": "score", "message": "the score's range is not stated; add min_score and max_score"})
    if view["default_tag"] == "unspecified":
        warnings.append({"field": "evidence_source", "message": "not stated; say who filled in the fields (see the five provenance tags)"})
    if view["default_tag"] == "LLM-extracted" and is_missing(ctx.get("extractor_model")):
        warnings.append({"field": "extractor_model", "message": "an LLM-extracted record should name the model that extracted it"})
    if is_missing(ctx.get("source_name")):
        warnings.append({"field": "source_name", "message": "not stated; say where the score is published, so that the registry can list the record under its source"})
    if values.get("scoring_mode") == "preference" and values.get("judge_model", "") is None:
        warnings.append({"field": "judge_model", "message": "preference scoring needs a scorer; name the judge model, or write 'human' for human raters"})

    fields, coverage = [], {t: {"have": 0, "of": 0, "first_hand": 0, "llm": 0, "inferred": 0} for t in TIERS}
    for f in FIELDS:
        name, cov = f["name"], coverage[f["tier"]]
        row = {"name": name, "tier": f["tier"]}
        if not applies(f, values):
            row["status"] = "not_applicable"
        elif name in values:
            cls = TAG_CLASS.get(view["provenance"][name].lower(), "inferred")
            row.update(status="reported", value=values[name], provenance=view["provenance"][name])
            cov["have"] += 1
            cov[{"first-hand": "first_hand"}.get(cls, cls)] += 1
            cov["of"] += 1
        else:
            row["status"] = "invalid" if name in invalid else "missing"
            cov["of"] += 1
        fields.append(row)
    tier = "none"
    for t in TIERS:
        if coverage[t]["have"] < coverage[t]["of"]:
            break
        tier = t
    return {"model_id": values.get("model_id"), "benchmark_id": values.get("benchmark_id"), "score": ctx.get("score"),
            "track": view["track"], "default_tag": view["default_tag"], "tag_inferred": view["tag_inferred"],
            "tier": tier, "well_formed": not errors, "coverage": coverage,
            "fields": fields, "errors": errors, "warnings": warnings}


def eee_structure_errors(doc: dict) -> list[str]:
    """The EEE keys a datastore file cannot do without. Full schema validation is EEE's own job."""
    need = {"": ["schema_version", "evaluation_id", "retrieved_timestamp", "source_metadata", "model_info", "eval_library", "evaluation_results"],
            "source_metadata": ["source_type", "source_organization_name", "evaluator_relationship"],
            "model_info": ["name", "id"], "eval_library": ["name", "version"]}
    out = []
    for p, keys in need.items():
        holder = doc if not p else (doc.get(p) if isinstance(doc.get(p), dict) else {})
        out += [f"{(p + '.') if p else ''}{k} is missing" for k in keys if k not in holder]
    for i, r in enumerate(doc.get("evaluation_results") or []):
        out += [f"evaluation_results[{i}].{k} is missing" for k in ("evaluation_name", "source_data", "metric_config", "score_details")
                if not isinstance(r, dict) or k not in r]
        mc = r.get("metric_config") if isinstance(r, dict) else None
        if isinstance(mc, dict):
            kind = mc.get("score_type", "levels")       # EEE reads a missing score_type as 'levels'
            need_keys = {"levels": ("level_names", "has_unknown_level"), "continuous": ("min_score", "max_score")}.get(kind, ())
            out += [f"evaluation_results[{i}].metric_config.{k} is missing (EEE requires it for a {kind} score)"
                    for k in ("lower_is_better", *need_keys) if k not in mc]
    return out


def views(obj) -> list[dict]:
    """Views for anything a user may hand in: an EEE file, a flat record, or a list of either."""
    if isinstance(obj, list):
        return [v for item in obj for v in views(item)]
    if is_eee(obj):
        return views_from_eee(obj)
    if isinstance(obj, dict):
        return [view_from_flat(obj)]
    raise ValueError("expected a JSON object or a list of objects")


# ---------------------------------------------------------------- flat record -> EEE file

def to_eee(rec: dict, now: float | None = None) -> dict:
    """An EEE v0.2.1 file holding one result, built from a flat record."""
    view = view_from_flat(rec)
    v, ctx = view["values"], view["context"]
    now = time.time() if now is None else now
    model_id = str(v.get("model_id", "unknown"))
    details = {}
    for f in FIELDS:
        name = f["name"]
        if name in v and v[name] is not None and "additional_details" in f["eee_path"]:
            details[name] = v[name] if isinstance(v[name], str) else json.dumps(v[name])
    judge = v.get("judge_model")
    if "judge_model" in v and judge is None and "scoring_mode" not in v:
        details["judge_model"] = "none"
    llm = None
    if isinstance(judge, str) and not judge.lower().startswith("human"):
        llm = {"judges": [{"model_info": {"name": j.split("/")[-1], "id": j}} for j in re.split(r",\s*", judge)],
               "input_prompt": "not recorded here; see judge_prompt_hash"}
    elif isinstance(judge, str):
        details["judge_model"] = judge
    details.update({f"evidence_source.{k}": t for k, t in view["provenance"].items()
                    if t not in (view["default_tag"], "unspecified") and not (k == "judge_model" and v[k] is None)})
    args = {k: v[n] for k, n in (("shots", "n_shot"), ("temperature", "temperature"), ("top_p", "top_p")) if n in v}
    if isinstance(ctx.get("chain_of_thought"), bool):
        args["chain_of_thought"] = ctx["chain_of_thought"]
    if not is_missing(ctx.get("prompt_template")):
        args["prompt_template"] = str(ctx["prompt_template"])
    source = ctx.get("source_name") or "unspecified source"
    author = view["track"] == "author-reported"
    file_details = {k: str(ctx[k]) for k in ("extractor_model", "extraction_date", "source_kind") if not is_missing(ctx.get(k))}
    if view["default_tag"] != "unspecified":
        file_details["evidence_source"] = view["default_tag"]
    metric = {"metric_name": ctx.get("metric_name") or "unspecified",
              "lower_is_better": bool(ctx.get("lower_is_better")), "score_type": "continuous"}
    metric.update({k: ctx[k] for k in ("min_score", "max_score") if _number(ctx.get(k)) is not None})
    if llm:
        metric["llm_scoring"] = llm
    result = {
        "evaluation_name": str(v.get("benchmark_id", "unknown")),
        "source_data": ({"dataset_name": str(v.get("benchmark_id", "unknown")), "source_type": "url", "url": [ctx["source_url"]]}
                        if not is_missing(ctx.get("source_url")) else
                        {"dataset_name": str(v.get("benchmark_id", "unknown")), "source_type": "other"}),
        "metric_config": metric,
        "score_details": {"score": ctx.get("score")},
        "generation_config": {"generation_args": args, "additional_details": details},
    }
    if "evaluation_timestamp" in v:
        result["evaluation_timestamp"] = v["evaluation_timestamp"]
    model = {"name": ctx.get("model_name") or model_id.split("/")[-1], "id": model_id}
    model.update({k: str(x) for k, x in (("developer", ctx.get("developer") or (model_id.split("/")[0] if "/" in model_id else None)),
                                         ("quantization", v.get("quantization"))) if x})
    meta = {"source_name": source, "source_type": "evaluation_run" if author else "documentation",
            "source_organization_name": ctx.get("source_organization_name") or source,
            "evaluator_relationship": ctx.get("evaluator_relationship") or "other"}
    if not is_missing(ctx.get("source_organization_url")):
        meta["source_organization_url"] = ctx["source_organization_url"]
    if file_details:
        meta["additional_details"] = file_details
    return {
        "schema_version": SPEC["extends"]["version"],
        "evaluation_id": ctx.get("evaluation_id") or f"{slug(source)}/{model_id.replace('/', '_')}/{slug(result['evaluation_name'])}/{int(now)}",
        "retrieved_timestamp": str(int(now)),
        "source_metadata": meta,
        "eval_library": {"name": v.get("harness_name", "unknown"), "version": v.get("harness_version", "unknown")},
        "model_info": model,
        "evaluation_results": [result],
    }


def to_eee_all(records: list, now: float | None = None) -> list[dict]:
    """EEE files for a list of records. A record that is an EEE file already passes through; generated ids are made unique."""
    seen, out = {}, []
    for rec in records:
        if is_eee(rec):
            out.append(rec)
            continue
        doc = to_eee(rec, now)
        n = seen[doc["evaluation_id"]] = seen.get(doc["evaluation_id"], 0) + 1
        if n > 1:
            doc["evaluation_id"] += f"/{n}"
        out.append(doc)
    return out


def slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", str(text)).strip("_") or "unnamed"


def datastore_path(doc: dict) -> str:
    """Where a file goes in the datastore: data/<source>/<developer>/<model>/<uuid>.json"""
    mid = doc["model_info"]["id"]
    developer = doc["model_info"].get("developer") or (mid.split("/")[0] if "/" in mid else "unknown")
    return f"data/{slug(doc['source_metadata'].get('source_name', 'unnamed'))}/{slug(developer)}/{slug(mid.split('/')[-1])}/{uuid.uuid4()}.json"


def prompt_hash(text: str) -> str:
    """sha256 of a prompt template after trimming trailing whitespace, as the released hook does."""
    canonical = "\n".join(line.rstrip() for line in re.split(r"\r\n|\r|\n", text.strip()))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- JSON Schema

def json_schema(base_url: str = "") -> dict:
    """JSON Schema (2020-12) of the flat view, generated from spec/fields.json."""
    kinds = {
        "string": {"type": "string", "minLength": 1}, "string_or_null": {"type": ["string", "null"]},
        "integer": {"type": "integer"}, "number": {"type": "number"},
        "integer_or_list": {"oneOf": [{"type": "integer"}, {"type": "array", "items": {"type": "integer"}, "minItems": 1}]},
        "sha256": {"type": "string", "pattern": SHA256.pattern}, "timestamp": {"type": "string", "pattern": TIMESTAMP.pattern},
        "url": {"type": "string", "pattern": URL.pattern},
    }
    props = {}
    for f in FIELDS:
        p = {"enum": f["enum"]} if f["type"] == "enum" else dict(kinds[f["type"]])
        p.update({k2: f[k1] for k1, k2 in (("min", "minimum"), ("exclusive_min", "exclusiveMinimum"), ("max", "maximum")) if k1 in f})
        p["description"] = f["description"]
        if "not_values" in f:
            p["not"] = {"enum": f["not_values"]}
        if f["name"] in IDENTITY:
            p["not"] = {"pattern": r"^\s*([uU][nN][kK][nN][oO][wW][nN])?\s*$"}
        # anywhere else, null, "" and "unknown" all say "not recorded"
        props[f["name"]] = p if f["name"] in IDENTITY else {"anyOf": [p, {"enum": ["unknown", "", None]}]}
    props.update({"score": {"type": "number"}, "metric_name": {"type": "string"}, "min_score": {"type": "number"},
                  "max_score": {"type": "number"}, "lower_is_better": {"type": "boolean"},
                  "evidence_source": {"description": "A provenance tag for the whole record, or an object mapping field names (and 'default') to tags.",
                                      "anyOf": [{"enum": [t["id"] for t in SPEC["provenance_tags"]]},
                                                {"type": "object", "additionalProperties": {"enum": [t["id"] for t in SPEC["provenance_tags"]]}}]}})

    def present(names):
        out = {"required": list(names), "properties": {}}
        for n in names:
            bad = ["unknown", ""] + ([] if n == "judge_model" else [None]) + FIELD[n].get("not_values", [])
            out["properties"][n] = {"not": {"enum": bad}}
        return out

    def tier(t):
        always = [f["name"] for f in FIELDS if f["tier"] == t and f["applies"] == "always" and f["name"] != "judge_model"]
        parts = [present(always)]
        if t == FIELD["judge_model"]["tier"]:       # may be left out when the scoring mode has no judge: it is then read as null
            parts.append({"if": {"required": ["scoring_mode"], "properties": {"scoring_mode": {"enum": list(NO_JUDGE)}}},
                          "else": present(["judge_model"])})
        gen = [f["name"] for f in FIELDS if f["tier"] == t and f["applies"] == "generation"]
        jud = [f["name"] for f in FIELDS if f["tier"] == t and f["applies"] == "judge"]
        if gen:
            parts.append({"if": {"required": ["scoring_mode"], "properties": {"scoring_mode": {"const": "generation"}}}, "then": present(gen)})
        if jud:
            parts.append({"if": {"anyOf": [{"required": ["scoring_mode"], "properties": {"scoring_mode": {"const": "preference"}}},
                                           {"required": ["judge_model"], "properties": {"judge_model": {"type": "string", "not": {"enum": ["unknown", ""]}}}}]},
                          "then": present(jud)})
        return parts

    defs, so_far = {}, []
    for t in TIERS:
        so_far = so_far + tier(t)
        defs[f"{t}_tier"] = {"description": f"A record that reaches the {t.capitalize()} tier.", "allOf": [{"$ref": "#"}] + so_far}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": f"{base_url}spec/evalspec-{SPEC['version']}.schema.json",
            "title": f"EvalSpec {SPEC['version']} record (flat view)",
            "description": "A well-formed record. Use #/$defs/required_tier, recommended_tier or full_tier to test conformance to a tier.",
            "type": "object", "required": ["model_id", "benchmark_id", "score"], "properties": props, "$defs": defs}


# ---------------------------------------------------------------- command line

def load(path: pathlib.Path):
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    return json.loads(text)


def files(paths):
    for p in map(pathlib.Path, paths):
        if p.is_dir():
            yield from sorted(q for q in p.rglob("*.json") if not q.name.startswith(("manifest", "snapshot")))
        else:
            yield p


def cmd_check(args) -> int:
    order = ["none", *TIERS]
    reports, bad = [], 0
    for path in files(args.paths):
        try:
            obj = load(path)
            structure = eee_structure_errors(obj) if is_eee(obj) else []
            found = [check(v) for v in views(obj)]
        except (ValueError, OSError) as e:
            print(f"{path}: cannot be read as a record ({e})", file=sys.stderr)
            bad += 1
            continue
        for r in found:
            r["file"] = str(path)
            r["errors"] = [{"field": "(EEE structure)", "message": m} for m in structure] + r["errors"]
            r["well_formed"] = not r["errors"]
            reports.append(r)
    if args.json:
        print(json.dumps(reports, indent=2))
    else:
        for r in reports:
            c = r["coverage"]["required"]
            print(f"{'ok ' if r['well_formed'] else 'BAD'} {r['tier']:<11} required {c['have']}/{c['of']}  {r['track']:<15} "
                  f"{r['model_id']} | {r['benchmark_id']} | {r['score']}  ({r['file']})")
            for e in r["errors"]:
                print(f"      error    {e['field']}: {e['message']}")
            if args.verbose:
                for w in r["warnings"]:
                    print(f"      warning  {w['field']}: {w['message']}")
                missing = [f["name"] for f in r["fields"] if f["status"] == "missing" and f["tier"] == "required"]
                if missing:
                    print(f"      missing  {', '.join(missing)}")
        tiers = {t: sum(r["tier"] == t for r in reports) for t in order}
        print(f"\n{len(reports)} record(s): " + ", ".join(f"{n} {t}" for t, n in tiers.items() if n)
              + f"; {sum(not r['well_formed'] for r in reports)} malformed")
    bad += sum(not r["well_formed"] for r in reports)
    below = sum(order.index(r["tier"]) < order.index(args.require_tier) for r in reports) if args.require_tier else 0
    return 1 if bad else (2 if below else 0)


def cmd_to_eee(args) -> int:
    """Writes one datastore file per record. A record that is not well formed, or that would not make a valid EEE file, is not written."""
    obj = load(pathlib.Path(args.file))
    out, left_out = pathlib.Path(args.output), 0
    for doc in to_eee_all(obj if isinstance(obj, list) else [obj]):
        problems = eee_structure_errors(doc) + [f'{e["field"]}: {e["message"]}' for v in views_from_eee(doc) for e in check(v)["errors"]]
        if problems:
            left_out += 1
            print(f'not written: {doc.get("model_info", {}).get("id")} | {doc["evaluation_results"][0].get("evaluation_name") if doc.get("evaluation_results") else "?"}: '
                  + "; ".join(problems), file=sys.stderr)
            continue
        target = out / datastore_path(doc)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(target)
    if left_out:
        print(f"{left_out} record(s) not written. In a flat record, the range of the score goes in min_score and max_score.", file=sys.stderr)
    return 1 if left_out else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Check and convert EvalSpec records.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="report tier and coverage")
    c.add_argument("paths", nargs="+")
    c.add_argument("--json", action="store_true", help="machine-readable report")
    c.add_argument("-v", "--verbose", action="store_true", help="also list warnings and missing Required fields")
    c.add_argument("--require-tier", choices=TIERS, help="exit with status 2 unless every record reaches this tier")
    f = sub.add_parser("flatten", help="EEE file -> flat view(s)")
    f.add_argument("file")
    t = sub.add_parser("to-eee", help="flat record(s) -> EEE datastore file(s)")
    t.add_argument("file")
    t.add_argument("-o", "--output", default=".", help="folder to write data/... into")
    h = sub.add_parser("hash", help="sha256 of a prompt template file")
    h.add_argument("file")
    sub.add_parser("schema", help="print the JSON Schema")
    args = ap.parse_args(argv)
    if args.cmd == "check":
        return cmd_check(args)
    if args.cmd == "to-eee":
        return cmd_to_eee(args)
    if args.cmd == "flatten":
        print(json.dumps([{**v["context"], **v["values"], "evidence_source": {"default": v["default_tag"], **{k: t for k, t in v["provenance"].items() if t != v["default_tag"]}}}
                          for v in views(load(pathlib.Path(args.file)))], indent=2, ensure_ascii=False))
    elif args.cmd == "hash":
        print(prompt_hash(pathlib.Path(args.file).read_text(encoding="utf-8")))
    elif args.cmd == "schema":
        print(json.dumps(json_schema(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
