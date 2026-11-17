"""Tests for the reference validator, and for its agreement with the browser validator.

  python -m unittest discover -s tests -v
"""
import copy
import json
import pathlib
import random
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import evalspec as E  # noqa: E402

try:
    import jsonschema
except ImportError:  # the schema cross-checks are skipped without it
    jsonschema = None

EXAMPLES = ROOT / "spec" / "examples"


def example(name):
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def report(rec):
    (view,) = E.views(rec)
    return E.check(view)


FULL = example("full-tier.eee.json")
(FULL_FLAT_VIEW,) = E.views(FULL)
GEN = example("required-generation.json")
JUDGE = example("required-judge.json")


def full_flat():
    """The Full-tier example as a flat record."""
    rec = {**{k: v for k, v in FULL_FLAT_VIEW["context"].items() if k in E.CONTEXT and v is not None}, **FULL_FLAT_VIEW["values"]}
    rec["evidence_source"] = "source-reported"
    return rec


class Examples(unittest.TestCase):
    def test_tiers(self):
        self.assertEqual(report(GEN)["tier"], "required")
        self.assertEqual(report(JUDGE)["tier"], "required")
        self.assertEqual(report(FULL)["tier"], "full")
        self.assertEqual(report(full_flat())["tier"], "full")

    def test_hook_output(self):
        r = report(example("hook-output.json"))
        self.assertTrue(r["well_formed"])
        self.assertEqual(r["tier"], "none")
        self.assertEqual((r["coverage"]["required"]["have"], r["coverage"]["required"]["of"]), (9, 11))
        self.assertEqual(r["coverage"]["recommended"]["have"], 2)
        missing = [f["name"] for f in r["fields"] if f["status"] == "missing" and f["tier"] == "required"]
        self.assertEqual(missing, ["benchmark_variant", "answer_parser_version"])
        self.assertTrue(any("benchmark_id" == w["field"] for w in r["warnings"]))   # 'benchmark' is the old key

    def test_hook_hash_matches_paper_figure(self):
        self.assertTrue(E.prompt_hash("Q: {{question}}\nA:").startswith("sha256:870"))


class FieldRules(unittest.TestCase):
    def one(self, **changes):
        rec = full_flat()
        rec.update(changes)
        return report(rec)

    def status(self, r, name):
        return next(f["status"] for f in r["fields"] if f["name"] == name)

    def test_missing_values(self):
        for missing in (None, "unknown", "", "  Unknown "):
            r = self.one(harness_name=missing)
            self.assertEqual(self.status(r, "harness_name"), "missing", missing)
            self.assertEqual(r["tier"], "none")
            self.assertTrue(r["well_formed"])

    def test_invalid_values(self):
        bad = {"scoring_mode": "multiple-choice", "harness_version": "latest", "n_shot": -1, "n_shot ": None,
               "evaluation_timestamp": "03/07/2026", "prompt_template_hash": "sha256:870", "temperature": -0.5,
               "top_p": 0, "random_seed": "forty-two", "provenance_url": "ftp://example.org", "compute_hours": "many"}
        for name, value in bad.items():
            if name.endswith(" "):
                continue
            r = self.one(**{name: value})
            self.assertEqual(self.status(r, name), "invalid", name)
            self.assertFalse(r["well_formed"], name)
        for value in ("2026-02-30", "2026-13-01", "1790000000"):
            self.assertEqual(self.status(self.one(evaluation_timestamp=value), "evaluation_timestamp"), "invalid", value)

    def test_accepted_spellings(self):
        r = self.one(scoring_mode="log_likelihood")
        self.assertEqual(self.status(r, "scoring_mode"), "reported")
        self.assertTrue(any(w["field"] == "scoring_mode" for w in r["warnings"]))
        self.assertEqual(self.status(self.one(random_seed=[42, 123, 7]), "random_seed"), "reported")
        self.assertEqual(self.status(self.one(evaluation_timestamp="2026-07-03"), "evaluation_timestamp"), "reported")
        self.assertEqual(self.status(self.one(harness_version="3f2a9c1"), "harness_version"), "reported")

    def test_conditional_fields(self):
        r = self.one(scoring_mode="generation")
        self.assertEqual(self.status(r, "answer_parser_version"), "missing")
        self.assertEqual(self.status(r, "judge_prompt_hash"), "not_applicable")
        r = self.one(scoring_mode="preference", judge_model="example-org/judge")
        self.assertEqual(self.status(r, "judge_prompt_hash"), "missing")
        self.assertEqual(self.status(r, "judge_score_rule"), "missing")
        self.assertEqual(self.status(r, "answer_parser_version"), "not_applicable")
        self.assertEqual(r["coverage"]["required"]["of"], 12)

    def test_judge_model_null(self):
        rec = full_flat()
        del rec["judge_model"]
        self.assertEqual(report(rec)["tier"], "full")              # implied by the scoring mode
        del rec["scoring_mode"]
        r = report(rec)
        self.assertEqual(next(f["status"] for f in r["fields"] if f["name"] == "judge_model"), "missing")
        rec["judge_model"] = None                                  # stated explicitly
        r = report(rec)
        self.assertEqual(next(f["status"] for f in r["fields"] if f["name"] == "judge_model"), "reported")

    def test_identity_and_score_are_needed(self):
        for key in ("model_id", "benchmark_id", "score"):
            rec = full_flat()
            del rec[key]
            self.assertFalse(report(rec)["well_formed"], key)


class Provenance(unittest.TestCase):
    def test_tracks(self):
        rec = full_flat()
        self.assertEqual(report(rec)["track"], "author-reported")
        for tag in ("LLM-extracted", "documentation-inferred", "pipeline-default", "API-exposed", None):
            rec["evidence_source"] = tag
            self.assertEqual(report(rec)["track"], "predicted", tag)

    def test_first_hand_counts(self):
        rec = full_flat()
        rec["evidence_source"] = {"default": "documentation-inferred", "n_shot": "source-reported"}
        cov = report(rec)["coverage"]["required"]
        self.assertEqual(cov["first_hand"], 3)       # model_id and benchmark_id (the source names them) and n_shot
        self.assertEqual(cov["inferred"], cov["have"] - 3)
        rec["evidence_source"] = "LLM-extracted"
        cov = report(rec)["coverage"]["required"]
        self.assertEqual((cov["llm"], cov["first_hand"]), (cov["have"], 0))

    def test_legacy_records_get_a_tag(self):
        doc = copy.deepcopy(FULL)
        del doc["source_metadata"]["additional_details"]
        self.assertEqual(report(doc)["default_tag"], "source-reported")            # an evaluation run
        doc["source_metadata"]["source_type"] = "documentation"
        self.assertEqual(report(doc)["default_tag"], "documentation-inferred")
        doc["source_metadata"]["source_name"] = "arXiv:2408.00118"
        r = report(doc)
        self.assertEqual((r["default_tag"], r["track"], r["tag_inferred"]), ("LLM-extracted", "predicted", True))

    def test_legacy_keys_are_read(self):
        doc = copy.deepcopy(FULL)
        details = doc["evaluation_results"][0]["generation_config"]["additional_details"]
        details["scoring_method"] = details.pop("scoring_mode").replace("-", "_")
        doc["eval_library"] = {"name": "unknown", "version": "unknown"}
        details["harness"] = "lm_eval"
        r = report(doc)
        values = {f["name"]: f.get("value") for f in r["fields"]}
        self.assertEqual((values["scoring_mode"], values["harness_name"]), ("log-likelihood", "lm_eval"))
        self.assertIsNone(values["harness_version"])


class Conversion(unittest.TestCase):
    def test_round_trip(self):
        for rec in (GEN, JUDGE, full_flat(), example("hook-output.json")):
            doc = E.to_eee(rec, now=1790000000)
            self.assertEqual(len(E.eee_structure_errors(doc)), 0 if "min_score" in rec else 2)
            a, b = report(rec), report(doc)
            for key in ("tier", "track", "coverage", "errors"):
                self.assertEqual(a[key], b[key], key)
            self.assertEqual([(f["name"], f["status"], f.get("value")) for f in a["fields"]],
                             [(f["name"], f["status"], f.get("value")) for f in b["fields"]])

    @unittest.skipIf(jsonschema is None, "jsonschema is not installed")
    def test_converted_files_are_valid_eee(self):
        schema = json.loads((ROOT / "spec" / "eee-0.2.1-extended.schema.json").read_text(encoding="utf-8-sig"))
        validator = jsonschema.Draft7Validator(schema)
        for rec in (GEN, JUDGE, full_flat()):
            errors = [e.message for e in validator.iter_errors(E.to_eee(rec, now=1790000000))]
            self.assertEqual(errors, [])
        self.assertEqual([e.message for e in validator.iter_errors(FULL)], [])
        # without a score range EEE rejects the file, and our own structure check names the same two keys
        doc = E.to_eee(example("hook-output.json"), now=1790000000)
        self.assertEqual(len(list(validator.iter_errors(doc))), 2)
        self.assertEqual(len(E.eee_structure_errors(doc)), 2)

    def test_datastore_path(self):
        path = E.datastore_path(E.to_eee(GEN, now=1790000000))
        self.assertRegex(path, r"^data/Illustrative_example_not_a_real_result/example-org/example-model-7b/[0-9a-f-]{36}\.json$")


@unittest.skipIf(jsonschema is None, "jsonschema is not installed")
class GeneratedSchema(unittest.TestCase):
    """The published JSON Schema and the reference validator must agree on canonical records."""

    def test_agreement(self):
        schema = E.json_schema()
        jsonschema.Draft202012Validator.check_schema(schema)
        order = ["none", *E.TIERS]

        def reaches(rec, tier):
            sub = {"$schema": schema["$schema"], "$ref": f"#/$defs/{tier}_tier", "$defs": {"root": schema}}
            sub = {**schema, "allOf": schema["$defs"][f"{tier}_tier"]["allOf"][1:]}
            return jsonschema.Draft202012Validator(sub).is_valid(rec)

        cases = canonical_cases()
        self.assertGreater(len(cases), 150)
        for rec in cases:
            r = report(rec)
            well_formed = jsonschema.Draft202012Validator(schema).is_valid(rec)
            self.assertEqual(well_formed, r["well_formed"], rec)
            if r["well_formed"]:
                for tier in E.TIERS:
                    self.assertEqual(reaches(rec, tier), order.index(r["tier"]) >= order.index(tier), (tier, rec))


def pipeline_records():
    """Two records in the shape the paper's pipeline writes (extract_paper.py, add_leaderboard_records.py)."""
    paper = {
        "schema_version": "0.2.1", "evaluation_id": "arxiv_html_llm/Gemma-7B/2404.07839/BBH/3_ab12cd34",
        "evaluation_timestamp": "2026-05-24", "retrieved_timestamp": "2026-05-24",
        "source_metadata": {"source_name": "arxiv_html_llm", "source_type": "documentation", "source_organization_name": "arXiv",
                            "source_organization_url": "https://arxiv.org", "evaluator_relationship": "first_party",
                            "additional_details": {"paper_url": "https://arxiv.org/abs/2404.07839", "arxiv_id": "2404.07839",
                                                   "paper_title": "RecurrentGemma", "is_baseline": "True", "extraction_approach": "llm"}},
        "eval_library": {"name": "lm-evaluation-harness", "version": "unknown"},
        "model_info": {"name": "Gemma-7B", "id": "Gemma-7B", "developer": "Google"},
        "evaluation_results": [{
            "evaluation_name": "BBH", "evaluation_timestamp": "2026-05-24",
            "source_data": {"dataset_name": "BBH", "source_type": "url", "url": ["https://arxiv.org/abs/2404.07839"]},
            "metric_config": {"metric_name": "exact_match", "lower_is_better": False, "score_type": "continuous", "min_score": 0.0, "max_score": 100.0},
            "score_details": {"score": 55.1},
            "generation_config": {"generation_args": {"shots": 3, "temperature": 0.0, "prompt_template": "chain-of-thought"},
                                  "additional_details": {"source": "arxiv_html_llm", "eval_harness": "lm-evaluation-harness", "seed": "1234",
                                                         "decoding_strategy": "greedy"}}}]}
    board = {
        "schema_version": "0.2.1", "evaluation_id": "open_llm_leaderboard_v2/google_gemma-2-9b/1785369600", "retrieved_timestamp": "1785369600",
        "source_metadata": {"source_name": "Open LLM Leaderboard v2", "source_type": "documentation", "source_organization_name": "HuggingFace",
                            "source_organization_url": "https://huggingface.co/spaces/open-llm-leaderboard/open_llm_leaderboard",
                            "evaluator_relationship": "third_party"},
        "eval_library": {"name": "lm_eval", "version": "unknown"},
        "model_info": {"name": "gemma-2-9b", "id": "google/gemma-2-9b", "developer": "google"},
        "evaluation_results": [{
            "evaluation_name": b, "source_data": {"dataset_name": b, "source_type": "url", "url": ["https://huggingface.co"]},
            "metric_config": {"metric_name": "accuracy", "lower_is_better": False, "score_type": "continuous", "min_score": 0.0, "max_score": 100.0},
            "score_details": {"score": s},
            "generation_config": {"generation_args": {"shots": n, "chain_of_thought": True},
                                  "additional_details": {"source": "open_llm_leaderboard_v2", "note": f"{n}-shot CoT"}}}
            for b, s, n in (("BBH", 34.1, 3), ("MMLU-Pro", 34.48, 5))]}
    return paper, board


class PipelineRecords(unittest.TestCase):
    """The existing corpus carries no provenance tags; the tools must still read it as the paper describes it."""

    def test_paper_record(self):
        paper, _ = pipeline_records()
        r = report(paper)
        self.assertEqual((r["track"], r["default_tag"], r["tag_inferred"]), ("predicted", "LLM-extracted", True))
        got = {f["name"]: f.get("value") for f in r["fields"] if f["status"] == "reported"}
        self.assertEqual(got["harness_name"], "lm-evaluation-harness")
        self.assertEqual((got["n_shot"], got["temperature"], got["random_seed"]), (3, 0.0, 1234))
        self.assertNotIn("evaluation_timestamp", got)        # it is the extraction date, not a run date
        self.assertEqual(r["coverage"]["required"]["llm"], r["coverage"]["required"]["have"])

    def test_leaderboard_record(self):
        _, board = pipeline_records()
        reports = [E.check(v) for v in E.views(board)]
        self.assertEqual(len(reports), 2)
        for r in reports:
            self.assertEqual((r["track"], r["default_tag"]), ("predicted", "documentation-inferred"))
            cov = r["coverage"]["required"]
            self.assertEqual((cov["have"], cov["first_hand"], cov["inferred"]), (4, 2, 2))   # the leaderboard itself names only model and benchmark


def canonical_cases():
    """Flat records in canonical spelling: every field dropped, blanked or broken in turn, plus random mixes."""
    base = full_flat()
    for k in ("model_name", "developer", "source_name", "source_organization_name", "evaluator_relationship", "evaluation_id"):
        base.pop(k, None)
    judged = {**base, "scoring_mode": "preference", "judge_model": "example-org/judge",
              "judge_prompt_hash": JUDGE["judge_prompt_hash"], "judge_score_rule": "mean rating"}
    generated = {**base, "scoring_mode": "generation", "answer_parser_version": "strict-match v3"}
    broken = {"scoring_mode": "ranked", "harness_version": "latest", "n_shot": -2, "evaluation_timestamp": "yesterday",
              "prompt_template_hash": "sha256:abc", "temperature": -1, "top_p": 1.5, "random_seed": 1.5,
              "provenance_url": "not a url", "compute_hours": -3, "judge_prompt_hash": "md5:123"}
    cases = [base, judged, generated]
    for start in (base, judged, generated):
        for name in E.FIELD:
            for change in ("drop", "unknown", "null", "broken"):
                rec = dict(start)
                if change == "drop":
                    rec.pop(name, None)
                elif change == "unknown":
                    rec[name] = "unknown"
                elif change == "null":
                    rec[name] = None
                elif name in broken:
                    rec[name] = broken[name]
                else:
                    continue
                cases.append(rec)
    rng = random.Random(7)
    for _ in range(120):
        rec = dict(rng.choice((base, judged, generated)))
        for name in rng.sample(sorted(E.FIELD), rng.randint(0, 6)):
            roll = rng.random()
            if roll < 0.5:
                rec.pop(name, None)
            elif roll < 0.7:
                rec[name] = "unknown"
            elif name in broken:
                rec[name] = broken[name]
        cases.append(rec)
    return cases


def loose_cases():
    """Inputs the validators accept beyond the canonical form: old key names, numbers as text, EEE files, lists."""
    hook = example("hook-output.json")
    old = {"@type": "EvaluationRun", "model_id": "allenai/Llama-3.1-Tulu-3-8B", "benchmark_id": "BBH (3-Shot)", "scoring_mode": None,
           "eval_library": {"name": None, "version": None}, "n_shot": None, "date": None,
           "provenance_link": "https://huggingface.co/allenai/Llama-3.1-Tulu-3-8B", "score": 16.86}
    text_numbers = {**full_flat(), "n_shot": "5", "temperature": "0.0", "random_seed": "42, 123", "compute_hours": " 1.5 ",
                    "top_p": "1e0", "harness_version": 0.4, "scoring_mode": " Log_Likelihood "}
    odd = [{"model_id": 7, "benchmark_id": ["x"], "score": "high", "n_shot": True, "judge_model": {"a": 1}, "random_seed": [1, "2", None]},
           {"model_id": "a/b", "benchmark_id": "x", "score": 0.5, "min_score": 0, "max_score": 1, "judge_model": "none",
            "evidence_source": {"default": "pipeline-default", "model_id": "source-reported", "n_shot": "nonsense"}, "n_shot": 0},
           {"model_id": "a/b", "benchmark_id": "x", "score": 1, "evidence_source": "made-up-tag", "scoring_mode": "preference", "judge_model": None},
           {"model_id": "a/b", "benchmark_id": "x", "score": 3, "judge_model": "human raters, 3 per item", "scoring_mode": "preference"},
           {}]
    eee = [FULL, E.to_eee(JUDGE, now=1), E.to_eee(hook, now=2)]
    legacy = copy.deepcopy(FULL)
    legacy["source_metadata"] = {"source_name": "arXiv:2408.00118", "source_type": "documentation",
                                 "source_organization_name": "arXiv", "evaluator_relationship": "first_party"}
    legacy["eval_library"] = {"name": "unknown", "version": "unknown"}
    legacy["evaluation_results"][0]["generation_config"]["additional_details"] = {
        "source": "arXiv:2408.00118", "extraction_confidence": "llm", "harness": "lm_eval", "scoring_method": "generation",
        "evidence_source.n_shot": "pipeline-default", "judge_model": "none", "random_seed": "[1, 2]"}
    legacy["evaluation_results"].append({"evaluation_name": "second", "score_details": {}})
    datastore = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((ROOT / "datastore").rglob("*.json"))
                 if p.name not in ("snapshot.json",)]
    return [hook, old, text_numbers, *odd, *eee, legacy, [hook, FULL], *pipeline_records()] + datastore


@unittest.skipIf(shutil.which("node") is None, "node is not installed")
class BrowserValidator(unittest.TestCase):
    """assets/js/evalspec.js must report exactly what tools/evalspec.py reports."""

    def test_same_reports(self):
        inputs = canonical_cases() + loose_cases()
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "inputs.json"
            path.write_text(json.dumps(inputs), encoding="utf-8")
            out = json.loads(subprocess.run(["node", str(ROOT / "tests" / "js_check.js"), str(path)],
                                            check=True, capture_output=True, text=True).stdout)
        for rec, js in zip(inputs, out):
            py = [E.check(v) for v in E.views(rec)]
            self.assertEqual(json.loads(json.dumps(py)), js["reports"], rec)
            self.assertEqual(E.eee_structure_errors(rec) if E.is_eee(rec) else [], js["structure"])
            if "eee" in js:                              # the file the browser builds must read back the same
                self.assertEqual(json.loads(json.dumps([E.check(v) for v in E.views(E.to_eee(rec, now=1790000000))])), js["eee_reports"], rec)
                self.assertEqual(json.loads(json.dumps([E.check(v) for v in E.views(js["eee"])])), js["eee_reports"], rec)
        texts = ["Q: {{question}}\nA:", "", "  trailing spaces  \r\nsecond line\t\n\n", "ünïcödé ✓ 測試", "x" * 200]
        self.assertEqual([E.prompt_hash(t) for t in texts], out[-1]["hashes"])


if __name__ == "__main__":
    unittest.main()
