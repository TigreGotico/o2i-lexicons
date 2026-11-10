"""Score a packaged lexicon on a gold from a different source.

    python scripts/measure.py en-GB ipadict:en-GB cmudict:en

Each ``dataset:tag`` gold is scored with the board's own normalisation and
distance (broad, stress-free PER): with the rules only, and with the rules and
each packaged lexicon of *code*: the exceptions, the patches, and both, as a
caller that asks for the patches loads them. For each lexicon the report also
gives the PER on the overlap, the gold words that the lexicon holds, because
only there can the lexicon act.

A lexicon is never scored on a gold that its build read: the ``source`` in the
lexicon's sidecar, the board dataset that holds it, each second source of the
build (``build_lexicon.SECOND_SOURCES``), and each of those datasets with its
corrections overlay are refused.

The script reads the lexicons of this checkout, never an installed copy.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# The checkout goes on the path before any import of o2i_lexicons, which
# build_lexicon makes, so an installed copy cannot take its place.
sys.path[:0] = [str(Path(__file__).resolve().parent), str(ROOT)]

from orthography2ipa import G2P, Pipeline  # noqa: E402
from orthography2ipa.lexicon import parse_lexicon_text  # noqa: E402
from orthography2ipa.registry import resolve  # noqa: E402
from orthography2ipa.version import VERSION_STR  # noqa: E402

import o2i_harness  # noqa: E402
from build_lexicon import SECOND_SOURCES, SOURCES  # noqa: E402
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
    """The board datasets that the build of *source* read: the source itself,
    the board dataset it is read from, its second sources, and each of those
    with its corrections."""
    board = SOURCES[source][2] if source in SOURCES else source
    read = {board, *SECOND_SOURCES.get(source, ())}
    return {source, *read, *(f"{d}_corrected" for d in read)}


def lexicons(code: str) -> dict[str, dict[str, str]]:
    """The exceptions, the patches, and both, of *code*. An exception wins
    over a patch for the same word, as in ``packaged_lexicon``."""
    exceptions, patches = (parse_lexicon_text(path.read_text(encoding="utf-8")) for path in
                           (o2i_lexicons.tsv_path(code), o2i_lexicons.patch_tsv_path(code)))
    return {"exception": exceptions, "patch": patches, "both": {**patches, **exceptions}}


def measure(code: str, golds: list[tuple[str, str]], cache: Path) -> dict:
    bench = o2i_harness.load_benchmark(cache)
    # One build writes both kinds, so the patches share the source of the exceptions.
    source = o2i_lexicons.load_meta(code)["source"]
    by_kind = lexicons(code)
    rows = []
    for dataset, tag in golds:
        if dataset in supplying_datasets(source):
            raise SystemExit(f"the build of the {code} lexicon read {dataset}; "
                             f"score it on another gold")
        if resolve(tag) != code:
            raise SystemExit(f"{tag} resolves to {resolve(tag)}, not {code}")
        loader = bench.DATASETS[dataset][0]
        pairs = loader(tag, sys.maxsize)
        n_full, per_rules = score(bench, pairs, tag, {})
        row = {
            "gold": dataset,
            "lang": tag,
            "tier": bench.provenance_for(dataset, tag),
            "gold_rows": len(pairs),
            "words_scored": n_full,
            "per_rules_only": round(per_rules, 4),
        }
        for kind, lexicon in by_kind.items():
            overlap = [(w, g) for w, g in pairs if w.lower() in lexicon]
            _, per_lex = score(bench, pairs, tag, lexicon)
            n_overlap, per_rules_ov = score(bench, overlap, tag, {}) if overlap else (0, 0.0)
            _, per_lex_ov = score(bench, overlap, tag, lexicon) if overlap else (0, 0.0)
            row[kind] = {
                "per_with_lexicon": round(per_lex, 4),
                "overlap_words": n_overlap,
                "overlap_per_rules_only": round(per_rules_ov, 4),
                "overlap_per_with_lexicon": round(per_lex_ov, 4),
            }
        rows.append(row)
    return {
        "lexicon": code,
        "lexicon_source": source,
        "lexicon_entries": {kind: len(lexicon) for kind, lexicon in by_kind.items()},
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
    package = Path(o2i_lexicons.__file__).resolve().parent
    if package != ROOT / "o2i_lexicons":
        raise SystemExit(f"o2i_lexicons was imported from {package}, not from this checkout")
    golds = [tuple(g.split(":", 1)) for g in args.golds]
    report = measure(args.code, golds, args.cache)
    text = json.dumps(report, ensure_ascii=False, indent=1)
    if args.report:
        args.report.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
