"""Score a packaged lexicon on a gold from a different source.

    python scripts/measure.py en-GB ipadict:en-GB cmudict:en

Each ``dataset:tag`` gold is scored twice with the board's own normalisation
and distance (broad, stress-free PER): with the rules only, and with the rules
and the packaged lexicon for *code*. The report also gives the PER on the
overlap, the gold words that the lexicon holds, because only there can the
lexicon act.

A lexicon is never scored on the gold it came from: the ``source`` in the
lexicon's sidecar, the board dataset that holds it, and that dataset with its
corrections overlay are refused.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from orthography2ipa import G2P, Pipeline
from orthography2ipa.lexicon import parse_lexicon_text
from orthography2ipa.registry import resolve
from orthography2ipa.version import VERSION_STR

import o2i_harness
from build_lexicon import SOURCES

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import o2i_lexicons  # noqa: E402


def score(bench, pairs, tag: str, lexicon: dict[str, str]) -> tuple[int, float]:
    """``(covered words, PER)`` of *pairs* with *lexicon* as the only lexicon.

    ``bench.evaluate_words`` builds its own engine and takes no pipeline, so
    this loop repeats its 1-best scoring: each word against the best of its golds.
    """
    engine = G2P(tag, expose_ambiguous_endings=False, pipeline=Pipeline(lexicon=lexicon))
    extra = bench._prosody_marks(tag)

    def norm(ipa: str) -> str:
        return bench.normalize(ipa, strip_stress=True, broad=True, extra_strip=extra)

    golds: dict[str, list[str]] = {}
    for word, gold in pairs:
        golds.setdefault(word, []).append(norm(gold))
    pers = []
    for word, refs in golds.items():
        transcribe = engine.transcribe if bench._is_multiword(word) else engine.transcribe_word
        try:
            hyp = norm(transcribe(word))
        except Exception:
            continue
        if hyp:
            pers.append(min(bench.levenshtein(hyp, ref) / max(len(ref), 1) for ref in refs))
    return len(pers), sum(pers) / len(pers) if pers else 1.0


def supplying_datasets(source: str) -> set[str]:
    """The board datasets that hold the rows of *source*: the source itself,
    the board dataset it is read from, and that dataset with its corrections."""
    board = SOURCES[source][2] if source in SOURCES else source
    return {source, board, f"{board}_corrected"}


def measure(code: str, golds: list[tuple[str, str]], cache: Path) -> dict:
    bench = o2i_harness.load_benchmark(cache)
    meta = o2i_lexicons.load_meta(code)
    lexicon = parse_lexicon_text(o2i_lexicons.tsv_path(code).read_text(encoding="utf-8"))
    rows = []
    for dataset, tag in golds:
        if dataset in supplying_datasets(meta["source"]):
            raise SystemExit(f"{dataset} supplied the {code} lexicon; score it on another gold")
        if resolve(tag) != code:
            raise SystemExit(f"{tag} resolves to {resolve(tag)}, not {code}")
        loader = bench.DATASETS[dataset][0]
        pairs = loader(tag, sys.maxsize)
        overlap = [(w, g) for w, g in pairs if w.lower() in lexicon]
        n_full, per_rules = score(bench, pairs, tag, {})
        _, per_lex = score(bench, pairs, tag, lexicon)
        n_overlap, per_rules_ov = score(bench, overlap, tag, {}) if overlap else (0, 0.0)
        _, per_lex_ov = score(bench, overlap, tag, lexicon) if overlap else (0, 0.0)
        rows.append({
            "gold": dataset,
            "lang": tag,
            "tier": bench.provenance_for(dataset, tag),
            "gold_rows": len(pairs),
            "words_scored": n_full,
            "per_rules_only": round(per_rules, 4),
            "per_with_lexicon": round(per_lex, 4),
            "overlap_words": n_overlap,
            "overlap_per_rules_only": round(per_rules_ov, 4),
            "overlap_per_with_lexicon": round(per_lex_ov, 4),
        })
    return {
        "lexicon": code,
        "lexicon_source": meta["source"],
        "lexicon_entries": len(lexicon),
        "o2i_version": VERSION_STR,
        "harness_sha256": o2i_harness.harness_sha256(cache),
        "rows": rows,
    }


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("code")
    ap.add_argument("golds", nargs="+", help="dataset:tag, e.g. ipadict:en-GB")
    ap.add_argument("--cache", type=Path, default=ROOT / ".cache")
    ap.add_argument("--report", type=Path)
    args = ap.parse_args(argv)
    golds = [tuple(g.split(":", 1)) for g in args.golds]
    report = measure(args.code, golds, args.cache)
    text = json.dumps(report, ensure_ascii=False, indent=1)
    if args.report:
        args.report.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
