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


def first_usable(golds: list[str], usable: Callable[[str], Optional[str]]) -> Optional[str]:
    """The first gold reading, in source order, that *usable* accepts.

    *usable* returns the storage form of a reading, or ``None`` to refuse it.
    """
    for gold in golds:
        ipa = usable(gold)
        if ipa is not None:
            return ipa
    return None
