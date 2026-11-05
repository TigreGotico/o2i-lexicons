"""The pure steps of a lexicon build: select, classify, group, write.

Nothing here loads a gold file or runs the engine. ``build_lexicon.py`` does
that and passes the results in, so each step can be tested on its own.
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Optional

#: A headword the lexicon can hold: letters, with optional internal apostrophes.
#: A space, a hyphen, a digit or an edge apostrophe makes the source entry a
#: phrase, a compound or a clipping that the engine tokenises differently.
WORD_RE = re.compile(r"^[^\W\d_]+(?:['’][^\W\d_]+)*$")

#: The evidence for each reason class that the build assigns. Every other
#: word is ``unclassified``: the data alone claims no linguistic fact.
REASON_BASIS = {
    "acronym": "The source headword is written in capitals only.",
    "proper_noun": "The source headword starts with a capital letter and is "
                   "not written in capitals only.",
}


@dataclass(frozen=True)
class Candidate:
    """A source word that the rules get wrong."""
    headword: str          # as the source writes it
    word: str              # the lexicon key: NFC, lowercase
    hyp: str               # the engine output, normalised as the board does
    gold: str              # the chosen gold reading, normalised as the board does
    ipa: str               # the chosen gold reading, as the TSV stores it


@dataclass
class Lead:
    """Words that share a spelling pattern and the same error at that pattern.

    A lead is a question for the literature, never a rule.
    """
    pattern: str           # e.g. "ough"
    position: str          # "initial", "final" or "any"
    engine: str            # what the engine wrote at the pattern
    gold: str              # what the gold has there
    words: list[str] = field(default_factory=list)

    @property
    def key(self) -> tuple[str, str, str, str]:
        return (self.pattern, self.position, self.engine, self.gold)


def lexicon_key(headword: str) -> str:
    return unicodedata.normalize("NFC", headword).lower()


#: The tie bars. The board scoring drops them as notation, and a spec may
#: write an affricate without one.
TIE_BARS = "\u0361\u035c"


def storage_ipa(gold: str) -> str:
    """The gold reading without the phone-separating spaces of the source."""
    return unicodedata.normalize("NFC", "".join(gold.split()))


def storage_forms(gold: str) -> list[str]:
    """The storage form of *gold*, then the same form without tie bars."""
    ipa = storage_ipa(gold)
    untied = "".join(c for c in ipa if c not in TIE_BARS)
    return [ipa] if untied == ipa else [ipa, untied]


def reason_for(headword: str) -> str:
    """The reason class that the source spelling itself supports."""
    letters = [c for c in headword if c.isalpha()]
    if len(letters) >= 2 and all(c.isupper() for c in letters):
        return "acronym"
    if headword[:1].isupper():
        return "proper_noun"
    return "unclassified"


def error_chunks(gold: str, hyp: str, align: Callable) -> list[tuple[str, str, float, float]]:
    """The runs of disagreement between *gold* and *hyp*.

    Each run is ``(engine_text, gold_text, start, end)``, where start and end
    are fractions of the length of *gold*. *align* is the character alignment
    of the board harness.
    """
    chunks = []
    pos = 0
    run_gold, run_hyp, run_start = "", "", None
    for g, h in align(gold, hyp) + [("\0", "\0")]:
        if g == h:
            if run_start is not None:
                chunks.append((run_hyp, run_gold, run_start / len(gold),
                               max(pos, run_start + 1) / len(gold)))
                run_gold, run_hyp, run_start = "", "", None
        else:
            if run_start is None:
                run_start = pos
            run_gold += g or ""
            run_hyp += h or ""
        if g and g != "\0":
            pos += 1
    return chunks


def spelling_patterns(word: str, sizes: Iterable[int] = (2, 3, 4)):
    """Yield ``(pattern, position, start, end)`` for the letter n-grams of *word*.

    Each n-gram is yielded with position ``any``, and again as ``initial`` or
    ``final`` at the edges. Start and end are fractions of the word length.
    """
    n = len(word)
    for size in sizes:
        for i in range(n - size + 1):
            gram = word[i:i + size]
            if not gram.isalpha():
                continue
            span = (i / n, (i + size) / n)
            yield gram, "any", *span
            if i == 0:
                yield gram, "initial", *span
            if i + size == n:
                yield gram, "final", *span


def find_leads(candidates: list[Candidate], align: Callable, min_size: int,
               tolerance: float = 0.2, overlap: float = 0.8) -> list[Lead]:
    """Group candidates by spelling pattern and by the error at that pattern.

    An error belongs to a pattern when their relative spans overlap, within
    *tolerance*. A group of at least *min_size* words is a lead. Of several
    leads with the same error whose word sets overlap by *overlap* or more
    (intersection over union), only the most specific pattern is kept: the
    longest one, and an edge position before ``any``.
    """
    groups: dict[tuple, set[str]] = defaultdict(set)
    for cand in candidates:
        chunks = error_chunks(cand.gold, cand.hyp, align)
        for pattern, position, p0, p1 in spelling_patterns(cand.word):
            for engine, gold, c0, c1 in chunks:
                if c0 <= p1 + tolerance and p0 - tolerance <= c1:
                    groups[(pattern, position, engine, gold)].add(cand.word)
    big = {k: v for k, v in groups.items() if len(v) >= min_size}
    # Most specific first: the longest pattern, an edge before "any", then
    # the larger group. A lead is dropped when a kept lead with the same
    # error covers nearly the same words.
    order = sorted(big, key=lambda k: (-len(k[0]), k[1] == "any", -len(big[k]), k))
    kept: dict[tuple[str, str], list[set[str]]] = defaultdict(list)
    leads = []
    for key in order:
        words = big[key]
        same_error = kept[(key[2], key[3])]
        if any(len(words & other) >= overlap * len(words | other) for other in same_error):
            continue
        same_error.append(words)
        leads.append(Lead(*key, words=sorted(words)))
    leads.sort(key=lambda lead: (-len(lead.words), lead.key))
    return leads


def held_out_words(leads: list[Lead]) -> set[str]:
    return {w for lead in leads for w in lead.words}


def write_lexicon(out_dir: Path, source: str, entries: dict[str, str],
                  meta: dict) -> tuple[Path, Path]:
    """Write ``<source>.tsv`` (sorted) and ``<source>.meta.json`` into *out_dir*."""
    out_dir.mkdir(parents=True, exist_ok=True)
    tsv = out_dir / f"{source}.tsv"
    tsv.write_text("".join(f"{w}\t{entries[w]}\n" for w in sorted(entries)),
                   encoding="utf-8")
    meta_file = out_dir / f"{source}.meta.json"
    meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                         encoding="utf-8")
    return tsv, meta_file


#: Infopédia symbol -> the pt-PT spec's symbol for the same sound. Infopédia
#: writes the reduced vowel [ə], the tap [r] and the strong rhotic [ʀ]; the
#: spec writes [ɨ] (with [ə] as its allophone), [ɾ] and [ʁ].
INFOPEDIA_NOTATION = {"ə": "ɨ", "r": "ɾ", "ʀ": "ʁ"}

#: A spelling position where European Portuguese has the strong rhotic: a
#: word-initial ⟨r⟩, ⟨rr⟩, and ⟨r⟩ after ⟨n⟩, ⟨l⟩ or ⟨s⟩.
STRONG_R_RE = re.compile(r"(?<![^\W\d_])r|rr|(?<=[nls])r")


def infopedia_to_spec(reading: str) -> str:
    """An Infopédia reading in the symbols of the pt-PT spec."""
    return "".join(INFOPEDIA_NOTATION.get(c, c) for c in reading)


#: Spellings whose [ɐj] is not the Lisbon diphthong: an unstressed ⟨ai⟩ or
#: ⟨ay⟩, which pt-PT writes [ɐj] too, and ⟨a⟩ before the consonant ⟨j⟩.
PT_PT_AJ_RE = re.compile(r"[aâ][iyj]")

#: The Lisbon [ɐj] as Infopédia writes it: oral, not the nasal [ɐ̃j̃].
LISBON_AJ_RE = re.compile("ɐj(?!\u0303)")


def lisbon_to_pt_pt(word: str, reading: str) -> str:
    """*reading* with the Lisbon [ɐj] in the pt-PT norm [ej].

    Infopédia writes the Lisbon (Estremenho) [ɐj] of ⟨ei⟩, of ⟨e⟩ before
    ⟨x⟩ and of the English [eɪ] of a loanword. The pt-PT spec writes [ej]: the
    pt-PT-x-lisbon notes list "<ei> -> [ɐj]" as a Lisbon delta "where more
    conservative/Northern EP keeps [ej]", and pt-PT gives leite ˈlejtɨ. A word
    spelled with ⟨ai⟩, ⟨ay⟩ or ⟨aj⟩ keeps its reading, because there [ɐj] is
    the unstressed ⟨a⟩ of pt-PT, or a misread ⟨j⟩.
    """
    if PT_PT_AJ_RE.search(lexicon_key(word)):
        return reading
    return LISBON_AJ_RE.sub("ej", reading)


#: The palatal consonants before which Lisbon centralises a stressed ⟨e⟩.
PALATALS = frozenset("ʎɲʃʒ")


def lisbon_prepalatal_vowel(rules: str, reading: str, align: Callable) -> bool:
    """Whether *reading* has the Lisbon [ɐ] where the rules have the pt-PT
    [e] or [ɛ] before a palatal consonant (espelho [ɨʃˈpɐʎu]).

    The pt-PT-x-lisbon notes give this centralisation as a Lisbon delta: "The
    conservative/central (Coimbra-type = pt-PT base) norm keeps [e]/[ɛ] here".
    The pt-PT vowel is lexical [e] or [ɛ], so the reading cannot be mapped.
    """
    pairs = align(reading, rules)
    for i, (g, h) in enumerate(pairs):
        if g == "ɐ" and h in ("e", "ɛ"):
            after = next((p[0] for p in pairs[i + 1:] if p[0] is not None), None)
            if after in PALATALS:
                return True
    return False


def misplaced_stress(ipa: str) -> bool:
    """Whether a stress mark stands between a consonant and the vowel after it.

    A consonant before a vowel is the onset of that vowel's syllable, so the
    mark goes before the consonant: jaˈkuzɐ, not jakˈuzɐ.
    """
    before = None
    for i, ch in enumerate(ipa):
        if ch in "ˈˌ":
            after = ipa[i + 1] if i + 1 < len(ipa) else ""
            if before is not None and before not in VOWELS | GLIDES and after in VOWELS:
                return True
        elif ch == ".":
            before = None
        elif not unicodedata.combining(ch) and ch not in "ːˑ":
            before = ch
    return False


def strong_r_is_ambiguous(word: str, reading: str) -> bool:
    """Whether *reading* writes [r] where the spelling of *word* has the strong
    rhotic, so that its [r] cannot be read as the tap."""
    return len(STRONG_R_RE.findall(word.lower())) > reading.count("ʀ")


def full_form_first(readings: list[str]) -> list[str]:
    """*readings* with the full form of each optional [ə] first.

    Infopédia writes an optional vowel as ``(ə)``, and the dataset gives the
    short form and the full form as two readings, the short one first. The
    spec writes the vowel, so the full form leads its pair. Other readings
    keep their source order.
    """
    groups: dict[str, list[str]] = {}
    for reading in readings:
        groups.setdefault(reading.replace("ə", ""), []).append(reading)
    return [r for group in groups.values()
            for r in sorted(group, key=lambda r: -r.count("ə"))]


#: The vowel letters of the readings, each a syllable nucleus unless a
#: non-syllabic mark follows it.
VOWELS = frozenset("aɐeɛəɨioɔuʊɪæyøœɑɒʌɜɘɯ")
GLIDES = frozenset("jwɥ")
NON_SYLLABIC = "̯"
#: The vowels that European Portuguese deletes ([ɨ], [u]) or turns into a
#: glide ([i], [u]) in unstressed syllables.
REDUCIBLE = frozenset("ɨəiu")
#: Consonants that one Portuguese spelling stands for in different positions
#: share a class: ⟨s x z⟩ read [s z ʃ ʒ] by position, ⟨r⟩ reads the tap or
#: the strong rhotic and its allophones, ⟨l⟩ is [l] or [ɫ], and a stop has a
#: spirant allophone. A consonant outside the map is its own class.
CONSONANT_CLASS = {
    **dict.fromkeys("szʃʒ", "S"), **dict.fromkeys("ɾrʁʀhɦχ", "R"),
    **dict.fromkeys("lɫʎ", "L"), **dict.fromkeys("mnɲŋ", "N"),
    **dict.fromkeys("pbβ", "P"), **dict.fromkeys("tdð", "T"),
    **dict.fromkeys("kɡgɣx", "K"), **dict.fromkeys("fvɸ", "F"),
}
_SKIP = set("ˈˌːˑ.·‿") | set(TIE_BARS)


def segments(ipa: str) -> list[tuple[str, str]]:
    """``(kind, letter)`` per segment of *ipa*: kind ``V`` for a nucleus,
    ``G`` for a glide, ``C`` for a consonant. Stress, length and the other
    combining marks are not segments."""
    out: list[tuple[str, str]] = []
    for ch in unicodedata.normalize("NFD", ipa):
        if ch in _SKIP:
            continue
        if unicodedata.combining(ch):
            if ch == NON_SYLLABIC and out and out[-1][0] == "V":
                out[-1] = ("G", out[-1][1])
            continue
        kind = "V" if ch in VOWELS else "G" if ch in GLIDES else "C"
        out.append((kind, ch))
    return out


def skeleton(segs: list[tuple[str, str]]) -> list[str]:
    """The consonant classes of *segs*, in order."""
    return [CONSONANT_CLASS.get(c, c) for kind, c in segs if kind == "C"]


def edit_distance(a: list[str], b: list[str]) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def onset_class(segs: list[tuple[str, str]]) -> Optional[str]:
    """The class of the first consonant before the first nucleus, if any."""
    for kind, c in segs:
        if kind == "V":
            return None
        if kind == "C":
            return CONSONANT_CLASS.get(c, c)
    return None


def other_reading_reason(rules: str, reading: str) -> Optional[str]:
    """Why *reading* is not a correction of the rules' reading *rules* of the
    same headword, or ``None`` when it can be one.

    A correction changes how the rules read a few graphemes. It keeps the
    word's consonants, its syllables and its end:

    1. The first syllable starts with a consonant of the same class, or both
       start with a vowel. The consonant classes differ by at most one edit
       plus one per four consonants: a misread grapheme costs one edit (a
       substitution, the extra [k] of ⟨x⟩ = [ks], a silent letter), and a
       long word may hold a second one.
    2. The number of nuclei is equal, or differs by one where the longer
       reading has a vowel that deletes or turns into a glide, or where the
       shorter one has more glides.
    3. The reading ends on the same consonant class as the rules' reading,
       and keeps a final coda when the rules' reading has one.
    """
    r_segs, g_segs = segments(rules), segments(reading)
    if onset_class(r_segs) != onset_class(g_segs):
        return "first-syllable onset"
    r_skel, g_skel = skeleton(r_segs), skeleton(g_segs)
    if edit_distance(r_skel, g_skel) > 1 + max(len(r_skel), len(g_skel)) // 4:
        return "consonant skeleton"
    (long_nuclei, long_glides), (short_nuclei, short_glides) = sorted(
        (([c for k, c in s if k == "V"], sum(k == "G" for k, _ in s))
         for s in (r_segs, g_segs)),
        key=lambda pair: -len(pair[0]))
    diff = len(long_nuclei) - len(short_nuclei)
    if diff > 1 or (diff == 1 and short_glides <= long_glides
                    and not REDUCIBLE & set(long_nuclei)):
        return "syllable count"
    if r_skel[-1:] != g_skel[-1:] or (
            r_segs and r_segs[-1][0] == "C" and (not g_segs or g_segs[-1][0] != "C")):
        return "truncated end"
    return None


#: The Universal Dependencies closed-class tags that portuguese_unified writes,
#: and its tag for a contraction (do = de + o).
CLOSED_CLASS_POS = frozenset({"ADP", "CONJ", "CCONJ", "SCONJ", "DET", "PRON", "CONTR"})

#: An interjection spelled as a vowel letter and a silent ⟨h⟩ (ah, eh, oh): the
#: source reads it as the name of the letter.
LETTER_INTERJECTION_RE = re.compile(r"[aeiou]h")


def closed_class_reason(headword: str, closed_words: frozenset[str]) -> Optional[str]:
    """Why *headword* must not take a citation reading, or ``None``.

    A dictionary reads a one-letter headword as the letter name, and a
    function word in its stressed citation form. In a sentence the same
    spelling is an article, a preposition or a clitic with a reduced vowel,
    so the dictionary reading would override the rules in every sentence.
    """
    word = lexicon_key(headword)
    if len(word) == 1:
        return "one letter"
    if LETTER_INTERJECTION_RE.fullmatch(word):
        return "interjection spelled as a letter"
    if word in closed_words:
        return "closed class"
    return None


#: The open orthography2ipa issues on a pt-PT rule, as a fix of the rules'
#: output: issue -> (the spelling the defect needs, the substitutions in order).
OPEN_RULE_BUGS = {
    "pt-PT": {
        # ⟨ã⟩ reads [ã]; the nasal vowel is central [ɐ̃].
        2046: (re.compile("ã"), ((re.compile("ã"), "ɐ̃"),)),
        # A word-internal coda sibilant voices before a voiced consonant, and
        # deletes before /ʒ/ (Cruz-Ferreira 1999: 128).
        2041: (re.compile(r"[sxz](?=[bdgvjmnlr])"),
               ((re.compile(r"ʃ(?=[ˈˌ]?ʒ)"), ""),
                (re.compile(r"ʃ(?=[ˈˌ]?[bdɡgvzmnɲlɫʎɾʁ])"), "ʒ"))),
    },
}


def open_rule_bugs(code: str, headword: str, rules: str, reading: str,
                   same: Callable[[str, str], bool]) -> list[int]:
    """The open issues whose fix makes the rules read *reading*, or ``[]``.

    A residual entry for such a word only hides the open defect: once the
    issue is fixed, the rules are right and the build drops the word.
    """
    spelling = lexicon_key(headword)
    fixed, issues = rules, []
    for issue, (needs, substitutions) in OPEN_RULE_BUGS.get(code, {}).items():
        if not needs.search(spelling):
            continue
        out = fixed
        for pattern, replacement in substitutions:
            out = pattern.sub(replacement, out)
        if out != fixed:
            issues.append(issue)
            fixed = out
    return issues if issues and same(fixed, reading) else []


def stress_on_nucleus(ipa: str) -> str:
    """*ipa* with each primary stress mark just before the vowel it stresses,
    and no secondary stress.

    Sources write the mark in different places for the same stress:
    Infopédia before the syllable (ˈkazɐ), the Portal before the vowel
    (kˈazɐ).
    """
    out, pending = [], False
    for ch in ipa.replace("'", "ˈ"):
        if ch == "ˈ":
            pending = True
        elif ch != "ˌ":
            if pending and ch in VOWELS:
                out.append("ˈ")
                pending = False
            out.append(ch)
    return "".join(out)


def readings_agree(a: str, b: str, form: Callable[[str], str]) -> bool:
    """Whether two readings are the same after *form*. The stress is compared
    only when both readings mark it: WikiPron, for one, writes no stress."""
    fa, fb = stress_on_nucleus(form(a)), stress_on_nucleus(form(b))
    if "ˈ" not in fa or "ˈ" not in fb:
        fa, fb = fa.replace("ˈ", ""), fb.replace("ˈ", "")
    return fa == fb


def corroborating_sources(word: str, reading: str, references: dict[str, dict[str, list[str]]],
                          form: Callable[[str], str]) -> list[str]:
    """The reference sources that give *word* the reading *reading*.

    *references* maps a source name to its readings per lexicon key.
    """
    return [name for name, readings in references.items()
            if any(readings_agree(reading, r, form) for r in readings.get(word, ()))]


#: The sources whose agreement keeps an entry. The Portal Lisbon readings are
#: generator output, a comparison and not a gold, so a Portal agreement is
#: recorded but keeps no entry on its own.
CORROBORATING_SOURCES = frozenset({"wikipron", "wiktionary"})


def single_readings(readings: dict[str, list[str]]) -> dict[str, list[str]]:
    """The words of *readings* that have exactly one distinct reading.

    WikiPron pt comes from the en.wiktionary ``{{pt-IPA}}`` template, which
    lists several variants for many words (cupé: [kupe] and [kupɛ]). A match
    against one of several variants is no evidence for the reading.
    """
    return {word: rs for word, rs in readings.items() if len(set(rs)) == 1}


#: Headwords with two readings by sense, per language: headword -> the senses.
#: A lexicon entry cannot choose by context, so the rules keep the word.
HOMOGRAPHS = {
    "pt-PT": {
        "pola": "the archaic contraction of por + a [pulɐ] and the noun [ˈpɔlɐ] "
                "(pt.wiktionary: Contração (ô), Substantivo 2 (ó))",
    },
}

#: Source readings that a hand check found wrong, per language: headword ->
#: the defect. Each is a candidate for the orthography2ipa corrections overlay.
KNOWN_SOURCE_DEFECTS = {
    "pt-PT": {
        "armazém": "intervocalic ⟨z⟩ is [z], not [ʒ]",
        "cupé": "the acute marks [ɛ], not [e]",
        "deve": "the final [ɨ] is dropped",
        "bajulação": "⟨j⟩ is [ʒ], not the glide [j]",
        "bombardeiro": "⟨om⟩ before a consonant is the nasal [õ]",
    },
}


def first_usable(golds: list[str], usable: Callable[[str], Optional[str]]) -> Optional[str]:
    """The first gold reading, in source order, that *usable* accepts.

    *usable* returns the storage form of a reading, or ``None`` to refuse it.
    """
    for gold in golds:
        ipa = usable(gold)
        if ipa is not None:
            return ipa
    return None
