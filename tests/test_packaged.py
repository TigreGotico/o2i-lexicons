"""Every lexicon that ships in the package satisfies the contract."""
from importlib.metadata import entry_points

import o2i_lexicons
from o2i_lexicons.schema import validate_meta, validate_tsv

GROUP = "orthography2ipa.lexicons"


def own_entry_points():
    return [ep for ep in entry_points(group=GROUP)
            if ep.dist is not None and ep.dist.name.replace("_", "-") == "o2i-lexicons"]


def test_packaged_files_are_valid():
    problems = {}
    for code in o2i_lexicons.available_codes():
        text = o2i_lexicons.tsv_path(code).read_text(encoding="utf-8")
        entries = {w: ipa for w, _, ipa in (line.partition("\t") for line in text.splitlines() if line)}
        found = [f"tsv line {n}: {r}" for n, r in validate_tsv(text)]
        found += validate_meta(o2i_lexicons.load_meta(code), code, entries)
        if found:
            problems[code] = found
    assert problems == {}


def test_each_meta_sits_next_to_its_tsv():
    for code in o2i_lexicons.available_codes():
        assert o2i_lexicons.meta_path(code).is_file(), code


def test_entry_points_name_exactly_the_packaged_codes():
    names = sorted(ep.name for ep in own_entry_points())
    assert names == o2i_lexicons.available_codes()


def test_each_entry_point_returns_its_own_file():
    for ep in own_entry_points():
        provider = ep.load()
        assert provider is o2i_lexicons.tsv_path
        assert provider(ep.name) == o2i_lexicons.tsv_path(ep.name)
        assert provider(ep.name).is_file()


def test_the_en_gb_pilot_ships_with_its_provenance():
    # WikiPron README: the Wiktionary data has Wiktionary's own terms, which
    # Wiktionary:Copyrights states as CC BY-SA 4.0 (and GFDL). The tier is the
    # one orthography2ipa's benchmark registry gives the wikipron gold.
    assert "en-GB" in o2i_lexicons.available_codes()
    meta = o2i_lexicons.load_meta("en-GB")
    assert (meta["source"], meta["tier"], meta["licence"]) == (
        "wikipron", "crowd-scraped", "CC-BY-SA-4.0")
    # WikiPron scrapes with stress removed ("stress": False in
    # data/scrape/lib/scrape.py), so the stress comes from the o2i rules.
    assert meta["stress"] == "rules"
    assert meta["source_url"].endswith("/eng_latn_uk_broad.tsv")


def test_the_pt_pt_lexicon_ships_with_its_provenance():
    # The Infopédia rows of portuguese-unified: the dataset card gives
    # cc-by-sa-4.0, and the orthography2ipa benchmark registry gives the
    # portuguese_unified gold the lexicon-derived tier.
    assert "pt-PT" in o2i_lexicons.available_codes()
    assert o2i_lexicons.tsv_path("pt-PT").name == "infopedia.tsv"
    meta = o2i_lexicons.load_meta("pt-PT")
    assert (meta["source"], meta["tier"], meta["licence"]) == (
        "infopedia", "lexicon-derived", "CC-BY-SA-4.0")
    assert meta["stress"] == "source"
    assert meta["source_url"].endswith(
        "/portuguese-unified-pronunciation-lexicon/resolve/main/"
        "portuguese_pronunciation_lexicon.jsonl")


def test_the_pt_br_lexicon_ships_with_its_provenance():
    # The NILC training file is BSD 3-Clause, Copyright (c) 2014, Gustavo Mendonça.
    # The pt.wiktionary readings are CC BY-SA 4.0, so the file takes that licence.
    assert "pt-BR" in o2i_lexicons.available_codes()
    assert o2i_lexicons.tsv_path("pt-BR").name == "nilc.tsv"
    meta = o2i_lexicons.load_meta("pt-BR")
    assert (meta["source"], meta["tier"], meta["licence"]) == (
        "nilc", "expert-human", "CC-BY-SA-4.0")
    assert meta["stress"] == "source"
    assert meta["source_url"].endswith("/etc/unitex_sample_transcribed.txt")
    notice = (o2i_lexicons.DATA_DIR / "pt-BR" / "LICENSE.nilc").read_text(encoding="utf-8")
    assert "Copyright (c) 2014, Gustavo Mendonça" in notice


def test_the_pt_br_lexicon_holds_the_lexical_classes():
    # Expected readings: Barbosa & Albano 2004 for sete, and the standard
    # dictionaries for the rest. Each word is outside what the spelling shows.
    entries = dict(line.split("\t") for line in o2i_lexicons.tsv_path(
        "pt-BR").read_text(encoding="utf-8").splitlines())
    assert entries["foto"] == "ˈfɔtu"
    assert entries["táxi"] == "ˈtaksi"
    assert entries["tórax"] == "ˈtɔɾaks"


def test_a_wiktionary_reading_is_named_in_the_sidecar():
    meta = o2i_lexicons.load_meta("pt-BR")
    entries = o2i_lexicons.tsv_path("pt-BR").read_text(encoding="utf-8")
    words = {line.split("\t")[0] for line in entries.splitlines()}
    assert "deboche" in meta["wiktionary_readings"]
    assert set(meta["wiktionary_readings"]) <= words


def test_the_pt_br_entries_use_the_spec_symbols():
    text = o2i_lexicons.tsv_path("pt-BR").read_text(encoding="utf-8")
    assert text
    # the file writes [ɪ ʊ ə y], the fricative rhotics, and the spec does not
    readings = "".join(line.split("\t")[1] for line in text.splitlines())
    assert set(readings) & set("ɪʊəyɣ") == set()
    assert "x" not in readings.replace("ks", "")


def test_the_pt_pt_entries_use_the_spec_symbols():
    # Infopédia writes abete ɐˈbet(ə), rap ˈʀɛp and retrorso ʀəˈtrorsu.
    # The pt-PT spec writes the reduced vowel ɨ, the strong rhotic ʁ and the
    # tap ɾ, and the full form of an optional vowel.
    text = o2i_lexicons.tsv_path("pt-PT").read_text(encoding="utf-8")
    entries = dict(line.split("\t") for line in text.splitlines())
    assert entries["abete"] == "ɐˈbetɨ"
    assert entries["rap"] == "ˈʁɛp"
    assert entries["retrorso"] == "ʁɨˈtɾoɾsu"
    assert [w for w, ipa in entries.items() if set(ipa) & set("əʀr")] == []


def test_the_pt_pt_lexicon_holds_no_reading_of_another_headword():
    # Infopédia rows that transcribe another word: augustinista reads
    # vjuliˈniʃtɐ, aquilombado reads mɐɾõˈbadu, cucaracho reads mɐmɐˈɾaʃu and
    # blitz reads blitzkrieg. The rules read each of them better.
    text = o2i_lexicons.tsv_path("pt-PT").read_text(encoding="utf-8")
    words = {line.split("\t")[0] for line in text.splitlines()}
    assert words & {"augustinista", "aquilombado", "cucaracho", "blitz"} == set()


def test_the_pt_pt_lexicon_holds_no_letter_name_or_function_word():
    # Infopédia reads a as [a] and o as [ˈɔ], the letter names; the articles
    # are [ɐ] and [u]. The spec's unstressed words must keep the rules.
    import orthography2ipa
    text = o2i_lexicons.tsv_path("pt-PT").read_text(encoding="utf-8")
    words = {line.split("\t")[0] for line in text.splitlines()}
    assert {w for w in words if len(w) == 1} == set()
    assert words & {"ah", "eh", "oh"} == set()
    assert words & set(orthography2ipa.get("pt-PT").stress.cliticless_words) == set()


def test_the_pt_pt_lexicon_hides_no_open_rule_defect():
    # o2i#2046: ⟨ã⟩ reads [ã]. These words differ from the rules only there.
    text = o2i_lexicons.tsv_path("pt-PT").read_text(encoding="utf-8")
    words = {line.split("\t")[0] for line in text.splitlines()}
    assert words & {"afã", "fã", "chã", "sã", "pã"} == set()


def test_the_pt_pt_lexicon_holds_no_known_source_defect():
    # A hand check found armazém ɐɾmɐˈʒɐ̃j̃, cupé kuˈpe, deve ˈdɛv, bajulação
    # bɐjulɐˈsɐ̃w̃ and bombardeiro bobɐɾˈdɐjɾu wrong.
    text = o2i_lexicons.tsv_path("pt-PT").read_text(encoding="utf-8")
    words = {line.split("\t")[0] for line in text.splitlines()}
    assert words & {"armazém", "cupé", "deve", "bajulação", "bombardeiro"} == set()


def test_no_packaged_entry_has_a_stress_mark_inside_an_onset():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import lexicon_build as lb
    found = {}
    for code in o2i_lexicons.available_codes():
        text = o2i_lexicons.tsv_path(code).read_text(encoding="utf-8")
        bad = [w for w, _, ipa in (line.partition("\t") for line in text.splitlines()) if lb.misplaced_stress(ipa)]
        if bad:
            found[code] = bad
    assert found == {}


def test_the_pt_pt_lexicon_follows_the_pt_pt_norm():
    # Infopédia writes the Lisbon [ɐj] (êxito ˈɐjzitu); pt-PT writes [ej].
    # yakuza carries a stress mark inside an onset, pola is a homograph, and
    # the [ɐj] of rugby spells ⟨u⟩, so it has no pt-PT [ej].
    text = o2i_lexicons.tsv_path("pt-PT").read_text(encoding="utf-8")
    entries = dict(line.split("\t") for line in text.splitlines())
    lisbon = [w for w, ipa in entries.items()
              if "ɐj" in ipa.replace("ɐ̃j̃", "") and not any(s in w for s in ("ai", "ay", "aj", "âi"))]
    assert lisbon == []
    assert entries.keys() & {"yakuza", "pola", "rugby"} == set()


def test_no_pt_pt_entry_rests_on_a_merged_row_alone():
    # A row merged from Infopédia and pt.wiktionary repeats the Infopédia
    # reading. These words have no other second source.
    text = o2i_lexicons.tsv_path("pt-PT").read_text(encoding="utf-8")
    entries = {line.split("\t")[0] for line in text.splitlines()}
    merged_only = {"airbag", "amuado", "beatlemania", "bluff", "cear", "coevo",
                   "coibir", "cânon", "flirt", "jazz", "soufflé", "tweed",
                   "êxito", "óptico"}
    assert entries & merged_only == set()


def test_a_pt_pt_entry_may_end_a_nasal_diphthong_in_a_nasal_glide():
    # Infopédia proibição [pɾuibiˈsɐ̃w̃].
    text = o2i_lexicons.tsv_path("pt-PT").read_text(encoding="utf-8")
    entries = dict(line.split("\t") for line in text.splitlines())
    assert entries["proibição"] == "pɾuibiˈsɐ̃w̃"


def pt_pt_entries():
    text = o2i_lexicons.tsv_path("pt-PT").read_text(encoding="utf-8")
    return dict(line.split("\t") for line in text.splitlines())


def test_the_pt_pt_lexicon_holds_the_lexical_classes():
    # The Infopédia rows, in the spec's symbols: acetona ɐsəˈtonɐ, exógamo
    # eˈzɔɡɐmu, próximo ˈprɔsimu, táxi ˈtaksi, cinquenta sĩˈkwẽtɐ.
    entries = pt_pt_entries()
    assert entries["acetona"] == "ɐsɨˈtonɐ"
    assert entries["exógamo"] == "eˈzɔɡɐmu"
    assert entries["próximo"] == "ˈpɾɔsimu"
    assert entries["táxi"] == "ˈtaksi"
    assert entries["cinquenta"] == "sĩˈkwẽtɐ"


def test_a_pt_pt_class_word_needs_no_second_source():
    # No WikiPron or pt.wiktionary reading agrees with Infopédia exógamo
    # eˈzɔɡɐmu or abelota ɐbɨˈlotɐ, and both are entries. The sidecar keeps
    # the class and the result of the second-source test of each such entry.
    entries = pt_pt_entries()
    classes = o2i_lexicons.load_meta("pt-PT")["lexical_classes"]
    assert classes["exógamo"] == {"class": "⟨x⟩ as [z]", "second_source": "no second source"}
    assert classes["abelota"] == {"class": "stressed mid vowel",
                                  "second_source": "no second source"}
    assert entries["abelota"] == "ɐbɨˈlotɐ"
    assert set(classes) <= set(entries)


def test_the_pt_pt_lexicon_drops_a_class_word_a_second_source_reads_as_the_rules_do():
    # WikiPron or pt.wiktionary gives the rules' reading of each of these words
    # and Infopédia gives another one. One source against one does not settle
    # the word, so the rules keep it.
    conflicts = {"ameba", "anguiforme", "anguiliforme", "anguípede", "bancarrota", "bauxite",
                 "bixina", "cairota", "codorna", "cunete", "eba", "longinquidade",
                 "patinete", "rolete", "sanguento", "saragoça", "sestro", "tormentelo"}
    meta = o2i_lexicons.load_meta("pt-PT")
    assert pt_pt_entries().keys() & conflicts == set()
    assert meta["lexical_classes"].keys() & conflicts == set()


def test_the_pt_pt_lexicon_holds_no_demonstrative():
    # Cunha & Cintra p. 343 list the demonstratives and their contractions with
    # ⟨de em a⟩. They are a closed class, and stress in the sentence sets
    # their vowel.
    demonstratives = {"este", "esta", "esse", "essa", "aquele", "aquela", "isto", "isso",
                      "aquilo", "deste", "desta", "neste", "nesta", "daquele", "naquele",
                      "àquele", "àquela"}
    assert pt_pt_entries().keys() & demonstratives == set()


def test_the_pt_pt_lexicon_holds_the_unstressed_vowel_classes():
    # The Infopédia rows, in the spec's symbols: orelhado orəˈʎadu, ebó eˈbɔ,
    # golpada ɡɔɫˈpadɐ, adactilia ɐdaktiˈliɐ, ativo aˈtivu.
    entries = pt_pt_entries()
    classes = o2i_lexicons.load_meta("pt-PT")["lexical_classes"]
    expected = {
        "orelhado": ("oɾɨˈʎadu", "unstressed initial ⟨o⟩"),
        "ebó": ("eˈbɔ", "unstressed initial ⟨e⟩"),
        "golpada": ("ɡɔɫˈpadɐ", "unstressed vowel before a coda ⟨l⟩"),
        "adactilia": ("ɐdaktiˈliɐ", "unstressed vowel before a coda stop"),
        "ativo": ("aˈtivu", "unreduced learned vowel"),
    }
    assert {w: (entries.get(w), classes.get(w, {}).get("class")) for w in expected} == expected


def test_the_pt_pt_lexicon_holds_no_mesmo():
    # Cunha & Cintra p. 343 name mesmo as a demonstrative too.
    assert pt_pt_entries().keys() & {"mesmo", "mesma", "mesmos", "mesmas"} == set()


def test_no_pt_pt_entry_has_two_primary_stresses():
    assert [w for w, ipa in pt_pt_entries().items() if ipa.count("ˈ") > 1] == []


def test_the_pt_pt_lexicon_holds_no_word_that_a_cited_rule_reads():
    # Cunha & Cintra pp. 429-433 give the stem vowel of a rhizotonic verb form:
    # abordo, choro (lograr), achego (levar), corro (mover). A written accent
    # gives the height of cupé, and desvelo is in the bifonia homograph list.
    # The rules read alterado aɫtəˈradu right.
    entries = pt_pt_entries()
    assert entries.keys() & {"abordo", "choro", "achego", "corro", "cupé", "desvelo",
                             "alterado"} == set()


def test_an_entry_puts_its_stress_mark_where_the_rules_do():
    # Infopédia writes agnelo ɐˈɡnelu and the rules ɐɡˈnɛlu. An entry takes
    # the place of the rules' reading, so its mark follows the rules' onset
    # wherever the two readings have the same sounds before the stressed vowel.
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import lexicon_build as lb
    import orthography2ipa
    entries = pt_pt_entries()
    assert entries["agnelo"] == "ɐɡˈnelu"
    assert entries["advectar"] == "ɐdvɛkˈtaɾ"
    assert entries["agalactia"] == "ɐɡɐlakˈtiɐ"
    assert entries["acatalepsia"] == "ɐkɐtɐlɛpˈsiɐ"
    assert entries["afixar"] == "ɐfiˈksaɾ"
    found = {}
    for code in o2i_lexicons.available_codes():
        engine = orthography2ipa.G2P(code, pipeline=orthography2ipa.Pipeline(lexicon={}))
        text = o2i_lexicons.tsv_path(code).read_text(encoding="utf-8")
        moved = [w for w, _, ipa in (line.partition("\t") for line in text.splitlines())
                 if lb.onset_stress(ipa, engine.transcribe_word(w)) not in (None, ipa)]
        if moved:
            found[code] = moved
    assert found == {}
