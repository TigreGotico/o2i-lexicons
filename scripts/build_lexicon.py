"""Build the residual lexicon of one language from one gold.

    python scripts/build_lexicon.py en-GB wikipron --cache .cache \\
        --report build-report.json
    python scripts/build_lexicon.py pt-PT infopedia --homographs heterophonic_homographs.csv \\
        --preao preao_words.txt --report build-report.json
    python scripts/build_lexicon.py pt-BR nilc --nilc unitex_sample_transcribed.txt \\
        --michaelis entries.jsonl --homographs heterophonic_homographs.csv \\
        --report build-report.json

The script runs the installed orthography2ipa over every word of the gold. It
keeps a word only when the rules get it wrong under the board's own scoring:
the PER against every gold reading of the word is above zero, after the
board's broad, stress-free normalisation. The entry is the first gold reading,
in the order the loader of the source gives, that is IPA-only and inside the
spec's phoneme inventory.

Words that share a spelling pattern and the same error at it form a lead. A
lead is a question for the linguistic literature, not a rule. Its words stay
out of the lexicon until a cited source settles the pattern, and the build
report lists every lead.

A source can screen the words that pass the leads (``screen_infopedia``).
An Infopédia entry must pass four tests, in this order:

1. It reads the same headword as the rules: the same first onset, nearly the
   same consonants, the same number of syllables up to one deleted vowel or
   formed glide, and the same end (``lexicon_build.other_reading_reason``).
2. It is not a closed-class word or a one-letter headword, whose dictionary
   reading is a citation form or a letter name
   (``lexicon_build.closed_class_reason``).
3. It is not a homograph with two readings by sense
   (``lexicon_build.HOMOGRAPHS`` and the bifonia list that ``--homographs``
   names), and it carries no Lisbon-only feature that
   cannot be put in the pt-PT norm (``lexicon_build.lisbon_prepalatal_vowel``).
   The build writes the Lisbon [ɐj] as [ej] before it compares the rules
   (``lexicon_build.lisbon_to_pt_pt``). Its only difference from the rules is
   not an open orthography2ipa rule defect (``lexicon_build.OPEN_RULE_BUGS``),
   and a hand check did not find the reading wrong
   (``lexicon_build.KNOWN_SOURCE_DEFECTS``).
4. A second source gives the same reading: a hand-typed pt.wiktionary
   reading, or WikiPron pt-PT where it gives the word one reading. The Portal
   da Língua Portuguesa Lisbon reading and a row merged from Infopédia and
   pt.wiktionary are recorded, but they keep no entry on their own.

A word that differs from the rules only in a fact that the spelling cannot show
never joins a lead and needs no second source (``infopedia_residual``). The
sources that agree with it are still recorded. An unstressed vowel in a slot of
``lexicon_build.vowel_slots`` is such a fact. The slot of a vowel where AO90
dropped a silent consonant needs ``--preao``, a word list in the spelling before
AO90 (``lexicon_build.ao90_dropped_consonant``).

``--screened`` lists every word that reaches the screen, with the test it
fails, or ``kept`` and the sources that agree with it.

A reading with a stress mark between a consonant and the vowel after it
places the mark inside the onset (jakˈuzɐ for jaˈkuzɐ). The build takes the
next reading of the word, or leaves the word out.

A NILC entry passes the same screen (``screen_nilc``). Its reading is first put
in the pt-BR norm (``lexicon_build.nilc_to_pt_br``). Its second source is a
hand-typed pt.wiktionary Brazil line, Michaelis where the correction is one that
its notation shows, or WikiPron pt-BR where it gives the word one reading. A word
that differs from the rules only in a fact that the spelling cannot show never
joins a lead (``lexicon_build.lexical_class``). ``mine_wiktionary`` adds the words
of Michaelis and pt.wiktionary that the file lacks.

The gold must sit on a tier that can gate a quality decision in
orthography2ipa. A silver set or a competitor's output is refused.
"""
from __future__ import annotations

import argparse
import csv
import functools
import json
import shlex
import sys
from collections import Counter
from pathlib import Path
from typing import Callable, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent))

import orthography2ipa
from orthography2ipa.inventory import phoneme_inventory, tokenize as inventory_tokenize
from orthography2ipa.lexicon import is_ipa_string
from orthography2ipa.version import VERSION_STR

import lexicon_build as lb
import o2i_harness

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from o2i_lexicons.schema import ALLOWED_TIERS, STRESS_MARKS  # noqa: E402

#: The sources of the portuguese_unified gold that are Infopédia rows: an
#: Infopédia entry, and an entry with the same reading in Infopédia and in
#: Wiktionary.
INFOPEDIA_SOURCES = {"infopedia", "infopedia+wiktionary"}


#: The portuguese_unified region of the Portal readings that can corroborate
#: a pt-PT entry: the Portal's Lisbon standard.
PORTAL_LISBON = "pt-PT-x-lisboa"

#: The regions of the pt.wiktionary readings that can corroborate a pt-PT
#: entry: European Portuguese, and a reading with no region qualifier.
WIKTIONARY_REGIONS = {"pt-PT", "pt"}


#: The regions of the pt.wiktionary readings that can corroborate a pt-BR entry.
#: A row with no region is not a Brazil line.
WIKTIONARY_BR_REGIONS = {"pt-BR", "pt-BR-x-paulistano", "pt-BR-x-paulista"}

#: The NILC tags of a closed-class word (DELAF), and of a line that spells out
#: an abbreviation or an acronym or lists a prefix.
NILC_CLOSED_TAGS = ("PREP", "CONJ", "DET", "PRO")
NILC_SPELLED_TAGS = ("SIGL", "ABREV", "PFX")

#: The tag of a verb form, and of the noun or adjective a verb form may share a
#: spelling with.
NILC_VERB_TAG = "V"
NILC_NOMINAL_TAGS = ("N", "A")

NILC_URL = ("https://github.com/dash219/aeiouado_g2p/blob/"
            "92055ad7844ad7713bc115db4e6baec071ce7a9b/etc/unitex_sample_transcribed.txt")


def load_wikipron(bench, code: str, inputs: dict[str, Path]):
    return bench.load_wikipron(code, sys.maxsize), []


def load_infopedia(bench, code: str, inputs: dict[str, Path]):
    """The ``(headword, reading)`` pairs of the Infopédia rows of the
    portuguese_unified gold, and the ``(headword, reason, reading)`` rows of
    the readings left out.

    Infopédia transcribes the European Portuguese standard, so only pt-PT
    takes them. A row that the board's corrections overlay lists is left out:
    its reading contradicts a written accent, lacks the stress mark, or
    transcribes another headword. A row with several readings, separated by
    commas, gives each of them in order. Each reading is put in the spec's
    symbols (``lexicon_build.INFOPEDIA_NOTATION``), except one that writes
    [r] where the spelling has the strong rhotic: there [r] is not the tap.
    """
    if code != "pt-PT":
        raise SystemExit(f"Infopédia transcribes European Portuguese; {code} cannot take it")
    region = bench._PT_UNIFIED_REGIONS[code]
    overlay = {(r["word"], r["source"], r["pos"], r["original_reading"])
               for r in bench.read_pt_unified_corrections()
               if r["region"] == region and r["field"] == "ipa_narrow"}
    text = bench._fetch(bench._PT_UNIFIED_URL, "portuguese_pronunciation_lexicon.jsonl")
    readings: dict[str, list[str]] = {}
    excluded: list[tuple[str, str, str]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        source = bench.pt_unified_source(row)
        if row.get("region") != region or source not in INFOPEDIA_SOURCES:
            continue
        word, ipa = row["word"], (row.get("ipa_narrow") or "").strip()
        if not word or not ipa:
            continue
        if (word, source, row.get("pos") or "", row.get("ipa_narrow")) in overlay:
            excluded.append((word, "listed by the board's corrections overlay", ipa))
            continue
        for reading in filter(None, (r.strip() for r in ipa.split(","))):
            if lb.strong_r_is_ambiguous(word, reading):
                excluded.append((word, "[r] where the spelling has the strong rhotic",
                                 reading))
                continue
            readings.setdefault(word, []).append(reading)
    pairs = [(word, lb.infopedia_to_spec(reading)) for word, group in readings.items()
             for reading in lb.full_form_first(group)]
    return pairs, excluded


def infopedia_references(bench, engine, code: str):
    """The closed-class words of the language, and the readings of the
    sources that can corroborate an Infopédia reading, per lexicon key.

    WikiPron corroborates only the words for which it gives one reading. A
    row that is in Infopédia and in pt.wiktionary goes under ``merged``: it
    repeats the Infopédia reading. A closed-class word is one that the spec reads unstressed
    (``stress.cliticless_words``), or that a portuguese_unified row tags with
    a closed-class part of speech (``lexicon_build.CLOSED_CLASS_POS``), or a
    demonstrative (``lexicon_build.PT_DEMONSTRATIVES``).
    """
    region = bench._PT_UNIFIED_REGIONS[code]
    closed = {lb.lexicon_key(w) for w in engine.spec.stress.cliticless_words}
    closed |= lb.PT_DEMONSTRATIVES
    references: dict[str, dict[str, list[str]]] = {
        "wikipron": {}, "wiktionary": {}, "merged": {}, "portal_lisbon": {}}
    text = bench._fetch(bench._PT_UNIFIED_URL, "portuguese_pronunciation_lexicon.jsonl")
    for line in text.splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        word = lb.lexicon_key(row["word"])
        if row.get("pos") in lb.CLOSED_CLASS_POS:
            closed.add(word)
        source, where = bench.pt_unified_source(row), row.get("region")
        readings = [r.strip() for r in (row.get("ipa_narrow") or "").split(",") if r.strip()]
        if source == "infopedia+wiktionary" and where == region:
            readings, name = [lb.infopedia_to_spec(r) for r in readings], "merged"
        elif source == "wiktionary" and where in WIKTIONARY_REGIONS:
            name = "wiktionary"
        elif source == "portal" and where == PORTAL_LISBON:
            name = "portal_lisbon"
        else:
            continue
        references[name].setdefault(word, []).extend(readings)
    wikipron: dict[str, list[str]] = {}
    for word, ipa in bench.load_wikipron(code, sys.maxsize):
        wikipron.setdefault(lb.lexicon_key(word), []).append("".join(ipa.split()))
    references["wikipron"] = lb.single_readings(wikipron)
    return frozenset(closed), references


def screen_infopedia(bench, engine, code: str, kept: list[lb.Candidate],
                     norm: Callable[[str], str], inputs: dict[str, Path],
                     lexical: dict[str, str]):
    """The Infopédia words that pass the four tests of the module docstring,
    and one ``(candidate, rules, stage, reason)`` row per screened word.

    A word of *lexical* needs no second source. The sources that agree with it
    are still recorded.
    """
    if "homographs" not in inputs:
        raise SystemExit("the pt-PT build needs --homographs, the bifonia homograph list")
    closed, references = infopedia_references(bench, engine, code)
    listed_homographs = read_homographs(inputs["homographs"])

    def same(a: str, b: str) -> bool:
        return norm(a) == norm(b)

    def form(ipa: str) -> str:
        return bench.normalize(ipa, strip_stress=False, broad=True)

    defects = lb.KNOWN_SOURCE_DEFECTS.get(code, {})
    homographs = lb.HOMOGRAPHS.get(code, {})
    passed, screened = [], []
    for c in kept:
        rules = engine.transcribe_word(c.headword)
        issues = lb.open_rule_bugs(code, c.headword, rules, c.ipa, same)
        mapped = {name: {c.word: [lb.lisbon_to_pt_pt(c.word, r, rules, bench.align)
                                  for r in by_word.get(c.word, ())]}
                  for name, by_word in references.items()}
        sources = lb.corroborating_sources(c.word, c.ipa, mapped, form)
        for stage, reason in (
                ("same headword", lb.other_reading_reason(rules, c.ipa)),
                ("closed class", lb.closed_class_reason(c.headword, closed)),
                ("homograph", homographs.get(c.word) or (
                    "the homograph list holds the word" if c.word in listed_homographs else None)),
                ("Lisbon-only feature",
                 "[ɐ] before a palatal" if lb.lisbon_prepalatal_vowel(
                     norm(rules), norm(c.ipa), bench.align)
                 else "[ɐj] for a vowel not spelled ⟨e ê ei⟩ or an English [eɪ]"
                 if lb.lisbon_aj_left(c.word, c.ipa) else None),
                ("open rule bug", ", ".join(f"o2i#{n}" for n in issues) or None),
                ("known source defect", defects.get(c.word)),
                ("conflict-removed", None if c.word not in lexical or sources else "; ".join(
                     f"{name} {r}" for name in sorted(lb.CORROBORATING_SOURCES)
                     for r in mapped[name][c.word] if lb.readings_agree(rules, r, form))
                 or None),
                ("uncorroborated", None if c.word in lexical
                 or lb.CORROBORATING_SOURCES & set(sources)
                 else "only " + "+".join(sources) if sources
                 else "no second source agrees")):
            if reason is not None:
                screened.append((c, rules, stage, reason))
                break
        else:
            passed.append(c)
            screened.append((c, rules, "kept", "+".join(sources) or "no second source"))
    return passed, screened


@functools.cache
def pt_pt_headwords(bench) -> frozenset[str]:
    """The lexicon keys of the pt-PT rows of portuguese_unified, the
    infinitives among them."""
    region = bench._PT_UNIFIED_REGIONS["pt-PT"]
    text = bench._fetch(bench._PT_UNIFIED_URL, "portuguese_pronunciation_lexicon.jsonl")
    rows = (json.loads(line) for line in text.splitlines() if line.strip())
    return frozenset(lb.lexicon_key(row["word"]) for row in rows if row.get("region") == region)


@functools.cache
def read_pre_ao90(path: Path) -> frozenset[str]:
    """The lexicon keys of a word list in the spelling before AO90."""
    return frozenset(lb.lexicon_key(line.strip())
                     for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def infopedia_residual(bench, engine, c: lb.Candidate, listed: frozenset[str],
                       inputs: dict[str, Path]):
    """``(class, cited rule)`` of an Infopédia candidate, as ``nilc_residual``.

    The comparison keeps every difference that the board scores. A stressed
    height that a cited rule decides keeps the word a lead: a word that a
    ``PT_LEX`` height rule lists, a written accent, and a rhizotonic form of a
    verb of the first or second conjugation
    (``lexicon_build.rhizotonic_verb_form``).

    The unstressed vowels that the spelling does not show come from the
    engine's lattice (``lexicon_build.vowel_slots``). A vowel where AO90
    dropped a silent consonant needs the pre-AO90 word list that ``--preao``
    names.
    """
    def form(ipa: str) -> str:
        return bench.normalize(ipa, strip_stress=False, broad=True).replace("ˌ", "")

    if "preao" not in inputs:
        raise SystemExit("the pt-PT build needs --preao, a word list in the spelling before AO90")
    pre_ao90, headwords = read_pre_ao90(inputs["preao"]), pt_pt_headwords(bench)

    def learned(word: str, end: int) -> bool:
        return lb.ao90_dropped_consonant(word, end, pre_ao90, headwords)

    rules = engine.transcribe_word(c.headword)
    lattice = [(slot.span[0], slot.span[1], [cand.ipa for cand in slot.candidates])
               for slot in engine.ipa_lattice(c.headword)]
    slots = lb.vowel_slots(c.word, rules, lattice, form, learned)
    found = lb.lexical_class(c.word, rules, c.ipa, form, lb.PT_PT_X_VALUES, slots)
    if found is None or "stressed mid vowel" not in found:
        return found, None
    verb = lb.rhizotonic_verb_form(c.word, pt_pt_headwords(bench))
    return found, (lb.cited_rule_reason(c.word, c.ipa, listed, nasal_closes=False)
                   or (f"a rhizotonic form of {verb}: Cunha & Cintra pp. 429-433 give its vowel"
                       if verb else None))


def infopedia_norm(bench, headword: str, reading: str, rules: str) -> str:
    """An Infopédia reading in the pt-PT norm, given the rules' reading."""
    return lb.lisbon_to_pt_pt(headword, reading, rules, bench.align)


def nilc_tag(entry: str) -> str:
    """The DELAF tag of a ``lemma.TAG:flexion`` entry, without the flexion."""
    return entry.rpartition(".")[2].partition(":")[0]


def read_nilc(path: Path) -> dict[str, dict[str, set[str]]]:
    """word -> NILC reading -> the tags of its lines."""
    words: dict[str, dict[str, set[str]]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        head, _, transcription = line.rpartition(";")
        surface, _, entry = head.partition(",")
        if transcription:
            word = lb.lexicon_key(surface)
            words.setdefault(word, {}).setdefault(lb.nilc_to_ipa(transcription), set()).add(
                nilc_tag(entry))
    return words


def load_nilc(bench, code: str, inputs: dict[str, Path]):
    """The ``(headword, reading)`` pairs of the NILC training file, and the
    ``(headword, reason, reading)`` rows of the readings left out.

    An abbreviation, an acronym and a prefix are spelled out or bound, so they
    are not word readings. Lines repeat per dictionary entry, so each word and
    reading comes once.
    """
    if code != "pt-BR":
        raise SystemExit(f"the NILC build keys its entries to pt-BR; {code} cannot take them")
    pairs, excluded = [], []
    for word, readings in read_nilc(inputs["nilc"]).items():
        for reading, tags in readings.items():
            spelled = [t for t in tags if t.startswith(NILC_SPELLED_TAGS)]
            if spelled:
                excluded.append((word, f"tagged {spelled[0]}", reading))
            else:
                pairs.append((word, reading))
    return pairs, excluded


def read_michaelis(path: Path | None) -> dict[str, list[str]]:
    """The one-word headwords that Michaelis transcribes, and their readings."""
    words: dict[str, list[str]] = {}
    if path is None:
        return words
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        headword, ipa = row.get("headword") or "", row.get("ipa")
        if row.get("status") == "found" and ipa and lb.WORD_RE.match(headword):
            found = words.setdefault(lb.lexicon_key(headword), [])
            if ipa not in found:
                found.append(ipa)
    return words


def nilc_references(bench, code: str, inputs: dict[str, Path]):
    """The sources that can corroborate a NILC reading, per lexicon key.

    WikiPron pt-BR is the output of the en.wiktionary ``{{pt-IPA}}`` template, so
    it corroborates only the words for which it gives one reading. The Aeiouadô
    lexicon is machine-generated and never takes part.
    """
    wiktionary: dict[str, list[str]] = {}
    closed: set[str] = set()
    text = bench._fetch(bench._PT_UNIFIED_URL, "portuguese_pronunciation_lexicon.jsonl")
    for line in text.splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        word = lb.lexicon_key(row["word"])
        if row.get("pos") in lb.CLOSED_CLASS_POS:
            closed.add(word)
        if (bench.pt_unified_source(row) == "wiktionary"
                and row.get("region") in WIKTIONARY_BR_REGIONS):
            wiktionary.setdefault(word, []).extend(
                r.strip() for r in (row.get("ipa_narrow") or "").split(",") if r.strip())
    wikipron: dict[str, list[str]] = {}
    for word, ipa in bench.load_wikipron(code, sys.maxsize):
        wikipron.setdefault(lb.lexicon_key(word), []).append("".join(ipa.split()))
    return closed, {"wikipron": lb.single_readings(wikipron), "wiktionary": wiktionary}


def read_homographs(path: Path | None) -> frozenset[str]:
    """The words of a heterophonic homograph list (bifonia), by lexicon key."""
    if path is None:
        return frozenset()
    with path.open(encoding="utf-8", newline="") as f:
        return frozenset(lb.lexicon_key(row["word"]) for row in csv.DictReader(f))


def nilc_homograph(word: str, tags: set[str], readings: list[str], others: list[str],
                   entry: str, listed: frozenset[str]) -> str | None:
    """Why a lexicon entry cannot stand for every use of the word, or ``None``.

    A verb form and a noun or adjective with one spelling can differ in the
    stressed mid vowel (gosto [ɔ] and [o]). A homograph list can say so, and so
    can two readings of the file or of another source (*others*).
    """
    mid = lb.stressed_vowel(entry) in tuple("eɛoɔ")
    if mid and NILC_VERB_TAG in tags and tags & set(NILC_NOMINAL_TAGS):
        return "a verb form and a noun or adjective share the spelling"
    if mid and word in listed:
        return "the homograph list holds the word"
    for name, found in (("NILC", readings), ("other source", others)):
        if any(not lb.same_stressed_vowel(found[0], r) for r in found[1:]):
            return f"two {name} readings differ in the stress or the stressed vowel"
    return None


def nilc_residual(bench, engine, c: lb.Candidate, listed: frozenset[str],
                  inputs: dict[str, Path]):
    """``(class, cited rule)`` of a candidate. A class names the lexical facts
    that alone separate it from the rules. A cited rule keeps it a lead."""
    rules = engine.transcribe_word(c.headword)
    found = lb.lexical_class(c.word, rules, c.ipa)
    if found is None or "stressed mid vowel" not in found:
        return found, None
    return found, lb.cited_rule_reason(c.word, c.ipa, listed)


def spec_listed_words(engine) -> frozenset[str]:
    """The words that the stressed-height rules of the spec name."""
    return frozenset(lb.lexicon_key(w) for rule in engine.spec.allophone_rules
                     if rule.id.startswith(("PT_LEX_CLOSE", "PT_LEX_OPEN")) for w in rule.word)


def mine_wiktionary(engine, words: Iterable[str], wiktionary: dict[str, list[str]],
                    michaelis: dict[str, list[str]], closed: frozenset[str],
                    homographs: frozenset[str], listed: frozenset[str], norm):
    """The words that Michaelis and a hand-typed pt.wiktionary Brazil line hold
    and the NILC file does not.

    The reading comes from the pt.wiktionary line. Michaelis only corroborates
    it, so the line may differ from the rules only in the height of the stressed
    vowel, and the entry is the rules' reading with that height: an entry in
    the norm by construction. Returns the entries and one
    ``(candidate, rules, stage, reason)`` row per word.
    """
    passed, rows = [], []
    for word in sorted(words):
        rules = engine.transcribe_word(word)
        lines = [lb.wiktionary_to_ipa(r) for r in wiktionary[word]]
        shown = [r for r in lines if lb.michaelis_can_show(rules, r) and lb.same_stress(rules, r)]
        heights = {lb.stressed_vowel(r) for r in shown}
        changed = heights - {lb.stressed_vowel(rules)}
        entry = lb.with_stressed_vowel(rules, min(changed)) if len(heights) == 1 and changed else rules
        c = lb.Candidate(word, word, norm(rules), norm(entry), entry)
        for stage, reason in (
                ("mined: no reading", None if lines else "the pt.wiktionary row has no reading"),
                ("mined: Michaelis cannot show", None if shown else
                 "the line differs from the rules in more than the stressed vowel height"),
                ("mined: two heights", "the lines give two heights" if len(heights) > 1 else None),
                ("mined: rules right", None if changed else "the line has the rules' height"),
                ("mined: closed class", lb.closed_class_reason(word, closed)),
                ("mined: cited rule", lb.cited_rule_reason(word, entry, listed)),
                ("mined: homograph", nilc_homograph(word, set(), lines, michaelis[word], entry,
                                                    homographs)),
                ("mined: uncorroborated", None if lb.michaelis_agrees(rules, entry, michaelis[word])
                 else "Michaelis gives another stressed vowel")):
            if reason is not None:
                rows.append((c, rules, stage, reason))
                break
        else:
            passed.append(c)
            rows.append((c, rules, "mined", "wiktionary+michaelis"))
    return passed, rows


def screen_nilc(bench, engine, code: str, kept: list[lb.Candidate],
                norm: Callable[[str], str], inputs: dict[str, Path],
                lexical: dict[str, str]):
    """The NILC words that pass the tests of the module docstring, and one
    ``(candidate, rules, stage, reason)`` row per screened word."""
    closed, references = nilc_references(bench, code, inputs)
    closed |= {lb.lexicon_key(w) for w in engine.spec.stress.cliticless_words}
    file_rows = read_nilc(inputs["nilc"])
    michaelis = read_michaelis(inputs.get("michaelis"))
    homographs = read_homographs(inputs.get("homographs"))
    defects = lb.KNOWN_SOURCE_DEFECTS.get(code, {})
    wiktionary = references["wiktionary"]

    def form(ipa: str) -> str:
        return lb.pt_br_form(bench.normalize(ipa, strip_stress=False, broad=False))

    passed, screened = [], []
    for c in kept:
        rules = engine.transcribe_word(c.headword)
        rows = file_rows[c.word]
        tags = set().union(*rows.values())
        readings = [lb.nilc_to_pt_br(c.headword, r, rules, bench.align) for r in rows]
        closed_tag = next((t for t in tags if t.startswith(NILC_CLOSED_TAGS)), None)
        sources = lb.corroborating_sources(c.word, c.ipa, references, form)
        if lb.michaelis_agrees(rules, c.ipa, michaelis.get(c.word, ())):
            sources.append("michaelis")
        for stage, reason in (
                ("same headword", lb.other_reading_reason(rules, c.ipa)),
                ("closed class", lb.closed_class_reason(c.headword, frozenset(closed))
                 or (f"tagged {closed_tag}" if closed_tag else None)),
                ("homograph", nilc_homograph(
                    c.word, tags, readings,
                    michaelis.get(c.word, []) + wiktionary.get(c.word, []), c.ipa, homographs)),
                ("known source defect", defects.get(c.word)),
                ("uncorroborated", None if lb.PT_BR_CORROBORATING_SOURCES & set(sources)
                 else "no second source agrees")):
            if reason is not None:
                screened.append((c, rules, stage, reason))
                break
        else:
            passed.append(c)
            screened.append((c, rules, "kept", "+".join(sources)))
    mined, rows = mine_wiktionary(
        engine, (set(michaelis) & set(wiktionary)) - set(file_rows), wiktionary, michaelis,
        frozenset(closed), homographs, spec_listed_words(engine), norm)
    return passed + mined, screened + rows


def nilc_norm(bench, headword: str, reading: str, rules: str) -> str:
    """A NILC reading in the pt-BR norm, given the rules' reading."""
    return lb.nilc_to_pt_br(headword, reading, rules, bench.align)


#: dataset -> (loader, licence of the entries, the board dataset that holds it,
#: the screen of the words that pass the leads or ``None``, the map of a gold
#: reading to the language's norm before the rules are compared or ``None``,
#: the test that takes a lexical word out of the leads or ``None``). The nilc
#: file is BSD 3-Clause. Its entries ship beside pt.wiktionary readings, so the
#: file takes CC BY-SA 4.0 and keeps the BSD notice.
SOURCES = {
    "wikipron": (load_wikipron, "CC-BY-SA-4.0", "wikipron", None, None, None),
    "infopedia": (load_infopedia, "CC-BY-SA-4.0", "portuguese_unified", screen_infopedia,
                  infopedia_norm, infopedia_residual),
    "nilc": (load_nilc, "CC-BY-SA-4.0", "nilc", screen_nilc, nilc_norm, nilc_residual),
}

#: The tier of a gold that no board dataset holds: dataset -> tier.
OFF_BOARD_TIERS = {"nilc": "expert-human"}


def gold_url(bench, dataset: str, code: str) -> str:
    if dataset == "nilc":
        return NILC_URL
    if dataset == "wikipron":
        return bench._WIKIPRON_BASE + bench._WIKIPRON_FILES[code]
    return bench._PT_UNIFIED_URL


#: Words listed per lead in the report; ``--held-out`` lists every word.
LEAD_EXAMPLES = 5


def held_out_rows(leads: list[lb.Lead]) -> list[str]:
    """One ``word<TAB>pattern<TAB>position<TAB>engine<TAB>gold`` row per held-out
    word, naming the largest lead that holds it."""
    first: dict[str, lb.Lead] = {}
    for lead in leads:                      # largest first
        for word in lead.words:
            first.setdefault(word, lead)
    return [f"{w}\t{l.pattern}\t{l.position}\t{l.engine}\t{l.gold}"
            for w, l in sorted(first.items())]


def build(code: str, dataset: str, cache: Path, min_lead: int, out_root: Path,
          command: str, held_out_file: Path | None = None,
          screened_file: Path | None = None, excluded_file: Path | None = None,
          inputs: dict[str, Path] | None = None) -> dict:
    bench = o2i_harness.load_benchmark(cache)
    loader, licence, board_dataset, screen, to_norm, residual = SOURCES[dataset]
    inputs = inputs or {}
    tier = OFF_BOARD_TIERS.get(dataset) or bench.provenance_for(board_dataset, code)
    if tier not in ALLOWED_TIERS or not bench.can_gate_promotion(tier):
        raise SystemExit(f"{dataset}/{code} is on tier {tier!r}, which cannot supply entries")
    pairs, dropped = loader(bench, code, inputs)
    readings_excluded = Counter(reason for _, reason, _ in dropped)

    golds: dict[str, list[str]] = {}
    for headword, gold in pairs:
        golds.setdefault(headword, []).append(gold)
    casings: dict[str, set[str]] = {}
    for headword in golds:
        casings.setdefault(lb.lexicon_key(headword), set()).add(headword)

    engine = orthography2ipa.G2P(code, expose_ambiguous_endings=False)
    spec = engine.spec
    inventory = phoneme_inventory(spec)
    extra = bench._prosody_marks(code)

    def norm(ipa: str) -> str:
        return bench.normalize(ipa, strip_stress=True, broad=True, extra_strip=extra)

    def outside(ipa: str) -> list[str]:
        return lb.outside_inventory(inventory_tokenize(ipa, spec), inventory)

    def usable(gold: str):
        for ipa in lb.storage_forms(gold):
            if is_ipa_string(ipa) and not outside(ipa):
                return ipa
        return None

    def exclude(headword: str, reason: str, detail: str = "") -> None:
        excluded[reason] += 1
        dropped.append((headword, reason, detail))

    excluded = Counter()
    candidates: list[lb.Candidate] = []
    right = 0
    for headword, readings in golds.items():
        word = lb.lexicon_key(headword)
        if not lb.WORD_RE.match(headword):
            exclude(headword, "not a single word")
            continue
        if len(casings[word]) > 1:
            exclude(headword, "two source headwords differ only in case")
            continue
        try:
            rules = engine.transcribe_word(headword)
        except Exception:
            rules = ""
        hyp = norm(rules)
        if not hyp:
            exclude(headword, "the engine gives no output")
            continue
        if to_norm is not None:
            readings = [to_norm(bench, headword, g, rules) for g in readings]
        normed = [norm(g) for g in readings]
        if any(bench.levenshtein(hyp, g) == 0 for g in normed):
            right += 1
            continue
        placed = [g for g in readings if not lb.misplaced_stress(g)]
        if not placed:
            exclude(headword, "every reading has a stress mark inside an onset",
                    ", ".join(readings))
            continue
        ipa = lb.first_usable(placed, usable)
        if ipa is None:
            exclude(headword, "no gold reading is IPA-only and inside the inventory",
                    ", ".join(f"{g} ({' '.join(outside(lb.storage_ipa(g))) or 'not IPA'})"
                              for g in placed))
            continue
        candidates.append(lb.Candidate(headword, word, hyp, norm(ipa), ipa))

    lexical: dict[str, str] = {}
    cited: dict[str, str] = {}
    if residual is not None:
        listed = spec_listed_words(engine)
        for c in candidates:
            found, rule = residual(bench, engine, c, listed, inputs)
            if rule is not None:
                cited[c.word] = rule
            elif found is not None:
                lexical[c.word] = found

    leads = lb.find_leads([c for c in candidates if c.word not in lexical], bench.align, min_lead)
    held = lb.held_out_words(leads)
    kept = [c for c in candidates if c.word not in held]
    screened: list[tuple[lb.Candidate, str, str, str]] = []
    if screen is not None:
        kept, screened = screen(bench, engine, code, kept, norm, inputs, lexical)
    entries = {c.word: c.ipa for c in kept}
    reasons = {c.word: lb.reason_for(c.headword) for c in kept}
    used = set(reasons.values()) - {"unclassified"}
    meta = {
        "code": code,
        "source": dataset,
        "source_url": gold_url(bench, dataset, code),
        "tier": tier,
        "licence": licence,
        "build_command": command,
        "o2i_version": VERSION_STR,
        "stress": "source" if any(m in ipa for ipa in entries.values()
                                  for m in STRESS_MARKS) else "rules",
        "reasons": reasons,
        "reason_basis": {r: lb.REASON_BASIS[r] for r in sorted(used)},
    }
    wiktionary_words = sorted(c.word for c, _, stage, _ in screened if stage == "mined")
    if wiktionary_words:
        meta["wiktionary_readings"] = wiktionary_words
    lexical_entries = {c.word: {"class": lexical[c.word], "second_source": sources}
                       for c, _, stage, sources in screened
                       if stage == "kept" and c.word in lexical}
    if lexical_entries:
        meta["lexical_classes"] = lexical_entries
    tsv, meta_file = lb.write_lexicon(out_root / code, dataset, entries, meta)
    if held_out_file is not None:
        held_out_file.write_text("\n".join(held_out_rows(leads)) + "\n", encoding="utf-8")
    if excluded_file is not None:
        excluded_file.write_text("word\treason\tdetail\n" + "".join(
            f"{word}\t{reason}\t{detail}\n" for word, reason, detail in sorted(dropped)),
            encoding="utf-8")
    if screened_file is not None:
        screened_file.write_text("word\tstage\treason\trules\treading\n" + "".join(
            f"{c.word}\t{stage}\t{why}\t{rules}\t{c.ipa}\n"
            for c, rules, stage, why in sorted(screened, key=lambda d: d[0].word)),
            encoding="utf-8")
    stages: dict[str, Counter] = {}
    for _, _, stage, why in screened:
        stages.setdefault(stage, Counter())[why] += 1
    return {
        "code": code,
        "dataset": dataset,
        "tier": tier,
        "licence": licence,
        "o2i_version": VERSION_STR,
        "harness_sha256": o2i_harness.harness_sha256(cache),
        "gold_rows": len(pairs),
        "gold_readings_excluded": dict(readings_excluded),
        "gold_headwords": len(golds),
        "rules_right": right,
        "excluded": dict(excluded),
        "rules_wrong_candidates": len(candidates),
        "min_lead_size": min_lead,
        "leads": [{"pattern": l.pattern, "position": l.position, "engine": l.engine,
                   "gold": l.gold, "size": len(l.words), "examples": l.words[:LEAD_EXAMPLES]}
                  for l in leads],
        "lexical_words": lexical,
        "cited_rule_words": cited,
        "held_out_words": len(held),
        "screen": {stage: dict(reasons) for stage, reasons in stages.items()},
        "entries": len(entries),
        "entries_per_reason": dict(Counter(reasons.values())),
        "tsv": str(tsv.relative_to(ROOT)) if tsv.is_relative_to(ROOT) else str(tsv),
        "meta": str(meta_file.relative_to(ROOT)) if meta_file.is_relative_to(ROOT) else str(meta_file),
    }


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("code")
    ap.add_argument("dataset", choices=sorted(SOURCES))
    ap.add_argument("--cache", type=Path, default=ROOT / ".cache")
    ap.add_argument("--min-lead", type=int, default=10,
                    help="the smallest group of words that is a lead (default 10)")
    ap.add_argument("--out", type=Path, default=ROOT / "o2i_lexicons" / "data")
    ap.add_argument("--report", type=Path, help="write the build report here")
    ap.add_argument("--held-out", type=Path,
                    help="write each held-out word and its largest lead here")
    ap.add_argument("--excluded", type=Path,
                    help="write each reading and headword the build leaves out, and why, here")
    ap.add_argument("--screened", type=Path,
                    help="write each word that the source's screen tests, and its result, here")
    ap.add_argument("--nilc", type=Path, help="the NILC unitex_sample_transcribed.txt")
    ap.add_argument("--michaelis", type=Path, help="the entries.jsonl of the Michaelis crawl")
    ap.add_argument("--homographs", type=Path, help="the heterophonic_homographs.csv of bifonia")
    ap.add_argument("--preao", type=Path,
                    help="a pt-PT word list in the spelling before AO90, one word per line")
    args = ap.parse_args(argv)
    names = ("nilc", "michaelis", "homographs", "preao")
    files = [arg for name in names if getattr(args, name)
             for arg in (f"--{name}", getattr(args, name).name)]
    command = "python scripts/build_lexicon.py " + shlex.join(
        [args.code, args.dataset, "--min-lead", str(args.min_lead), *files])
    report = build(args.code, args.dataset, args.cache, args.min_lead, args.out, command,
                   args.held_out, args.screened, args.excluded,
                   {name: getattr(args, name) for name in names if getattr(args, name)})
    text = json.dumps(report, ensure_ascii=False, indent=1)
    if args.report:
        args.report.write_text(text + "\n", encoding="utf-8")
    summary = {k: v for k, v in report.items() if k != "leads"}
    summary["leads"] = len(report["leads"])
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
