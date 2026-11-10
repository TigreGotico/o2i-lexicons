"""Each entry is an exception or a patch, by the class of what the rules miss.

The rules readings below are orthography2ipa 7.122.11a2 output and the
entries are the readings of the packaged files, except three made-up rows that
reach a branch no packaged entry reaches: caprichoso with [ɔ], aceleradora
with a ⟨qu gu⟩ class, and trapo.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import build_lexicon as bl  # noqa: E402
import entry_kinds as ek  # noqa: E402

CC_40 = "Cunha & Cintra p. 40; AO90 Base IX 3.º for ⟨ei oi⟩"


@pytest.mark.parametrize("word, rules, entry, cls, expected", [
    # The spelling does not show the height of a stressed mid vowel.
    ("abelota", "ɐbɨˈlɔtɐ", "ɐbɨˈlotɐ", "stressed mid vowel", ("exception", CC_40)),
    # ⟨-oide⟩ is [ɔ] and ⟨-dora⟩ is [o] in nearly every Infopédia word.
    ("acaroide", "ɐkɐˈɾojdɨ", "ɐkɐˈɾɔjdɨ", "stressed mid vowel",
     ("patch", "rule-leads.md § Entries in ⟨-oide⟩")),
    ("aceleradora", "ɐsɨlɨɾɐˈdɔɾɐ", "ɐsɨlɨɾɐˈdoɾɐ", "stressed mid vowel",
     ("patch", "rule-leads.md § Entries in ⟨-dora⟩")),
    ("abertona", "ɐbɨɾˈtɔnɐ", "ɐbɨɾˈtonɐ", "stressed mid vowel",
     ("patch", "lead: ⟨-ona⟩ takes [o] in at least 90% of the Infopédia words")),
    # Cunha & Cintra p. 431 name frechar among the verbs with [ɛ] before a
    # palatal; any other such [ɛ] is a misfire of the prepalatal rule.
    ("frecha", "ˈfɾeʃɐ", "ˈfɾɛʃɐ", "stressed mid vowel", ("exception", "Cunha & Cintra p. 431")),
    ("alfrecha", "aɫˈfɾeʃɐ", "aɫˈfɾɛʃɐ", "stressed mid vowel",
     ("patch", "PT_STRESSED_E_PREPALATAL_CLOSE misfires")),
    ("caprichoso", "kɐpɾiˈʃozu", "kɐpɾiˈʃɔzu", "stressed mid vowel",
     ("patch", "PT_SUFFIX_OSO_CLOSE misfires")),
    # Initial ⟨e⟩: open syllable of a learned word, before /R/, a learned first
    # element, before /S/.
    ("ebanite", "ibɐˈnitɨ", "ɛbɐˈnitɨ", "unstressed initial ⟨e⟩",
     ("exception", "Cunha & Cintra p. 53; Mateus & d'Andrade 1998 p. 26 (b)")),
    ("erguer", "ɛɾˈɡeɾ", "eɾˈɡeɾ", "unstressed initial ⟨e⟩",
     ("exception", "Mateus & d'Andrade 1998 p. 26 (c)")),
    ("ecográfico", "ikuˈɡɾafiku", "ɛkuˈɡɾafiku", "unstressed initial ⟨e⟩",
     ("patch", "rule-leads.md § word-initial e")),
    ("essonite", "isuˈnitɨ", "ɛsuˈnitɨ", "unstressed initial ⟨e⟩",
     ("patch", "Mateus & d'Andrade 1998 p. 26 (a, b, d)")),
    # Initial ⟨o⟩: [o] against [ɔ] is lexical; [u] in honesto is a stem lead.
    ("homana", "ɔˈmɐnɐ", "oˈmɐnɐ", "unstressed initial ⟨o⟩",
     ("exception", "Mateus & d'Andrade 1998 p. 27")),
    ("honesto", "ɔˈnɛʃtu", "uˈnɛʃtu", "unstressed initial ⟨o⟩",
     ("patch", "lead: the stems honest- and honor- take an initial [u]")),
    # orthography2ipa#2218 opens an ⟨e o⟩ before a coda stop and leaves ⟨a⟩
    # reduced, so absonante waits on another lead. A stop before l is an
    # onset, so eclético has no vowel before a coda stop.
    ("absonante", "ɐbsuˈnɐ̃tɨ", "absuˈnɐ̃tɨ", "unstressed vowel before a coda stop",
     ("patch", ek.CODA_STOP_A)),
    ("eclético", "iklɛtiku", "ɛˈklɛtiku", "unstressed vowel before a coda stop",
     ("patch", ek.NO_LEAD)),
    # Under #2218: impregnar is [ɛ] in the rules and [ɨ] in Infopédia;
    # cretcheu is [ɛ] in the rules and [e] in Infopédia.
    ("impregnar", "ĩpɾɛɡˈnaɾ", "ĩpɾɨɡˈnaɾ", "unstressed vowel before a coda stop",
     ("patch", ek.CODA_STOP_REDUCED)),
    ("cretcheu", "kɾɛˈtʃew", "kɾeˈtʃew", "unstressed vowel before a coda stop",
     ("patch", ek.CODA_STOP_CLOSE)),
    # Under #2218 the coda stop of etmoide is right, so only ⟨-oide⟩ is left.
    ("etmoide", "ɛtˈmojdɨ", "ɛtˈmɔjdɨ", "stressed mid vowel+unstressed vowel before a coda stop",
     ("patch", "rule-leads.md § Entries in ⟨-oide⟩")),
    ("abjeção", "ɐbʒɨˈsɐ̃w̃", "ɐbʒɛˈsɐ̃w̃", "unreduced learned vowel",
     ("patch", "rule-leads.md § learned words")),
    # Two patch parts give a patch with both gaps.
    ("polpectomia", "poɫpɨktuˈmiɐ", "puɫpɛktuˈmiɐ",
     "unstressed vowel before a coda stop+unstressed vowel before a coda ⟨l⟩",
     ("patch", "orthography2ipa#2218; rule-leads.md § coda l")),
    # An exception part makes an exception, and only its citations remain.
    ("adoxa", "ɐˈdɔʃɐ", "ɐˈdoksɐ", "stressed mid vowel+⟨x⟩ as [ks]",
     ("exception", f"{CC_40}; AO90 Base III; Ciberdúvidas 4068")),
    ("aceleradora", "ɐsɨlɨɾɐˈdɔɾɐ", "ɐsɨlɨɾɐˈdoɾɐ", "stressed mid vowel+⟨qu gu⟩ with [w]",
     ("exception", "AO90 Base XIV 1.º; Cunha & Cintra p. 79")),
    # No class: a spelling outside the native system is a loan. Infopédia
    # gives its reading; a loan that differs from the rules only in a doubled
    # consonant letter or an initial ⟨s⟩ before a consonant is a patch.
    ("antidumping", "ɐ̃tiˈdũpĩɡ", "ɐ̃tiˈdɐ̃pĩɡ", None, ("exception", ek.LOAN.format("Infopédia"))),
    ("lobby", "ˈlɔbbi", "ˈlɔbi", None, ("patch", ek.LOAN_DOUBLED)),
    ("swing", "ˈʃwĩɡ", "ˈswĩɡ", None, ("patch", ek.LOAN_INITIAL_S)),
    ("puzzle", "ˈpuzzlɨ", "ˈpɐzlɨ", None, ("exception", ek.LOAN.format("Infopédia"))),
    ("jogging", "ˈʒɔɡʒĩɡ", "ˈʒɔɡĩɡ", None, ("exception", ek.LOAN.format("Infopédia"))),
    # AO90 Base I 2.º c): "kg-quilograma, km-quilómetro, kW-kilowatt".
    ("kilowatt", "kiˈlɔwɐtt", "kilɔˈwɔt", None, ("exception", ek.AO90_UNIT)),
    ("breja", "ˈbɾeʒɐ", "ˈbɾɛʒɐ", None, ("patch", ek.NO_LEAD)),
])
def test_pt_pt_kind(word, rules, entry, cls, expected):
    assert ek.pt_pt_kind(word, rules, entry, cls) == expected


def test_an_unknown_pt_pt_class_is_refused():
    with pytest.raises(ValueError, match="unknown lexical class"):
        ek.pt_pt_kind("abelota", "ɐbɨˈlɔtɐ", "ɐbɨˈlotɐ", "stressed vowel")


@pytest.mark.parametrize("word, rules, entry, tenses, expected", [
    ("foto", "ˈfotu", "ˈfɔtu", frozenset(), ("exception", "Cunha & Cintra p. 40; orthography2ipa#1824")),
    ("táxi", "ˈtaʃi", "ˈtaksi", frozenset(), ("exception", "AO90 Base III; Ciberdúvidas 4068")),
    ("exu", "eˈzu", "eˈʃu", frozenset(), ("exception", "AO90 Base III; Ciberdúvidas 4068")),
    ("sexy", "ˈsesi", "ˈsɛksi", frozenset(), ("exception", ek.LOAN.format("NILC"))),
    ("melo", "ˈmelu", "ˈmɛlu", frozenset("P"),
     ("patch", "Cunha & Cintra pp. 429-433: the stem vowel of a rhizotonic verb form")),
    ("joga", "ˈʒoɡa", "ˈʒɔɡa", frozenset("PY"),
     ("patch", "Cunha & Cintra pp. 429-433: the stem vowel of a rhizotonic verb form")),
    ("deram", "ˈdeɾɐ̃w̃", "ˈdɛɾɐ̃w̃", frozenset("JQ"),
     ("patch", "lead: the stem vowel of a pt-BR preterite or imperfect form")),
    ("transação", "tɾɐ̃saˈsɐ̃w̃", "tɾɐ̃zaˈsɐ̃w̃", frozenset(),
     ("patch", "lead: the ⟨s⟩ of the prefix trans- before a vowel is [z]")),
    ("trapo", "ˈtɾapu", "ˈtɾabu", frozenset(), ("patch", ek.NO_LEAD)),
])
def test_pt_br_kind(word, rules, entry, tenses, expected):
    assert ek.pt_br_kind(word, rules, entry, tenses) == expected


@pytest.mark.parametrize("word, reason, expected", [
    # A name or an acronym: no spelling rule gives its reading.
    ("leeds", "proper_noun", ("exception", ek.EN_GB_CITATION)),
    ("nato", "acronym", ("exception", ek.EN_GB_CITATION)),
    # An inflection of a headword that is no entry: the rules read the base.
    ("cringes", "unclassified", ("patch", ek.EN_GB_INFLECTION)),
    ("dyeing", "unclassified", ("patch", ek.EN_GB_INFLECTION)),
    # Any other word: nothing shows that a rule cannot reach it.
    ("yacht", "unclassified", ("patch", ek.EN_GB_UNAUDITED)),
    ("colonels", "unclassified", ("patch", ek.EN_GB_UNAUDITED)),   # colonel is an entry
    ("flurbs", "unclassified", ("patch", ek.EN_GB_UNAUDITED)),     # flurb is no headword
])
def test_en_gb_kind(word, reason, expected):
    headwords = frozenset({"cringe", "dye", "colonel", "leed"})
    entries = frozenset({word, "colonel"})
    assert ek.en_gb_kind(word, reason, headwords, entries) == expected


def test_an_en_gb_citation_names_the_provenance_of_the_reading():
    assert ek.EN_GB_CITATION == "Wiktionary via WikiPron (en-GB); not checked against a dictionary"
    assert ek.EN_GB_UNAUDITED == "lead: en-GB spelling rules not audited"


def test_split_gives_each_kind_its_own_records():
    entries = {"ela": "ˈɛlɐ", "foto": "ˈfɔtu", "joga": "ˈʒɔɡa"}
    meta = {"code": "pt-BR", "source": "nilc", "o2i_version": "7.0.0",
            "reasons": {"ela": "unclassified", "foto": "unclassified", "joga": "unclassified"},
            "reason_basis": {}, "wiktionary_readings": ["joga"],
            "lexical_classes": {"foto": {"class": "stressed mid vowel"}}}
    kinds = {"ela": ("patch", "lead: a"), "foto": ("exception", "C&C p. 40"),
             "joga": ("patch", "lead: b")}
    parts = ek.split(entries, meta, kinds)
    exceptions, exception_meta = parts["exception"]
    patches, patch_meta = parts["patch"]
    assert exceptions == {"foto": "ˈfɔtu"}
    assert patches == {"ela": "ˈɛlɐ", "joga": "ˈʒɔɡa"}
    assert exception_meta == {
        "code": "pt-BR", "source": "nilc", "o2i_version": "7.0.0", "kind": "exception",
        "reasons": {"foto": "unclassified"}, "reason_basis": {},
        "lexical_classes": {"foto": {"class": "stressed mid vowel"}},
        "wiktionary_readings": [], "citations": {"foto": "C&C p. 40"}}
    assert patch_meta["gaps"] == {"ela": "lead: a", "joga": "lead: b"}
    assert patch_meta["wiktionary_readings"] == ["joga"]
    assert patch_meta["lexical_classes"] == {}
    assert "citations" not in patch_meta


def test_split_gives_an_empty_file_to_a_kind_with_no_word():
    meta = {"code": "en-GB", "reasons": {"leeds": "proper_noun"}, "reason_basis": {}}
    parts = ek.split({"leeds": "liːdz"}, meta, {"leeds": ("exception", ek.EN_GB_CITATION)})
    assert parts["patch"] == ({}, {"code": "en-GB", "kind": "patch", "reasons": {},
                                   "reason_basis": {}, "gaps": {}})


def test_nilc_verb_tenses_keeps_only_words_tagged_as_verbs(tmp_path):
    nilc = tmp_path / "nilc.txt"
    nilc.write_text("joga,jogar.V:P3s;@JÓ-G6\njoga,jogar.V:Y2s;@JÓ-G6\n"
                    "bola,bola.V:P3s;@BÓ-L6\nbola,bola.N:fs;@BÓ-L6\n"
                    "deram,dar.V:J3p:Q3p;@DÉ-ŔÃŴ\n", encoding="utf-8")
    assert bl.nilc_verb_tenses(nilc) == {"joga": frozenset("PY"), "deram": frozenset("JQ")}


def test_a_code_with_no_kind_rules_is_refused():
    with pytest.raises(SystemExit, match="no rules for fr-FR"):
        bl.entry_kinds("fr-FR", None, {"chat": "ʃa"}, {}, {}, frozenset(), {})


def test_a_loan_citation_names_the_dictionary_for_the_reading():
    # AO90 Base I 2.º keeps ⟨k w y⟩ in foreign names, their derivatives and
    # units such as kW-kilowatt. It gives no reading, so the citation of a
    # loan names the dictionary, and only a unit the Base names cites it.
    assert ek.LOAN.format("Infopédia").startswith("Infopédia gives the reading.")
    assert "AO90" not in ek.LOAN
    assert ek.AO90_UNIT.startswith("AO90 Base I 2.º c) for the spelling")
    assert "kilowatt" in ek.AO90_UNITS
