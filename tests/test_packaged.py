"""Every lexicon that ships in the package satisfies the contract."""
from importlib.metadata import entry_points

import pytest

import o2i_lexicons
from o2i_lexicons.schema import validate_meta, validate_tsv

GROUPS = {"exception": "orthography2ipa.lexicons", "patch": "orthography2ipa.lexicon_patches"}
FILES = {"exception": (o2i_lexicons.tsv_path, o2i_lexicons.load_meta),
         "patch": (o2i_lexicons.patch_tsv_path, o2i_lexicons.load_patch_meta)}


def own_entry_points(kind):
    return [ep for ep in entry_points(group=GROUPS[kind])
            if ep.dist is not None and ep.dist.name.replace("_", "-") == "o2i-lexicons"]


def file_entries(code, kind):
    text = FILES[kind][0](code).read_text(encoding="utf-8")
    return dict(line.split("\t") for line in text.splitlines())


def all_entries(code):
    """The entries of both files of *code*."""
    return {**file_entries(code, "patch"), **file_entries(code, "exception")}


def all_text(code):
    return "".join(f"{w}\t{ipa}\n" for w, ipa in all_entries(code).items())


def lexical_classes(code):
    return {w: c for kind in FILES for w, c in FILES[kind][1](code)["lexical_classes"].items()}


@pytest.mark.parametrize("kind", FILES)
def test_packaged_files_are_valid(kind):
    tsv_of, meta_of = FILES[kind]
    problems = {}
    for code in o2i_lexicons.available_codes(kind):
        text = tsv_of(code).read_text(encoding="utf-8")
        entries = {w: ipa for w, _, ipa in (line.partition("\t") for line in text.splitlines() if line)}
        found = [f"tsv line {n}: {r}" for n, r in validate_tsv(text, code)]
        found += validate_meta(meta_of(code), code, entries, kind)
        if found:
            problems[code] = found
    assert problems == {}


@pytest.mark.parametrize("kind", FILES)
def test_no_packaged_entry_is_shadowed_by_the_spec(kind):
    # The spec's word_exceptions win over a lexicon, so such an entry never applies.
    import orthography2ipa
    shadowed = {code: sorted(file_entries(code, kind).keys()
                             & orthography2ipa.get(code).word_exceptions.keys())
                for code in o2i_lexicons.available_codes(kind)}
    assert {code: words for code, words in shadowed.items() if words} == {}


def test_the_sdist_holds_the_scripts_that_its_tests_import(tmp_path):
    import shutil
    import subprocess
    import sys
    import tarfile
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    tree = tmp_path / "tree"
    shutil.copytree(root, tree, ignore=shutil.ignore_patterns(
        ".git", ".venv", ".cache", "build", "dist", "*.egg-info", "__pycache__", ".pytest_cache"))
    name = subprocess.run(
        [sys.executable, "-c", "from setuptools import build_meta; print(build_meta.build_sdist('dist'))"],
        cwd=tree, capture_output=True, text=True, check=True).stdout.split()[-1]
    with tarfile.open(tree / "dist" / name) as sdist:
        members = {Path(m).relative_to(Path(m).parts[0]).as_posix() for m in sdist.getnames()}
    for folder in ("scripts", "tests"):
        expected = {f"{folder}/{p.name}" for p in (root / folder).glob("*.py")}
        assert {m for m in members if m.startswith(f"{folder}/")} == expected, folder


def test_each_meta_sits_next_to_its_tsv():
    for code in o2i_lexicons.available_codes():
        assert o2i_lexicons.meta_path(code).is_file(), code
        assert o2i_lexicons.patch_meta_path(code).is_file(), code


def test_each_code_ships_a_patch_file_and_no_word_is_in_both():
    codes = o2i_lexicons.available_codes()
    assert o2i_lexicons.available_codes("patch") == codes
    for code in codes:
        assert file_entries(code, "exception").keys() & file_entries(code, "patch").keys() == set()


def test_each_data_directory_holds_one_tsv():
    dirs = [d for d in o2i_lexicons.DATA_DIR.rglob("*") if d.is_dir()]
    assert {d.name: len(list(d.glob("*.tsv"))) for d in dirs if d.name != "patches"} == {
        code: 1 for code in o2i_lexicons.available_codes()}
    assert sorted(f.parent.name for f in o2i_lexicons.DATA_DIR.glob("*/*.tsv")) == \
        o2i_lexicons.available_codes()


@pytest.mark.parametrize("kind", FILES)
def test_entry_points_name_exactly_the_packaged_codes(kind):
    names = sorted(ep.name for ep in own_entry_points(kind))
    assert names == o2i_lexicons.available_codes(kind)


@pytest.mark.parametrize("kind", FILES)
def test_each_entry_point_returns_its_own_file(kind):
    tsv_of = FILES[kind][0]
    for ep in own_entry_points(kind):
        provider = ep.load()
        assert provider is tsv_of
        assert provider(ep.name) == tsv_of(ep.name)
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
    assert meta["source_url"] == (
        "https://raw.githubusercontent.com/CUNY-CL/wikipron/"
        "d282e848a211ea31cfd730f0ced8bc8cdab9e83d/data/scrape/tsv/eng_latn_uk_broad.tsv")
    assert meta["source_sha256"] == (
        "f8ca476aa2e96cb22cafbf9099d689b5902a9d321579055081909b2eeafa1b8d")


@pytest.mark.parametrize("kind", FILES)
def test_the_en_gb_second_source_is_pinned(kind):
    # Britfone 3.0.1 (MIT): its README calls it "British English
    # (RP/Standard Southern British) pronunciation dictionary".
    source = FILES[kind][1]("en-GB")["agreement_source"]
    assert (source["name"], source["version"], source["licence"]) == ("britfone", "3.0.1", "MIT")
    assert source["url"] == ("https://github.com/JoseLlarena/Britfone/blob/"
                             "1062be14adc96c358f2087ac5449d72130c7a6f4/britfone.main.3.0.1.csv")
    assert source["sha256"] == "59f197e98520856d1cc88e380beb54e4314d8712efc4d588b6778819c502d920"


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
    entries = all_entries("pt-BR")
    assert entries["foto"] == "ˈfɔtu"
    assert entries["táxi"] == "ˈtaksi"
    assert entries["tórax"] == "ˈtɔɾaks"


def test_a_wiktionary_reading_is_named_in_the_sidecar():
    for kind, (_, meta_of) in FILES.items():
        assert set(meta_of("pt-BR")["wiktionary_readings"]) <= file_entries("pt-BR", kind).keys()
    assert "deboche" in o2i_lexicons.load_meta("pt-BR")["wiktionary_readings"]


def test_the_pt_br_entries_use_the_spec_symbols():
    text = all_text("pt-BR")
    assert text
    # the file writes [ɪ ʊ ə y], the fricative rhotics, and the spec does not
    readings = "".join(line.split("\t")[1] for line in text.splitlines())
    assert set(readings) & set("ɪʊəyɣ") == set()
    assert "x" not in readings.replace("ks", "")


def test_the_pt_pt_entries_use_the_spec_symbols():
    # Infopédia writes abete ɐˈbet(ə), rap ˈʀɛp and retrorso ʀəˈtrorsu.
    # The pt-PT spec writes the reduced vowel ɨ, the strong rhotic ʁ and the
    # tap ɾ, and the full form of an optional vowel.
    text = all_text("pt-PT")
    entries = dict(line.split("\t") for line in text.splitlines())
    assert entries["abete"] == "ɐˈbetɨ"
    assert entries["rap"] == "ˈʁɛp"
    assert entries["retrorso"] == "ʁɨˈtɾoɾsu"
    assert [w for w, ipa in entries.items() if set(ipa) & set("əʀr")] == []


def test_the_pt_pt_lexicon_holds_no_reading_of_another_headword():
    # Infopédia rows that transcribe another word: augustinista reads
    # vjuliˈniʃtɐ, aquilombado reads mɐɾõˈbadu, cucaracho reads mɐmɐˈɾaʃu and
    # blitz reads blitzkrieg. The rules read each of them better.
    text = all_text("pt-PT")
    words = {line.split("\t")[0] for line in text.splitlines()}
    assert words & {"augustinista", "aquilombado", "cucaracho", "blitz"} == set()


def test_the_pt_pt_lexicon_holds_no_letter_name_or_function_word():
    # Infopédia reads a as [a] and o as [ˈɔ], the letter names; the articles
    # are [ɐ] and [u]. The spec's unstressed words must keep the rules.
    import orthography2ipa
    text = all_text("pt-PT")
    words = {line.split("\t")[0] for line in text.splitlines()}
    assert {w for w in words if len(w) == 1} == set()
    assert words & {"ah", "eh", "oh"} == set()
    assert words & set(orthography2ipa.get("pt-PT").stress.cliticless_words) == set()


def test_the_pt_pt_lexicon_hides_no_open_rule_defect():
    # o2i#2046: ⟨ã⟩ reads [ã]. These words differ from the rules only there.
    text = all_text("pt-PT")
    words = {line.split("\t")[0] for line in text.splitlines()}
    assert words & {"afã", "fã", "chã", "sã", "pã"} == set()


def test_the_pt_pt_lexicon_holds_no_known_source_defect():
    # A hand check found armazém ɐɾmɐˈʒɐ̃j̃, cupé kuˈpe, deve ˈdɛv, bajulação
    # bɐjulɐˈsɐ̃w̃ and bombardeiro bobɐɾˈdɐjɾu wrong.
    text = all_text("pt-PT")
    words = {line.split("\t")[0] for line in text.splitlines()}
    assert words & {"armazém", "cupé", "deve", "bajulação", "bombardeiro"} == set()


def test_no_packaged_entry_has_a_stress_mark_inside_an_onset():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import lexicon_build as lb
    found = {}
    for code in o2i_lexicons.available_codes():
        text = all_text(code)
        bad = [w for w, _, ipa in (line.partition("\t") for line in text.splitlines()) if lb.misplaced_stress(ipa)]
        if bad:
            found[code] = bad
    assert found == {}


def test_the_pt_pt_lexicon_follows_the_pt_pt_norm():
    # Infopédia writes the Lisbon [ɐj] (êxito ˈɐjzitu); pt-PT writes [ej].
    # yakuza carries a stress mark inside an onset, pola is a homograph, and
    # the [ɐj] of rugby spells ⟨u⟩, so it has no pt-PT [ej].
    text = all_text("pt-PT")
    entries = dict(line.split("\t") for line in text.splitlines())
    lisbon = [w for w, ipa in entries.items()
              if "ɐj" in ipa.replace("ɐ̃j̃", "") and not any(s in w for s in ("ai", "ay", "aj", "âi"))]
    assert lisbon == []
    assert entries.keys() & {"yakuza", "pola", "rugby"} == set()


def test_no_pt_pt_entry_rests_on_a_merged_row_alone():
    # A row merged from Infopédia and pt.wiktionary repeats the Infopédia
    # reading. These words have no other second source.
    text = all_text("pt-PT")
    entries = {line.split("\t")[0] for line in text.splitlines()}
    merged_only = {"airbag", "amuado", "beatlemania", "bluff", "cear", "coevo",
                   "coibir", "cânon", "flirt", "jazz", "soufflé", "tweed",
                   "êxito", "óptico"}
    assert entries & merged_only == set()


def test_a_pt_pt_entry_may_end_a_nasal_diphthong_in_a_nasal_glide():
    # Infopédia proibição [pɾuibiˈsɐ̃w̃].
    text = all_text("pt-PT")
    entries = dict(line.split("\t") for line in text.splitlines())
    assert entries["proibição"] == "pɾuibiˈsɐ̃w̃"


def pt_pt_entries():
    return all_entries("pt-PT")


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
    classes = lexical_classes("pt-PT")
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
    assert pt_pt_entries().keys() & conflicts == set()
    assert lexical_classes("pt-PT").keys() & conflicts == set()


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
    classes = lexical_classes("pt-PT")
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


def test_an_entry_puts_its_stress_mark_before_the_onset_of_the_stressed_syllable():
    # The onset is one consonant or an obstruent + liquid cluster of Cunha &
    # Cintra (p. 64); a consonant before it has an empty nucleus of its own
    # (Mateus & d'Andrade 1998, pp. 17-18). Infopédia writes agnelo ɐˈɡnelu,
    # afixar ɐfiˈksaɾ, axioma ɐˈksjomɐ and epiblasto ɛpiˈblaʃtu.
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import build_lexicon as bl
    import lexicon_build as lb
    entries = pt_pt_entries()
    assert entries["agnelo"] == "ɐɡˈnelu"
    assert entries["agalactia"] == "ɐɡɐlakˈtiɐ"
    assert entries["afixar"] == "ɐfikˈsaɾ"
    assert entries["axioma"] == "ɐkˈsjomɐ"
    assert entries["epiblasto"] == "ɛpiˈblaʃtu"
    assert entries["anguífero"] == "ɐ̃ˈɡwifɨɾu"
    text = all_text("pt-BR")
    assert dict(line.split("\t") for line in text.splitlines())["flexão"] == "flekˈsɐ̃w̃"
    found = {}
    for code in o2i_lexicons.available_codes():
        text = all_text(code)
        moved = [w for w, _, ipa in (line.partition("\t") for line in text.splitlines())
                 if lb.onset_stress(ipa, bl.prefix_seam(w)) not in (None, ipa)]
        if moved:
            found[code] = moved
    assert found == {}


def notes(code, kind):
    return FILES[kind][1](code)["citations" if kind == "exception" else "gaps"]


def test_no_en_gb_entry_is_rhotic():
    # The en-GB spec models Received Pronunciation, which has no r-coloured
    # vowel (Roach 2004, JIPA 34(2), p. 243) and /r/ before a vowel only
    # (p. 244).
    import re
    vowels = "iyɨʉɯuɪʏʊeøɘɵɤoəɛœɜɞʌɔæɐaɶɑɒ"
    rhotic = re.compile(f"[ɚɝ˞ʴ]|[ɹɻrɾ][\u0300-\u036fː]*(?![{vowels}])")
    entries = {**file_entries("en-GB", "exception"), **file_entries("en-GB", "patch")}
    assert {w: ipa for w, ipa in entries.items() if rhotic.search(ipa)} == {}


def test_an_en_gb_entry_is_the_non_rhotic_reading():
    # WikiPron gives cupboard [kʊbəɹd] and [kʌbəd]; the build takes the
    # non-rhotic reading, which Britfone gives (CUPBOARD, k ˈɐ b ə d).
    entries = all_entries("en-GB")
    assert entries["cupboard"] == "kʌbəd"
    # drawer is the box [dɹɔː] and one who draws [ˈdɹɔːə] (en.wiktionary):
    # an entry cannot choose by sense, so the rules keep the word.
    assert "drawer" not in entries


# The expected entry is the Britfone 3.0.1 reading of the word, in WikiPron's
# storage form, or no entry. The dev data had the reading in the comment.
@pytest.mark.parametrize("word, britfone", [
    ("you", "juː"),             # YOU(3), j ˈuː; dev: iː
    ("their", "ðɛə"),           # THEIR, ð ˈɛə; dev: zɛə
    ("goes", "ɡəʊz"),           # GOES, g ˈəʊ z; dev: ɡænz
    ("only", "əʊnli"),          # ONLY, ˈəʊ n l i; dev: ɑːnli
    ("into", "ɪntuː"),          # INTO(2), ɪ n t ˈuː; dev: ɪntiː
    ("ask", "ɑːsk"),            # ASK, ˈɑː s k; dev: ɑːks
    ("this", "ðɪs"),            # THIS(2), ð ˈɪ s; dev: ðəs
    ("nothing", "nʌθɪŋ"),       # NOTHING, n ˈɐ θ ɪ ŋ; dev: nʌtɪŋ
    ("thesis", "θiːsɪs"),       # THESIS, θ ˈiː s ɪ s; dev: θisiz
    ("cathedral", "kəθiːdɹəl"),  # CATHEDRAL, k ə θ ˈiː d ɹ ə l; dev: kətiːdɹəl
    ("heir", "ɛə"),             # HEIR, ˈɛə; dev: ɜː
    ("i'll", "aɪl"),            # I, ˈaɪ; dev: ɑːl
    ("default", "diːfɔːlt"),    # DEFAULT(1), d ˈiː f ɔː l t; dev: diːfɑlt
])
def test_an_en_gb_entry_is_the_britfone_reading_or_none(word, britfone):
    assert all_entries("en-GB").get(word, britfone) == britfone


@pytest.mark.parametrize("word", ["aussie", "jambol", "rere", "guomindang", "zzxjoanw"])
def test_an_en_gb_word_that_britfone_cannot_confirm_has_no_bad_entry(word):
    # Britfone 3.0.1 has no line for these words. The dev data had aussie [s]
    # and jambol [j] (too few phones), rere [ɾiːɾ] (rhotic), guomindang [ɡwɑ]
    # (short [ɑ]), and zzxjoanw [ʃɑ], one of two WikiPron readings with no
    # second source to choose between them.
    assert word not in all_entries("en-GB")


def test_the_en_gb_entries_ship():
    # Not every check above is met by an empty file: these readings ship.
    entries = all_entries("en-GB")
    assert (entries["cathedral"], entries["nothing"], entries["their"], entries["heir"]) == (
        "kəθiːdɹəl", "nʌθɪŋ", "ðɛə", "ɛə")


def test_every_en_gb_entry_has_rp_vowels_only():
    # Roach 2004, JIPA 34(2), p. 243 lists the RP vowels; a short [ɑ] is not one.
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import lexicon_build as lb
    entries = all_entries("en-GB")
    assert {w: ipa for w, ipa in entries.items() if lb.rp_vowel_outside(ipa)} == {}
    assert {w: ipa for w, ipa in entries.items() if lb.truncated(w, ipa)} == {}


@pytest.mark.parametrize("kind", FILES)
def test_each_en_gb_entry_names_its_confirmation(kind):
    meta = FILES[kind][1]("en-GB")
    assert set(meta["confirmation"]) == set(file_entries("en-GB", kind))
    assert set(meta["confirmation"].values()) == {"second_source", "single_reading"}
    assert set(meta["confirmation_basis"]) == {"second_source", "single_reading"}


# The one WikiPron reading of a word that Britfone 3.0.1 has no line for, from
# eng_latn_uk_broad.tsv at commit d282e848: "Fareham\tf ɛ ə ɹ ə m",
# "Keays\tk iː z", "apophthegm\tæ p ə θ ɛ m".
@pytest.mark.parametrize("word, kind, entry", [
    ("fareham", "exception", "fɛəɹəm"),
    ("keays", "exception", "kiːz"),
    ("apophthegm", "patch", "æpəθɛm"),
])
def test_a_single_en_gb_reading_ships_unconfirmed(word, kind, entry):
    assert file_entries("en-GB", kind)[word] == entry
    assert FILES[kind][1]("en-GB")["confirmation"][word] == "single_reading"


def test_the_pronoun_i_is_no_en_gb_exception():
    exceptions = file_entries("en-GB", "exception")
    assert {"i", "i'll", "i'm", "i'd", "i've"}.isdisjoint(exceptions)


EN_GB_CITATION = "Wiktionary via WikiPron (en-GB); the reading agrees with Britfone 3.0.1"
EN_GB_UNCHECKED_CITATION = "Wiktionary via WikiPron (en-GB); not checked against a dictionary"


def test_an_en_gb_exception_is_a_name_or_an_acronym():
    # No spelling rule gives the reading of a name or of an acronym. The
    # citation names where the reading comes from, and whether Britfone
    # confirmed it.
    meta = FILES["exception"][1]("en-GB")
    assert set(meta["reasons"].values()) == {"proper_noun", "acronym"}
    expected = {"second_source": EN_GB_CITATION, "single_reading": EN_GB_UNCHECKED_CITATION}
    assert meta["citations"] == {w: expected[c] for w, c in meta["confirmation"].items()}
    assert set(meta["citations"].values()) == {EN_GB_CITATION, EN_GB_UNCHECKED_CITATION}
    assert meta["reasons"]["aldeburgh"] == "proper_noun"
    assert meta["reasons"]["ascii"] == "acronym"


def test_no_exception_cites_no_source():
    for code in o2i_lexicons.available_codes():
        assert "no source read" not in notes(code, "exception").values(), code


def test_an_unclassified_en_gb_word_is_a_patch():
    # Nothing shows that a rule cannot reach ⟨yacht⟩ /jɒt/, so it waits on
    # an audit of the en-GB spelling rules.
    assert file_entries("en-GB", "patch")["yacht"] == "jɒt"
    assert notes("en-GB", "patch")["yacht"] == "lead: en-GB spelling rules not audited"
    assert set(FILES["patch"][1]("en-GB")["reasons"].values()) == {"unclassified"}


def test_an_en_gb_inflection_names_its_own_gap():
    # moves is an inflection of move, which the WikiPron file holds and the
    # lexicon does not.
    gaps = notes("en-GB", "patch")
    assert file_entries("en-GB", "patch")["moves"] == "muːvz"
    assert "move" not in all_entries("en-GB")
    assert gaps["moves"] == "lead: en-GB inflection morphology"
    assert set(gaps.values()) == {"lead: en-GB inflection morphology",
                                  "lead: en-GB spelling rules not audited"}


def test_each_pt_exception_cites_a_page_or_a_section():
    import re
    for code in ("pt-PT", "pt-BR"):
        uncited = {w: c for w, c in notes(code, "exception").items()
                   if not re.search(r"pp?\. \d|Base [IVX]+", c)}
        assert uncited == {}, code


def test_each_pt_patch_names_its_gap():
    import re
    gap = re.compile(r"orthography2ipa#\d+|rule-leads\.md § |^PT_\w+ misfires|^lead: |^no lead"
                     r"|Cunha & Cintra pp?\. \d|Mateus & d'Andrade 1998 p\. \d")
    for code in ("pt-PT", "pt-BR"):
        assert {w: g for w, g in notes(code, "patch").items() if not gap.search(g)} == {}, code


def test_the_pt_pt_kinds_follow_their_class():
    # The spelling does not show the value of ⟨x⟩ (AO90 Base III), ⟨qu⟩ with
    # [w] (AO90 Base XIV 1.º) or the open initial ⟨o⟩ of orelhado (Mateus &
    # d'Andrade 1998 p. 27). A word-initial ⟨e⟩, the coda ⟨l⟩ and a learned
    # vowel are rule leads.
    exceptions, patches = notes("pt-PT", "exception"), notes("pt-PT", "patch")
    assert exceptions["táxi"] == "AO90 Base III; Ciberdúvidas 4068"
    assert exceptions["cinquenta"] == "AO90 Base XIV 1.º; Cunha & Cintra p. 79"
    assert exceptions["orelhado"] == "Mateus & d'Andrade 1998 p. 27"
    assert patches["eritroide"] == "rule-leads.md § word-initial e"
    assert patches["golpada"] == "rule-leads.md § coda l"
    assert patches["ativo"] == "rule-leads.md § learned words"


def test_the_coda_stop_rule_took_its_patches():
    # orthography2ipa#2218 keeps a full vowel before a stop and a consonant,
    # so the rules read advectar ɐdvɛkˈtaɾ and acatalepsia ɐkɐtɐlɛpˈsiɐ.
    assert pt_pt_entries().keys() & {"advectar", "acatalepsia"} == set()


def test_the_oide_and_dora_rules_took_their_entries():
    # orthography2ipa#2250 gives the open [ɔj] of ⟨-oide⟩ and #2251 the close
    # [o] of ⟨-dora -tora -sora⟩, so the rules read asteroide ɐʃtɨˈɾɔjdɨ,
    # atloide ɐtˈlɔjdɨ, calculadora kaɫkulɐˈdoɾɐ and impressora ĩpɾɨˈsoɾɐ.
    assert pt_pt_entries().keys() & {"asteroide", "atloide", "calculadora",
                                     "impressora"} == set()
    patches = notes("pt-PT", "patch")
    assert {w for w, g in patches.items() if "⟨-oide⟩" in g or "⟨-dora⟩" in g} == set()


def test_a_pt_br_verb_form_is_a_patch():
    # NILC tags melo melar.V:P1s only, a rhizotonic form of the levar model.
    patches = notes("pt-BR", "patch")
    assert patches["melo"].startswith("Cunha & Cintra pp. 429-433")
    assert patches["deram"] == "lead: the stem vowel of a pt-BR preterite or imperfect form"
    assert "foto" in notes("pt-BR", "exception")


# Infopédia gives the open diphthong [ɔj] in each of these ⟨-oide⟩ words, and
# orthography2ipa reads that ending as [ɔj] (PT_SUFFIX_OIDE_OPEN). The stressed
# vowel is no longer what separates the entry from the rules, so the class
# names only the part that still differs: the [ks] of ⟨x⟩, the [w] of ⟨gu⟩,
# or the full initial ⟨e⟩ of a learned word.
@pytest.mark.parametrize("word, cls", [
    ("anguiloide", "⟨qu gu⟩ with [w]"),
    ("axoide", "⟨x⟩ as [ks]"), ("prefixoide", "⟨x⟩ as [ks]"), ("sufixoide", "⟨x⟩ as [ks]"),
    ("epicicloide", "unstressed initial ⟨e⟩"), ("epileptoide", "unstressed initial ⟨e⟩"),
    ("eritroide", "unstressed initial ⟨e⟩"),
])
def test_an_oide_entry_has_no_stressed_vowel_class(word, cls):
    assert "ɔj" in pt_pt_entries()[word]
    assert lexical_classes("pt-PT")[word]["class"] == cls


# AO90 Base I 2.º keeps ⟨k w y⟩ "c) Em siglas, símbolos e mesmo em palavras
# adotadas como unidades de medida de curso internacional: ... kW-kilowatt".
# It names no other loan of the lexicon and gives no reading. In Infopédia a
# doubled consonant letter other than ⟨rr ss cc⟩ is one consonant in each of
# 174 single words, and an initial ⟨s⟩ before a consonant is [s] in 65 of 67.
def test_only_kilowatt_cites_ao90_base_i():
    for code, source in (("pt-PT", "Infopédia"), ("pt-BR", "NILC")):
        for word, citation in notes(code, "exception").items():
            assert "Base I 2.º-3.º" not in citation, (code, word)
    assert notes("pt-PT", "exception")["kilowatt"].startswith("AO90 Base I 2.º c)")


# No source states that the reading of a loan is lexical (docs/kinds.md: "A
# cited source must state that class"), so a loan is a patch. Its gap names the
# English loan spelling, and ⟨tch⟩, ⟨zz⟩ or a final ⟨-ing⟩ where the word has one.
@pytest.mark.parametrize("code, word, mark", [
    ("pt-PT", "antidumping", " (final ⟨-ing⟩)"), ("pt-PT", "freelance", ""),
    ("pt-PT", "jogging", " (final ⟨-ing⟩)"), ("pt-PT", "ketchup", " (⟨tch⟩)"),
    ("pt-PT", "puzzle", " (⟨zz⟩)"), ("pt-PT", "rap", ""), ("pt-PT", "shorts", ""),
    ("pt-PT", "skinhead", ""), ("pt-PT", "timing", " (final ⟨-ing⟩)"),
    ("pt-PT", "windsurf", ""), ("pt-BR", "sexy", "")])
def test_a_loan_is_a_patch_with_the_loan_lead(code, word, mark):
    source = {"pt-PT": "Infopédia", "pt-BR": "NILC"}[code]
    assert word not in notes(code, "exception")
    assert notes(code, "patch")[word] == (
        f"lead: {code} English loan spelling{mark}; {source} gives the reading")


@pytest.mark.parametrize("word, lead", [
    ("lobby", "doubled consonant letter"), ("zapping", "doubled consonant letter"),
    ("snobismo", "initial ⟨s⟩ before a consonant is [s]"),
    ("swing", "initial ⟨s⟩ before a consonant is [s]")])
def test_a_loan_a_rule_could_read_is_a_patch(word, lead):
    assert word not in notes("pt-PT", "exception")
    gap = notes("pt-PT", "patch")[word]
    assert gap.startswith("lead: ") and lead in gap


# Infopédia gives [e] in 93% of the 29 words in ⟨-queta⟩ and 93% of the 28 in
# ⟨-eso⟩, [ɛ] in all 104 longer words in ⟨-eca⟩ and [ɔ] in 96% of the 296 in
# ⟨-ose⟩, so the spelling shows the vowel and a rule could take it. No source
# read states the height of these endings, so each entry is a patch with the
# family as its lead.
@pytest.mark.parametrize("word, ending, value", [
    ("etiqueta", "queta", "e"), ("obeso", "eso", "e"), ("aceso", "eso", "e"),
    ("eca", "eca", "ɛ"), ("ose", "ose", "ɔ"),
])
def test_an_ending_family_entry_is_a_patch_with_its_lead(word, ending, value):
    assert word in file_entries("pt-PT", "patch")
    assert word not in file_entries("pt-PT", "exception")
    assert notes("pt-PT", "patch")[word] == (
        f"lead: ⟨-{ending}⟩ takes [{value}] in at least 90% of the Infopédia words")


# With the feminines of the 18 ⟨-reto⟩ adjectives that have [ɛ], ⟨-reta⟩ has
# [e] in 47 of 64 Infopédia words, under 90%. ⟨gu⟩ + ⟨-eta⟩ has 9 words.
@pytest.mark.parametrize("word", ["preta", "careta", "creta", "malagueta", "fugueta"])
def test_a_reta_or_gueta_entry_stays_an_exception(word):
    assert word not in file_entries("pt-PT", "patch")
    assert notes("pt-PT", "exception")[word] == "Cunha & Cintra p. 40; AO90 Base IX 3.º for ⟨ei oi⟩"


def test_an_eso_word_with_an_initial_e_cites_only_that_part():
    # equeso is in ⟨-eso⟩, so its stressed vowel is a patch part, and only the
    # unstressed initial ⟨e⟩ remains an exception part.
    assert "Cunha & Cintra p. 40" not in notes("pt-PT", "exception")["equeso"]
