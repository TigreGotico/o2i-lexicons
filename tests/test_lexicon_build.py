"""The pure steps of a build. Expected values are worked out by hand."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import lexicon_build as lb  # noqa: E402


def naive_align(a, b):
    """Position-by-position pairs, padded with None: enough for equal-length tests."""
    n = max(len(a), len(b))
    return [(a[i] if i < len(a) else None, b[i] if i < len(b) else None) for i in range(n)]


@pytest.mark.parametrize("gold, stored", [
    ("k ɜː n əl", "kɜːnəl"),
    ("ˈθ ʌ ɹ ə", "ˈθʌɹə"),
    ("ké", "ké"),
])
def test_storage_ipa_drops_phone_spaces_and_composes(gold, stored):
    assert lb.storage_ipa(gold) == stored


@pytest.mark.parametrize("headword, reason", [
    ("NATO", "acronym"),
    ("AAALAC", "acronym"),
    ("London", "proper_noun"),
    ("McDonald", "proper_noun"),
    ("colonel", "unclassified"),
    ("yacht", "unclassified"),
])
def test_reason_comes_only_from_the_source_spelling(headword, reason):
    assert lb.reason_for(headword) == reason


def test_only_acronym_and_proper_noun_have_a_basis():
    assert set(lb.REASON_BASIS) == {"acronym", "proper_noun"}


@pytest.mark.parametrize("headword, ok", [
    ("colonel", True),
    ("o'clock", True),
    ("naïve", True),
    ("'cause", False),
    ("well-known", False),
    ("ice cream", False),
    ("4x4", False),
])
def test_word_shape(headword, ok):
    assert bool(lb.WORD_RE.match(headword)) is ok


def test_error_chunks_give_engine_text_gold_text_and_span():
    # gold "rʌf" vs engine "rɔː": positions 1-2 differ -> one run.
    assert lb.error_chunks("rʌf", "rɔː", naive_align) == [("ɔː", "ʌf", 1 / 3, 3 / 3)]


def test_error_chunks_of_identical_strings_are_empty():
    assert lb.error_chunks("kæt", "kæt", naive_align) == []


def test_spelling_patterns_mark_edges():
    found = set(lb.spelling_patterns("tough", sizes=(4,)))
    assert found == {
        ("toug", "any", 0.0, 0.8), ("toug", "initial", 0.0, 0.8),
        ("ough", "any", 0.2, 1.0), ("ough", "final", 0.2, 1.0),
    }


def cand(word, hyp, gold):
    return lb.Candidate(word, word, hyp, gold, gold)


def test_shared_pattern_and_error_make_a_lead():
    # Ten final-<ough> words, all with the same error at their end, and one
    # word with an unrelated error. Each gold ends in "ʌf" where the engine
    # wrote "ɔː"; the stems are made distinct so no stem n-gram is shared.
    stems = ["t", "r", "en", "sl", "ch", "b", "g", "pl", "sn", "fl"]
    words = [cand(s + "ough", "x" * len(s) + "ɔː", "x" * len(s) + "ʌf") for s in stems]
    other = cand("yacht", "jætʃt", "jɒt")
    leads = lb.find_leads(words + [other], naive_align, min_size=10)
    assert [(l.pattern, l.position, l.engine, l.gold) for l in leads] == [
        ("ough", "final", "ɔː", "ʌf")]
    assert leads[0].words == sorted(s + "ough" for s in stems)
    assert lb.held_out_words(leads) == {s + "ough" for s in stems}


def test_a_group_below_the_threshold_is_no_lead():
    stems = ["t", "r", "en", "sl", "ch", "b", "g", "pl", "sn"]
    words = [cand(s + "ough", "x" * len(s) + "ɔː", "x" * len(s) + "ʌf") for s in stems]
    assert lb.find_leads(words, naive_align, min_size=10) == []


def test_first_usable_keeps_source_order():
    refuse_r = lambda g: None if "ɚ" in g else lb.storage_ipa(g)  # noqa: E731
    assert lb.first_usable(["k ɚ n əl", "k ɜː n əl", "k ɜ n l"], refuse_r) == "kɜːnəl"
    assert lb.first_usable(["k ɚ n əl"], refuse_r) is None


def test_write_lexicon_sorts_entries(tmp_path):
    tsv, meta = lb.write_lexicon(tmp_path / "en-GB", "wikipron",
                                 {"yacht": "jɒt", "colonel": "kɜːnəl"}, {"code": "en-GB"})
    assert tsv.read_text(encoding="utf-8") == "colonel\tkɜːnəl\nyacht\tjɒt\n"
    assert meta.name == "wikipron.meta.json"


def test_storage_forms_offer_an_untied_affricate():
    assert lb.storage_forms("d͡ʒ æ m") == ["d͡ʒæm", "dʒæm"]
    assert lb.storage_forms("k æ t") == ["kæt"]


def test_nearly_identical_groups_collapse_to_the_most_specific():
    # "-tion" words: the error sits at the ending, so "tion", "ion", "on" and
    # so on all collect the same ten words. One lead remains, the longest
    # final pattern.
    stems = ["na", "sta", "ra", "lo", "mo", "ca", "po", "no", "fic", "mu"]
    words = [cand(s + "tion", "x" * len(s) + "tiɒn", "x" * len(s) + "ʃən") for s in stems]
    leads = lb.find_leads(words, naive_align, min_size=10)
    assert [(l.pattern, l.position) for l in leads] == [("tion", "final")]


@pytest.mark.parametrize("infopedia, spec", [
    ("ɐˈmor", "ɐˈmoɾ"),        # amor: the tap
    ("ˈkaʀu", "ˈkaʁu"),        # carro: the strong rhotic
    ("pəˈsoɐ", "pɨˈsoɐ"),      # pessoa: the reduced vowel
    ("ˈkazɐ", "ˈkazɐ"),        # casa: nothing to map
])
def test_infopedia_reading_takes_the_spec_symbols(infopedia, spec):
    assert lb.infopedia_to_spec(infopedia) == spec


@pytest.mark.parametrize("word, reading, ambiguous", [
    ("acarreja", "ɐkɐˈrɐʒɐ", True),     # ⟨rr⟩ written [r]
    ("rapidamente", "rapidɐˈmẽt", True),  # initial ⟨r⟩ written [r]
    ("carro", "ˈkaʀu", False),
    ("caro", "ˈkaru", False),
    ("honra", "ˈõʀɐ", False),
    ("Israel", "iʒʀɐˈɛɫ", False),
])
def test_strong_r_written_as_r_is_ambiguous(word, reading, ambiguous):
    assert lb.strong_r_is_ambiguous(word, reading) is ambiguous


def test_full_form_of_an_optional_vowel_comes_first():
    # paciente is pɐˈsjẽt(ə) in Infopédia: short form first in the dataset.
    assert lb.full_form_first(["pɐˈsjẽt", "pɐˈsjẽtə"]) == ["pɐˈsjẽtə", "pɐˈsjẽt"]
    # Two readings that differ in more than the optional vowel keep their order.
    assert lb.full_form_first(["ajfəˈljɐnu", "ɐjfəˈljɐnu"]) == ["ajfəˈljɐnu", "ɐjfəˈljɐnu"]


@pytest.mark.parametrize("rules, reading, reason", [
    # paciente: the glide forms and one nucleus goes; same consonants.
    ("pɐsiˈẽtɨ", "pɐˈsjẽtɨ", None),
    # exame: the rules misread ⟨x⟩ and the vowels; same consonant classes.
    ("eˈʃamɨ", "iˈzɐmɨ", None),
    # augustinista read as another word: a vowel onset against [v].
    ("awɡuʃtiˈniʃtɐ", "vjuliˈniʃtɐ", "first-syllable onset"),
    # despampanadeira cut after its second syllable: classes T S P P N T R
    # against T S P P, three edits for seven consonants (limit 1 + 7 // 4).
    ("dɨʃpɐ̃pɐnɐˈdejɾɐ", "dɨʃˈpɐ̃pɐ", "consonant skeleton"),
    # one nucleus more, of [a], which neither deletes nor glides.
    ("ˈbaba", "ˈbababa", "syllable count"),
    # carapotós without its final [ʃ].
    ("kɐɾɐpuˈtɔʃ", "kɐɾɐpuˈtɔ", "truncated end"),
])
def test_other_reading_reason(rules, reading, reason):
    assert lb.other_reading_reason(rules, reading) == reason


def test_a_non_syllabic_mark_makes_a_glide():
    assert lb.segments("ai̯") == [("V", "a"), ("G", "i")]


@pytest.mark.parametrize("headword, reason", [
    # The letter names: a and o read [a] and [ˈɔ] in Infopédia.
    ("a", "one letter"),
    ("O", "one letter"),
    ("à", "one letter"),
    ("oh", "interjection spelled as a letter"),
    ("eh", "interjection spelled as a letter"),
    ("do", "closed class"),
    ("Naquele", "closed class"),
    ("casa", None),
    ("hoje", None),
])
def test_closed_class_reason(headword, reason):
    assert lb.closed_class_reason(headword, frozenset({"do", "naquele"})) == reason


def stress_free(a, b):
    return a.replace("ˈ", "") == b.replace("ˈ", "")


@pytest.mark.parametrize("headword, rules, reading, issues", [
    # o2i#2046: afã and fã differ from the rules only in ⟨ã⟩.
    ("afã", "ɐˈfã", "ɐˈfɐ̃", [2046]),
    ("fã", "ˈfã", "ˈfɐ̃", [2046]),
    # maçã with a second difference, in the first vowel: the entry stays.
    ("maçã", "maˈsã", "mɐˈsɐ̃", []),
    # [ã] that no ⟨ã⟩ spells is outside the issue.
    ("tanta", "ˈtãtɐ", "ˈtɐ̃tɐ", []),
    # o2i#2041: the coda sibilant voices before a voiced consonant (desdém),
    # and deletes before /ʒ/ (desgelo).
    ("desdém", "dɨʃˈdɐ̃j̃", "dɨʒˈdɐ̃j̃", [2041]),
    ("desgelo", "dɨʃˈʒelu", "dɨˈʒelu", [2041]),
    # mesmo also takes another stressed vowel, so the issue does not explain it.
    ("mesmo", "ˈmɛʃmu", "ˈmeʒmu", []),
    # a word-final sibilant is outside the issue.
    ("gás", "ˈɡaʃ", "ˈɡaʒ", []),
])
def test_open_rule_bugs(headword, rules, reading, issues):
    assert lb.open_rule_bugs("pt-PT", headword, rules, reading, stress_free) == issues


def test_no_open_rule_bug_outside_its_language():
    assert lb.open_rule_bugs("pt-BR", "afã", "aˈfã", "aˈfɐ̃", stress_free) == []


def test_the_stress_mark_moves_to_its_vowel():
    # Infopédia writes the mark before the syllable, the Portal before the vowel.
    assert lb.stress_on_nucleus("ˈkazɐ") == lb.stress_on_nucleus("kˈazɐ") == "kˈazɐ"
    assert lb.stress_on_nucleus("ˌɐkɐˈdɛmjɐ") == "ɐkɐdˈɛmjɐ"


def test_corroborating_sources():
    refs = {
        # WikiPron writes no stress: its segments are compared.
        "wikipron": {"exame": ["i z ɐ m ɨ"], "mesmo": ["m e ʒ m u"]},
        "wiktionary": {"exame": ["iˈzamɨ"]},
        "portal_lisbon": {"exame": ["izˈɐmɨ"], "mesmo": ["mˈɛʒmu"]},
    }
    def form(ipa):
        return "".join(ipa.split())
    assert lb.corroborating_sources("exame", "iˈzɐmɨ", refs, form) == ["wikipron", "portal_lisbon"]
    # The Portal stresses the same vowel but writes another one: no agreement.
    assert lb.corroborating_sources("mesmo", "ˈmeʒmu", refs, form) == ["wikipron"]
    # A stress on another vowel is a disagreement when both mark it.
    assert lb.corroborating_sources("exame", "ˈizɐmɨ", refs, form) == ["wikipron"]
    assert lb.corroborating_sources("casa", "ˈkazɐ", refs, form) == []
