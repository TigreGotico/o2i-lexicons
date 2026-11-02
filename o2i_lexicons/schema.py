"""The contract that each packaged lexicon file and its sidecar must satisfy.

A ``<source>.meta.json`` sidecar is a JSON object with these keys:

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
    The orthography2ipa version whose rules got each entry wrong.
``reasons``
    A map from each word in the TSV file to its reason class.
``reason_basis``
    A map from each reason class in use, other than ``unclassified``, to the
    evidence for it. A class claims a linguistic fact, so it needs a stated
    basis. A word that has no basis other than the data is ``unclassified``.
"""
from __future__ import annotations

import re

from orthography2ipa.lexicon import validate_lexicon_text

__all__ = [
    "REASON_CLASSES",
    "ALLOWED_TIERS",
    "REQUIRED_META_KEYS",
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
    "code", "source", "source_url", "tier", "licence", "build_command",
    "o2i_version", "reasons", "reason_basis",
)

_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(a\d+)?$")
_SPDX_RE = re.compile(r"^[A-Za-z0-9.+-]+$")


def validate_tsv(text: str) -> list[tuple[int, str]]:
    """Return the problems in the body of a lexicon TSV file.

    The checks of :func:`orthography2ipa.lexicon.validate_lexicon_text` apply:
    one TAB per line, NFC lowercase word, IPA-only NFC transcription, no
    duplicate word. In addition, the words must be in sorted order, so that
    "first entry wins" picks a deterministic entry, and the file ends with
    one newline.
    """
    problems = list(validate_lexicon_text(text))
    if text and not text.endswith("\n"):
        problems.append((text.count("\n") + 1, "no newline at end of file"))
    previous = None
    for line_no, line in enumerate(text.split("\n"), start=1):
        if not line:
            continue
        word = line.split("\t", 1)[0]
        if previous is not None and word < previous:
            problems.append((line_no, f"not sorted: {word!r} after {previous!r}"))
        previous = word
    return problems


def validate_meta(meta: dict, code: str, words: list[str]) -> list[str]:
    """Return the problems in the sidecar *meta* of the TSV file for *code*.

    *words* are the words of that TSV file, in file order.
    """
    missing = [k for k in REQUIRED_META_KEYS if k not in meta]
    if missing:
        return [f"missing key: {k}" for k in missing]
    problems: list[str] = []
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
