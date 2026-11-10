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

    def make(exceptions, patches, patch_meta=None):
        write_file(tmp_path / "en-GB", "en-GB", "".join(f"{w}\t{i}\n" for w, i in exceptions.items()),
                   {**SIDECAR, "kind": "exception",
                    "reasons": dict.fromkeys(exceptions, "unclassified"),
                    "citations": dict.fromkeys(exceptions, "a cited source")})
        write_file(tmp_path / "patches" / "en-GB", "en-GB",
                   "".join(f"{w}\t{i}\n" for w, i in patches.items()),
                   {**SIDECAR, "kind": "patch",
                    "reasons": dict.fromkeys(patches, "unclassified"),
                    "gaps": dict.fromkeys(patches, "lead: x"), **(patch_meta or {})})
        return tmp_path
    return make


#: The fields of a valid en-GB sidecar that a prune leaves as they are.
SIDECAR = {"code": "en-GB", "source": "wikipron", "source_url": "https://example.org/en.tsv",
           "tier": "crowd-scraped", "licence": "CC-BY-SA-4.0",
           "build_command": "python scripts/build_lexicon.py en-GB", "o2i_version": "1.0.0",
           "stress": "rules", "reason_basis": {}}


def test_write_prunes_a_stale_patch(packaged):
    # The rules read cat /kæt/; colonel stays wrong.
    root = packaged({"colonel": "kɜːnəl"}, {"cat": "kæt", "colonel": "kɜːnəl"})
    assert prune_check.main(["--cache", str(root)]) == 1
    assert prune_check.main(["--cache", str(root), "--write"]) == 0
    patches = root / "patches" / "en-GB"
    assert (patches / "wikipron.tsv").read_text(encoding="utf-8") == "colonel\tkɜːnəl\n"
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
    root = packaged({"colonel": "kɜːnəl"}, {})
    report = root / "report.json"
    assert prune_check.main(["--cache", str(root), "--write", "--report", str(report)]) == 0
    assert json.loads(report.read_text(encoding="utf-8"))["codes"] == {"en-GB": {
        "exception": {"entries": 1, "stale": []}, "patch": {"entries": 0, "stale": []}}}
    assert (root / "patches" / "en-GB" / "wikipron.tsv").read_text(encoding="utf-8") == ""


def test_write_stops_when_a_written_file_fails_the_schema(packaged):
    # The prune keeps colonel, whose reading holds a digit, which is not IPA.
    root = packaged({"colonel": "kɜːnəl"}, {"cat": "kæt", "colonel": "kɜːn3l"})
    report = root / "report.json"
    with pytest.raises(SystemExit, match=r"wikipron.tsv line 1: IPA not NFC / not IPA-only: 'kɜːn3l'"):
        prune_check.main(["--cache", str(root), "--write", "--report", str(report)])
    assert not report.exists()


def test_write_stops_when_a_written_sidecar_fails_the_schema(packaged):
    root = packaged({"colonel": "kɜːnəl"}, {"cat": "kæt", "colonel": "kɜːnəl"},
                    patch_meta={"tier": "llm-generated"})
    report = root / "report.json"
    with pytest.raises(SystemExit, match="tier 'llm-generated' cannot supply entries"):
        prune_check.main(["--cache", str(root), "--write", "--report", str(report)])
    assert not report.exists()
