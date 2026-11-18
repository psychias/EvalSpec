"""Helpers of scripts/dataset_card_numbers.py. The script itself needs the dataset on disk."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import dataset_card_numbers as card


def test_shares_are_written_as_on_the_card():
    assert card.pct(1977, 2027) == "97.5%"
    assert card.pct(436, 436) == "100%"
    assert card.pct(0, 442) == "0.0%"
    assert card.pct(1, 0) == "0.0%"


def test_paper_titles_are_shortened_to_the_names_on_the_card():
    assert card.short("Pre-training via Structured Pruning: a general framework") == "Sheared LLaMA"
    assert card.short("Phi-3 Technical Report: A Highly Capable Language Model Locally on Your Phone") == "Phi-3"
    assert card.short("A paper that is not in the audit") == "A paper that is not in the audit"


def test_every_source_has_a_file_name():
    import reproduce_paper as rp
    assert (rp.LEADERBOARD_SOURCES | {"arxiv_html_llm", "papers_with_code"}) == set(card.SOURCE_FILES)
