"""The pure steps of a build. Expected values are worked out by hand."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import build_lexicon as bl  # noqa: E402
import lexicon_build as lb  # noqa: E402


def naive_align(a, b):
    """Position-by-position pairs, padded with None: enough for equal-length tests."""
    n = max(len(a), len(b))
    return [(a[i] if i < len(a) else None, b[i] if i < len(b) else None) for i in range(n)]


def edit_align(a, b):
    """A unit-cost edit alignment of two strings, as pairs with None for a gap."""
    n, m = len(a), len(b)
    d = [[i + j if i * j == 0 else 0 for j in range(m + 1)] for i in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] != b[j - 1]))
    pairs, i, j = [], n, m
    while i or j:
        if i and j and d[i][j] == d[i - 1][j - 1] + (a[i - 1] != b[j - 1]):
            pairs.append((a[i - 1], b[j - 1])); i, j = i - 1, j - 1
        elif i and d[i][j] == d[i - 1][j] + 1:
            pairs.append((a[i - 1], None)); i -= 1
        else:
            pairs.append((None, b[j - 1])); j -= 1
    return pairs[::-1]


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


def test_wikipron_corroborates_only_a_single_reading():
    readings = {"cupé": ["k u p e", "k u p ɛ"], "casa": ["k a z ɐ"], "asno": ["a ʒ n u", "a ʒ n u"]}
    assert lb.single_readings(readings) == {"casa": ["k a z ɐ"], "asno": ["a ʒ n u", "a ʒ n u"]}


def test_the_portal_and_a_merged_row_keep_no_entry_on_their_own():
    # A merged Infopédia and pt.wiktionary row repeats the Infopédia reading.
    assert lb.CORROBORATING_SOURCES.isdisjoint({"portal_lisbon", "merged"})
    assert lb.CORROBORATING_SOURCES == {"wikipron", "wiktionary"}


@pytest.mark.parametrize("ipa, misplaced", [
    # yakuza: the syllables are ja.ˈku.zɐ, so [k] belongs after the mark.
    ("jakˈuzɐ", True),
    ("jaˈkuzɐ", False),
    ("ˈkazɐ", False),
    # A glide before the mark closes the syllable before it.
    ("mawˈiʃtɐ", False),
    # A syllable dot before the mark states where the syllable starts.
    ("ak.ˈa", False),
    ("ɐ̃ˌtiˈdɐ̃pĩɡ", False),
])
def test_misplaced_stress(ipa, misplaced):
    assert lb.misplaced_stress(ipa) is misplaced


@pytest.mark.parametrize("word, reading, rules, expected", [
    # ⟨ei⟩ and ⟨ê⟩ before ⟨x⟩: Lisbon [ɐj], pt-PT [ej]. The rules read [e].
    ("leite", "ˈlɐjtɨ", "ˈlejtɨ", "ˈlejtɨ"),
    ("êxito", "ˈɐjzitu", "ˈeʃitu", "ˈejzitu"),
    # The English [eɪ] of basebol, spelled ⟨a⟩: the rules read [ɐ], no glide.
    ("basebol", "bɐjzɨˈbɔɫ", "bɐzɨˈbɔɫ", "bejzɨˈbɔɫ"),
    # game: the aligner may pair [j] with the rules' [m].
    ("game", "ˈɡɐjm", "ˈɡamɨ", "ˈɡejm"),
    # rugby: the [ɐj] spells ⟨u⟩, and no source gives [ej].
    ("rugby", "ˈʁɐjɡɨbi", "ˈʁuɡbi", "ˈʁɐjɡɨbi"),
    # The unstressed ⟨ai⟩ is [ɐj] in pt-PT too.
    ("baixar", "bɐjˈʃaɾ", "bajˈʃaɾ", "bɐjˈʃaɾ"),
    # ⟨aj⟩: the [j] is a misread ⟨j⟩, not a diphthong.
    ("bajulação", "bɐjulɐˈsɐ̃w̃", "bɐʒulɐˈsɐ̃w̃", "bɐjulɐˈsɐ̃w̃"),
    # The nasal diphthong is not the Lisbon [ɐj].
    ("mãe", "ˈmɐ̃j̃", "ˈmɐ̃j̃", "ˈmɐ̃j̃"),
])
def test_lisbon_ej_takes_the_pt_pt_norm(word, reading, rules, expected):
    assert lb.lisbon_to_pt_pt(word, reading, rules, edit_align) == expected


def test_the_rules_vowel_may_align_with_the_glide():
    # The board aligner pairs êxito's rules [e] with the [j] of [ɐj].
    def tie_align(a, b):
        return [("ɐ", None), ("j", "e"), ("z", "ʃ"), ("i", "i"), ("t", "t"), ("u", "u")]
    assert lb.lisbon_to_pt_pt("êxito", "ˈɐjzitu", "ˈeʃitu", tie_align) == "ˈejzitu"


def test_rugby_keeps_a_lisbon_aj_that_the_build_drops():
    reading = lb.lisbon_to_pt_pt("rugby", "ˈʁɐjɡɨbi", "ˈʁuɡbi", edit_align)
    assert "ej" not in reading
    assert lb.lisbon_aj_left("rugby", reading)
    assert not lb.lisbon_aj_left("êxito", lb.lisbon_to_pt_pt("êxito", "ˈɐjzitu", "ˈeʃitu", edit_align))
    assert not lb.lisbon_aj_left("baixar", "bɐjˈʃaɾ")


@pytest.mark.parametrize("rules, reading, lisbon", [
    # espelho: Lisbon [ɐ] before [ʎ], where pt-PT has [ɛ].
    ("ɨʃpɛʎu", "ɨʃpɐʎu", True),
    ("kuɛʎu", "kuɐʎu", True),
    # [ɐ] against [e] before a non-palatal is another difference.
    ("sedɐ", "sɐdɐ", False),
    # [ɐ] before a palatal where the rules also have [ɐ].
    ("ɐʎu", "ɐʎu", False),
])
def test_lisbon_prepalatal_vowel(rules, reading, lisbon):
    assert lb.lisbon_prepalatal_vowel(rules, reading, naive_align) is lisbon


@pytest.mark.parametrize("rules, reading, lisbon", [
    # velho, brecha: the rules give the close [e] before a palatal (o2i#2215).
    # The Lisbon [ɐ] stays out, and the pt-PT [ɛ] is no Lisbon feature.
    ("veʎu", "vɐʎu", True),
    ("bɾeʃɐ", "bɾɐʃɐ", True),
    ("bɾeʃɐ", "bɾɛʃɐ", False),
])
def test_the_lisbon_vowel_stays_out_where_the_rules_give_close_e(rules, reading, lisbon):
    assert lb.lisbon_prepalatal_vowel(rules, reading, naive_align) is lisbon


def test_pola_is_a_homograph():
    assert "pola" in lb.HOMOGRAPHS["pt-PT"]


@pytest.fixture(scope="module")
def pt_pt_tokens():
    import orthography2ipa
    from orthography2ipa.inventory import phoneme_inventory, tokenize

    spec = orthography2ipa.G2P("pt-PT").spec
    return phoneme_inventory(spec), lambda ipa: tokenize(ipa, spec)


@pytest.mark.parametrize("word", ["mãe", "pão", "põe"])
def test_the_pt_pt_rules_emit_nasal_diphthongs(pt_pt_tokens, word):
    import orthography2ipa

    inventory, tokens = pt_pt_tokens
    rules = orthography2ipa.G2P("pt-PT").transcribe_word(word)
    assert any(t.endswith(("j̃", "w̃")) for t in tokens(rules))
    assert lb.outside_inventory(tokens(rules), inventory) == []


@pytest.mark.parametrize("reading, outside", [
    # muito: the nasal glide follows a nasal vowel, as in the rules' [ɐ̃j̃].
    ("ˈmũj̃tu", []),
    ("ˈmũw̃", []),
    # A nasal glide after an oral vowel, or at the start, is not spec output.
    ("ˈnuvɐj̃", ["j̃"]),
    ("j̃a", ["j̃"]),
    ("ˈføn", ["ø"]),
])
def test_a_nasal_glide_after_a_nasal_vowel_is_inside_the_inventory(
        pt_pt_tokens, reading, outside):
    inventory, tokens = pt_pt_tokens
    assert lb.outside_inventory(tokens(reading), inventory) == outside


def test_a_spec_with_no_nasal_diphthong_has_no_nasal_glide():
    inventory = frozenset({"ˈ", "m", "ũ", "t", "u"})
    assert lb.outside_inventory(["ˈ", "m", "ũ", "j̃", "t", "u"], inventory) == ["j̃"]


@pytest.mark.parametrize("reading, spec", [
    # Infopédia marks the nasality of [ɐ̃j̃] and [ɐ̃w̃] once, on the glide.
    ("ˈtɾɐj̃", "ˈtɾɐ̃j̃"),
    ("tẽˈsɐw̃", "tẽˈsɐ̃w̃"),
    ("ˈmɐ̃j̃", "ˈmɐ̃j̃"),
    # An oral [ɐj] and a nasal glide after another vowel stay as they are.
    ("bɐjˈʃaɾ", "bɐjˈʃaɾ"),
    ("ɐˈɾaw̃", "ɐˈɾaw̃"),
])
def test_infopedia_nasal_diphthong_takes_a_nasal_nucleus(reading, spec):
    assert lb.infopedia_to_spec(reading) == spec


@pytest.mark.parametrize("word, reading", [("trem", "ˈtɾɐj̃"), ("tensão", "tẽˈsɐw̃")])
def test_the_pt_pt_rules_read_the_mapped_nasal_diphthong(word, reading):
    import orthography2ipa

    assert orthography2ipa.G2P("pt-PT").transcribe_word(word) == lb.infopedia_to_spec(reading)


@pytest.mark.parametrize("transcription, ipa", [
    ("KÁ-@DÊY-Ŕ6S", "kaˈdej.ɾəs"),
    ("TŔÔW-@SÉ-ŔÃŴ", "tɾowˈsɛ.ɾɐ̃w̃"),
    ("@HÍ7-MU", "ˈʁit͡ʃ.mu"),
    ("@TÁR-8I", "ˈtaʁ.d͡ʒi"),
    ("@FÍ-QU", "ˈfi.ksu"),
])
def test_nilc_symbols_are_the_spec_symbols(transcription, ipa):
    assert lb.nilc_to_ipa(transcription) == ipa


@pytest.mark.parametrize("word, transcription, rules, expected", [
    # the fricative coda is the tap of the spec, and the file's [ə] is [ɐ] at the end
    ("porta", "@PÓH-T6", "ˈpoɾtɐ", "ˈpɔɾtɐ"),
    ("tarde", "@TÁR-8I", "ˈtaɾd͡ʒi", "ˈtaɾd͡ʒi"),
    # a final rhotic goes where the rules drop it, and stays a tap where they keep it
    ("falar", "FÁ-@LÁH", "faˈla", "faˈla"),
    ("fizer", "FÍ-@ZÉH", "fiˈze", "fiˈzɛ"),
    ("mar", "@MÁH", "ˈmaɾ", "ˈmaɾ"),
    # the strong rhotic stays
    ("carro", "@KÁ-HU", "ˈkaʁu", "ˈkaʁu"),
    # initial ⟨es en⟩ raise, and an onset sibilant or a stressed vowel does not
    ("escola", "ÊS-@KÓ-L6", "isˈkolɐ", "isˈkɔlɐ"),
    ("essencial", "Ê-SẼ-SÍ-@ÁW", "esẽsiˈaw", "esẽsiˈaw"),
    ("este", "@ÊS-7I", "ˈest͡ʃi", "ˈest͡ʃi"),
    ("entregar", "Ẽ-TŔÊ-@GÁH", "ĩtɾeˈɡa", "ĩtɾeˈɡa"),
    # ⟨ex⟩ takes no raising: the spec keeps [e], so the sibilant is the only change
    ("explica", "ÊS-@PLÍ-K6", "eʃˈplikɐ", "esˈplikɐ"),
    # the epenthetic [i] after a stop in the coda
    ("ritmo", "@HÍ7-MU", "ˈʁitmu", "ˈʁit͡ʃimu"),
    ("advogado", "Á8-VÔ-@GÁ-DU", "ad͡ʒivoˈɡadu", "ad͡ʒivoˈɡadu"),
    ("compacta", "KÕ-@PÁK-T6", "kõˈpakitɐ", "kõˈpakitɐ"),
    # a coda sibilant stays alveolar before [t͡ʃ]
    ("vestindo", "VÊX-@7Ĩ-DU", "vesˈt͡ʃĩdu", "vesˈt͡ʃĩdu"),
    # a stressed vowel before an onset nasal is nasal, an open one is not
    ("crime", "@KŔÍ-MI", "ˈkɾĩmi", "ˈkɾĩmi"),
    ("tema", "@TÉ-M6", "ˈtẽmɐ", "ˈtɛmɐ"),
    # pretonic [e o] are not raised or opened, and a non-final [ə] is [a]
    ("vestido", "VÍS-@7Í-DU", "vesˈt͡ʃidu", "vesˈt͡ʃidu"),
    ("costura", "KÓS-@TÚ-Ŕ6", "kosˈtuɾɐ", "kosˈtuɾɐ"),
    ("açúcar", "6-@SÚ-KÁH", "aˈsukaɾ", "aˈsukaɾ"),
    # an unstressed nasal vowel before an onset nasal is oral, elsewhere it stays
    ("comida", "KÕ-@MÍ-D6", "koˈmidɐ", "koˈmidɐ"),
    ("corrida", "KÕ-@HÍ-D6", "koˈʁidɐ", "kõˈʁidɐ"),
    # a word-final sibilant is [s]
    ("acidez", "Á-SÍ-@DÊZ", "asiˈdes", "asiˈdes"),
    # the stressed mid vowel is what the rules cannot reach, so it stays
    ("sete", "@SÉ-7I", "ˈset͡ʃi", "ˈsɛt͡ʃi"),
])
def test_nilc_reading_in_the_pt_br_norm(word, transcription, rules, expected):
    reading = lb.nilc_to_ipa(transcription)
    assert lb.nilc_to_pt_br(word, reading, rules, edit_align) == expected


@pytest.mark.parametrize("left, right", [
    ("ˈkaʁu", "ˈkaxʊ"),                # a notation of the strong rhotic
    ("ˈpɔɾtɐ", "ˈpɔʁta"),              # the coda rhotic and the final [ɐ a]
    ("ˈmɐ̃w̃", "ˈmɐ̃w"),                 # the nasal mark of a glide
    ("ad͡ʒivoˈɡadu", "adʒivoˈɡadu"),    # the tie bar
])
def test_pt_br_form_folds_notation(left, right):
    assert lb.pt_br_form(left) == lb.pt_br_form(right)


@pytest.mark.parametrize("left, right", [
    ("ˈsɛt͡ʃi", "ˈset͡ʃi"),             # a mid vowel is lexical
    ("ˈtɔɾaks", "ˈtɔɾaʃ"),              # the value of ⟨x⟩
    ("ˈkaɾu", "ˈkaʁu"),                # the tap between vowels is not the rhotic
])
def test_pt_br_form_keeps_lexical_differences(left, right):
    assert lb.pt_br_form(left) != lb.pt_br_form(right)


@pytest.mark.parametrize("ipa, vowel", [
    ("ˈsɛt͡ʃi", "ɛ"),
    ("kaˈfɛ", "ɛ"),
    ("ˈlɐ̃padɐ", "a"),
    ("mesa", None),
])
def test_stressed_vowel(ipa, vowel):
    assert lb.stressed_vowel(ipa) == vowel


@pytest.mark.parametrize("left, right", [
    ("ˈvakwu", "ˈvakuu"),            # vácuo: a post-tonic glide against a hiatus
    ("ˈɔlju", "ˈɔleu"),              # óleo
    ("siˈẽsjə", "siˈẽsiɐ"),          # ciência
    ("aˈdɛptu", "aˈdepitu"),         # adepto: the epenthetic [i] after the stress
    ("ˈpaktu", "ˈpakitu"),           # pacto
    ("eˈʒipsju", "eˈʒipisiu"),       # egípcio: epenthesis and a hiatus together
    ("faˈlaɾ", "faˈla"),             # falar: a dropped infinitive ⟨r⟩
    ("ad͡ʒivoˈɡadu", "advoˈɡadu"),    # advogado: the epenthesis before the stress
    ("ˈtaksi", "ˈtaʃi"),             # táxi: the value of ⟨x⟩
    ("ˈvou", "ˈvoo"),                # a repeated vowel leaves a tie
    ("ˈɛlɐ", "ˈelɐ"),                # height is no stress difference
])
def test_notation_is_no_stress_difference(left, right):
    assert lb.same_stress(left, right)
    assert lb.same_stress(right, left)


@pytest.mark.parametrize("left, right", [
    ("saˈidɐ", "ˈsajdɐ"),            # saída
    ("paˈpa", "ˈpapa"),
    ("abadiˈa", "abaˈd͡ʒiɐ"),         # abadia: Michaelis against the rules
    ("owˈzadiə", "owzaˈd͡ʒiɐ"),       # ousadia
    ("iɾakũˈdu", "iɾaˈkũdu"),        # iracundo
    ("aˈlastɾaɾ", "alasˈtɾa"),       # alastrar
    ("baˈu", "ˈbaw"),                # baú against a falling diphthong
])
def test_a_true_stress_difference_stays(left, right):
    assert not lb.same_stress(left, right)
    assert not lb.same_stress(right, left)


def test_michaelis_counts_only_for_what_its_notation_shows():
    # sete: the correction is the stressed mid vowel, and Michaelis prints it
    assert lb.michaelis_agrees("ˈset͡ʃi", "ˈsɛt͡ʃi", ["ˈsɛti"])
    # a broad [t] and [ə] do not stop the agreement, and a close vowel does
    assert not lb.michaelis_agrees("ˈset͡ʃi", "ˈsɛt͡ʃi", ["ˈseti"])
    # a stress correction is one it shows too
    assert lb.michaelis_agrees("ˈtɾɐ̃zitu", "tɾɐ̃ˈzitu", ["tɾɐ̃ˈzitu"])
    # tórax: the correction is the value of ⟨x⟩, which is outside its two features
    assert not lb.michaelis_agrees("ˈtɔɾɐʃ", "ˈtɔɾaks", ["ˈtɔɾaks"])
    assert not lb.michaelis_agrees("ˈset͡ʃi", "ˈsɛt͡ʃi", [])


def test_michaelis_agrees_through_its_notation():
    # adepto: the epenthetic [i] changes the nuclei after the stress, not the stress
    assert lb.michaelis_agrees("aˈdepitu", "aˈdɛpitu", ["aˈdɛptu"])
    # chato [ʃa′tu]: a misplaced Michaelis mark is no agreement
    assert not lb.michaelis_agrees("ˈʃatu", "ˈʃɔtu", ["ʃɔˈtu"])


@pytest.mark.parametrize("word, rules, entry, expected", [
    ("sete", "ˈset͡ʃi", "ˈsɛt͡ʃi", "stressed mid vowel"),
    ("foto", "ˈfotu", "ˈfɔtu", "stressed mid vowel"),
    ("táxi", "ˈtaʃi", "ˈtaksi", "⟨x⟩ as [ks]"),
    ("tórax", "ˈtɔɾɐʃ", "ˈtɔɾaks", "⟨x⟩ as [ks]"),
    ("reflexo", "ʁeˈfleʃu", "ʁeˈflɛksu", "stressed mid vowel+⟨x⟩ as [ks]"),
    ("frequente", "fɾeˈkẽt͡ʃi", "fɾeˈkwẽt͡ʃi", "⟨qu gu⟩ with [w]"),
    ("sequestro", "seˈkestɾu", "seˈkwɛstɾu", "stressed mid vowel+⟨qu gu⟩ with [w]"),
    ("linguiça", "lĩˈɡisɐ", "lĩˈɡwisɐ", "⟨qu gu⟩ with [w]"),
])
def test_a_lexical_difference_is_a_residual_word(word, rules, entry, expected):
    assert lb.lexical_class(word, rules, entry) == expected


@pytest.mark.parametrize("word, rules, entry", [
    ("exclama", "eʃˈklɐ̃mɐ", "esˈklɐ̃mɐ"),     # coda ⟨x⟩ as [s]: a rule lead
    ("nascer", "naˈse", "nasˈse"),            # ⟨sc⟩
    ("gato", "ˈɡatu", "ˈɡatu"),               # no difference
    ("sete", "ˈset͡ʃi", "seˈt͡ʃi"),             # a stress difference is no height
    ("sete", "ˈset͡ʃi", "ˈsɛti"),              # height and something else
])
def test_anything_else_stays_out_of_the_lexical_classes(word, rules, entry):
    assert lb.lexical_class(word, rules, entry) is None


def test_a_height_outside_the_stressed_vowel_is_not_lexical():
    # The open pretonic [ɛ] of texano is not the height of the stressed vowel.
    assert lb.lexical_class("texano", "teˈʃɐ̃nu", "tɛˈksɐ̃nu") is None
    assert lb.lexical_class("sete", "ˈsetɛ", "ˈsɛte") is None


def pt_pt_form(ipa):
    """The Infopédia readings below are in the spec's symbols already."""
    return ipa


# Each entry is the Infopédia row in the spec's symbols (ə -> ɨ, r -> ɾ).
@pytest.mark.parametrize("word, rules, entry, expected", [
    ("acetona", "ɐsɨˈtɔnɐ", "ɐsɨˈtonɐ", "stressed mid vowel"),       # ɐsəˈtonɐ
    ("abeto", "ɐˈbɛtu", "ɐˈbetu", "stressed mid vowel"),             # ɐˈbetu
    ("táxi", "ˈtaʃi", "ˈtaksi", "⟨x⟩ as [ks]"),                      # ˈtaksi
    ("exógamo", "eˈʃɔɡɐmu", "eˈzɔɡɐmu", "⟨x⟩ as [z]"),               # eˈzɔɡɐmu
    ("próximo", "ˈpɾɔʃimu", "ˈpɾɔsimu", "⟨x⟩ as [s]"),               # ˈprɔsimu
    ("cinquenta", "sĩˈkẽtɐ", "sĩˈkwẽtɐ", "⟨qu gu⟩ with [w]"),        # sĩˈkwẽtɐ
    ("aguentar", "ɐɡẽˈtaɾ", "ɐɡwẽˈtaɾ", "⟨qu gu⟩ with [w]"),         # ɐɡwẽˈtar
])
def test_the_pt_pt_lexical_classes(word, rules, entry, expected):
    assert lb.lexical_class(word, rules, entry, pt_pt_form, lb.PT_PT_X_VALUES) == expected


@pytest.mark.parametrize("word, rules, entry", [
    ("alterado", "ɐɫtɨˈɾadu", "aɫtɨˈɾadu"),     # aɫtəˈradu: an unreduced pretonic vowel
    ("colete", "koˈlɛtɨ", "kɔˈletɨ"),           # a second height, on an unstressed vowel
    ("exclamar", "ɨʃklɐˈmaɾ", "ɨsklɐˈmaɾ"),     # ⟨x⟩ before a consonant is a coda
    ("fixos", "ˈfiʃuʃ", "ˈfiksus"),             # one ⟨x⟩ cannot change twice
])
def test_anything_else_stays_out_of_the_pt_pt_classes(word, rules, entry):
    assert lb.lexical_class(word, rules, entry, pt_pt_form, lb.PT_PT_X_VALUES) is None


def letter_lattice(readings, others=None):
    """One lattice grapheme per letter: its reading in the rules' reading
    *readings*, then the readings that *others* lists for it."""
    others = others or {}
    return [(i, i + 1, [reading, *others.get(i, "")]) for i, reading in enumerate(readings)]


def never_learned(word, end):
    return False


def always_learned(word, end):
    return True


def pt_pt_class(word, rules, entry, readings, others, learned=never_learned):
    slots = lb.vowel_slots(word, rules, letter_lattice(readings, others), pt_pt_form, learned)
    return lb.lexical_class(word, rules, entry, pt_pt_form, lb.PT_PT_X_VALUES, slots)


# Each entry is the Infopédia row in the spec's symbols. The lattice lists the
# rules' readings of the vowel in rank order, as orthography2ipa 7.122.11a2 does.
@pytest.mark.parametrize("word, rules, entry, readings, others, expected", [
    # odrada oˈdradɐ: the rules rank [ɔ u o] for an unstressed initial ⟨o⟩
    ("odrada", "ɔˈdɾadɐ", "oˈdɾadɐ", ["ɔ", "d", "ɾ", "a", "d", "ɐ"], {0: "uo"},
     "unstressed initial ⟨o⟩"),
    # honesto uˈnɛʃtu: the same vowel after a silent initial ⟨h⟩
    ("honesto", "ɔˈnɛʃtu", "uˈnɛʃtu", ["", "ɔ", "n", "ɛ", "ʃ", "t", "u"], {1: "uo"},
     "unstressed initial ⟨o⟩"),
    # ebó eˈbɔ: the rules rank [i e ɛ] for an unstressed initial ⟨e⟩
    ("ebó", "iˈbɔ", "eˈbɔ", ["i", "b", "ɔ"], {0: "eɛ"}, "unstressed initial ⟨e⟩"),
    # golpada ɡɔɫˈpadɐ: an ⟨o⟩ before a coda ⟨l⟩
    ("golpada", "ɡoɫˈpadɐ", "ɡɔɫˈpadɐ", ["ɡ", "o", "ɫ", "p", "a", "d", "ɐ"], {1: "ɔu"},
     "unstressed vowel before a coda ⟨l⟩"),
    # adactilia ɐdaktiˈliɐ: an ⟨a⟩ before a stop that closes the syllable
    ("adactilia", "ɐdɐktiˈliɐ", "ɐdaktiˈliɐ", ["ɐ", "d", "ɐ", "k", "t", "i", "l", "i", "ɐ"],
     {2: "a"}, "unstressed vowel before a coda stop"),
])
def test_an_unstressed_vowel_slot_is_a_lexical_class(word, rules, entry, readings, others,
                                                     expected):
    assert pt_pt_class(word, rules, entry, readings, others) == expected


def test_a_vowel_where_ao90_dropped_a_consonant_is_a_lexical_class():
    # ativo aˈtivu, pre-AO90 activo: Cunha & Cintra p. 53 keep the vowel of a
    # learned word unreduced.
    readings, others = ["ɐ", "t", "i", "v", "u"], {0: "a"}
    assert pt_pt_class("ativo", "ɐˈtivu", "aˈtivu", readings, others,
                       always_learned) == "unreduced learned vowel"
    assert pt_pt_class("ativo", "ɐˈtivu", "aˈtivu", readings, others) is None


@pytest.mark.parametrize("word, rules, entry, readings, others", [
    # a second difference outside the slot: the final [ɔ] against [u]
    ("ebó", "iˈbɔ", "eˈbu", ["i", "b", "ɔ"], {0: "eɛ", 2: "u"}),
    # the Lisbon [ɐ] is no reading of ⟨e⟩ that the slot admits
    ("ebó", "iˈbɔ", "ɐˈbɔ", ["i", "b", "ɔ"], {0: "eɛɐ"}),
    # a value of the letter that the lattice does not rank there
    ("golpada", "ɡoɫˈpadɐ", "ɡuɫˈpadɐ", ["ɡ", "o", "ɫ", "p", "a", "d", "ɐ"], {1: "ɔ"}),
    # the stressed vowel before a coda ⟨l⟩ is no slot: alto ˈaɫtu
    ("alto", "ˈaɫtu", "ˈɐɫtu", ["a", "ɫ", "t", "u"], {0: "ɐ"}),
    # an ⟨a⟩ before a stop and ⟨r⟩: the stop starts the next syllable (abrir ɐˈbrir)
    ("abrir", "ɐˈbɾiɾ", "aˈbɾiɾ", ["ɐ", "b", "ɾ", "i", "ɾ"], {0: "a"}),
    # an initial ⟨o⟩ before a vowel letter
    ("oeste", "ɔˈɛʃtɨ", "oˈɛʃtɨ", ["ɔ", "ɛ", "ʃ", "t", "ɨ"], {0: "uo"}),
])
def test_a_difference_outside_a_vowel_slot_is_no_class(word, rules, entry, readings, others):
    assert pt_pt_class(word, rules, entry, readings, others) is None


@pytest.mark.parametrize("word, rules, readings", [
    ("ebó", "iˈbɔ", ["e", "b", "ɔ"]),      # the first grapheme reads apart
    ("ebós", "iˈbɔʃ", ["i", "b", "ɔ"]),    # the lattice stops short of ⟨s⟩
])
def test_a_lattice_that_does_not_spell_the_rules_places_no_slot(word, rules, readings):
    assert lb.vowel_slots(word, rules, letter_lattice(readings, {0: "eɛ"}),
                          pt_pt_form, never_learned) == []


@pytest.mark.parametrize("word, end, pre_ao90, headwords, dropped", [
    ("ativo", 1, {"activo"}, set(), True),           # activo
    ("adoção", 3, {"adopção"}, set(), True),         # adopção
    ("direção", 4, {"direcção"}, set(), True),       # direcção
    ("pato", 2, {"pacto"}, {"pacto"}, False),        # pacto is a word of its own
    ("pato", 2, {"pacto", "pato"}, set(), False),    # so is pato
    ("apagar", 1, {"acpagar"}, set(), False),        # no AO90 drop before ⟨p⟩
])
def test_ao90_dropped_consonant(word, end, pre_ao90, headwords, dropped):
    assert lb.ao90_dropped_consonant(word, end, frozenset(pre_ao90),
                                     frozenset(headwords)) is dropped


def test_a_reading_with_two_primary_stresses_has_no_class():
    # Infopédia maquimono mɐˈkiˈmonu shows no single stressed vowel.
    assert lb.lexical_class("maquimono", "mɐkiˈmɔnu", "mɐˈkiˈmonu", pt_pt_form,
                            lb.PT_PT_X_VALUES) is None


@pytest.mark.parametrize("word", ["mesmo", "mesma", "mesmos", "mesmas"])
def test_mesmo_is_a_demonstrative(word):
    # Cunha & Cintra p. 343: "Podem também ser demonstrativos o (a, os, as),
    # mesmo, próprio, semelhante e tal".
    assert lb.closed_class_reason(word, lb.PT_DEMONSTRATIVES) == "closed class"


def test_pt_br_reads_only_x_as_ks_by_word():
    # pt-BR takes only [ks] for the rules' [ʃ] as a lexical value of ⟨x⟩.
    assert lb.lexical_class("próximo", "ˈpɾɔʃimu", "ˈpɾɔsimu") is None


def test_pt_pt_has_no_nasal_closing_rule():
    # fome is [ˈfɔmɨ] in pt-PT; BR_NASAL_STRESSED is a pt-BR rule.
    assert lb.cited_rule_reason("fome", "ˈfɔmɨ", frozenset(), nasal_closes=False) is None
    assert lb.cited_rule_reason("fome", "ˈfɔmi", frozenset()) is not None


# Cunha & Cintra pp. 429-433 give the stem vowel of these verb forms.
@pytest.mark.parametrize("word, headwords, infinitive", [
    ("rogo", {"rogar"}, "rogar"),        # lograr: rogo [ɔ]
    ("rogue", {"rogar"}, "rogar"),       # the subjunctive spells ⟨gu⟩
    ("toque", {"tocar"}, "tocar"),
    ("levas", {"levar"}, "levar"),       # levar: levas [ɛ]
    ("voo", {"voar"}, "voar"),           # -oar: voo [o]
    ("corro", {"correr"}, "correr"),     # mover: corro [o], corres [ɔ]
    ("deves", {"dever"}, "dever"),
    ("conheço", {"conhecer"}, "conhecer"),
    ("canto", {"cantar"}, None),         # the stem vowel is ⟨a⟩
    ("pernoito", {"pernoitar"}, None),   # ⟨oi⟩ is a diphthong
    ("rogo", set(), None),               # no such infinitive
])
def test_a_rhizotonic_verb_form_has_its_vowel_by_rule(word, headwords, infinitive):
    assert lb.rhizotonic_verb_form(word, frozenset(headwords)) == infinitive


def test_a_w_that_the_spelling_cannot_hide_is_not_lexical():
    # ⟨qua⟩ always has [w], so [k] against [kw] there is no ⟨qu gu⟩ fact
    assert lb.lexical_class("quatro", "ˈkatɾu", "ˈkwatɾu") is None


@pytest.mark.parametrize("word, entry, reason", [
    ("sobre", "ˈsɔbɾi", "a PT_LEX height rule lists the word"),
    ("avô", "aˈvɔ", "a written accent gives the height"),
    ("tema", "ˈtɛmɐ", "BR_NASAL_STRESSED closes a vowel before a nasal"),
    ("sete", "ˈsɛt͡ʃi", None),
])
def test_a_cited_rule_keeps_a_word_a_lead(word, entry, reason):
    assert lb.cited_rule_reason(word, entry, frozenset({"sobre"})) == reason


def test_with_stressed_vowel_changes_only_the_stressed_vowel():
    assert lb.with_stressed_vowel("deˈbose", "ɔ") == "deˈbɔse"
    assert lb.with_stressed_vowel("ˈʒew", "ɛ") == "ˈʒɛw"


@pytest.mark.parametrize("reading, expected", [
    ("foˈdeɾ", "foˈdeɾ"),
    ("fo'deɾ", "foˈdeɾ"),
    ("ˈa(j)ʃkʊ", "ˈaʃkʊ"),
    ("pˌet͡ʃiˈsɐ̃w̃", "pet͡ʃiˈsɐ̃w̃"),
    ("iˈglu", "iˈɡlu"),
])
def test_wiktionary_typing_variants(reading, expected):
    assert lb.wiktionary_to_ipa(reading) == expected


def test_the_aeiouado_lexicon_never_corroborates():
    assert lb.PT_BR_CORROBORATING_SOURCES == {"wikipron", "wiktionary", "michaelis"}


class FakeSpec:
    allophone_rules = ()


class FakeEngine:
    """The rules' readings of the mining test."""
    spec = FakeSpec()
    rules = {"deboche": "deˈboʃi", "gato": "ˈɡatu", "bola": "ˈbolɐ", "asco": "ˈasku",
             "seco": "ˈseku", "sala": "ˈsalɐ", "sobre": "ˈsobɾi", "pele": "ˈpeli"}

    def transcribe_word(self, word):
        return self.rules[word]


def test_mining_takes_the_reading_from_wiktionary_and_never_from_michaelis():
    wiktionary = {
        "deboche": ["deˈbɔʃi"],          # an entry in the norm, with the rules' [i]
        "gato": ["ˈɡatʊ"],               # the rules read it right
        "bola": ["ˈbɔlɐ"],               # Michaelis prints the close vowel
        "asco": ["ˈaʃkʊ"],               # the difference is one Michaelis cannot show
        "seco": ["ˈseku", "ˈsɛku"],      # the line gives two heights
        "sala": [],
        "sobre": ["ˈsɔbɾi"],             # the spec lists the word
        "pele": ["ˈpɛli"],               # the homograph list holds the word
    }
    michaelis = {"deboche": ["deˈbɔʃi"], "gato": ["ˈɡatu"], "bola": ["ˈbolə"],
                 "asco": ["ˈasku"], "seco": ["ˈseku"], "sala": ["ˈsalə"],
                 "sobre": ["ˈsɔbɾi"], "pele": ["ˈpɛli"]}
    passed, rows = bl.mine_wiktionary(
        FakeEngine(), wiktionary, wiktionary, michaelis, frozenset(), frozenset({"pele"}),
        frozenset({"sobre"}), lambda ipa: ipa)
    assert [c.ipa for c in passed] == ["deˈbɔʃi"]
    assert {c.word: stage for c, _, stage, _ in rows} == {
        "deboche": "mined", "gato": "mined: rules right", "bola": "mined: uncorroborated",
        "asco": "mined: Michaelis cannot show", "seco": "mined: two heights",
        "sala": "mined: no reading", "sobre": "mined: cited rule", "pele": "mined: homograph"}


def test_a_homograph_needs_a_mid_vowel_or_a_second_reading():
    assert bl.nilc_homograph("gosto", {"V", "N"}, ["ˈɡɔstu"], [], "ˈɡɔstu", frozenset())
    assert bl.nilc_homograph("gosto", set(), ["ˈɡɔstu"], [], "ˈɡɔstu", frozenset({"gosto"}))
    assert bl.nilc_homograph("sede", set(), ["ˈsedi", "ˈsɛdi"], [], "ˈsɛdi", frozenset())
    assert bl.nilc_homograph("sede", set(), ["ˈsɛdi"], ["ˈsɛd͡ʒi", "ˈsedi"], "ˈsɛdi", frozenset())
    assert bl.nilc_homograph("vaca", {"V", "N"}, ["ˈvakɐ"], [], "ˈvakɐ", frozenset()) is None
    # a notation difference between two readings is no homograph
    assert bl.nilc_homograph("pacto", set(), ["ˈpakitu", "ˈpaktu"], [], "ˈpakitu",
                             frozenset()) is None


# Infopédia puts the stress mark at its own syllable boundary, the rules at
# their own onset. The entry keeps its sounds and takes the rules' place.
@pytest.mark.parametrize("entry, rules, expected", [
    ("ɐˈɡnelu", "ɐɡˈnɛlu", "ɐɡˈnelu"),                  # agnelo
    ("ɐdvɛˈktaɾ", "ɐdvɨkˈtaɾ", "ɐdvɛkˈtaɾ"),            # advectar
    ("ɐkɐtɐlɛˈpsiɐ", "ɐkɐtɐlɨpˈsiɐ", "ɐkɐtɐlɛpˈsiɐ"),   # acatalepsia
    ("ɐɡɐlaˈktiɐ", "ɐɡɐlɐkˈtiɐ", "ɐɡɐlakˈtiɐ"),         # agalactia
    ("ɡajˈolu", "ɡaˈjɔlu", "ɡaˈjolu"),                  # gaiolo: a glide onset
    ("ɐˈbebɾɐ", "ɐˈbɛbɾɐ", "ɐˈbebɾɐ"),                  # abebra: already there
    ("ˈɡnomu", "ˈɡnɔmu", "ˈɡnomu"),                     # a word-initial cluster
    ("ɐˈpt͡ʃu", "ɐpˈt͡ʃu", "ɐpˈt͡ʃu"),                    # an affricate before the vowel
    ("sõˈktu", "sõkˈtu", "sõkˈtu"),               # NFC entry, NFD rules: the entry's bytes stay
])
def test_an_entry_takes_the_rules_place_of_the_stress_mark(entry, rules, expected):
    assert lb.onset_stress(entry, rules) == expected


@pytest.mark.parametrize("entry, rules", [
    ("ɐfiˈksaɾ", "ɐfiˈʃaɾ"),          # afixar: [ks] against [ʃ]
    ("ˈkwezu", "kuˈɛzu"),             # coeso: a glide against a vowel
    ("kɛˈtʃɐp", "ˈkɛtʃup"),           # ketchup: another stressed vowel
    ("ɐkˈtaktu", "ɐktɐˈktu"),         # the same consonants before another stressed vowel
    ("mɐˈkiˈmonu", "mɐkiˈmɔnu"),      # maquimono: two primary marks
    ("ɐˈɡnaˈɡnu", "ɐɡnɐɡˈnu"),        # two marks, the first before the rules' cluster
    ("kæt", "ˈkæt"),                  # an entry with no mark
])
def test_an_entry_keeps_its_stress_mark_when_the_readings_differ_before_it(entry, rules):
    assert lb.onset_stress(entry, rules) is None


def test_the_build_writes_the_rules_place_of_the_stress_mark():
    import orthography2ipa
    engine = orthography2ipa.G2P("pt-PT", expose_ambiguous_endings=False)
    kept = [lb.Candidate(w, w, "", "", ipa) for w, ipa in
            (("agnelo", "ɐˈɡnelu"), ("afixar", "ɐfiˈksaɾ"), ("abebra", "ɐˈbebɾɐ"))]
    entries, counts = bl.rules_stress_place(engine, kept)
    assert entries == {"agnelo": "ɐɡˈnelu", "afixar": "ɐfiˈksaɾ", "abebra": "ɐˈbebɾɐ"}
    assert counts == {"moved": 1, "kept": 1, "same": 1}
