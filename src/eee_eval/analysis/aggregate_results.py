"""
aggregate_results.py — flatten all per-benchmark JSONs into one master CSV.

    python -m eee_eval.analysis.aggregate_results

From Python, the steps are separate functions:

    rows_from_record(record)      the CSV rows of one record (a dict in the schema below)
    collect(data_dir)             the rows of every record file under a folder
    relabel_olv2_gpqa(rows)       the one source-specific correction applied to the rows
    aggregate(data_dir, out_dir)  all of the above, written to all_results.csv

A new column is a new key in the dict of `iter_rows`; a new alias of a benchmark name
is a new entry of `_BENCHMARK_FIXUP`.

Field paths are matched exactly to the JSON structure produced by
PaperConverter._convert_model() → EvaluationLog.model_dump(mode='json').

JSON structure written by PaperWriter (one EvaluationResult per file):
  {
    "schema_version": "...",
    "evaluation_id":  "...",
    "retrieved_timestamp": "...",
    "source_metadata": {
        "source_name": "arXiv:...",
        "source_type": "documentation",
        "source_organization_name": "arXiv",
        "source_organization_url": "https://...",
        "evaluator_relationship": "first_party|third_party"
    },
    "eval_library": { "name": "lm_eval|internal|...", "version": "unknown" },
    "model_info": {
        "name": "Llama-3-70B",
        "id":   "meta-llama/Llama-3-70B",
        "developer": "meta-llama",
        "parameter_count": "70B",        # optional
        "model_alignment": "instruct",   # optional
        "quantization": "BF16"           # optional
    },
    "evaluation_results": [              # always exactly ONE item per file
      {
        "evaluation_name": "MMLU",
        "source_data": { ... },
        "metric_config": {
            "metric_name": "accuracy",
            "lower_is_better": false,
            "score_type": "continuous",
            "min_score": 0.0,
            "max_score": 1.0
        },
        "score_details": {
            "score": 0.8732,
            "details": { ... }           # optional — relative_to, score_type
        },
        "generation_config": {
            "generation_args": {         # optional — omitted if all None
                "shots": 5,
                "temperature": 0.0,
                "top_p": null,
                "chain_of_thought": null,
                "prompt_template": null
            },
            "additional_details": {      # always present — dict[str, str]
                "source": "arXiv:...",
                "extraction_confidence": "high|medium|low|llm|prose",
                "harness": "lm_eval|internal|...",
                "scoring_method": "log_likelihood|generation",  # optional
                "protocol_source": "paper_default|explicit|...",  # optional
                "page_number": "3",      # optional
                "table": "Table 2",      # optional
                "table_caption": "..."   # optional
            }
        }
      }
    ]
  }
"""

import collections
import csv
import json
import pathlib

from eee_eval.paths import DATA_DIR, ROOT

OUT_DIR  = DATA_DIR / "aggregated"

# Settings whose documentation rate is tracked per benchmark (coverage_stats.json).
COVERAGE_FIELDS = ("shots", "temperature", "top_p", "prompt_template", "harness", "chain_of_thought", "reasoning")
# The subset of them printed after a run.
SUMMARY_FIELDS = ("shots", "temperature", "prompt_template", "harness", "chain_of_thought", "reasoning")
OLV2 = "open_llm_leaderboard_v2"

# ── Post-hoc benchmark name canonicalization ────────────────────────────────
# Fixes stale names in already-written JSON files from before the normalisation
# audit. Only maps clear aliases — ambiguous names (e.g. "GPQA" without subset
# qualifier from an arxiv paper) are left as-is.
_BENCHMARK_FIXUP: dict[str, str] = {
    "ARC-C":   "ARC-Challenge",
    "ARC-E":   "ARC-Easy",
    "ARC-c":   "ARC-Challenge",
    "ARC-e":   "ARC-Easy",
    "arc-c":   "ARC-Challenge",
    "arc-e":   "ARC-Easy",
    # BigBench-Hard variants → BBH
    "BigBench-Hard": "BBH", "bigbench-hard": "BBH",
    "Big-Bench Hard": "BBH", "big-bench hard": "BBH",
    "Big-Bench-Hard": "BBH", "big-bench-hard": "BBH",
    "Bigbench Hard": "BBH", "bigbench hard": "BBH",
    # GPQA variants → canonical
    "GPQA Diamond": "GPQA-Diamond", "GPQA-D": "GPQA-Diamond",
    "gpqa diamond": "GPQA-Diamond", "gpqa-d": "GPQA-Diamond",
}


def iter_rows(rec: dict, file: str = ""):
    """The rows of all_results.csv for one record: one per evaluation result.

    `file` is what goes into the `file` column, the path of the record on disk.
    """
    # ── Top-level record fields ─────────────────────────────────────────────
    mi  = rec.get("model_info", {})
    src = rec.get("source_metadata", {})
    lib = rec.get("eval_library", {})

    # ── Each file has exactly ONE evaluation_result ─────────────────────────
    for er in rec.get("evaluation_results", []):
        mc = er.get("metric_config", {})
        sd = er.get("score_details", {})
        gc = er.get("generation_config", {})

        # generation_args is optional (excluded when all fields are None)
        ga = gc.get("generation_args") or {}

        # additional_details is always present — dict[str, str]
        ad = gc.get("additional_details") or {}

        # score_details.details holds relative_to / comparability_warning
        sd_details = sd.get("details") or {}

        row = {
            # ── Model identity ──────────────────────────────────────────
            "model":                  mi.get("name", ""),
            "model_id":               mi.get("id", ""),
            "developer":              mi.get("developer", ""),
            "parameter_count":        mi.get("parameter_count", ""),
            "model_alignment":        mi.get("model_alignment", ""),
            "quantization":           mi.get("quantization", ""),

            # ── Benchmark + score ───────────────────────────────────────
            "benchmark":              _BENCHMARK_FIXUP.get(er.get("evaluation_name", ""), er.get("evaluation_name", "")),
            "score":                  sd.get("score", ""),
            "lower_is_better":        mc.get("lower_is_better", ""),
            "min_score":              mc.get("min_score", ""),
            "max_score":              mc.get("max_score", ""),
            "metric_name":            mc.get("metric_name", ""),
            "score_type":             sd_details.get("score_type", "absolute"),
            "relative_to":            sd_details.get("relative_to", ""),

            # ── Evaluation protocol (generation_args) ───────────────────
            # Paths: generation_config.generation_args.*
            "shots":                  ga.get("shots", ""),
            "temperature":            ga.get("temperature", ""),
            "top_p":                  ga.get("top_p", ""),
            "reasoning":              ga.get("reasoning", ""),
            "chain_of_thought":       ga.get("chain_of_thought", ""),
            "prompt_template":        ga.get("prompt_template", ""),

            # ── Extraction provenance (additional_details) ───────────────
            # Paths: generation_config.additional_details.*
            "extraction_confidence":  ad.get("extraction_confidence", ""),
            # harness: prefer additional_details.harness, fall back to eval_library.name
            "harness":                ad.get("harness", "") or lib.get("name", ""),
            "scoring_method":         ad.get("scoring_method", ""),
            "protocol_source":        ad.get("protocol_source", ""),
            "page_number":            ad.get("page_number", ""),
            "table_id":               ad.get("table", ""),
            "table_caption":          ad.get("table_caption", ""),

            # ── Source metadata ─────────────────────────────────────────
            # source_name may be a paper title; arxiv_id is always
            # the arXiv identifier for consistent grouping.
            "source":                 ad.get("source", src.get("source_name", "")),
            "source_name":            src.get("source_name", ""),
            # evaluator_relationship: EvaluatorRelationship enum → string
            "evaluator_relationship": src.get("evaluator_relationship", ""),
            "eval_library":           lib.get("name", ""),
            "eval_library_version":   lib.get("version", ""),

            # ── Record provenance ───────────────────────────────────────
            "evaluation_id":          rec.get("evaluation_id", ""),
            "retrieved_timestamp":    rec.get("retrieved_timestamp", ""),
            "file":                   file,
        }
        yield row


def rows_from_record(rec: dict, file: str = "") -> list[dict]:
    """`iter_rows` as a list."""
    return list(iter_rows(rec, file))


def record_files(data_dir: pathlib.Path):
    """The record files under a data folder.

    The canonical ArXiv source is archiv_paper_extraction/llm/ only: the audit-sample
    copies (samples/) and the superseded naive extraction (naive/) are left out so that
    they do not inflate the aggregate, and so is the output folder aggregated/.
    """
    for f in data_dir.rglob("*.json"):
        if "aggregated" in str(f):
            continue
        if "samples" in f.parts or "naive" in f.parts:
            continue
        yield f


def collect(data_dir: pathlib.Path = DATA_DIR, root: pathlib.Path | None = None) -> list[dict]:
    """The rows of every record file under `data_dir`. Files that cannot be read are skipped
    with a message. The `file` column is the path relative to `root` (the parent of `data_dir`
    by default)."""
    root = data_dir.parent if root is None else root
    rows: list[dict] = []
    for f in record_files(data_dir):
        try:
            rec = json.loads(f.read_text(encoding="utf-8"))
            rows.extend(iter_rows(rec, str(f.relative_to(root))))    # the rows before a faulty result are kept
        except Exception as e:  # noqa: BLE001  one unreadable record must not stop the run
            print(f"  skip {f.name}: {e}")
    return rows


def coverage_by_benchmark(rows: list[dict], fields=COVERAGE_FIELDS) -> dict:
    """{benchmark: {field: records with a value, ..., "total": records}}."""
    coverage: dict = collections.defaultdict(lambda: collections.defaultdict(int))
    for row in rows:
        b = row["benchmark"]
        for field in fields:
            val = row.get(field, "")
            if val not in ("", None, "unknown"):
                coverage[b][field] += 1
        coverage[b]["total"] += 1
    return dict(coverage)


def relabel_olv2_gpqa(rows: list[dict]) -> int:
    """Fix the OLv2 GPQA-Diamond metric mismatch, in place; returns the rows changed.

    OLv2 reports GPQA-Diamond using acc_norm (max ~29) but mislabels it "accuracy".
    Papers report raw accuracy (up to 92). The rows are relabelled so that the two are
    not treated as the same benchmark in downstream analysis.
    """
    n = 0
    for row in rows:
        if row["benchmark"] == "GPQA-Diamond" and row.get("source", "") == OLV2:
            row["benchmark"] = "GPQA-Diamond (acc_norm)"
            row["metric_name"] = "acc_norm"
            n += 1
    return n


def aggregate(data_dir: pathlib.Path = DATA_DIR, out_dir: pathlib.Path | None = None) -> list[dict]:
    """Flatten the records under `data_dir` into `out_dir`/all_results.csv and return the rows."""
    data_dir = pathlib.Path(data_dir)
    out_dir = data_dir / "aggregated" if out_dir is None else pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = collect(data_dir)
    if not rows:
        print("  no records found — run extraction first (pipeline: 1b — extract batch)")
        return rows

    coverage = coverage_by_benchmark(rows)            # under the names before the relabelling
    n_gpqa_relabeled = relabel_olv2_gpqa(rows)
    if n_gpqa_relabeled:
        print(f"  Relabeled {n_gpqa_relabeled:,} OLv2 GPQA-Diamond -> GPQA-Diamond (acc_norm)")

    keys = list(rows[0].keys())
    with open(out_dir / "all_results.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)

    with open(out_dir / "coverage_stats.json", "w", encoding="utf-8") as fh:
        json.dump(coverage, fh, indent=2)

    # Also collect the native coverage_report_*.json files the pipeline writes
    native_reports = sorted(
        (ROOT / "scripts" / "scrapers" / "raw").glob("coverage_report_*.json")
    )
    if native_reports:
        latest = json.loads(native_reports[-1].read_text(encoding="utf-8"))
        with open(out_dir / "pipeline_coverage_report.json", "w", encoding="utf-8") as fh:
            json.dump(latest, fh, indent=2)
        print("  pipeline coverage report -> data/aggregated/pipeline_coverage_report.json")

    models      = len({r["model"]     for r in rows})
    benchmarks  = len({r["benchmark"] for r in rows})
    sources     = len({r["source"]    for r in rows})
    developers  = len({r["developer"] for r in rows})

    print(f"OK {len(rows)} records -> data/aggregated/all_results.csv")
    print(f"  {models} models  |  {benchmarks} benchmarks  |  "
          f"{sources} sources  |  {developers} developers")

    # Quick metadata coverage summary
    print("\n  Metadata documentation rates:")
    for field in SUMMARY_FIELDS:
        filled = sum(1 for r in rows if r.get(field) not in ("", None, "unknown"))
        pct = filled / len(rows) * 100
        print(f"    {field:20s}  {filled:4d}/{len(rows)}  ({pct:.1f}%)")
    return rows


def main() -> None:
    aggregate()


if __name__ == "__main__":
    main()
