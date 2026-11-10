"""Find the entries that the installed orthography2ipa rules now get right.

    python scripts/prune_check.py            # exit 1 when an entry is stale
    python scripts/prune_check.py --write    # remove stale patches in place

Each entry is transcribed by an engine with an empty lexicon, so the check sees
the rules alone, and compared with the entry's IPA under the board's broad,
stress-free normalisation. In a file whose sidecar gives ``"stress": "source"``,
the entry's stress is part of its reading, so the rules must also stress the
same vowel. In a ``rules`` file the entry has no stress mark and the rules place
the stress anyway. An entry that now matches is stale: the rules reach it, so
the lexicon must not hold it.

The two kinds of entry are stale for different reasons. A stale patch is the
expected result: the rule of its gap landed. ``--write`` removes it and its
records, and records the installed version as the one where the remaining
patches last failed. It then reads each file it wrote back from disk and
checks it against the schema; a file that fails stops the run with exit 1
before the report is written. A stale exception means that its class is
wrong, because the spelling does give its reading. The check lists it and
exits 1, also with ``--write``, and never removes it: a person decides where
the word goes.

An entry whose word the spec's ``word_exceptions`` hold never applies, because
the spec wins over a lexicon. The check lists such a shadowed entry as it lists
a stale one: ``--write`` removes a shadowed patch, and a shadowed exception
fails the check.

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

from orthography2ipa import G2P, Pipeline, get as get_spec  # noqa: E402
from orthography2ipa.lexicon import parse_lexicon_text  # noqa: E402
from orthography2ipa.version import VERSION_STR  # noqa: E402

import lexicon_build as lb  # noqa: E402
import o2i_harness  # noqa: E402
import o2i_lexicons  # noqa: E402
from o2i_lexicons.schema import validate_meta, validate_tsv  # noqa: E402


def stale_entries(code: str, entries: dict[str, str], bench, stress: str) -> list[str]:
    """The words of *entries* that the rules alone now transcribe right.

    *stress* is the ``stress`` field of the file's sidecar.
    """
    engine = G2P(code, expose_ambiguous_endings=False, pipeline=Pipeline(lexicon={}))
    extra = bench._prosody_marks(code)

    def norm(ipa: str, strip_stress: bool = True) -> str:
        return bench.normalize(ipa, strip_stress=strip_stress, broad=True, extra_strip=extra)

    stale = []
    for word, ipa in entries.items():
        try:
            rules = engine.transcribe_word(word)
        except Exception:
            continue
        hyp = norm(rules)
        if not hyp or hyp != norm(ipa):
            continue
        if stress == "rules" or lb.same_stress(norm(rules, False), norm(ipa, False)):
            stale.append(word)
    return sorted(stale)


def written_problems(tsv: Path, meta_file: Path, code: str, kind: str) -> list[str]:
    """The schema problems of a lexicon file and its sidecar as they are on disk."""
    text = tsv.read_text(encoding="utf-8")
    problems = [f"{tsv.name} line {n}: {p}" for n, p in validate_tsv(text, code)]
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    return problems + validate_meta(meta, code, parse_lexicon_text(text), kind)


def shadowed_entries(code: str, entries: dict[str, str]) -> list[str]:
    """The words of *entries* that the spec's ``word_exceptions`` hold."""
    exceptions = get_spec(code).word_exceptions
    return sorted(w for w in entries if w in exceptions)


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
            meta = json.loads(meta_of(code).read_text(encoding="utf-8"))
            stale = stale_entries(code, entries, bench, meta["stress"])
            shadowed = shadowed_entries(code, entries)
            report["codes"].setdefault(code, {})[kind] = {"entries": len(entries),
                                                          "stale": stale, "shadowed": shadowed}
            print(f"{code} {kind} file: {len(entries)} entries, {len(stale)} now right under "
                  f"orthography2ipa {VERSION_STR}, {len(shadowed)} shadowed by the spec's "
                  f"word_exceptions")
            for word in stale + shadowed:
                print(f"  {word}\t{entries[word]}")
            removed = sorted({*stale, *shadowed})
            if kind == "patch" and args.write and removed:
                for word in removed:
                    del entries[word]
                forget(meta, removed)
                meta["o2i_version"] = VERSION_STR
                written = lb.write_lexicon(tsv.parent, tsv.stem, entries, meta)
                problems = written_problems(*written, code, kind)
                if problems:
                    raise SystemExit(f"the pruned {code} {kind} file fails the schema:\n  "
                                     + "\n  ".join(problems))
    if args.report:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n",
                               encoding="utf-8")
    stale = {kind: sum(len(c[kind]["stale"]) + len(c[kind]["shadowed"])
                       for c in report["codes"].values() if kind in c)
             for kind in files}
    if stale["exception"]:
        print(f"{stale['exception']} exceptions are right under the rules or shadowed by the "
              f"spec, so their class is wrong; move each one by hand")
    return 1 if stale["exception"] or (stale["patch"] and not args.write) else 0


if __name__ == "__main__":
    sys.exit(main())
