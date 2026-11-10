"""The contract that each packaged lexicon file and its sidecar must satisfy.

A ``<source>.meta.json`` sidecar is a JSON object with these keys:

``kind``
    ``exception`` for the file under ``data/<code>/`` and ``patch`` for the
    file under ``data/patches/<code>/``.
``code``
    The language code. It is the name of the directory that holds the file.
``source``
    The name of the gold dataset that supplied the entries.
``source_url``
    Where the gold file can be fetched.
``tier``
    The reliability tier of that gold, in the orthography2ipa ladder. Only a
    tier that can gate a quality decision there may supply entries. A silver
    set (``llm-generated``, which includes engine-pinned gold) or the output
    of a system orthography2ipa benchmarks against never does.
``licence``
    The SPDX id of the licence of the source. The file keeps that licence.
``build_command``
    The command that rebuilds the file.
``o2i_version``
    The orthography2ipa version whose rules got each entry wrong: the version
    of the build, or of the last ``prune_check.py --write`` that removed an
    entry from the file.
``stress``
    Where the stress of the entries comes from: ``source`` when the entries
    carry the stress marks of the source, ``rules`` when the source has no
    stress marks and the orthography2ipa stress rules place the stress on
    output. A ``rules`` file holds no stress mark.
``reasons``
    A map from each word in the TSV file to its reason class.
``reason_basis``
    A map from each reason class in use, other than ``unclassified``, to the
    evidence for it. A class claims a linguistic fact, so it needs a stated
    basis. A word that has no basis other than the data is ``unclassified``.

An exception sidecar also has:

``citations``
    A map from each word in the TSV file to the source that states that the
    spelling cannot give its reading, with the page or section. The reading
    itself comes from ``source``, or from pt.wiktionary for a word that
    ``wiktionary_readings`` names.

A patch sidecar also has:

``gaps``
    A map from each word in the TSV file to the gap that keeps the rules from
    it: the orthography2ipa pull request or the rule lead that will reach it.
"""
from __future__ import annotations

import re
import unicodedata

import orthography2ipa
from orthography2ipa.inventory import phoneme_inventory, tokenize
from orthography2ipa.lexicon import validate_lexicon_text

__all__ = [
    "REASON_CLASSES",
    "ALLOWED_TIERS",
    "REQUIRED_META_KEYS",
    "KIND_KEYS",
    "STRESS_ORIGINS",
    "STRESS_MARKS",
    "outside_inventory",
    "validate_tsv",
    "validate_meta",
]

REASON_CLASSES = frozenset({
    "loanword",
    "proper_noun",
    "lexical_stress",
    "irregular",
    "acronym",
    "homograph_default",
    "unclassified",
})

#: The tiers of the orthography2ipa reliability ladder that can gate a quality
#: decision there (``can_gate_promotion``). The tiers below them are the
#: output of a benchmarked competitor or of a language model.
ALLOWED_TIERS = frozenset({
    "expert-human",
    "lexicon-derived",
    "crowd-scraped",
    "machine-generated",
})

REQUIRED_META_KEYS = (
    "kind", "code", "source", "source_url", "tier", "licence", "build_command",
    "o2i_version", "stress", "reasons", "reason_basis",
)

STRESS_ORIGINS = frozenset({"source", "rules"})

#: The per-word key that each kind of sidecar adds: the citation of an
#: exception, the gap of a patch.
KIND_KEYS = {"exception": "citations", "patch": "gaps"}

#: The primary and secondary stress marks.
STRESS_MARKS = "ˈˌ"

_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(a\d+)?$")
_SPDX_RE = re.compile(r"^[A-Za-z0-9.+-]+$")

_GLIDES = frozenset("jwɥ")
_NASAL = "\u0303"


def outside_inventory(tokens: list[str], inventory: frozenset[str]) -> list[str]:
    """The tokens of a reading that are not in the spec's token *inventory*.

    A spec emits a nasal glide only as the second half of a nasal diphthong
    (pt-PT mãe ˈmɐ̃j̃, pão ˈpɐ̃w̃, põe ˈpõj̃), so the glide is not a token of its
    own. A nasal glide is inside the inventory only after a nasal vowel, and
    only when an inventory token ends in that glide: muito ˈmũj̃tu tokenises as
    ũ j̃. A spec that lists the bare glide changes neither condition.
    """
    nasal_glides = {t[-2:] for t in inventory
                    if len(t) > 2 and t.endswith(_NASAL) and t[-2] in _GLIDES}
    def after_nasal_vowel(i: int) -> bool:
        return i > 0 and unicodedata.normalize("NFD", tokens[i - 1]).endswith(_NASAL)

    return [t for i, t in enumerate(tokens)
            if not (after_nasal_vowel(i) if t in nasal_glides else t in inventory)]


def validate_tsv(text: str, code: str | None = None) -> list[tuple[int, str]]:
    """Return the problems in the body of a lexicon TSV file.

    The checks of :func:`orthography2ipa.lexicon.validate_lexicon_text` apply:
    one TAB per line, NFC lowercase word, IPA-only NFC transcription, no
    duplicate word. In addition, the words must be in sorted order, so that
    "first entry wins" picks a deterministic entry, and the file ends with
    one newline. With *code*, each transcription must also cut into tokens of
    the phoneme inventory of the orthography2ipa spec for *code*, because the
    IPA-only check accepts any letter.
    """
    problems = list(validate_lexicon_text(text))
    if text and not text.endswith("\n"):
        problems.append((text.count("\n") + 1, "no newline at end of file"))
    if code is not None:
        spec = orthography2ipa.get(code)
        inventory = phoneme_inventory(spec)
    previous = None
    for line_no, line in enumerate(text.split("\n"), start=1):
        if not line:
            continue
        word, _, ipa = line.partition("\t")
        if previous is not None and word < previous:
            problems.append((line_no, f"not sorted: {word!r} after {previous!r}"))
        previous = word
        if code is not None and ipa:
            outside = outside_inventory(tokenize(ipa, spec), inventory)
            if outside:
                problems.append((line_no, f"outside the {code} inventory: {' '.join(outside)}"))
    return problems


def validate_meta(meta: dict, code: str, entries: dict[str, str],
                  kind: str = "exception") -> list[str]:
    """Return the problems in the sidecar *meta* of the *kind* TSV file for *code*.

    *entries* maps each word of that TSV file to its IPA, in file order.
    """
    words = list(entries)
    missing = [k for k in (*REQUIRED_META_KEYS, KIND_KEYS[kind]) if k not in meta]
    if missing:
        return [f"missing key: {k}" for k in missing]
    problems: list[str] = []
    if meta["kind"] != kind:
        problems.append(f"kind {meta['kind']!r} does not match the {kind} file")
    key = KIND_KEYS[kind]
    notes = meta[key]
    if not isinstance(notes, dict):
        problems.append(f"{key} must be an object")
    else:
        for word in words:
            note = notes.get(word)
            if not isinstance(note, str) or not note.strip():
                problems.append(f"{key} has no entry for {word!r}")
        problems += [f"{key} names {word!r}, which is not in the TSV file"
                     for word in notes if word not in entries]
    if meta["code"] != code:
        problems.append(f"code {meta['code']!r} does not match directory {code!r}")
    for key in ("source", "source_url", "licence", "build_command"):
        if not isinstance(meta[key], str) or not meta[key].strip():
            problems.append(f"{key} must be a non-empty string")
    if meta["tier"] not in ALLOWED_TIERS:
        problems.append(f"tier {meta['tier']!r} cannot supply entries")
    if isinstance(meta["licence"], str) and not _SPDX_RE.match(meta["licence"]):
        problems.append(f"licence {meta['licence']!r} is not an SPDX id")
    if not isinstance(meta["o2i_version"], str) or not _VERSION_RE.match(meta["o2i_version"]):
        problems.append(f"o2i_version {meta['o2i_version']!r} is not a release version")
    if meta["stress"] not in STRESS_ORIGINS:
        problems.append(f"stress {meta['stress']!r} is not one of {sorted(STRESS_ORIGINS)}")
    elif meta["stress"] == "rules":
        marked = [w for w, ipa in entries.items() if any(m in ipa for m in STRESS_MARKS)]
        if marked:
            problems.append(f"stress is 'rules' but {len(marked)} entries carry a "
                            f"stress mark, the first {marked[0]!r}")

    reasons = meta["reasons"]
    if not isinstance(reasons, dict):
        return problems + ["reasons must be an object"]
    for word in words:
        if word not in reasons:
            problems.append(f"no reason class for {word!r}")
    word_set = set(words)
    for word, reason in reasons.items():
        if word not in word_set:
            problems.append(f"reason for {word!r}, which is not in the TSV file")
        if reason not in REASON_CLASSES:
            problems.append(f"unknown reason class {reason!r} for {word!r}")

    basis = meta["reason_basis"]
    if not isinstance(basis, dict):
        return problems + ["reason_basis must be an object"]
    for reason in sorted(set(reasons.values()) & REASON_CLASSES - {"unclassified"}):
        text = basis.get(reason)
        if not isinstance(text, str) or not text.strip():
            problems.append(f"reason class {reason!r} is used with no stated basis")
    return problems
