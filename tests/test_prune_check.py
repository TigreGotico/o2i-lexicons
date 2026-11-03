"""The prune check finds the entries that the rules alone now get right."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from orthography2ipa import g2p as g2p_module  # noqa: E402

import prune_check  # noqa: E402

STRESS = "ˈˌ"


def board_like_normalize(ipa, strip_stress, broad, extra_strip=""):
    return "".join(c for c in ipa if c not in STRESS)


BENCH = SimpleNamespace(normalize=board_like_normalize, _prosody_marks=lambda code: "")


@pytest.fixture
def rules_only(monkeypatch):
    monkeypatch.setattr(g2p_module, "get_lexicon", lambda code: {})


def test_an_entry_the_rules_reach_is_stale(rules_only):
    # English ⟨cat⟩ is /kæt/; ⟨colonel⟩ is /ˈkɜːnəl/, which no letter-by-letter
    # reading gives.
    entries = {"cat": "kæt", "colonel": "ˈkɜːnəl"}
    assert prune_check.stale_entries("en-GB", entries, BENCH) == ["cat"]


def test_the_check_needs_every_lexicon_disabled(monkeypatch):
    # With the lexicon active, colonel would come back right from the lexicon.
    # main() disables every lexicon before it checks, as this fixture does.
    entries = {"colonel": "ˈkɜːnəl"}
    monkeypatch.setattr(g2p_module, "get_lexicon", lambda code: dict(entries))
    assert prune_check.stale_entries("en-GB", entries, BENCH) == ["colonel"]
    monkeypatch.setattr(g2p_module, "get_lexicon", lambda code: {})
    assert prune_check.stale_entries("en-GB", entries, BENCH) == []
