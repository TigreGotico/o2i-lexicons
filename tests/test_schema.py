import pytest

from o2i_lexicons.schema import REASON_CLASSES, validate_meta, validate_tsv


def good_meta(**overrides):
    meta = {
        "kind": "exception",
        "code": "en-GB",
        "source": "wikipron",
        "source_url": "https://example.org/eng_latn_uk_broad.tsv",
        "tier": "crowd-scraped",
        "licence": "CC-BY-SA-3.0",
        "build_command": "python scripts/build.py en-GB",
        "o2i_version": "7.111.21a1",
        "stress": "rules",
        "reasons": {"colonel": "unclassified", "nato": "acronym"},
        "reason_basis": {"acronym": "the source headword is all capitals"},
        "citations": {"colonel": "no source read", "nato": "no source read"},
    }
    meta.update(overrides)
    return meta


WORDS = {"colonel": "kɜːnəl", "nato": "neɪtəʊ"}


def test_clean_tsv_has_no_problems():
    assert validate_tsv("choir\tˈkwaɪə\ncolonel\tˈkɜːnəl\n") == []


@pytest.mark.parametrize("text, line_no, needle", [
    ("colonel ˈkɜːnəl\n", 1, "expected 'word<TAB>ipa'"),
    ("Colonel\tˈkɜːnəl\n", 1, "not lowercase"),
    ("colonel\tkɜːnəl1\n", 1, "IPA-only"),
    ("colonel\tké\n", 1, "IPA not NFC"),
    ("café\tkafe\n", 1, "not NFC"),
    ("choir\tˈkwaɪə\nchoir\tˈkwaɪɚ\n", 2, "duplicate word"),
    ("colonel\tˈkɜːnəl\nchoir\tˈkwaɪə\n", 2, "not sorted"),
    ("choir\tˈkwaɪə", 1, "no newline"),
])
def test_bad_tsv_is_reported(text, line_no, needle):
    problems = validate_tsv(text)
    assert any(n == line_no and needle in reason for n, reason in problems), problems


def test_clean_meta_has_no_problems():
    assert validate_meta(good_meta(), "en-GB", WORDS) == []


def test_missing_keys_are_named():
    meta = good_meta()
    del meta["licence"]
    del meta["o2i_version"]
    assert validate_meta(meta, "en-GB", WORDS) == [
        "missing key: licence", "missing key: o2i_version"]


@pytest.mark.parametrize("tier", ["llm-generated", "espeak-derived", "epitran-derived", "gold"])
def test_silver_and_competitor_tiers_are_refused(tier):
    assert validate_meta(good_meta(tier=tier), "en-GB", WORDS) == [
        f"tier {tier!r} cannot supply entries"]


@pytest.mark.parametrize("tier", ["expert-human", "lexicon-derived", "crowd-scraped", "machine-generated"])
def test_gating_tiers_are_accepted(tier):
    assert validate_meta(good_meta(tier=tier), "en-GB", WORDS) == []


def test_code_must_match_directory():
    assert validate_meta(good_meta(), "en-US", WORDS) == [
        "code 'en-GB' does not match directory 'en-US'"]


@pytest.mark.parametrize("version", ["7.111", "latest", "7.111.21-alpha", ""])
def test_o2i_version_must_be_a_release(version):
    assert validate_meta(good_meta(o2i_version=version), "en-GB", WORDS) == [
        f"o2i_version {version!r} is not a release version"]


def test_licence_must_be_spdx_shaped():
    assert validate_meta(good_meta(licence="CC BY-SA 3.0"), "en-GB", WORDS) == [
        "licence 'CC BY-SA 3.0' is not an SPDX id"]


def test_every_word_needs_a_reason_and_every_reason_a_word():
    meta = good_meta(reasons={"colonel": "unclassified", "choir": "unclassified"})
    assert validate_meta(meta, "en-GB", WORDS) == [
        "no reason class for 'nato'",
        "reason for 'choir', which is not in the TSV file",
    ]


def test_unknown_reason_class_is_refused():
    meta = good_meta(reasons={"colonel": "spooky", "nato": "acronym"})
    assert validate_meta(meta, "en-GB", WORDS) == [
        "unknown reason class 'spooky' for 'colonel'"]


def test_a_claimed_class_needs_a_basis():
    meta = good_meta(reason_basis={})
    assert validate_meta(meta, "en-GB", WORDS) == [
        "reason class 'acronym' is used with no stated basis"]


def test_unclassified_needs_no_basis():
    meta = good_meta(reasons={"colonel": "unclassified", "nato": "unclassified"},
                     reason_basis={})
    assert validate_meta(meta, "en-GB", WORDS) == []


def test_reason_classes_are_the_plan_classes_plus_unclassified():
    assert REASON_CLASSES == {
        "loanword", "proper_noun", "lexical_stress", "irregular",
        "acronym", "homograph_default", "unclassified"}


@pytest.mark.parametrize("stress", ["", "lexicon", None])
def test_stress_origin_must_be_named(stress):
    assert validate_meta(good_meta(stress=stress), "en-GB", WORDS) == [
        f"stress {stress!r} is not one of ['rules', 'source']"]


def test_rules_stress_means_no_stress_mark_in_the_file():
    entries = {"colonel": "ˈkɜːnəl", "nato": "neɪtəʊ"}
    assert validate_meta(good_meta(), "en-GB", entries) == [
        "stress is 'rules' but 1 entries carry a stress mark, the first 'colonel'"]
    assert validate_meta(good_meta(stress="source"), "en-GB", entries) == []


def good_patch_meta(**overrides):
    meta = good_meta(kind="patch", gaps={"colonel": "lead: x", "nato": "o2i#1"})
    del meta["citations"]
    meta.update(overrides)
    return meta


def test_clean_patch_meta_has_no_problems():
    assert validate_meta(good_patch_meta(), "en-GB", WORDS, kind="patch") == []


def test_an_exception_sidecar_needs_citations_and_a_patch_sidecar_gaps():
    assert validate_meta(good_patch_meta(), "en-GB", WORDS) == ["missing key: citations"]
    assert validate_meta(good_meta(), "en-GB", WORDS, kind="patch") == ["missing key: gaps"]


def test_the_kind_must_match_the_file():
    meta = good_meta(gaps={"colonel": "o2i#1", "nato": "o2i#1"})
    assert validate_meta(meta, "en-GB", WORDS, kind="patch") == [
        "kind 'exception' does not match the patch file"]


def test_every_exception_needs_a_citation_and_every_citation_a_word():
    meta = good_meta(citations={"colonel": " ", "choir": "Carney p. 1"})
    assert validate_meta(meta, "en-GB", WORDS) == [
        "citations has no entry for 'colonel'",
        "citations has no entry for 'nato'",
        "citations names 'choir', which is not in the TSV file"]


def test_every_patch_needs_a_gap():
    meta = good_patch_meta(gaps={"colonel": "o2i#1"})
    assert validate_meta(meta, "en-GB", WORDS, kind="patch") == ["gaps has no entry for 'nato'"]


def test_an_empty_patch_file_is_valid():
    meta = good_patch_meta(reasons={}, reason_basis={}, gaps={})
    assert validate_meta(meta, "en-GB", {}, kind="patch") == []
