"""Find the entries that the installed orthography2ipa rules now get right.

    python scripts/prune_check.py            # exit 1 when an entry is stale
    python scripts/prune_check.py --write    # remove stale entries in place

Each entry is transcribed by an engine with an empty lexicon, so the check sees
the rules alone, and compared with the entry's IPA under the board's broad,
stress-free normalisation. An entry that now matches is stale: the rules reach
it, so the lexicon must not hold it.

``--write`` removes the stale entries and their reasons, and records the
installed version as the one where the remaining entries last failed.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from orthography2ipa import G2P, Pipeline
from orthography2ipa.lexicon import parse_lexicon_text
from orthography2ipa.version import VERSION_STR

import lexicon_build as lb
import o2i_harness

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cache", type=Path, default=ROOT / ".cache")
    ap.add_argument("--write", action="store_true", help="remove stale entries in place")
    ap.add_argument("--report", type=Path, help="write the stale words here as JSON")
    args = ap.parse_args(argv)

    bench = o2i_harness.load_benchmark(args.cache)
    report = {"o2i_version": VERSION_STR, "codes": {}}
    for code in o2i_lexicons.available_codes():
        tsv = o2i_lexicons.tsv_path(code)
        entries = parse_lexicon_text(tsv.read_text(encoding="utf-8"))
        stale = stale_entries(code, entries, bench)
        report["codes"][code] = {"entries": len(entries), "stale": stale}
        print(f"{code}: {len(entries)} entries, {len(stale)} now right under "
              f"orthography2ipa {VERSION_STR}")
        for word in stale:
            print(f"  {word}\t{entries[word]}")
        if args.write and stale:
            meta = o2i_lexicons.load_meta(code)
            for word in stale:
                del entries[word]
                del meta["reasons"][word]
            used = set(meta["reasons"].values())
            meta["reason_basis"] = {r: b for r, b in meta["reason_basis"].items() if r in used}
            meta["o2i_version"] = VERSION_STR
            lb.write_lexicon(tsv.parent, tsv.stem, entries, meta)
    if args.report:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n",
                               encoding="utf-8")
    stale_total = sum(len(c["stale"]) for c in report["codes"].values())
    return 1 if stale_total and not args.write else 0


if __name__ == "__main__":
    sys.exit(main())
