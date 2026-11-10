"""The prune check finds the entries that the rules alone now get right."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import orthography2ipa  # noqa: E402
import orthography2ipa.version  # noqa: E402

import prune_check  # noqa: E402

STRESS = "ˈˌ"


def board_like_normalize(ipa, strip_stress, broad, extra_strip=""):
    return "".join(c for c in ipa if c not in STRESS) if strip_stress else ipa


BENCH = SimpleNamespace(normalize=board_like_normalize, _prosody_marks=lambda code: "")


def test_an_entry_the_rules_reach_is_stale():
    # English ⟨cat⟩ is /kæt/; ⟨colonel⟩ is /ˈkɜːnəl/, which no letter-by-letter
    # reading gives.
    entries = {"cat": "kæt", "colonel": "ˈkɜːnəl"}
    assert prune_check.stale_entries("en-GB", entries, BENCH, "rules") == ["cat"]


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
        assert prune_check.stale_entries("en-GB", entries, BENCH, "rules") == []
    finally:
        orthography2ipa.clear_lexicons()


def test_a_pruned_word_leaves_every_record_of_the_sidecar():
    meta = {
        "reasons": {"gel": "open", "bege": "open", "hotel": "final"},
        "reason_basis": {"open": "a", "final": "b"},
        "wiktionary_readings": ["bege", "gel"],
        "gaps": {"gel": "o2i#1", "bege": "o2i#2", "hotel": "o2i#3"},
        "lexical_classes": {"gel": {"class": "x"}, "bege": {"class": "y"}},
    }
    prune_check.forget(meta, ["gel", "hotel"])
    assert meta == {
        "reasons": {"bege": "open"},
        "reason_basis": {"open": "a"},
        "wiktionary_readings": ["bege"],
        "gaps": {"bege": "o2i#2"},
        "lexical_classes": {"bege": {"class": "y"}},
    }


def test_a_sidecar_without_mined_words_needs_no_such_field():
    meta = {"reasons": {"sal": "x"}, "reason_basis": {}}
    prune_check.forget(meta, ["sal"])
    assert meta == {"reasons": {}, "reason_basis": {}}


def write_file(root, code, body, meta):
    root.mkdir(parents=True, exist_ok=True)
    (root / "wikipron.tsv").write_text(body, encoding="utf-8")
    (root / "wikipron.meta.json").write_text(json.dumps(meta), encoding="utf-8")


@pytest.fixture
def packaged(tmp_path, monkeypatch):
    """An en-GB exception file and patch file under a temporary data tree."""
    import o2i_lexicons
    monkeypatch.setattr(o2i_lexicons, "DATA_DIR", tmp_path)
    monkeypatch.setattr(prune_check.o2i_harness, "load_benchmark", lambda cache: BENCH)

    def make(exceptions, patches, code="en-GB", stress="rules"):
        write_file(tmp_path / code, code, "".join(f"{w}\t{i}\n" for w, i in exceptions.items()),
                   {"kind": "exception", "o2i_version": "1.0.0", "stress": stress,
                    "reasons": dict.fromkeys(exceptions, "unclassified"), "reason_basis": {},
                    "citations": dict.fromkeys(exceptions, "a cited source")})
        write_file(tmp_path / "patches" / code, code,
                   "".join(f"{w}\t{i}\n" for w, i in patches.items()),
                   {"kind": "patch", "o2i_version": "1.0.0", "stress": stress,
                    "reasons": dict.fromkeys(patches, "unclassified"), "reason_basis": {},
                    "gaps": dict.fromkeys(patches, "lead: x")})
        return tmp_path
    return make


def test_write_prunes_a_stale_patch(packaged):
    # The rules read cat /kæt/; colonel stays wrong.
    root = packaged({"colonel": "ˈkɜːnəl"}, {"cat": "kæt", "colonel": "ˈkɜːnəl"})
    assert prune_check.main(["--cache", str(root)]) == 1
    assert prune_check.main(["--cache", str(root), "--write"]) == 0
    patches = root / "patches" / "en-GB"
    assert (patches / "wikipron.tsv").read_text(encoding="utf-8") == "colonel\tˈkɜːnəl\n"
    meta = json.loads((patches / "wikipron.meta.json").read_text(encoding="utf-8"))
    assert (meta["gaps"], meta["reasons"]) == ({"colonel": "lead: x"}, {"colonel": "unclassified"})
    assert meta["o2i_version"] == orthography2ipa.version.VERSION_STR
    assert prune_check.main(["--cache", str(root)]) == 0


def test_a_stale_exception_fails_and_stays(packaged):
    # An exception that the rules read means that its class is wrong; a
    # person moves it.
    root = packaged({"cat": "kæt"}, {})
    before = (root / "en-GB" / "wikipron.tsv").read_text(encoding="utf-8")
    assert prune_check.main(["--cache", str(root), "--write"]) == 1
    assert (root / "en-GB" / "wikipron.tsv").read_text(encoding="utf-8") == before


def test_an_empty_patch_file_is_checked(packaged):
    root = packaged({"colonel": "ˈkɜːnəl"}, {})
    report = root / "report.json"
    assert prune_check.main(["--cache", str(root), "--write", "--report", str(report)]) == 0
    assert json.loads(report.read_text(encoding="utf-8"))["codes"] == {"en-GB": {
        "exception": {"entries": 1, "stale": []}, "patch": {"entries": 0, "stale": []}}}
    assert (root / "patches" / "en-GB" / "wikipron.tsv").read_text(encoding="utf-8") == ""


def rules_reading(code, word):
    engine = orthography2ipa.G2P(code, expose_ambiguous_endings=False,
                                 pipeline=orthography2ipa.Pipeline(lexicon={}))
    return engine.transcribe_word(word)


def first_syllable_stress(code, word):
    """The rules' reading of *word* with the stress moved to the first sound."""
    rules = rules_reading(code, word)
    assert rules.index("ˈ") > 0
    return "ˈ" + rules.replace("ˈ", "")


def test_a_source_entry_that_differs_only_in_stress_is_not_stale():
    # The rules stress taoismo on ⟨o⟩; this entry stresses ⟨a⟩. The rules would
    # read it with the wrong stress, so the entry stays.
    moved = first_syllable_stress("pt-PT", "taoismo")
    assert prune_check.stale_entries("pt-PT", {"taoismo": moved}, BENCH, "source") == []
    rules = rules_reading("pt-PT", "taoismo")
    assert prune_check.stale_entries("pt-PT", {"taoismo": rules}, BENCH, "source") == ["taoismo"]


def test_a_rules_entry_takes_its_stress_from_the_rules():
    # A rules file holds no stress mark: the rules place the stress on output.
    entry = rules_reading("pt-PT", "taoismo").replace("ˈ", "")
    assert prune_check.stale_entries("pt-PT", {"taoismo": entry}, BENCH, "rules") == ["taoismo"]


def test_a_mark_after_the_onset_stresses_the_same_vowel():
    # cavalo: the rules write the mark before [v], the entry after it. Both
    # stress the same [a].
    rules = rules_reading("pt-PT", "cavalo")
    mark = rules.index("ˈ")
    assert rules[mark + 1] not in "aɐeɛiɨoɔu"
    entry = rules[:mark] + rules[mark + 1] + "ˈ" + rules[mark + 2:]
    assert prune_check.stale_entries("pt-PT", {"cavalo": entry}, BENCH, "source") == ["cavalo"]


def test_write_keeps_a_patch_whose_stress_the_rules_miss(packaged):
    moved = first_syllable_stress("pt-PT", "taoismo")
    root = packaged({}, {"taoismo": moved}, code="pt-PT", stress="source")
    assert prune_check.main(["--cache", str(root), "--write"]) == 0
    patches = root / "patches" / "pt-PT" / "wikipron.tsv"
    assert patches.read_text(encoding="utf-8") == f"taoismo\t{moved}\n"


def test_an_exception_whose_stress_the_rules_miss_is_not_stale(packaged):
    moved = first_syllable_stress("pt-PT", "taoismo")
    root = packaged({"taoismo": moved}, {}, code="pt-PT", stress="source")
    assert prune_check.main(["--cache", str(root)]) == 0
