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
    assert entries["papel"] == "paˈpɛw"
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
    # Infopédia writes exame iˈzɐm(ə), rap ˈʀɛp and bisbilhotar bəʒbiʎuˈtar.
    # The pt-PT spec writes the reduced vowel ɨ, the strong rhotic ʁ and the
    # tap ɾ, and the full form of an optional vowel.
    text = o2i_lexicons.tsv_path("pt-PT").read_text(encoding="utf-8")
    entries = dict(line.split("\t") for line in text.splitlines())
    assert entries["exame"] == "iˈzɐmɨ"
    assert entries["rap"] == "ˈʁɛp"
    assert entries["bisbilhotar"] == "bɨʒbiʎuˈtaɾ"
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
