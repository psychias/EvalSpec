"""The reproduction scripts find records in the published JSONL files as well as in the pipeline tree."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import dataset_access as ds


def _doc(title, model, results):
    return {"evaluation_id": f"arxiv/{model}", "model_info": {"name": model, "id": model},
            "source_metadata": {"additional_details": {"paper_title": title}},
            "evaluation_results": [{"evaluation_name": name, "score_details": {"score": score}} for name, score in results]}


@pytest.fixture
def records(tmp_path, monkeypatch):
    arxiv = tmp_path / "arxiv.jsonl"
    olv2 = tmp_path / "olv2.jsonl"
    arxiv.write_text("\n".join(json.dumps(d) for d in [
        _doc("Falcon2-11B Technical Report", "Mistral-7B", [("Belebele (English, 0-shot)", 32.48)]),
        _doc("Falcon2-11B Technical Report", "Mistral-7B", [("Belebele (English, 5-shot)", 79.42)]),
        _doc("OLMo : Accelerating the Science of Language Models", "Llama-2-7B-Chat", [("TruthfulQA", 26.3)]),
        _doc("RecurrentGemma: Moving Past Transformers for Efficient Open Language Models", "Gemma-7B", [("BBH", 57.4)]),
    ]), encoding="utf-8")
    olv2.write_text(json.dumps({"evaluation_id": "olv2/google_gemma-7b", "model_info": {"id": "google/gemma-7b"},
                                "evaluation_results": [{"evaluation_name": "BBH", "score_details": {"score": 21.12}}]}), encoding="utf-8")
    monkeypatch.setattr(ds, "_SOURCES", {"arxiv": ([tmp_path / "no_tree"], arxiv), "olv2": ([tmp_path / "no_tree"], olv2)})
    ds._cache.clear()
    yield
    ds._cache.clear()


def _score(path):
    return json.loads(path.read_text(encoding="utf-8"))["evaluation_results"][0]["score_details"]["score"]


def test_a_record_file_of_the_tree_is_found_in_the_jsonl_file(records):
    path = ds.RecordPath("arxiv") / "Falcon2-11B_Technical_Report" / "Mistral-7B" / "Belebele (English, 5-shot)" / "0000.json"
    assert path.exists()
    assert _score(path) == 79.42
    assert "arxiv/Mistral-7B" in str(path)


def test_shortened_titles_and_reordered_model_names_match(records):
    olmo = ds.RecordPath("arxiv") / "OLMo__Accelerating_the_Science_of_Language_Models" / "Llama-2-Chat-7B" / "TruthfulQA" / "x.json"
    gemma = ds.RecordPath("arxiv") / "RecurrentGemma__Moving_Past_Transformers_for_Efficient_Open_LMs" / "Gemma-7B" / "BBH" / "x.json"
    assert _score(olmo) == 26.3
    assert _score(gemma) == 57.4


def test_a_record_that_is_not_there_does_not_exist(records):
    assert not (ds.RecordPath("arxiv") / "Some_Other_Paper" / "Mistral-7B" / "BBH" / "x.json").exists()
    assert not (ds.RecordPath("arxiv") / "Falcon2-11B_Technical_Report" / "Mistral-7B" / "GSM8K" / "x.json").exists()


def test_leaderboard_records_are_found_by_organisation_and_model(records):
    path = ds.RecordPath("olv2") / "google" / "gemma-7B" / "uuid.json"
    assert _score(path) == 21.12
    assert len(list(ds.RecordPath("olv2").rglob("*.json"))) == 1
