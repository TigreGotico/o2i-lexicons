"""Sort each lexicon entry into an exception or a patch.

An exception is a word whose reading the spelling cannot give. Its note is the
source that states this, with the page or section. It stays in the lexicon
for as long as the rules read by spelling.

A patch is a word that a rule could reach. Its note is the gap: the
orthography2ipa pull request, or the section of ``rule-leads.md`` in the
o2i-lexicons audit of the wiki, that will reach it. A patch leaves the
lexicon when ``prune_check.py`` finds that the rules read it right.

An entry with an exception part is an exception, because it stays needed
after the rule of its patch part lands.

Each function returns ``(kind, note)``.
"""
from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Optional

from o2i_lexicons.schema import KIND_KEYS
from lexicon_build import lexical_class as find_lexical_class, stressed_vowel

LEADS = "rule-leads.md"
NO_LEAD = "no lead: the rules miss the word outside every class and lead"

VOWELS = "aeiouáéíóúâêôãõ"

#: The stressed-vowel rules of the pt-PT spec, as spelling gates at the end of
#: the word, with the height each rule gives.
PT_SUFFIX_RULES = (
    ("PT_SUFFIX_EZ_CLOSE", re.compile(r"ez$"), "e"),
    ("PT_SUFFIX_EZA_ESA_CLOSE", re.compile(r"e[zs]a$"), "e"),
    ("PT_SUFFIX_EMA_CLOSE", re.compile(r"ema$"), "e"),
    ("PT_SUFFIX_ESCO_CLOSE", re.compile(r"esc[aou]s?$"), "e"),
    ("PT_ER_CLOSE", re.compile(r"er$"), "e"),
    ("PT_SUFFIX_OR_CLOSE", re.compile(r"or$"), "o"),
    ("PT_SUFFIX_OSO_CLOSE", re.compile(r"oso$"), "o"),
    ("PT_SUFFIX_ONHO_CLOSE", re.compile(r"onh[oa]$"), "o"),
)

#: A spelling outside the native system: ⟨k w y⟩, a doubled consonant or vowel
#: that Portuguese does not write, ⟨s⟩ + consonant at the start, or a final
#: consonant letter that Portuguese does not end a word with.
LOAN_SPELLING = re.compile(
    r"[kwy]|pp|bb|zz|tt|gg|ee(?!m)|ng$|^s[^aeiouáéíóúâêôãõh]|sh|[bcdfgkpt]$")

#: A doubled consonant letter other than ⟨cc rr ss⟩, and an initial ⟨s⟩ before
#: a consonant: two loan spellings that Infopédia reads one way.
DOUBLED_CONSONANT = re.compile(r"bb|dd|ff|gg|kk|ll|mm|nn|pp|tt|zz")
INITIAL_S = re.compile(r"^s[^aeiouáéíóúâêôãõh]")

#: AO90 Base I 2.º c) keeps ⟨k w y⟩ in "palavras adotadas como unidades de
#: medida de curso internacional" and names kW-kilowatt.
AO90_UNITS = frozenset({"kilowatt"})

#: Spellings that mark an English loan, named in the gap of a loan patch.
LOAN_MARKS = (("⟨tch⟩", re.compile(r"tch")), ("⟨zz⟩", re.compile(r"zz")),
              ("final ⟨-ing⟩", re.compile(r"ing$")))

PREPALATAL = re.compile(r"e(lh|nh|j|ch)[aeiou]")

#: Cunha & Cintra p. 431 give [ɛ] before a palatal only in these four verbs.
CC431_OPEN = re.compile(r"^(invej|embrech|frech|vex)")

#: Learned first elements under an initial ⟨e⟩ in an open syllable.
LEARNED_E = ("eco", "epi", "equi", "eritr", "etil", "etol", "ego", "endo", "ecto")

#: Endings whose stressed vowel takes one value in at least 90% of the
#: single-word Infopédia pt-PT rows, with at least 25 words. The spelling
#: shows the value, so a rule could take it.
DOMINANT_ENDINGS = {"oide": "ɔ", "orro": "o", "osto": "o", "ostro": "o", "olho": "o",
                    "oma": "o", "ona": "o", "ena": "e", "eno": "e", "edo": "e", "dora": "o"}

#: A gap named by a section of rule-leads.md, by ending.
ENDING_SECTIONS = {"oide": "Entries in ⟨-oide⟩", "dora": "Entries in ⟨-dora⟩"}

CC_STRESSED_MID = "Cunha & Cintra p. 40; AO90 Base IX 3.º for ⟨ei oi⟩"
X_VALUE = "AO90 Base III; Ciberdúvidas 4068"
QU_GU = "AO90 Base XIV 1.º; Cunha & Cintra p. 79"
AO90_UNIT = "AO90 Base I 2.º c) for the spelling; Infopédia gives the reading"
LOAN_DOUBLED = ("lead: a doubled consonant letter is one consonant in every Infopédia "
                "word that has one")
LOAN_INITIAL_S = ("lead: an initial ⟨s⟩ before a consonant is [s] in at least 90% of the "
                  "Infopédia words")
CODA_STOP = "orthography2ipa#2218"
CODA_STOP_A = "lead: an unstressed ⟨a⟩ before a coda stop keeps [a]; orthography2ipa#2218 leaves ⟨a⟩ out"
CODA_STOP_REDUCED = ("lead: the source reduces a vowel before a coda stop that "
                     "orthography2ipa#2218 keeps full")
CODA_STOP_CLOSE = ("lead: the source has a close mid vowel before a coda stop, where "
                   "orthography2ipa#2218 gives an open one")

#: The changes of a vowel before a coda stop that orthography2ipa#2218 makes:
#: a reduced or close ⟨e o⟩ becomes [ɛ ɔ].
CODA_STOP_OPENS = frozenset({("ɨ", "ɛ"), ("u", "ɔ"), ("e", "ɛ"), ("o", "ɔ"), ("i", "ɛ")})
STOP_SOUNDS = frozenset("pbtdkɡ")
NON_CONSONANTS = frozenset("aɐeɛɨioɔujw\u0303lɾɫʎ")


def _plain(ipa: str) -> str:
    return unicodedata.normalize("NFC", ipa.replace("ˈ", "").replace("ˌ", ""))


def _initial_coda(word: str) -> str:
    """The coda of the word-initial syllable whose nucleus is ⟨e o⟩."""
    after = (word[1:] if word[0] == "h" else word)[1:]
    if len(after) >= 2 and after[0] not in VOWELS and after[1] not in VOWELS + "hlr":
        return {"l": "/L/", "r": "/R/", "s": "/S/", "x": "/S/", "z": "/S/",
                "m": "nasal", "n": "nasal"}.get(after[0], "stop or other")
    if len(after) >= 2 and after[0] in "lr" and after[1] not in VOWELS + "h":
        return "/L/" if after[0] == "l" else "/R/"
    return "open"


def _coda_stop_changes(rules: str, entry: str) -> set[tuple[str, str]]:
    """The ``(rules, entry)`` vowel pairs that differ where the rules' vowel
    stands before a stop and another consonant."""
    a, b = _plain(rules), _plain(entry)
    changes = set()
    for op, i1, i2, j1, j2 in SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        after = a[i2:i2 + 2]
        if (op == "replace" and i2 - i1 == 1 and j2 - j1 == 1 and len(after) == 2
                and after[0] in STOP_SOUNDS and after[1] not in NON_CONSONANTS):
            changes.add((a[i1], b[j1]))
    return changes


def _pt_pt_coda_stop(rules: str, entry: str) -> Optional[str]:
    """The gap of a vowel before a coda stop, or ``None`` when the rules read
    that vowel right. orthography2ipa#2218 opens an ⟨e o⟩ there and leaves
    an ⟨a⟩ reduced."""
    changes = _coda_stop_changes(rules, entry)
    if not changes:
        return None
    gaps = []
    if ("ɐ", "a") in changes:
        gaps.append(CODA_STOP_A)
    if changes & {("ɛ", "ɨ"), ("ɔ", "u")}:
        gaps.append(CODA_STOP_REDUCED)
    if changes & CODA_STOP_OPENS:
        gaps.append(CODA_STOP)
    if changes - CODA_STOP_OPENS - {("ɐ", "a"), ("ɛ", "ɨ"), ("ɔ", "u")}:
        gaps.append(CODA_STOP_CLOSE)
    return "; ".join(gaps)


def _loan_gap(word: str, rules: str, entry: str) -> Optional[str]:
    """The gap of a pt-PT loan that differs from the rules only in a doubled
    consonant letter or an initial ⟨s⟩ before a consonant, or ``None``."""
    a, b = _plain(rules), _plain(entry)
    gaps = []
    for op, i1, i2, j1, j2 in SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        if (op == "delete" and i2 - i1 == 1 and i1 and a[i1] == a[i1 - 1]
                and DOUBLED_CONSONANT.search(word)):
            gaps.append(LOAN_DOUBLED)
        elif (op == "replace" and i1 == 0 and (a[i1:i2], b[j1:j2]) == ("ʃ", "s")
                and INITIAL_S.match(word)):
            gaps.append(LOAN_INITIAL_S)
        else:
            return None
    return "; ".join(dict.fromkeys(gaps)) or None


def loan_lead(code: str, word: str, source: str) -> str:
    """The gap of a loan that no narrower lead covers. No source states that
    the reading of a loan is lexical, so a loan is a patch."""
    marks = ", ".join(name for name, mark in LOAN_MARKS if mark.search(word))
    return (f"lead: {code} English loan spelling{f' ({marks})' if marks else ''}; "
            f"{source} gives the reading")


def _pt_pt_loan(word: str, rules: str, entry: str) -> tuple[str, str]:
    if word in AO90_UNITS:
        return "exception", AO90_UNIT
    return "patch", _loan_gap(word, rules, entry) or loan_lead("pt-PT", word, "Infopédia")


def _pt_pt_stressed(word: str, rules: str, entry: str) -> tuple[str, str]:
    have, want = stressed_vowel(rules), stressed_vowel(entry)
    for end, value in DOMINANT_ENDINGS.items():
        if word.endswith((end, end + "s")) and want == value and have != value:
            section = ENDING_SECTIONS.get(end)
            return "patch", (f"{LEADS} § {section}" if section
                             else f"lead: ⟨-{end}⟩ takes [{value}] in at least 90% of "
                                  f"the Infopédia words")
    for rule, gate, height in PT_SUFFIX_RULES:
        if gate.search(word) and have == height and want != height:
            return "patch", f"{rule} misfires"
    if PREPALATAL.search(word) and have == "e" and want == "ɛ":
        if CC431_OPEN.match(word):
            return "exception", "Cunha & Cintra p. 431"
        return "patch", "PT_STRESSED_E_PREPALATAL_CLOSE misfires"
    return "exception", CC_STRESSED_MID


def _pt_pt_part(word: str, rules: str, entry: str, name: str) -> tuple[str, str]:
    if name == "stressed mid vowel":
        return _pt_pt_stressed(word, rules, entry)
    if name.startswith("⟨x⟩ as"):
        return "exception", X_VALUE
    if name == "⟨qu gu⟩ with [w]":
        return "exception", QU_GU
    if name == "unstressed initial ⟨e⟩":
        coda = _initial_coda(word)
        if coda == "open" and word.startswith(LEARNED_E):
            return "patch", f"{LEADS} § word-initial e"
        if coda == "stop or other" and word.lstrip("h")[1:2] in "pbtdcgk":
            return "patch", _pt_pt_coda_stop(rules, entry)
        if coda == "/R/":
            return "exception", "Mateus & d'Andrade 1998 p. 26 (c)"
        if coda == "open":
            return "exception", "Cunha & Cintra p. 53; Mateus & d'Andrade 1998 p. 26 (b)"
        return "patch", "Mateus & d'Andrade 1998 p. 26 (a, b, d)"
    if name == "unstressed initial ⟨o⟩":
        if {_plain(rules)[0], _plain(entry)[0]} == {"o", "ɔ"}:
            return "exception", "Mateus & d'Andrade 1998 p. 27"
        return "patch", "lead: the stems honest- and honor- take an initial [u]"
    if name == "unstressed vowel before a coda stop":
        return "patch", _pt_pt_coda_stop(rules, entry)
    if name == "unreduced learned vowel":
        return "patch", f"{LEADS} § learned words"
    if name == "unstressed vowel before a coda ⟨l⟩":
        return "patch", f"{LEADS} § coda l"
    raise ValueError(f"unknown lexical class {name!r}")


def _join(parts: list[tuple[str, str]], kind: str) -> str:
    return "; ".join(dict.fromkeys(note for k, note in parts if k == kind))


def pt_pt_kind(word: str, rules: str, entry: str, lexical_class: Optional[str]) -> tuple[str, str]:
    """The kind of a pt-PT entry. *lexical_class* is the class that
    ``lexicon_build.lexical_class`` gives the word, or ``None``.

    The note of an exception joins the citations of its exception parts.
    """
    if lexical_class is None:
        if LOAN_SPELLING.search(word):
            return _pt_pt_loan(word, rules, entry)
        return "patch", NO_LEAD
    parts = [part for name in lexical_class.split("+")
             if (part := _pt_pt_part(word, rules, entry, name))[1] is not None]
    if not parts:
        return "patch", NO_LEAD
    kind = "exception" if any(k == "exception" for k, _ in parts) else "patch"
    return kind, _join(parts, kind)


#: The DELAF tense codes of the NILC file whose verb forms stress the stem:
#: the present indicative, the present subjunctive and the imperative.
RHIZOTONIC_TENSES = frozenset("PSY")


def pt_br_kind(word: str, rules: str, entry: str,
               verb_tenses: frozenset[str]) -> tuple[str, str]:
    """The kind of a pt-BR entry, with the class of ``lexicon_build.lexical_class``.
    *verb_tenses* holds the DELAF tense codes of
    the word's NILC lines when every line tags it as a verb, and is empty
    otherwise.

    The stem vowel of a verb form follows the model verbs of Cunha & Cintra
    pp. 429-433, so a rule can read it.
    """
    if verb_tenses:
        if verb_tenses <= RHIZOTONIC_TENSES:
            return "patch", ("Cunha & Cintra pp. 429-433: the stem vowel of a rhizotonic "
                             "verb form")
        return "patch", "lead: the stem vowel of a pt-BR preterite or imperfect form"
    if re.match(r"trans[aeiouáéíóúâêôãõ]", word):
        return "patch", "lead: the ⟨s⟩ of the prefix trans- before a vowel is [z]"
    if LOAN_SPELLING.search(word):
        return "patch", loan_lead("pt-BR", word, "NILC")
    lexical_class = find_lexical_class(word, rules, entry)
    if lexical_class is None:
        return ("exception", X_VALUE) if "x" in word else ("patch", NO_LEAD)
    parts = []
    if "stressed mid vowel" in lexical_class:
        parts.append("Cunha & Cintra p. 40; orthography2ipa#1824")
    if "⟨x⟩" in lexical_class:
        parts.append(X_VALUE)
    if "⟨qu gu⟩" in lexical_class:
        parts.append(QU_GU)
    return "exception", "; ".join(parts)


#: The citation of an en-GB proper noun or acronym. No rule of English
#: spelling gives the reading of a name or of an acronym, so the class is the
#: ground. The reading is the one WikiPron scraped from Wiktionary.
#: EN_GB_CITATION is for a reading that agrees with Britfone;
#: EN_GB_UNCHECKED_CITATION is for the one reading of a word that Britfone
#: does not hold.
EN_GB_CITATION = "Wiktionary via WikiPron (en-GB); the reading agrees with Britfone 3.0.1"
EN_GB_UNCHECKED_CITATION = "Wiktionary via WikiPron (en-GB); not checked against a dictionary"

#: The en-GB reason classes whose entries are exceptions.
EN_GB_EXCEPTION_REASONS = frozenset({"proper_noun", "acronym"})

#: The gap of an en-GB inflection whose base the rules read right.
EN_GB_INFLECTION = "lead: en-GB inflection morphology"

#: The gap of any other en-GB entry: nothing shows that a rule cannot reach it.
EN_GB_UNAUDITED = "lead: en-GB spelling rules not audited"


def en_gb_bases(word: str):
    """The candidate bases of *word* as an inflection in -s -es -ies -ed -ing."""
    if word.endswith("ies"):
        yield word[:-3] + "y"
    if word.endswith("es"):
        yield word[:-2]
    if word.endswith("s") and not word.endswith("ss"):
        yield word[:-1]
    if word.endswith("ied"):
        yield word[:-3] + "y"
    if word.endswith("ed"):
        yield word[:-2]
        yield word[:-1]
    if word.endswith("ing"):
        yield word[:-3]
        yield word[:-3] + "e"
    if len(word) > 5 and word[-3] == word[-4] and word.endswith(("ed", "ing")):
        yield word[:-3] if word.endswith("ing") else word[:-2]


def en_gb_kind(word: str, reason: str, headwords: frozenset[str],
               entries: frozenset[str], confirmed: bool) -> tuple[str, str]:
    """The kind of an en-GB entry. A proper noun or an acronym is an
    exception, because no spelling rule gives the reading of a name or of an
    acronym. Every other entry is a patch, because nothing shows that a rule
    cannot reach it. An inflection of a source headword that is not an entry
    names its own gap: the rules read that base right, and a morphology rule
    could read the inflection. The citation of an exception says whether
    Britfone *confirmed* the reading.
    """
    if reason in EN_GB_EXCEPTION_REASONS:
        return "exception", EN_GB_CITATION if confirmed else EN_GB_UNCHECKED_CITATION
    if any(len(base) >= 2 and base in headwords and base not in entries
           for base in en_gb_bases(word)):
        return "patch", EN_GB_INFLECTION
    return "patch", EN_GB_UNAUDITED


#: The sidecar fields that hold one record per word.
PER_WORD_FIELDS = ("reasons", "lexical_classes", "confirmation")


def split(entries: dict[str, str], meta: dict,
          kinds: dict[str, tuple[str, str]]) -> dict[str, tuple[dict[str, str], dict]]:
    """Split one lexicon into its exception and patch files.

    *meta* is the sidecar of all *entries*, and *kinds* gives each word its
    ``(kind, note)``. Each kind gets its entries and a sidecar with the
    records of its own words, its ``kind``, and its notes as ``citations``
    or ``gaps``. A kind with no word gets an empty file.
    """
    out = {}
    for kind, key in KIND_KEYS.items():
        words = [w for w in entries if kinds[w][0] == kind]
        part = {k: v for k, v in meta.items()
                if k not in (*PER_WORD_FIELDS, "reason_basis", "wiktionary_readings")}
        part["kind"] = kind
        part["reasons"] = {w: meta["reasons"][w] for w in words}
        used = set(part["reasons"].values())
        part["reason_basis"] = {r: b for r, b in meta["reason_basis"].items() if r in used}
        for field in ("lexical_classes", "confirmation"):
            if field in meta:
                part[field] = {w: meta[field][w] for w in words if w in meta[field]}
        if "wiktionary_readings" in meta:
            part["wiktionary_readings"] = [w for w in meta["wiktionary_readings"]
                                           if kinds[w][0] == kind]
        part[key] = {w: kinds[w][1] for w in words}
        out[kind] = ({w: entries[w] for w in words}, part)
    return out
