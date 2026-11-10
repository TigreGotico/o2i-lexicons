"""Find the entries that the installed orthography2ipa rules now get right.

    python scripts/prune_check.py            # exit 1 when an entry is stale
    python scripts/prune_check.py --write    # remove stale patches in place

Each entry is transcribed by an engine with an empty lexicon, so the check sees
the rules alone, and compared with the entry's IPA under the board's broad,
stress-free normalisation. An entry that now matches is stale: the rules reach
it, so the lexicon must not hold it.

The two kinds of entry are stale for different reasons. A stale patch is the
expected result: the rule of its gap landed. ``--write`` removes it and its
records, and records the installed version as the one where the remaining
patches last failed. A stale exception means that its class is wrong, because
the spelling does give its reading. The check lists it and exits 1, also with
``--write``, and never removes it: a person decides where the word goes.

The script checks the files of this checkout, never an installed copy.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# The checkout goes on the path before any import of o2i_lexicons, which
# lexicon_build makes, so an installed copy cannot take its place.
sys.path[:0] = [str(Path(__file__).resolve().parent), str(ROOT)]

from orthography2ipa import G2P, Pipeline  # noqa: E402
from orthography2ipa.lexicon import parse_lexicon_text  # noqa: E402
from orthography2ipa.version import VERSION_STR  # noqa: E402

import lexicon_build as lb  # noqa: E402
import o2i_harness  # noqa: E402
import o2i_lexicons  # noqa: E402


def stale_entries(code: str, entries: dict[str, str], bench) -> list[str]:
    """The words of *entries* that the rules alone now transcribe right."""
    engine = G2P(code, expose_ambiguous_endings=False, pipeline=Pipeline(lexicon={}))
    extra = bench._prosody_marks(code)

    def norm(ipa: str) -> str:
        return bench.normalize(ipa, strip_stress=True, broad=True, extra_strip=extra)

    stale = []
    for word, ipa in entries.items():
        try:
            hyp = norm(engine.transcribe_word(word))
        except Exception:
            continue
        if hyp and hyp == norm(ipa):
            stale.append(word)
    return sorted(stale)


def forget(meta: dict, words: list[str]) -> None:
    """Remove from the sidecar *meta* each record of *words*."""
    for word in words:
        for key in ("reasons", "citations", "gaps", "lexical_classes"):
            meta.get(key, {}).pop(word, None)
    used = set(meta["reasons"].values())
    meta["reason_basis"] = {r: b for r, b in meta["reason_basis"].items() if r in used}
    if "wiktionary_readings" in meta:
        meta["wiktionary_readings"] = [w for w in meta["wiktionary_readings"] if w not in words]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cache", type=Path, default=ROOT / ".cache")
    ap.add_argument("--write", action="store_true", help="remove stale entries in place")
    ap.add_argument("--report", type=Path, help="write the stale words here as JSON")
    args = ap.parse_args(argv)
    package = Path(o2i_lexicons.__file__).resolve().parent
    if package != ROOT / "o2i_lexicons":
        raise SystemExit(f"o2i_lexicons was imported from {package}, not from this checkout")

    bench = o2i_harness.load_benchmark(args.cache)
    report = {"o2i_version": VERSION_STR, "codes": {}}
    files = {"exception": (o2i_lexicons.tsv_path, o2i_lexicons.meta_path),
             "patch": (o2i_lexicons.patch_tsv_path, o2i_lexicons.patch_meta_path)}
    for kind, (tsv_of, meta_of) in files.items():
        for code in o2i_lexicons.available_codes(kind):
            tsv = tsv_of(code)
            entries = parse_lexicon_text(tsv.read_text(encoding="utf-8"))
            stale = stale_entries(code, entries, bench)
            report["codes"].setdefault(code, {})[kind] = {"entries": len(entries),
                                                          "stale": stale}
            print(f"{code} {kind} file: {len(entries)} entries, {len(stale)} now right under "
                  f"orthography2ipa {VERSION_STR}")
            for word in stale:
                print(f"  {word}\t{entries[word]}")
            if kind == "patch" and args.write and stale:
                meta = json.loads(meta_of(code).read_text(encoding="utf-8"))
                for word in stale:
                    del entries[word]
                forget(meta, stale)
                meta["o2i_version"] = VERSION_STR
                lb.write_lexicon(tsv.parent, tsv.stem, entries, meta)
    if args.report:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n",
                               encoding="utf-8")
    stale = {kind: sum(len(c[kind]["stale"]) for c in report["codes"].values() if kind in c)
             for kind in files}
    if stale["exception"]:
        print(f"{stale['exception']} exceptions are right under the rules, so their class "
              f"is wrong; move each one by hand")
    return 1 if stale["exception"] or (stale["patch"] and not args.write) else 0


if __name__ == "__main__":
    sys.exit(main())
