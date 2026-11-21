"""The analysis runs on other data and with other settings than the paper's."""
import csv
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import collision_prevalence as cp
import dataset_access as ds
import reproduce_paper as rp

from eee_eval.analysis import aggregate_results as agg

COLUMNS = ["model", "model_id", "benchmark", "score", "source", "shots", "temperature", "prompt_template",
           "chain_of_thought", "eval_library", "harness", "scoring_method"]
ROWS = [
    {"model_id": "org/model-a", "benchmark": "BBH", "score": "40", "source": "board", "shots": "3", "eval_library": "lm_eval",
     "harness": "lm_eval"},
    {"model_id": "model-a", "benchmark": "BBH (3-shot)", "score": "47", "source": "paper", "temperature": "0.0"},
    {"model_id": "org/model-b", "benchmark": "BBH", "score": "50", "source": "board", "shots": "3", "eval_library": "lm_eval",
     "harness": "lm_eval"},
    {"model_id": "org/model-b", "benchmark": "BBH", "score": "51.5", "source": "paper", "eval_library": "lm_eval", "harness": "lm_eval"},
]


@pytest.fixture
def dataset(tmp_path):
    """A small dataset in the published layout, in a folder of its own."""
    (tmp_path / "aggregated").mkdir()
    with open(tmp_path / "aggregated" / "all_results.csv", "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(ROWS)
    yield tmp_path
    ds.use_data_dir()


def test_data_folder_is_switched_for_every_script(dataset, monkeypatch):
    assert ds.use_data_dir(dataset) == dataset.resolve()
    assert ds.AGGREGATE_CSV == dataset.resolve() / "aggregated" / "all_results.csv"
    assert len(rp.load_aggregate()) == len(ROWS)
    assert len(cp.load_cells()[0]) == len(ROWS)
    assert str(dataset.resolve()) in ds.FETCH_HINT

    ds.use_data_dir()
    assert ds.DATA == (ROOT / "data").resolve()
    monkeypatch.setenv(ds.DATA_ENV, str(dataset))
    assert ds.use_data_dir() == dataset.resolve()


def test_coverage_takes_other_fields_and_sources(dataset):
    rows = rp.load_aggregate(path=dataset / "aggregated" / "all_results.csv")
    assert rp.coverage(rows)["shots"] == 50.0
    assert rp.coverage(rows, {"scored_above_45": lambda r: float(r["score"]) > 45}) == {"scored_above_45": 75.0}
    numbers = rp.coverage_numbers(rows, leaderboards={"board"})
    assert numbers["subset_n"] == 2 and numbers["leaderboard_subset"]["harness"] == 100.0
    assert list(numbers["per_source"]) == ["board"]


def test_collision_thresholds_and_reference_source(dataset):
    _, cells = cp.load_cells(dataset / "aggregated" / "all_results.csv")
    assert cp.prevalence(cells)["differ_gt_1pp"] == 2 and cp.prevalence(cells)["differ_gt_5pp"] == 1
    assert cp.prevalence(cells, small=2, large=10)["differ_gt_1pp"] == 1
    assert cp.prevalence(cells)["harness_missing"] == 1
    assert sorted(cp.reference_gaps(cells, reference="board")["bbh"]) == [1.5, 7.0]
    assert cp.reference_gaps(cells) == {}          # the default reference, OLv2, is not in this data


def test_report_is_a_list_of_sections(dataset, capsys):
    assert len({s.key for s in rp.SECTIONS}) == len(rp.SECTIONS)
    chosen = [s for s in rp.SECTIONS if s.key == "dataset"]
    numbers = rp.compute(chosen, rp.load_aggregate(path=dataset / "aggregated" / "all_results.csv"))
    assert numbers["dataset"]["total_records"] == len(ROWS)
    assert rp.report(numbers, chosen)[0].startswith("Total records:   4")

    out = dataset / "numbers.json"
    assert rp.main(["--data", str(dataset), "--only", "dataset,coverage", "--out", str(out)]) == 0
    assert set(json.loads(out.read_text())) == {"dataset", "coverage", "missing_result_files"}
    assert "Coverage full" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        rp.main(["--only", "no_such_section"])


def test_aggregate_runs_on_any_record_tree(tmp_path, capsys):
    record = {
        "model_info": {"name": "Model A", "id": "org/model-a", "developer": "org"},
        "source_metadata": {"source_name": "open_llm_leaderboard_v2"},
        "eval_library": {"name": "lm_eval", "version": "0.4"},
        "evaluation_results": [
            {"evaluation_name": "Big-Bench Hard", "score_details": {"score": 40.0},
             "generation_config": {"generation_args": {"shots": 3}}},
            {"evaluation_name": "GPQA-Diamond", "score_details": {"score": 20.0}},
        ],
    }
    rows = agg.rows_from_record(record, "somewhere.json")
    assert [r["benchmark"] for r in rows] == ["BBH", "GPQA-Diamond"]
    assert rows[0]["shots"] == 3 and rows[0]["harness"] == "lm_eval" and rows[0]["file"] == "somewhere.json"

    data = tmp_path / "data"
    (data / "board" / "org").mkdir(parents=True)
    (data / "board" / "org" / "a.json").write_text(json.dumps(record), encoding="utf-8")
    (data / "board" / "samples").mkdir()
    (data / "board" / "samples" / "copy.json").write_text(json.dumps(record), encoding="utf-8")
    written = agg.aggregate(data, tmp_path / "out")
    assert len(written) == 2 and written[1]["benchmark"] == "GPQA-Diamond (acc_norm)"
    with open(tmp_path / "out" / "all_results.csv", encoding="utf-8", newline="") as fh:
        assert [r["benchmark"] for r in csv.DictReader(fh)] == ["BBH", "GPQA-Diamond (acc_norm)"]
    assert "OK 2 records" in capsys.readouterr().out
