"""scripts/olv2_raw_scores.py: the saved leaderboard rows carry the scores the paper quotes."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import olv2_raw_scores as olv2


def test_saved_rows_are_complete():
    rows = olv2.saved()
    assert {r["fullname"] for r in rows} == set(olv2.MODELS)
    assert all(len(r) == 36 for r in rows)          # every column of the leaderboard's table


def test_quoted_scores_are_in_the_saved_rows(capsys):
    assert olv2.check(olv2.saved()) == 0
    assert "DIFFERS" not in capsys.readouterr().out


def test_a_wrong_score_is_reported(capsys):
    rows = [dict(r) for r in olv2.saved()]
    for r in rows:
        if r["eval_name"] == "google_gemma-7b_bfloat16":
            r["BBH Raw"] = 0.5
    assert olv2.check(rows) == 1
    assert "DIFFERS" in capsys.readouterr().out
