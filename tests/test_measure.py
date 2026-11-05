"""measure.py never scores a lexicon on the gold that supplied it, and it reads
the lexicon it names and no other."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import orthography2ipa  # noqa: E402

import measure  # noqa: E402


def hamming(left, right):
    return sum(a != b for a, b in zip(left, right)) + abs(len(left) - len(right))


BENCH = SimpleNamespace(
    normalize=lambda ipa, strip_stress, broad, extra_strip="": ipa.replace("ˈ", ""),
    levenshtein=hamming,
    _prosody_marks=lambda code: "",
    _is_multiword=lambda word: " " in word,
)


def test_infopedia_refuses_the_board_dataset_that_holds_it():
    assert measure.supplying_datasets("infopedia") == {
        "infopedia", "portuguese_unified", "portuguese_unified_corrected"}


def test_wikipron_refuses_itself():
    assert measure.supplying_datasets("wikipron") == {"wikipron", "wikipron_corrected"}


def test_score_reads_the_lexicon_it_is_given():
    # One sound of three differs from the gold: PER 1/3.
    assert measure.score(BENCH, [("colonel", "kit")], "en-GB", {"colonel": "kat"}) == (1, 1 / 3)


def test_score_takes_the_best_gold_of_a_word():
    pairs = [("colonel", "kit"), ("colonel", "ˈkat")]
    assert measure.score(BENCH, pairs, "en-GB", {"colonel": "kat"}) == (1, 0.0)


def test_score_averages_over_the_words():
    pairs = [("colonel", "kat"), ("lieutenant", "kit")]
    lexicon = {"colonel": "kat", "lieutenant": "kat"}
    assert measure.score(BENCH, pairs, "en-GB", lexicon) == (2, 1 / 6)


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
def test_a_process_wide_lexicon_does_not_reach_the_rules_row(tmp_path):
    source = tmp_path / "en-GB.tsv"
    source.write_text("colonel\tˈkɜːnəl\n", encoding="utf-8")
    pairs = [("colonel", "ˈkɜːnəl")]
    orthography2ipa.register_lexicon("en-GB", str(source))
    try:
        assert orthography2ipa.G2P("en-GB").transcribe_word("colonel") == "ˈkɜːnəl"
        _covered, per = measure.score(BENCH, pairs, "en-GB", {})
    finally:
        orthography2ipa.clear_lexicons()
    assert per > 0
