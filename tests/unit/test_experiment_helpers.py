"""The helpers the experiment scripts share: statistics, and the frame of a GPU run."""
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments"))
from common import lm_eval_runs as runs
from common import stats

from eee_eval import paths

GROUPS = [[61.0, 63.5, 60.2, 64.1], [55.3, 57.9, 54.0, 58.8], [40.2, 44.7, 39.9, 47.3]]


def test_statistics_agree_with_scipy():
    scipy_stats = pytest.importorskip("scipy.stats")
    result = stats.oneway_anova(GROUPS)
    F, p = scipy_stats.f_oneway(*GROUPS)
    assert result["F"] == pytest.approx(F) and result["p"] == pytest.approx(p, rel=1e-4)
    assert (result["dfb"], result["dfw"], result["sizes"]) == (2, 9, [4, 4, 4])
    assert result["eta2"] == pytest.approx(stats.eta_squared(GROUPS))
    assert stats.chi2_sf(7.3, 2) == pytest.approx(scipy_stats.chi2.sf(7.3, 2))
    assert stats.f_sf(3.2, 2, 9) == pytest.approx(scipy_stats.f.sf(3.2, 2, 9), rel=1e-4)

    matrix = [[7, 5, 3], [8, 6, 2], [6, 7, 1], [9, 4, 5]]          # no ties: the plain statistic is exact
    stat, df, w = stats.friedman(matrix)
    assert stat == pytest.approx(scipy_stats.friedmanchisquare(*zip(*matrix)).statistic)
    assert df == 2 and w == pytest.approx(stat / (4 * 2))


def test_statistics_edge_cases():
    assert stats.oneway_anova([[1.0], [2.0]]) is None                 # no more values than groups
    constant = stats.oneway_anova([[1.0, 1.0], [2.0, 2.0]])
    assert constant["F"] == float("inf") and constant["p"] == 0.0 and constant["eta2"] == 1.0
    assert stats.eta_squared([[5.0, 5.0], [5.0]], when_constant=0.0) == 0.0
    assert stats.eta_squared([]) != stats.eta_squared([])             # nan by default


def test_model_option_and_cell_grouping():
    assert runs.model_spec("org/name") == ("org/name", "org/name", 8)
    assert runs.model_spec("mirror/name=org/name@4") == ("mirror/name", "org/name", 4)
    args = runs.parse(runs.grid_parser("x", [("a/b", "a/b", 16)], seeds=[42]), ["--seeds", "1", "2", "--formats", "cot"])
    assert args.models == [("a/b", "a/b", 16)] and args.seeds == [1, 2] and args.formats == ["cot"]
    cells = [dict(eval_id=m, model_id=m, batch_size=8, seed=s) for m in ("a", "b") for s in (1, 2)]
    assert [(key[0], len(group)) for key, group in runs.by_model(cells)] == [("a", 2), ("b", 2)]
    assert runs.seeded(7, fewshot=True)["fewshot_random_seed"] == 7 and "fewshot_random_seed" not in runs.seeded(7)
    assert runs.percent({"acc,none": 0.5}, "acc_norm,none", "acc,none") == 50.0
    assert runs.percent({}, "acc,none") is None


def test_run_cell_records_scores_and_failures(capsys, monkeypatch):
    calls = []

    def simple_evaluate(**kwargs):
        calls.append(kwargs)
        if len(calls) < 3:
            raise RuntimeError("out of memory")
        return {"results": {"gsm8k": {"exact_match,strict-match": 0.585}}}

    monkeypatch.setitem(sys.modules, "lm_eval", types.SimpleNamespace(simple_evaluate=simple_evaluate))
    monkeypatch.setattr(runs.time, "sleep", lambda seconds: None)

    record = runs.run_cell({"model_id": "m"}, lambda: runs.evaluate("lm", attempts=3, note="cell", tasks=["gsm8k"]),
                           lambda r: runs.percent(r["results"]["gsm8k"], "exact_match,strict-match"))
    assert record == {"model_id": "m", "score": 58.5, "status": "ok"} and len(calls) == 3
    assert calls[0] == {"model": "lm", "tasks": ["gsm8k"]}

    calls.clear()
    failed = runs.run_cell({"model_id": "m"}, lambda: runs.evaluate("lm", attempts=2, tasks=["gsm8k"]), lambda r: 1, note="m cot")
    assert failed["status"] == "error" and failed["reason"] == "out of memory"
    lines = capsys.readouterr().out.splitlines()
    assert json.loads(lines[-2].removeprefix("RESULT ")) == failed and lines[-1] == "[cell-error] m cot: out of memory"


@pytest.mark.parametrize("script", sorted(
    str(p.relative_to(ROOT)) for pattern in ("controlled_eval/scripts/rerun_*.py", "controlled_eval/scripts/gsm8k_hf_*.py",
                                             "controlled_eval/full_vs_*.py", "scoring_mode_eval/rerun_*.py",
                                             "bbh_protocol/sealion_provenance/rerun_*.py")
    for p in (ROOT / "experiments").glob(pattern)))
def test_gpu_scripts_import_without_starting_a_run(script, monkeypatch):
    for name in ("lm_eval", "torch"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    spec = importlib.util.spec_from_file_location("gpu_script", ROOT / script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)                    # would install packages and load a model if it ran anything
    assert callable(module.main) and "lm_eval" not in sys.modules
    if "--dry-run" in (module.__doc__ or ""):
        assert module.main(["--dry-run"]) is None


def test_package_folders_come_from_one_module(monkeypatch):
    from eee_eval.analysis import aggregate_results
    from eee_eval.validation import quality_audit
    assert aggregate_results.DATA_DIR == paths.DATA_DIR == quality_audit._DATA_DIR
    assert paths.SCHEMA_PATH.exists() and (paths.ROOT / "pyproject.toml").exists()

    monkeypatch.delenv("EVALSPEC_TEST_KEY", raising=False)
    env = paths.ROOT / "tests" / "data"
    monkeypatch.setattr(paths, "ENV_FILE", env / "no-such-file")
    paths.load_dotenv("EVALSPEC_TEST_KEY")             # a missing file is not an error
