"""The prune check finds the entries that the rules alone now get right."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import orthography2ipa  # noqa: E402

import prune_check  # noqa: E402

STRESS = "ˈˌ"


def board_like_normalize(ipa, strip_stress, broad, extra_strip=""):
    return "".join(c for c in ipa if c not in STRESS)


BENCH = SimpleNamespace(normalize=board_like_normalize, _prosody_marks=lambda code: "")


def test_an_entry_the_rules_reach_is_stale():
    # English ⟨cat⟩ is /kæt/; ⟨colonel⟩ is /ˈkɜːnəl/, which no letter-by-letter
    # reading gives.
    entries = {"cat": "kæt", "colonel": "ˈkɜːnəl"}
    assert prune_check.stale_entries("en-GB", entries, BENCH) == ["cat"]


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
def test_a_process_wide_lexicon_does_not_reach_the_check(tmp_path):
    # A plain engine reads colonel from this lexicon, so the entry would pass
    # as stale. The check reads the rules alone.
    entries = {"colonel": "ˈkɜːnəl"}
    source = tmp_path / "en-GB.tsv"
    source.write_text("colonel\tˈkɜːnəl\n", encoding="utf-8")
    orthography2ipa.register_lexicon("en-GB", str(source))
    try:
        assert orthography2ipa.G2P("en-GB").transcribe_word("colonel") == entries["colonel"]
        assert prune_check.stale_entries("en-GB", entries, BENCH) == []
    finally:
        orthography2ipa.clear_lexicons()


def test_a_pruned_word_leaves_every_record_of_the_sidecar():
    meta = {
        "reasons": {"gel": "open", "bege": "open", "hotel": "final"},
        "reason_basis": {"open": "a", "final": "b"},
        "wiktionary_readings": ["bege", "gel"],
    }
    prune_check.forget(meta, ["gel", "hotel"])
    assert meta == {
        "reasons": {"bege": "open"},
        "reason_basis": {"open": "a"},
        "wiktionary_readings": ["bege"],
    }


def test_a_sidecar_without_mined_words_needs_no_such_field():
    meta = {"reasons": {"sal": "x"}, "reason_basis": {}}
    prune_check.forget(meta, ["sal"])
    assert meta == {"reasons": {}, "reason_basis": {}}
