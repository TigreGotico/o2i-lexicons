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
from difflib import SequenceMatcher
from pathlib import Path
from typing import Callable, Iterable, Optional

from o2i_lexicons.schema import STRESS_MARKS

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


#: The vowel letters of the IPA chart, with the r-coloured vowels.
IPA_VOWELS = frozenset("iyɨʉɯuɪʏʊeøɘɵɤoəɛœɜɞʌɔæɐaɶɑɒᵻᵿɚɝ")

#: The /r/ sounds of a reading, and the marks of an r-coloured vowel.
R_SOUNDS = frozenset("ɹɻr")
R_COLOUR = frozenset("ɚɝ˞ʴ")


def rhotic_segment(reading: str) -> Optional[str]:
    """The first segment of *reading*, a WikiPron reading with one space
    between segments, that a non-rhotic accent does not have, or ``None``.

    Received Pronunciation is non-rhotic. Its vowel inventory has no
    r-coloured vowel (Roach 2004, JIPA 34(2), p. 243), and its /r/ stands
    only before a vowel: the phonemic transcription of p. 244 has north
    [nɔːθ], warm [wɔːm], first [fɜːst], hard [hɑːd], more [mɔː] and stronger
    [strɒŋɡə] before a pause, and [r] before a vowel only (around [əraʊnd],
    stronger of [strɒŋɡr̩ əv]). A syllabic /r/ is one of the syllabic
    sonorants of p. 241, so it follows the same rule. An r-coloured vowel,
    and an /r/ before a consonant or at the end of the word, are rhotic.
    """
    segments = reading.split()
    for i, segment in enumerate(segments):
        if R_COLOUR.intersection(segment):
            return segment
        if segment[0] in R_SOUNDS and (
                i + 1 == len(segments) or segments[i + 1][0] not in IPA_VOWELS):
            return segment
    return None


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


#: The nucleus of a nasal diphthong that Infopédia writes oral: it marks the
#: nasality once, on the glide (trem ˈtɾɐj̃, tensão tẽˈsɐw̃).
INFOPEDIA_ORAL_NASAL_NUCLEUS_RE = re.compile("ɐ(?=[jw]\u0303)")


def infopedia_to_spec(reading: str) -> str:
    """An Infopédia reading in the symbols of the pt-PT spec.

    The spec writes the nasal diphthongs [ɐ̃j̃] and [ɐ̃w̃] with a nasal nucleus
    (Mateus & d'Andrade 2000: ch.4 'The nasal diphthongs'), so an [ɐ] before a
    nasal glide takes the nasal mark too.
    """
    reading = "".join(INFOPEDIA_NOTATION.get(c, c) for c in reading)
    return INFOPEDIA_ORAL_NASAL_NUCLEUS_RE.sub("ɐ\u0303", reading)


#: Spellings whose [ɐj] is not the Lisbon diphthong: an unstressed ⟨ai⟩ or
#: ⟨ay⟩, which pt-PT writes [ɐj] too, and ⟨a⟩ before the consonant ⟨j⟩.
PT_PT_AJ_RE = re.compile(r"[aâ][iyj]")

#: The Lisbon [ɐj] as Infopédia writes it: oral, not the nasal [ɐ̃j̃].
LISBON_AJ_RE = re.compile("ɐj(?!\u0303)")


#: The rules' readings of a vowel spelled ⟨e ê ei ey⟩, and of a vowel spelled ⟨a⟩.
RULES_E = frozenset("eɛɨ")
RULES_A = frozenset("aɐ")


def lisbon_to_pt_pt(word: str, reading: str, rules: str, align: Callable) -> str:
    """*reading* with the Lisbon [ɐj] in the pt-PT norm [ej].

    Infopédia writes the Lisbon (Estremenho) [ɐj] of ⟨ei⟩, of ⟨e⟩ before
    ⟨x⟩ and of the English [eɪ] of a loanword. The pt-PT spec writes [ej]: the
    pt-PT-x-lisbon notes list "<ei> -> [ɐj]" as a Lisbon delta "where more
    conservative/Northern EP keeps [ej]", and pt-PT gives leite ˈlejtɨ.

    The rules' reading *rules* tells which vowel each [ɐj] spells. Where the
    rules read [e], [ɛ] or the reduced [ɨ], the vowel is ⟨e ê ei ey⟩. Where the
    rules read only [a] or [ɐ], with no glide, it is the English [eɪ] spelled
    ⟨a⟩ (basebol). Any other [ɐj] stays (rugby, where it spells ⟨u⟩). A word
    spelled with ⟨ai⟩, ⟨ay⟩ or ⟨aj⟩ keeps its reading, because there [ɐj] is
    the unstressed ⟨a⟩ of pt-PT, or a misread ⟨j⟩.
    """
    if PT_PT_AJ_RE.search(lexicon_key(word)) or not LISBON_AJ_RE.search(reading):
        return reading
    kept = [i for i, ch in enumerate(reading) if ch not in STRESS_MARKS]
    bare = "".join(reading[i] for i in kept)
    aligned: dict[int, Optional[str]] = {}
    k = 0
    for g, h in align(bare, "".join(ch for ch in rules if ch not in STRESS_MARKS)):
        if g is not None:
            aligned[k] = h
            k += 1
    out = list(reading)
    for m in LISBON_AJ_RE.finditer(bare):
        # The alignment may pair the rules' vowel with [ɐ] or with [j], and the
        # other half with a gap or a neighbouring consonant.
        rules_part = {aligned.get(m.start()), aligned.get(m.start() + 1)} & (VOWELS | GLIDES)
        if rules_part & RULES_E or (rules_part and rules_part <= RULES_A):
            out[kept[m.start()]] = "e"
    return "".join(out)


def lisbon_aj_left(word: str, reading: str) -> bool:
    """Whether *reading* keeps a Lisbon [ɐj] that ``lisbon_to_pt_pt`` could not
    put in the pt-PT norm."""
    return not PT_PT_AJ_RE.search(lexicon_key(word)) and bool(LISBON_AJ_RE.search(reading))


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


#: The symbols of the NILC Aeiouadô converter (``_conv2ipa`` of aeiouado_g2p), in
#: the order that it applies them, with the glides and [ã] in the spec's symbols.
NILC_SYMBOLS = (
    ("P", "p"), ("B", "b"), ("T", "t"), ("D", "d"), ("K", "k"), ("G", "ɡ"),
    ("7", "t͡ʃ"), ("8", "d͡ʒ"), ("M", "m"), ("Ñ", "ɲ"), ("N", "n"), ("F", "f"),
    ("V", "v"), ("S", "s"), ("Z", "z"), ("X", "ʃ"), ("J", "ʒ"), ("Ĺ", "ʎ"),
    ("L", "l"), ("Ŕ", "ɾ"), ("H", "ʁ"), ("R", "ʁ"), ("Q", "ks"), ("Ŵ", "w̃"),
    ("W", "w"), ("Ỹ", "j̃"), ("Y", "j"), ("Á", "a"), ("6", "ə"), ("É", "ɛ"),
    ("Ê", "e"), ("Ý", "i"), ("Í", "i"), ("I", "i"), ("Ó", "ɔ"), ("Ô", "o"),
    ("Ú", "u"), ("U", "u"), ("Ã", "ɐ̃"), ("Ẽ", "ẽ"), ("Ĩ", "ĩ"), ("Õ", "õ"),
    ("Ũ", "ũ"),
)


def nilc_to_ipa(transcription: str) -> str:
    """A NILC transcription in the symbols of the pt-BR spec, with ``.`` between
    syllables and ``ˈ`` before the stressed one.

    The file's final [ɪ ʊ] are the spec's [i u]. Its [x] and [ɣ] are one
    posterior rhotic, which the spec writes [ʁ], in the onset and in the coda.
    """
    text = unicodedata.normalize("NFC", transcription)
    for symbol, ipa in NILC_SYMBOLS:
        text = text.replace(symbol, ipa)
    return text.replace("-@", "ˈ").replace("@", "ˈ").replace("-", ".")


#: A syllable boundary or the end of the reading, after a coda consonant.
_CODA_END = r"(?=[.ˈ]|$)"

#: A stop or a labial fricative that closes a syllable. The pt-BR spec writes an
#: epenthetic [i] after it, and the NILC file leaves it in the coda.
_STOP_CODA_RE = re.compile(rf"(?<=[aɐeɛioɔu\u0303jw])(t͡ʃ|d͡ʒ|[pbkɡfv]){_CODA_END}")

#: A stressed oral vowel and the nasal vowel that pt-BR writes for it before an
#: onset ⟨m n nh⟩. The open vowels stay oral: homem [ˈɔmẽj̃].
_STRESSED_NASAL = {"a": "ɐ̃", "e": "ẽ", "i": "ĩ", "o": "õ", "u": "ũ"}
_STRESSED_BEFORE_NASAL_RE = re.compile(r"(ˈ[^.ˈaeiou]*)([aeiou])(\.)(?=[mnɲ])")

#: Unstressed vowels of the file and the vowel the spec writes for them. pt-BR
#: writes pretonic [e o] with no harmony raising, and no open vowel outside the
#: stress.
_UNSTRESSED_FOLD = {("i", "e"), ("u", "o"), ("ɛ", "e"), ("ɔ", "o")}

#: Nasal vowels of the file before an onset nasal. pt-BR keeps an unstressed
#: vowel oral there.
_UNSTRESSED_NASAL_FOLD = {("õ", "o"), ("ẽ", "e"), ("ĩ", "i"), ("ũ", "u")}

_NASAL_ONSETS = frozenset("mnɲ")
_READING_VOWELS = frozenset("aɐeɛioɔu")


def _fold_to_rules(reading: str, rules: str, align: Callable) -> str:
    """*reading* with the allophones that the spec does not write in the
    segment that the rules read at that place.

    The file's word-internal coda rhotic is a fricative, and the spec's is the
    tap. An unstressed vowel of ``_UNSTRESSED_FOLD`` takes the rules' vowel, and so does a nasal
    vowel of ``_UNSTRESSED_NASAL_FOLD`` before an onset nasal.
    """
    letters, stressed_at, stressed = [], [], False
    for i, ch in enumerate(reading):
        if ch == "ˈ":
            stressed = True
        elif ch == ".":
            stressed = False
        else:
            letters.append(i)
            stressed_at.append(stressed)
    bare = "".join(reading[i] for i in letters)
    out = list(reading)
    k = 0
    for g, h in align(bare, "".join(c for c in rules if c not in STRESS_MARKS)):
        if g is None:
            continue
        after = bare[k + 1] if k + 1 < len(bare) else ""
        coda = after not in _READING_VOWELS
        coda_tap = g == "ʁ" and coda and h == "ɾ"
        unstressed = not stressed_at[k] and ((g, h) in _UNSTRESSED_FOLD or (
            (g, h) in _UNSTRESSED_NASAL_FOLD and after in _NASAL_ONSETS))
        if coda_tap or unstressed:
            out[letters[k]] = h
        k += 1
    return "".join(out)


def nilc_to_pt_br(word: str, reading: str, rules: str, align: Callable) -> str:
    """A NILC reading (``nilc_to_ipa``) in the norm of the pt-BR spec.

    The file transcribes São Paulo city speech. Each step writes one of its
    choices as the spec does (``docs/languages/pt-BR.md`` of orthography2ipa):

    - A word-initial pretonic ⟨es⟩ before a coda sibilant is [is], and ⟨en em⟩
      is [ĩ], where the file has [es ẽ] (``BR_INITIAL_ES_RAISE``,
      ``BR_INITIAL_EN_RAISE``).
    - A stop that closes a syllable takes the epenthetic [i], where the file
      keeps it in the coda: advogado [ad͡ʒivoˈɡadu].
    - A coda sibilant stays alveolar before [t͡ʃ d͡ʒ], where the file has
      [ʃt͡ʃ ʒd͡ʒ].
    - A stressed vowel before an onset nasal is nasal (``BR_NASAL_STRESSED_*``).
    - The file's [ə] is [ɐ] at the end of a word and [a] elsewhere.
    - A word-final sibilant is [s], where the file has [z] for ⟨z⟩: a citation
      form stands before a pause.
    - A word-final rhotic is [ɾ] where the rules keep it, and goes where the
      rules drop a final ⟨r⟩, as they do in an infinitive.
    - The word-internal coda rhotic and the unstressed vowels follow
      ``_fold_to_rules``.

    The result has no syllable marks.
    """
    spelling = lexicon_key(word)
    if spelling.startswith("es"):
        reading = re.sub(rf"^e(?=[szʃʒ]{_CODA_END})", "i", reading)
    if re.match("e[nm]", spelling):
        reading = re.sub(rf"^ẽ{_CODA_END}", "ĩ", reading)
    reading = re.sub(r"ʃ(?=[.ˈ]?t͡ʃ)", "s", reading)
    reading = re.sub(r"ʒ(?=[.ˈ]?d͡ʒ)", "z", reading)
    reading = _STOP_CODA_RE.sub(r"\1i", reading)
    reading = _STRESSED_BEFORE_NASAL_RE.sub(
        lambda m: m[1] + _STRESSED_NASAL[m[2]] + m[3], reading)
    reading = re.sub(r"ə(?=s?$)", "ɐ", reading).replace("ə", "a")
    reading = re.sub(r"z$", "s", reading)
    if reading.endswith("ʁ"):
        reading = reading[:-1] + ("ɾ" if rules.endswith("ɾ") else "")
    reading = _fold_to_rules(reading, rules, align)
    return unicodedata.normalize("NFC", reading.replace(".", ""))


#: The notation that differs between the Brazilian sources and carries no
#: lexical fact: the unstressed [a ɐ] of a broad transcription, the near-close
#: vowels, and every posterior rhotic.
_BR_FOLD = {"ɐ": "a", "ə": "a", "ɪ": "i", "ʊ": "u", "x": "ʁ", "ɣ": "ʁ", "h": "ʁ",
            "ɦ": "ʁ", "χ": "ʁ", "r": "ʁ", "y": "j"}
_BR_CODA_TAP_RE = re.compile(r"ɾ(?=[^aeiouɛɔ\u0303ˈ.]|$)")


def pt_br_form(ipa: str) -> str:
    """*ipa* for a comparison between Brazilian sources, with the stress kept.

    The sources write the coda rhotic by accent, so a coda tap counts as the
    rhotic. A nasal glide counts as a glide, because the nasal vowel before it
    already shows the nasality.
    """
    text = unicodedata.normalize("NFD", ipa.replace("'", "ˈ"))
    text = "".join(_BR_FOLD.get(c, c) for c in text if c not in TIE_BARS and c != ".")
    text = _BR_CODA_TAP_RE.sub("ʁ", text)
    return unicodedata.normalize("NFC", text.replace("j\u0303", "j").replace("w\u0303", "w"))


#: The vowels whose quality Michaelis shows and the letter they fold to when a
#: comparison asks what else differs.
MID_VOWEL_FOLD = {"ɛ": "e", "ɔ": "o"}


#: One letter per vowel notation of the Brazilian sources, with the height kept.
_VOWEL_NOTATION = {"ɐ": "a", "ə": "a", "ʌ": "a", "ɪ": "i", "ʊ": "u", "ɨ": "i"}


def stressed_vowel(ipa: str) -> Optional[str]:
    """The letter of the stressed vowel of *ipa*, without nasality, or ``None``."""
    marked = False
    for ch in unicodedata.normalize("NFD", ipa):
        if ch == "ˈ":
            marked = True
        elif marked and ch in VOWELS:
            return _VOWEL_NOTATION.get(ch, ch)
    return None


def _sounds(ipa: str) -> tuple[list[str], Optional[int]]:
    """The sounds of *ipa*, and the index of its stressed vowel or ``None``.

    Combining marks drop, a tie bar keeps an affricate as one sound, and vowel
    height folds, because this comparison asks where the stress falls.
    """
    out: list[str] = []
    stressed, marked, tied = None, False, False
    for ch in unicodedata.normalize("NFD", ipa):
        if ch == "ˈ":
            marked = True
        elif ch in TIE_BARS:
            tied = True
        elif not unicodedata.combining(ch) and ch != ".":
            if tied:
                out[-1] += ch
                tied = False
                continue
            letter = _VOWEL_NOTATION.get(ch, ch)
            out.append(MID_VOWEL_FOLD.get(letter, letter))
            if marked and ch in VOWELS:
                stressed, marked = len(out) - 1, False
    return out, stressed


def _pair_cost(a: str, b: str) -> float:
    """A vowel pairs with a vowel or a glide, and a consonant with a consonant.
    A vowel against a consonant costs more than two gaps, so it never pairs."""
    if a == b:
        return 0.0
    vocalic = VOWELS | GLIDES
    return 0.5 if (a in vocalic) == (b in vocalic) else 3.0


def _alignment_cost(a: list[str], b: list[str]) -> float:
    row = [float(j) for j in range(len(b) + 1)]
    for i, x in enumerate(a, 1):
        last, row[0] = row[0], float(i)
        for j, y in enumerate(b, 1):
            last, row[j] = row[j], min(row[j] + 1, row[j - 1] + 1, last + _pair_cost(x, y))
    return row[-1]


def same_stress(left: str, right: str) -> bool:
    """Whether two readings put the stress on the same vowel of the word.

    The sources differ in notation after the stress: a glide against a hiatus
    (vácuo [ˈvakwu], [ˈvakuu]), an epenthetic [i] (pacto [ˈpaktu], [ˈpakitu]), a
    dropped infinitive ⟨r⟩. A count of nuclei reads each of those as a stress
    difference. So the readings are aligned sound by sound, and the stress
    agrees when a cheapest alignment pairs the two stressed vowels.
    """
    a, i = _sounds(left)
    b, j = _sounds(right)
    if i is None or j is None:
        return False
    through = (_alignment_cost(a[:i], b[:j]) + _pair_cost(a[i], b[j])
               + _alignment_cost(a[i + 1:], b[j + 1:]))
    return through <= _alignment_cost(a, b)


def same_stressed_vowel(left: str, right: str) -> bool:
    """Whether two readings stress the same vowel, and with the same height."""
    return same_stress(left, right) and stressed_vowel(left) == stressed_vowel(right)


def _plain(ipa: str) -> str:
    return pt_br_form(ipa).replace("ˈ", "")


def michaelis_can_show(rules: str, entry: str) -> bool:
    """Whether *entry* differs from *rules* only in the stress or the quality of
    a mid vowel, the two features of the Michaelis notation."""
    def bare(ipa: str) -> str:
        return "".join(MID_VOWEL_FOLD.get(c, c) for c in _plain(ipa))
    return bare(rules) == bare(entry)


def michaelis_agrees(rules: str, entry: str, readings: Iterable[str]) -> bool:
    """Whether a Michaelis reading stresses the vowel that *entry* stresses, with
    the same height, for an entry whose correction Michaelis can show."""
    return michaelis_can_show(rules, entry) and any(
        same_stressed_vowel(entry, r) for r in readings)


#: A ⟨qu gu⟩ before ⟨e i⟩, where the spelling cannot show whether [w] follows.
_QU_GU_RE = re.compile(r"[qg][uü][eiéíêî]")

#: An ⟨x⟩ before a vowel letter or at the end of the word. Before a consonant
#: ⟨x⟩ is a coda sibilant, which a rule reads.
_X_BEFORE_VOWEL_RE = re.compile(r"x(?=[aeiouáéíóúâêôãõày]|$)")

#: The ``(rules, entry)`` pairs of ⟨x⟩ values that are lexical. In pt-BR it is
#: [ks] where the rules read [ʃ] (táxi, fixo). In pt-PT any of the four values
#: [ʃ ks z s] can stand for the other (xadrez, táxi, exame, próximo).
PT_BR_X_VALUES = frozenset({("ʃ", "ks")})
PT_PT_X_VALUES = frozenset((a, b) for a in ("ʃ", "ks", "z", "s")
                           for b in ("ʃ", "ks", "z", "s") if a != b)


def _fold_stressed_mid_vowel(ipa: str) -> str:
    """*ipa* with the height of its stressed mid vowel folded, and no stress mark."""
    out, marked = [], False
    for ch in unicodedata.normalize("NFD", ipa):
        if ch == "ˈ":
            marked = True
            continue
        if marked and ch in VOWELS:
            ch, marked = MID_VOWEL_FOLD.get(ch, ch), False
        out.append(ch)
    return unicodedata.normalize("NFC", "".join(out))


@dataclass(frozen=True)
class VowelSlot:
    """An unstressed vowel of the rules' reading whose value the spelling does
    not show. *start* and *end* index the reading without stress marks, in the
    notation of the comparison. *values* holds the other readings of the vowel
    that the slot admits."""
    start: int
    end: int
    name: str
    values: frozenset[str]


#: The vowel letters of a spelling. Every other letter is a consonant letter.
VOWEL_LETTERS = frozenset("aeiouyáéíóúâêôãõàü")

#: The readings of an unstressed word-initial ⟨o⟩ and ⟨e⟩, as the pt-PT rules
#: rank them (orthography2ipa#2204, #2206, #2208).
INITIAL_VOWEL_VALUES = {"o": frozenset("ɔou"), "e": frozenset("ieɛ")}

#: The full and the reduced readings of an unstressed ⟨a e o⟩.
VOWEL_LETTER_VALUES = {"a": frozenset("aɐ"), "e": frozenset("ɛeɨ"), "o": frozenset("oɔu")}

#: The stop letters, and the letters after a stop that make an onset cluster
#: or a digraph with it.
STOP_LETTERS = frozenset("pbtdcgk")
_ONSET_AFTER_STOP = frozenset("lrh")

#: The letters that AO90 removed after a vowel, and the letters before which
#: it removed them (acção ação, adopção adoção, actor ator).
AO90_SILENT_LETTERS = "cp"
_AO90_NEXT_RE = re.compile(r"[tç]|c(?=[ei])")


def _consonant_letter(ch: str) -> bool:
    return ch.isalpha() and ch not in VOWEL_LETTERS


def ao90_dropped_consonant(word: str, end: int, pre_ao90: frozenset[str],
                           headwords: frozenset[str]) -> bool:
    """Whether AO90 dropped a silent ⟨c p⟩ at *end* of *word*.

    The pre-AO90 spelling with the letter put back must be in *pre_ao90*, and
    it must not be a headword of the source: a headword spells a spoken
    consonant (pacto beside pato, facto beside fato). *word* itself must not
    be in *pre_ao90*, where it is a word of its own and not a new spelling.
    """
    if word in pre_ao90 or not _AO90_NEXT_RE.match(word, end):
        return False
    return any(form in pre_ao90 and form not in headwords
               for form in (word[:end] + letter + word[end:] for letter in AO90_SILENT_LETTERS))


def vowel_slot_name(word: str, start: int, end: int,
                    learned: Callable[[str, int], bool]) -> Optional[str]:
    """The class of the unstressed vowel spelled ``word[start:end]``, or ``None``.

    - An initial ⟨o e⟩, or one after an initial ⟨h⟩, before a consonant letter:
      the rules rank its readings, and the word decides (orelha [o], horror [u],
      erguer [e]).
    - An ⟨a e o⟩ before a coda ⟨l⟩: the rules give the full vowel (Cunha &
      Cintra p. 53), and some words keep [ɐ ɨ u ɔ] (golpear [ɔ], polvorosa [u]).
    - An ⟨a e o⟩ before a stop that closes the syllable (pacto, infetar): no
      source gives the vowel.
    - An ⟨a e o⟩ where AO90 dropped a silent ⟨c p⟩ (*learned*): Cunha & Cintra
      p. 53 keep the vowel of a learned word unreduced (ator [a], direção [ɛ],
      adoção [ɔ]), and no letter shows it now.
    """
    letter = word[start:end]
    after, second = word[end:end + 1], word[end + 1:end + 2]
    if letter in INITIAL_VOWEL_VALUES and word[:start] in ("", "h") and _consonant_letter(after):
        return f"unstressed initial ⟨{letter}⟩"
    if letter not in VOWEL_LETTER_VALUES:
        return None
    if after == "l" and (not second or (_consonant_letter(second) and second != "h")):
        return "unstressed vowel before a coda ⟨l⟩"
    if after in STOP_LETTERS and _consonant_letter(second) and second not in _ONSET_AFTER_STOP:
        return "unstressed vowel before a coda stop"
    if learned(word, end):
        return "unreduced learned vowel"
    return None


def _stressed_index(marked: str) -> Optional[int]:
    """The index of the stressed vowel of *marked* once its stress marks are
    gone, or ``None`` when it marks no stress."""
    text = marked.replace("ˌ", "")
    mark = text.find("ˈ")
    if mark < 0:
        return None
    rest = text[mark + 1:]
    at = next((i for i, ch in enumerate(rest)
               if unicodedata.normalize("NFD", ch)[0] in VOWELS), None)
    return None if at is None else mark + at


def vowel_slots(word: str, rules: str, lattice: list[tuple[int, int, list[str]]],
                form: Callable[[str], str],
                learned: Callable[[str, int], bool]) -> list[VowelSlot]:
    """The unstressed vowel slots of the rules' reading *rules* of *word*.

    *lattice* holds ``(start, end, readings)`` per grapheme of the engine's
    lattice: the span of the grapheme in *word* and its readings in rank
    order, the rules' reading first. A slot admits only the readings of its
    vowel letter that the lattice also ranks there. When the first readings
    do not spell *rules*, the graphemes cannot be placed, and there is no slot.
    """
    marked = form(rules)
    stressed = _stressed_index(marked)
    bare = unicodedata.normalize("NFC", marked.replace("ˈ", "").replace("ˌ", ""))
    # A grapheme can read as a lone combining mark (the nasal tilde of ⟨in⟩),
    # so each span is measured on the composed text up to its grapheme.
    pieces, text, at = [], "", 0
    for start, end, readings in lattice:
        readings = [form(r) for r in readings]
        text += readings[0] if readings else ""
        end_at = len(unicodedata.normalize("NFC", text))
        pieces.append((start, end, readings, (at, end_at)))
        at = end_at
    if stressed is None or unicodedata.normalize("NFC", text) != bare:
        return []
    slots = []
    for start, end, readings, span in pieces:
        top = readings[0] if readings else ""
        if len(top) != 1 or bare[span[0]:span[1]] != top or span[0] == stressed:
            continue
        name = vowel_slot_name(word, start, end, learned)
        if name is None:
            continue
        letter = word[start:end]
        allowed = (INITIAL_VOWEL_VALUES[letter] if name.startswith("unstressed initial")
                   else VOWEL_LETTER_VALUES[letter])
        if top in allowed:
            slots.append(VowelSlot(*span, name, frozenset(readings[1:]) & allowed - {top}))
    return slots


def lexical_class(word: str, rules: str, entry: str,
                  form: Callable[[str], str] = pt_br_form,
                  x_values: frozenset[tuple[str, str]] = PT_BR_X_VALUES,
                  slots: Iterable[VowelSlot] = ()) -> Optional[str]:
    """The classes of lexical fact that alone separate *entry* from *rules*, or
    ``None`` when anything else differs.

    The spelling does not show the height of a stressed mid vowel (o2i#1824),
    the value of an ⟨x⟩ before a vowel (táxi, fixo), or whether ⟨qu gu⟩ before
    ⟨e i⟩ has [w] (frequente). So a word that differs in these only is a
    residual word and not a rule lead. *form* puts a reading in the notation
    of the comparison, with the stress mark kept, and *x_values* holds the
    ``(rules, entry)`` pairs of ⟨x⟩ values that the language reads by word.
    Each changed ⟨x⟩ value needs its own ⟨x⟩ in the spelling.

    *slots* are the unstressed vowels of *rules* whose value is lexical
    (``vowel_slots``). A change of one such vowel to a value its slot admits
    is the class of the slot. A reading with two primary stress marks
    (ˈlũpɛktuˈmiɐ) shows no single stressed vowel, so it has no class.
    """
    def plain(ipa: str) -> str:
        return form(ipa).replace("ˈ", "")

    def bare(ipa: str) -> tuple[str, list[int]]:
        """The compared text, and the index of each of its letters in the
        reading without stress marks."""
        text = _fold_stressed_mid_vowel(form(ipa))
        kept = list(range(len(text)))
        if _QU_GU_RE.search(word):
            kept = [i for i in kept if not (text[i] == "w" and i and text[i - 1] in "kɡ")]
        return "".join(text[i] for i in kept), kept

    def slot_class(i1: int, i2: int, j1: int, j2: int) -> Optional[str]:
        if i2 - i1 != 1 or j2 - j1 != 1:
            return None
        at = where[i1]
        return next((s.name for s in slots if s.start <= at < s.end and b[j1] in s.values), None)

    if form(entry).count("ˈ") > 1 or not same_stress(rules, entry):
        return None
    (a, where), (b, _) = bare(rules), bare(entry)
    slots = list(slots)
    changes, slotted = [], set()
    for op, i1, i2, j1, j2 in SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        name = slot_class(i1, i2, j1, j2) if op == "replace" else None
        if name is None:
            changes.append((a[i1:i2], b[j1:j2]))
        else:
            slotted.add(name)
    if (any(change not in x_values for change in changes)
            or len(changes) > len(_X_BEFORE_VOWEL_RE.findall(word))):
        return None
    classes = []
    if stressed_vowel(rules) != stressed_vowel(entry):
        classes.append("stressed mid vowel")
    classes += sorted({f"⟨x⟩ as [{value}]" for _, value in changes})
    if re.findall("[kɡ]w", plain(entry)) != re.findall("[kɡ]w", plain(rules)):
        classes.append("⟨qu gu⟩ with [w]")
    classes += sorted(slotted)
    return "+".join(classes) or None


def cited_rule_reason(word: str, entry: str, listed: frozenset[str],
                      nasal_closes: bool = True) -> Optional[str]:
    """The cited rule that decides the height of the stressed vowel of *word*,
    or ``None``. *listed* holds the words of the height rules ``PT_LEX_CLOSE_*``
    and ``PT_LEX_OPEN_*``. *nasal_closes* is true for pt-BR, where
    ``BR_NASAL_STRESSED`` closes a stressed vowel before a nasal. pt-PT has no
    such rule (fome [ˈfɔmɨ]).

    A word under such a rule stays a lead: the spec settles it, so a source
    that disagrees is a question for the spec and not an entry.
    """
    if lexicon_key(word) in listed:
        return "a PT_LEX height rule lists the word"
    if re.search("[éêóô]", word):
        return "a written accent gives the height"
    if nasal_closes and re.search("[ɛɔ](?:[mnɲ]|\u0303)", unicodedata.normalize("NFD", entry)):
        return "BR_NASAL_STRESSED closes a vowel before a nasal"
    return None


#: The rhizotonic present forms of the first and second conjugations: the
#: infinitive ending, and the endings of the present indicative and subjunctive
#: whose stress falls on the stem.
RHIZOTONIC_ENDINGS = (
    ("ar", ("as", "am", "es", "em", "o", "a", "e")),    # levo, leve
    ("er", ("as", "am", "es", "em", "o", "a", "e")),    # devo, deves, deva
)

#: A stem before the ending and the infinitive stem it is spelled from, per
#: infinitive ending: rogue, toque, comece (rogar, tocar, começar); conheço,
#: proteja (conhecer, proteger).
STEM_SPELLINGS = {
    "ar": (("qu", "c"), ("gu", "g"), ("c", "ç")),
    "er": (("ç", "c"), ("j", "g")),
}

#: The last vowel letters of a stem, and the consonants after them. A stem
#: can end in its vowel: voo, of voar.
_STEM_VOWEL_RE = re.compile(r"([aeiouáéíóúâêôãõ]+)[^aeiouáéíóúâêôãõ]*$")


def rhizotonic_verb_form(word: str, headwords: frozenset[str]) -> Optional[str]:
    """The infinitive of which *word* is a rhizotonic present form, when the
    stressed stem vowel is a single ⟨e⟩ or ⟨o⟩, or ``None``.

    Cunha & Cintra (pp. 429-433) give that vowel for every verb of the first
    and second conjugations. It is open in each rhizotonic form of the models
    levar and lograr (levo [ɛ], logro [ɔ]). In the models dever and mover it is
    close in the first person singular and in the subjunctive (devo, deva) and
    open in the other forms (deves, move). The exceptions are stated by class.
    A noun or an adjective with the same spelling can have the other height
    (rogo, gosto), so a lexicon entry cannot stand for every use of the word.
    *headwords* holds the headwords of the source, the infinitives among them.
    """
    for infinitive, endings in RHIZOTONIC_ENDINGS:
        for ending in endings:
            stem = word[:-len(ending)]
            if not word.endswith(ending) or len(stem) < 2:
                continue
            stems = [stem] + [stem[:-len(spelled)] + base
                              for spelled, base in STEM_SPELLINGS[infinitive]
                              if stem.endswith(spelled)]
            for base in stems:
                vowel = _STEM_VOWEL_RE.search(base)
                if vowel and vowel[1] in ("e", "o") and base + infinitive in headwords:
                    return base + infinitive
    return None


def with_stressed_vowel(rules: str, vowel: str) -> str:
    """*rules* with *vowel* as the letter of its stressed mid vowel."""
    mark = rules.index("ˈ")
    at = next(i for i in range(mark, len(rules)) if rules[i] in VOWELS)
    return rules[:at] + vowel + rules[at + 1:]


def wiktionary_to_ipa(reading: str) -> str:
    """A hand-typed pt.wiktionary reading without its typing variants: the
    apostrophe for the stress mark, the secondary stress, optional sounds in
    brackets, and the letter ⟨g⟩."""
    text = re.sub(r"\([^)]*\)", "", reading).replace("'", "ˈ").replace("ˌ", "")
    return text.replace("g", "ɡ")


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


def _units(ipa: str) -> list[str]:
    """*ipa* cut into units: a letter with its combining and length marks, or a mark."""
    units: list[str] = []
    for ch in ipa:
        if units and (unicodedata.combining(ch) or ch in "ːˑ"):
            units[-1] += ch
        else:
            units.append(ch)
    return units


def _is_nucleus(unit: str) -> bool:
    return unicodedata.normalize("NFD", unit)[0] in VOWELS and NON_SYLLABIC not in unit


#: The obstruent + liquid clusters that Cunha & Cintra (7th ed., p. 64) list
#: as inseparable, in the spec's symbols. Mateus & d'Andrade (1998, D.E.L.T.A.
#: 14(1), pp. 14-15, examples (2)) list the same fourteen as the onset clusters
#: of European Portuguese.
ONSET_CLUSTERS = frozenset({"bl", "bɾ", "kl", "kɾ", "dɾ", "fl", "fɾ", "ɡl", "ɡɾ",
                            "pl", "pɾ", "tl", "tɾ", "vɾ"})

#: The affricates of loanwords, which the spec writes with or without the tie
#: bar. An affricate is one consonant (ketchup kɛˈtʃɐp, hadji aˈdʒi, ɐpˈt͡ʃu).
AFFRICATES = frozenset({"tʃ", "dʒ", "ts", "dz"})


def _plain_unit(unit: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFC", unit) if ch not in TIE_BARS)


def _consonants(units: list[str]) -> list[list[str]]:
    """*units* grouped into consonants: an affricate is one group."""
    groups: list[list[str]] = []
    for unit in units:
        if groups and len(groups[-1]) == 1 and _plain_unit(groups[-1][0] + unit) in AFFRICATES:
            groups[-1].append(unit)
        else:
            groups.append([unit])
    return groups


def _is_glide(unit: str) -> bool:
    return _plain_unit(unit)[:1] in GLIDES


def _onset_size(run: list[str]) -> int:
    """How many units at the end of *run* are the onset of the syllable after it.

    *run* is the sequence between two vowels, with a consonant in it. A glide
    after a consonant goes with the vowel after it, so the onset ends before
    it: anguífero ɐ̃ˈɡwifɨɾu, axioma ɐkˈsjomɐ. The onset is then the longest
    legal sequence of consonants at the end: one consonant, or a cluster of
    ``ONSET_CLUSTERS``. A glide after a vowel closes the syllable before
    (auxina awkˈsinɐ).
    """
    glide = int(len(run) > 1 and _is_glide(run[-1]) and not _is_glide(run[-2]))
    groups = _consonants(run[:len(run) - glide])
    if _is_glide(groups[-1][0]):
        return glide
    size = len(groups[-1])
    if len(groups) > 1 and _plain_unit("".join(groups[-2] + groups[-1])) in ONSET_CLUSTERS:
        size += len(groups[-2])
    return size + glide


def onset_stress(entry: str, seam: Optional[int] = None) -> Optional[str]:
    """*entry* with its primary stress mark before the onset of the stressed
    syllable, or ``None``.

    The onset is the longest sequence before the stressed vowel that a
    Portuguese syllable can open with (``_onset_size``). Cunha & Cintra (7th
    ed., p. 64) list the obstruent + liquid clusters as inseparable, and say
    that gn, pn, ps, pt, tm inside a word can stand in one syllable or in two.
    Mateus & d'Andrade (1998, D.E.L.T.A. 14(1)) decide this for European
    Portuguese. The clusters of their example (1), [ɡn pt ks tm] among them, "do
    not belong to the same syllable" (p. 15). They "hypothesise ... the existence
    of an empty nucleus between the consonants ... and we propose that this
    nucleus is not filled at the phonetic level in EP" (pp. 17-18). So a
    consonant before the onset opens a syllable of its own with an empty
    nucleus, and the mark goes after it: agnelo ɐɡˈnelu, afixar ɐfikˈsaɾ, but
    atleta ɐˈtlɛtɐ.

    Between two vowels with no consonant, the mark stays where *entry* has it.
    A glide there closes a diphthong and "can associate with the onset of the
    following syllable ... and it becomes then ambisyllabic" (Mateus &
    d'Andrade 1998, p. 29), so both places are right: gaiolo ɡajˈolu, kilowatt
    kilɔˈwɔt. A hiatus has no onset to place: saúde sɐˈudɨ.

    At the start of a word the whole sequence before the first vowel is the
    onset: Cunha & Cintra (p. 64) say that an initial gn, pn, ps is
    inseparable (gno-mo, psi-có-lo-go), so gnomo stays ˈɡnomu.

    *seam* is the index of the vowel, counted from 0, that a live prefix seam
    stands before (sub.lo.car, ``build_lexicon.prefix_seam``). A morpheme
    boundary outranks the onset rule, so when the stressed vowel is that vowel
    the entry keeps its mark and the result is ``None``.

    The result differs from *entry* only in the place of the mark, and keeps
    its stressed vowel. ``None`` also means that *entry* has no single primary
    mark or no vowel after it.
    """
    units = _units(entry)
    if units.count("ˈ") != 1:
        return None
    mark = units.index("ˈ")
    sounds = units[:mark] + units[mark + 1:]
    end = next((i for i in range(mark, len(sounds)) if _is_nucleus(sounds[i])), None)
    if end is None:
        return None
    nuclei = [i for i in range(end) if _is_nucleus(sounds[i])]
    if seam is not None and seam == len(nuclei):
        return None
    if not nuclei:
        at = 0
    else:
        run = sounds[nuclei[-1] + 1:end]
        if all(_is_glide(unit) for unit in run):
            return entry
        at = end - _onset_size(run)
    return "".join(sounds[:at] + ["ˈ"] + sounds[at:])


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
NASAL = "\u0303"


def outside_inventory(tokens: list[str], inventory: frozenset[str]) -> list[str]:
    """The tokens of a reading that are not in the spec's token *inventory*.

    A spec emits a nasal glide only as the second half of a nasal diphthong
    (pt-PT mãe ˈmɐ̃j̃, pão ˈpɐ̃w̃, põe ˈpõj̃), so the glide is not a token of its
    own. A nasal glide is inside the inventory only after a nasal vowel, and
    only when an inventory token ends in that glide: muito ˈmũj̃tu tokenises as
    ũ j̃. A spec that lists the bare glide changes neither condition.
    """
    nasal_glides = {t[-2:] for t in inventory
                    if len(t) > 2 and t.endswith(NASAL) and t[-2] in GLIDES}
    def after_nasal_vowel(i: int) -> bool:
        return i > 0 and unicodedata.normalize("NFD", tokens[i - 1]).endswith(NASAL)

    return [t for i, t in enumerate(tokens)
            if not (after_nasal_vowel(i) if t in nasal_glides else t in inventory)]
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

#: The demonstrative pronouns of Portuguese and their contractions with ⟨de em
#: a⟩, and mesmo, which Cunha & Cintra name as a demonstrative too (p. 343).
#: No row of portuguese_unified tags some of them.
_DEMONSTRATIVES = ("este", "estes", "esta", "estas", "isto", "esse", "esses", "essa",
                   "essas", "isso", "aquele", "aqueles", "aquela", "aquelas", "aquilo")
PT_DEMONSTRATIVES = frozenset(
    [prefix + word for word in _DEMONSTRATIVES for prefix in ("", "d", "n")]
    + ["à" + word[1:] for word in _DEMONSTRATIVES if word.startswith("a")]
    + ["mesmo", "mesma", "mesmos", "mesmas"])

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
#: generator output, a comparison and not a gold. A row that portuguese_unified
#: merged from Infopédia and pt.wiktionary (``merged``) repeats the Infopédia
#: reading, so it is not independent. Their agreement is recorded, but it keeps
#: no entry on its own.
CORROBORATING_SOURCES = frozenset({"wikipron", "wiktionary"})

#: The sources whose agreement keeps a pt-BR entry. WikiPron pt-BR is template
#: output too, so it counts only as it does for pt-PT. The Aeiouadô lexicon is
#: machine-generated and never counts.
PT_BR_CORROBORATING_SOURCES = CORROBORATING_SOURCES | {"michaelis"}


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
