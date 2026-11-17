"""Tests for the registry: how records are grouped, ranked and compared, and what the build writes.

  python -m unittest discover -s tests -v

The last class checks the built site in place. Run  python source/build.py  first.
"""
import csv
import json
import pathlib
import re
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "source"))
import ingest  # noqa: E402

E = ingest.E
PAGES = ["index.html", "registry.html", "model.html", "spec.html", "submit.html", "statistics.html", "data.html", "article.html", "404.html"]


def flat(model="example-org/model-a", bench="gsm8k", score=50.0, source="Source A", **more):
    """A flat record with a 0 to 100 score. Keyword arguments add or replace keys."""
    return {"model_id": model, "benchmark_id": bench, "score": score, "min_score": 0, "max_score": 100,
            "source_name": source, "evidence_source": "source-reported", **more}


def registry(records):
    """The registry built from a list of flat records or EEE files, through a datastore folder on disk."""
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        for i, doc in enumerate(E.to_eee_all(records, now=1790000000)):
            path = root / "data" / f"{i:04d}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(doc), encoding="utf-8")
        return ingest.build(root, "datastore/")


def paper_file(model, bench, score, arxiv="2408.00118", title="A model report"):
    """A file in the layout of the paper's extraction pipeline."""
    return {"schema_version": "0.2.1", "evaluation_id": f"arxiv_html_llm/{model}/{arxiv}/{bench}/{score}", "retrieved_timestamp": "1790000000",
            "source_metadata": {"source_name": "arxiv_html_llm", "source_type": "documentation", "source_organization_name": "arXiv",
                                "evaluator_relationship": "first_party",
                                "additional_details": {"arxiv_id": arxiv, "paper_title": title, "paper_url": f"https://arxiv.org/abs/{arxiv}"}},
            "eval_library": {"name": "unknown", "version": "unknown"}, "model_info": {"name": model, "id": model},
            "evaluation_results": [{"evaluation_name": bench, "source_data": {"dataset_name": bench, "source_type": "url", "url": [f"https://arxiv.org/abs/{arxiv}"]},
                                    "metric_config": {"metric_name": "accuracy", "lower_is_better": False, "score_type": "continuous", "min_score": 0.0, "max_score": 100.0},
                                    "score_details": {"score": score}, "generation_config": {"generation_args": {}, "additional_details": {"source": "arxiv_html_llm"}}}]}


class Names(unittest.TestCase):
    def test_models_match_without_the_organisation(self):
        keys = {ingest.model_key(m) for m in ("google/gemma-2-9b", "Gemma-2-9B", "unsloth/gemma-2-9b")}
        self.assertEqual(keys, {"gemma29b"})
        self.assertNotEqual(ingest.model_key("google/gemma-2-9b-it"), "gemma29b")           # another checkpoint
        self.assertEqual(ingest.model_key("gpt-4o-mini-2024-07-18"), ingest.model_key("openai/gpt-4o-mini"))

    def test_a_name_without_ascii_letters_keeps_its_own_key(self):
        self.assertTrue(ingest.model_key("通义千问"))
        self.assertNotEqual(ingest.model_key("通义千问"), ingest.model_key("文心一言"))

    def test_benchmarks(self):
        self.assertEqual({ingest.benchmark(b)[0] for b in ("BBH", "BBH (3-Shot)", "Big-Bench Hard")}, {"bbh"})
        self.assertEqual(ingest.benchmark("mmlu_pro"), ("mmlupro", "MMLU-Pro"))
        self.assertEqual(ingest.benchmark("Some New Benchmark (5-shot)"), ("somenewbenchmark", "Some New Benchmark"))

    def test_shards_agree_with_the_browser(self):
        # the same numbers as shardOf() in assets/js/site.js gives for these keys
        self.assertEqual([ingest.shard_of("gemma29b", n) for n in (1, 7, 156)], [0, 2, 89])
        self.assertEqual([ingest.shard_of("通义千问", n) for n in (1, 7, 156)], [0, 0, 65])


class Sources(unittest.TestCase):
    def test_kinds(self):
        reg = registry([flat(source="My run"),
                        flat(source="Some Leaderboard", evidence_source="documentation-inferred"),
                        flat(source="HuggingFace Model Card", evidence_source="documentation-inferred"),
                        flat(source="A card", source_kind="Model card", evidence_source="LLM-extracted"),
                        paper_file("Model-A", "gsm8k", 40.0)])
        kinds = {s["label"]: s["kind"] for s in reg["sources"]}
        self.assertEqual(kinds, {"My run": "Evaluation run", "Some Leaderboard": "Leaderboard", "HuggingFace Model Card": "Model card",
                                 "A card": "Model card", "A model report": "Paper"})

    def test_a_paper_is_one_source_whoever_uploads_its_records(self):
        mine = flat(model="example-org/Model-A", source="A model report", source_kind="Paper", source_url="https://arxiv.org/abs/2408.00118", score=41.0)
        reg = registry([paper_file("Model-A", "gsm8k", 40.0), mine])
        self.assertEqual(len(reg["sources"]), 1)
        source = reg["sources"][0]
        self.assertEqual((source["kind"], source["ref"], source["author"], source["predicted"]), ("Paper", "arXiv:2408.00118", 1, 1))


class Board(unittest.TestCase):
    def test_first_hand_ranks_first(self):
        reg = registry([
            flat(source="Says nothing", evidence_source="documentation-inferred"),
            flat(source="Inferred", evidence_source="documentation-inferred", n_shot=5, harness_name="lm-evaluation-harness"),
            flat(source="Read by a model", evidence_source="LLM-extracted", n_shot=5),
            flat(source="Reports itself", n_shot=5),
            flat(source="Says nothing either", evidence_source="pipeline-default"),
        ])
        order = [(s["rank"], s["label"]) for s in reg["sources"]]
        self.assertEqual(order, [(1, "Reports itself"), (2, "Read by a model"), (3, "Inferred"), (4, "Says nothing"), (4, "Says nothing either")])

    def test_procedure_fields_leave_out_model_and_benchmark(self):
        (source,) = registry([flat(n_shot=5, scoring_mode="log-likelihood")])["sources"]
        # eight Required fields describe the procedure of a log-likelihood result; three are on record (judge_model follows from the mode)
        self.assertEqual((source["cov"]["of"], source["cov"]["have"], source["cov"]["first_hand"]), (8, 3, 3))

    def test_own_records_supersede_predicted_ones(self):
        reg = registry([paper_file("Model-A", "gsm8k", 40.0), paper_file("Model-A", "mmlu", 60.0),
                        flat(model="example-org/Model-A", source="A model report", source_kind="Paper", source_url="https://arxiv.org/abs/2408.00118",
                             score=40.0, n_shot=8, scoring_mode="generation")])
        (source,) = reg["sources"]
        self.assertEqual([r["superseded"] for r in reg["records"]], [True, False, False])
        self.assertEqual(source["superseded"], 1)
        self.assertEqual(source["cov"]["of"], 8 + 9)             # the mmlu record and the author's own; the superseded one is not counted
        self.assertEqual(reg["cells"], [])                       # and it is not compared with the record that replaces it


class Cells(unittest.TestCase):
    def cell(self, *records):
        (cell,) = registry(list(records))["cells"]
        return cell

    def test_a_firm_difference(self):
        c = self.cell(flat(source="A", n_shot=0, score=30.0), flat(source="B", n_shot=5, score=70.0))
        self.assertEqual((c["procedure"], c["differs"], c["spread"], c["sources"]), ("different", ["n_shot"], 40.0, 2))

    def test_inferred_values_do_not_make_a_firm_difference(self):
        c = self.cell(flat(source="A", n_shot=0, evidence_source="documentation-inferred"), flat(source="B", n_shot=5, evidence_source="pipeline-default"))
        self.assertEqual((c["procedure"], c["differs"], c["soft"]), ("unknown", [], ["n_shot"]))

    def test_harness_spellings_are_one_harness(self):
        c = self.cell(flat(source="A", harness_name="lm_eval"), flat(source="B", harness_name="lm-evaluation-harness"))
        self.assertNotIn("harness_name", c["differs"] + c["soft"])

    def test_same_procedure_needs_every_field(self):
        full = dict(scoring_mode="log-likelihood", harness_name="h", harness_version="1.0", n_shot=5, benchmark_variant="v",
                    prompt_template_hash="sha256:" + "a" * 64)
        c = self.cell(flat(source="A", evaluation_timestamp="2026-01-01", **full), flat(source="B", evaluation_timestamp="2026-02-01", **full))
        self.assertEqual((c["procedure"], c["independent"]), ("same", "yes"))
        c = self.cell(flat(source="A", n_shot=5), flat(source="B", n_shot=5))
        self.assertEqual(c["procedure"], "unknown")

    def test_equal_scores_without_dates_may_be_one_measurement(self):
        c = self.cell(flat(source="A", score=34.1), flat(source="B", score=34.1))
        self.assertEqual(c["independent"], "twins")


class Payload(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reg = ingest.build(ROOT / "datastore", "datastore/")
        cls.payload = json.loads(json.dumps(ingest.payload(cls.reg, {})))

    def record(self, p, i):
        """One record put back together, as decode() in assets/js/site.js does."""
        S, C = p["strings"], p["cols"]
        values = {"model_id": S[C["mid"][i]], "benchmark_id": S[C["bname"][i]]}
        values.update({k: S[C[k][i]] for k in ingest.KEY_FIELDS if C[k][i]})
        if C["more"][i]:
            values.update(json.loads(S[C["more"][i]]))
        return values

    def test_columns(self):
        p = self.payload
        self.assertEqual(p["n"], len(self.reg["records"]))
        self.assertEqual({len(col) for col in p["cols"].values()}, {p["n"]})

    def test_records_survive_the_encoding(self):
        text = lambda v: "none" if v is None else v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
        for i, r in enumerate(self.reg["records"]):
            got = self.record(self.payload, i)
            want = {k: (text(v) if k in ingest.KEY_FIELDS else v) for k, v in r["values"].items()}
            self.assertEqual(got, want)
            status = self.payload["strings"][self.payload["cols"]["sig"][i]]
            self.assertEqual(len(status), len(E.FIELDS))
            self.assertEqual(sum(c in "123" for c in status), sum(c["have"] for c in r["report"]["coverage"].values()))

    def test_every_model_is_in_exactly_one_per_model_file(self):
        shards, seen = 7, []
        for n in range(shards):
            keys = {m["key"] for m in self.reg["models"] if ingest.shard_of(m["key"], shards) == n}
            part = ingest.payload(ingest.subset(self.reg, keys), {})
            self.assertEqual({m["key"] for m in part["models"]}, keys)
            self.assertTrue(all(0 <= c["model"] < len(part["models"]) and 0 <= c["bench"] < len(part["benches"]) for c in part["cells"]))
            seen += [m["key"] for m in part["models"]]
        self.assertEqual(sorted(seen), sorted(m["key"] for m in self.reg["models"]))

    def test_the_bundled_sample(self):
        s = self.reg["stats"]
        snapshot = json.loads((ROOT / "datastore" / "snapshot.json").read_text(encoding="utf-8"))
        self.assertEqual((s["files"], s["records"]), (snapshot["files"], snapshot["records"]))
        self.assertEqual(s["malformed"], 0)
        self.assertEqual(self.reg["skipped"], [])
        # the case the paper opens with: 34.10 on the leaderboard, 68.20 in the model's own report
        scores = {r["context"]["score"] for r in self.reg["records"] if r["model"] == "gemma29b" and r["bench"] == "bbh"}
        self.assertLessEqual({34.1, 68.2}, scores)


@unittest.skipUnless((ROOT / "index.html").is_file() and (ROOT / "data" / "registry.js").is_file(), "the site has not been built")
class BuiltSite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = {p: (ROOT / p).read_text(encoding="utf-8") for p in PAGES}
        text = (ROOT / "data" / "registry.js").read_text(encoding="utf-8")
        cls.registry = json.loads(text[text.index("=") + 1:].rstrip().rstrip(";"))

    def test_pages_are_complete(self):
        for page, html in self.html.items():
            self.assertNotRegex(html, r"\{\{\w+\}\}", f"{page} has an unfilled placeholder")
            self.assertEqual(len(re.findall(r"<h1[ >]", html)), 1, f"{page} needs exactly one h1")
            self.assertIn('<main', html)
            ids = re.findall(r'\sid="([^"]+)"', html)
            self.assertEqual(len(ids), len(set(ids)), f"{page} repeats an id: {sorted({i for i in ids if ids.count(i) > 1})}")

    def test_nothing_is_loaded_from_another_site(self):
        for page, html in self.html.items():
            loaded = re.findall(r'<(?:script|img|iframe|source)[^>]*\ssrc="([^"]+)"', html) + re.findall(r'<link[^>]*rel="(?:stylesheet|preload|icon)"[^>]*href="([^"]+)"', html)
            self.assertEqual([u for u in loaded if re.match(r"(https?:)?//", u)], [], page)
        css = (ROOT / "assets" / "css" / "site.css").read_text(encoding="utf-8") + (ROOT / "assets" / "css" / "article.css").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"url\(\s*[\"']?(?:https?:)?//", css), [])

    def test_local_links_lead_somewhere(self):
        ids = {page: set(re.findall(r'\sid="([^"]+)"', html)) for page, html in self.html.items()}
        for page, html in self.html.items():
            html = re.sub(r"<script>.*?</script>", "", html, flags=re.S)       # the one inline script (404.html) writes a <base> tag
            for url in set(re.findall(r'(?:href|src)="([^"]+)"', html)):
                if re.match(r"(https?:|mailto:|data:)", url):
                    continue
                self.assertFalse(url.startswith("/"), f"{page}: {url} would break when the site is not served from the root of its host")
                path, _, fragment = url.partition("#")
                path = path.split("?")[0] or page
                self.assertTrue((ROOT / path).exists(), f"{page} links to {url}, which does not exist")
                fragment = fragment.split("?")[0]
                if fragment and path in ids and not (path == "registry.html" and fragment in ("board", "records", "cells")):
                    self.assertIn(fragment, ids[path], f"{page} links to {url}, but {path} has no element with that id")

    def test_data_files_agree(self):
        p = self.registry
        self.assertEqual({len(col) for col in p["cols"].values()}, {p["n"]})
        with open(ROOT / "data" / "records.csv", encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), p["n"])
        with open(ROOT / "data" / "board.csv", encoding="utf-8", newline="") as f:
            self.assertEqual(len(list(csv.DictReader(f))), len(p["sources"]))
        stats = json.loads((ROOT / "data" / "stats.json").read_text(encoding="utf-8"))
        self.assertEqual(stats["records"], p["n"])
        self.assertEqual(stats["tracks"]["author-reported"] + stats["tracks"]["predicted"], p["n"])
        ranks = [s["rank"] for s in p["sources"]]
        self.assertEqual(ranks, sorted(ranks))

    def test_per_model_files(self):
        spec = (ROOT / "data" / "spec.js").read_text(encoding="utf-8")
        site = json.loads(spec[spec.index("window.EVALSPEC_SITE = ") + len("window.EVALSPEC_SITE = "):].rstrip().rstrip(";"))
        files = sorted(int(f.stem) for f in (ROOT / "data" / "model").glob("*.js"))
        self.assertEqual(files, list(range(site["shards"])))
        found = 0
        for n in files:
            text = (ROOT / "data" / "model" / f"{n}.js").read_text(encoding="utf-8")
            part = json.loads(text[text.index(f"[{n}] = ") + len(f"[{n}] = "):].rstrip().rstrip(";"))
            self.assertTrue(all(ingest.shard_of(m["key"], site["shards"]) == n for m in part["models"]))
            found += part["n"]
        self.assertEqual(found, self.registry["n"])

    def test_bundled_records_can_be_opened(self):
        base = self.registry["meta"]["datastore"]["file_base"]
        if re.match(r"https?:", base):
            self.skipTest("built from the full datastore: the files are on Hugging Face")
        S, C = self.registry["strings"], self.registry["cols"]
        for i in range(self.registry["n"]):
            self.assertTrue((ROOT / base / S[C["file"][i]]).is_file())

    def test_the_schema_is_current(self):
        version = E.SPEC["version"]
        built = json.loads((ROOT / "spec" / f"evalspec-{version}.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(built["properties"], json.loads(json.dumps(E.json_schema()))["properties"])


if __name__ == "__main__":
    unittest.main()
