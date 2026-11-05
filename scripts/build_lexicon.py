"""Build the residual lexicon of one language from one gold.

    python scripts/build_lexicon.py en-GB wikipron --cache .cache \\
        --report build-report.json
    python scripts/build_lexicon.py pt-PT infopedia --report build-report.json

The script runs the installed orthography2ipa over every word of the gold. It
keeps a word only when the rules get it wrong under the board's own scoring:
the PER against every gold reading of the word is above zero, after the
board's broad, stress-free normalisation. The entry is the first gold reading,
in the order the loader of the source gives, that is IPA-only and inside the
spec's phoneme inventory.

Words that share a spelling pattern and the same error at it form a lead. A
lead is a question for the linguistic literature, not a rule. Its words stay
out of the lexicon until a cited source settles the pattern, and the build
report lists every lead.

A source can screen the words that pass the leads (``screen_infopedia``).
An Infopédia entry must pass four tests, in this order:

1. It reads the same headword as the rules: the same first onset, nearly the
   same consonants, the same number of syllables up to one deleted vowel or
   formed glide, and the same end (``lexicon_build.other_reading_reason``).
2. It is not a closed-class word or a one-letter headword, whose dictionary
   reading is a citation form or a letter name
   (``lexicon_build.closed_class_reason``).
3. Its only difference from the rules is not an open orthography2ipa rule
   defect (``lexicon_build.OPEN_RULE_BUGS``).
4. A second source gives the same reading: WikiPron pt-PT, a pt.wiktionary
   reading, or the Portal da Língua Portuguesa Lisbon reading.

``--screened`` lists every word that reaches the screen, with the test it
fails, or ``kept`` and the sources that agree with it.

The gold must sit on a tier that can gate a quality decision in
orthography2ipa. A silver set or a competitor's output is refused.
"""
from __future__ import annotations

import argparse
import json
import shlex
import sys
from collections import Counter
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))

import orthography2ipa
from orthography2ipa.inventory import phoneme_inventory, tokenize as inventory_tokenize
from orthography2ipa.lexicon import is_ipa_string
from orthography2ipa.version import VERSION_STR

import lexicon_build as lb
import o2i_harness

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from o2i_lexicons.schema import ALLOWED_TIERS, STRESS_MARKS  # noqa: E402

#: The sources of the portuguese_unified gold that are Infopédia rows: an
#: Infopédia entry, and an entry with the same reading in Infopédia and in
#: Wiktionary.
INFOPEDIA_SOURCES = {"infopedia", "infopedia+wiktionary"}


#: The portuguese_unified region of the Portal readings that can corroborate
#: a pt-PT entry: the Portal's Lisbon standard.
PORTAL_LISBON = "pt-PT-x-lisboa"

#: The regions of the pt.wiktionary readings that can corroborate a pt-PT
#: entry: European Portuguese, and a reading with no region qualifier.
WIKTIONARY_REGIONS = {"pt-PT", "pt"}


def load_wikipron(bench, code: str):
    return bench.load_wikipron(code, sys.maxsize), Counter()


def load_infopedia(bench, code: str):
    """The ``(headword, reading)`` pairs of the Infopédia rows of the
    portuguese_unified gold, and the readings left out, by reason.

    Infopédia transcribes the European Portuguese standard, so only pt-PT
    takes them. A row that the board's corrections overlay lists is left out:
    its reading contradicts a written accent, lacks the stress mark, or
    transcribes another headword. A row with several readings, separated by
    commas, gives each of them in order. Each reading is put in the spec's
    symbols (``lexicon_build.INFOPEDIA_NOTATION``), except one that writes
    [r] where the spelling has the strong rhotic: there [r] is not the tap.
    """
    if code != "pt-PT":
        raise SystemExit(f"Infopédia transcribes European Portuguese; {code} cannot take it")
    region = bench._PT_UNIFIED_REGIONS[code]
    overlay = {(r["word"], r["source"], r["pos"], r["original_reading"])
               for r in bench.read_pt_unified_corrections()
               if r["region"] == region and r["field"] == "ipa_narrow"}
    text = bench._fetch(bench._PT_UNIFIED_URL, "portuguese_pronunciation_lexicon.jsonl")
    readings: dict[str, list[str]] = {}
    excluded = Counter()
    for line in text.splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        source = bench.pt_unified_source(row)
        if row.get("region") != region or source not in INFOPEDIA_SOURCES:
            continue
        word, ipa = row["word"], (row.get("ipa_narrow") or "").strip()
        if not word or not ipa:
            continue
        if (word, source, row.get("pos") or "", row.get("ipa_narrow")) in overlay:
            excluded["listed by the board's corrections overlay"] += 1
            continue
        for reading in filter(None, (r.strip() for r in ipa.split(","))):
            if lb.strong_r_is_ambiguous(word, reading):
                excluded["[r] where the spelling has the strong rhotic"] += 1
                continue
            readings.setdefault(word, []).append(reading)
    pairs = [(word, lb.infopedia_to_spec(reading)) for word, group in readings.items()
             for reading in lb.full_form_first(group)]
    return pairs, excluded


def infopedia_references(bench, engine, code: str):
    """The closed-class words of the language, and the readings of the
    sources that can corroborate an Infopédia reading, per lexicon key.

    A closed-class word is one that the spec reads unstressed
    (``stress.cliticless_words``), or that a portuguese_unified row tags with
    a closed-class part of speech (``lexicon_build.CLOSED_CLASS_POS``). A row
    that is in Infopédia and in pt.wiktionary has the same reading in both,
    so it corroborates its own reading.
    """
    region = bench._PT_UNIFIED_REGIONS[code]
    closed = {lb.lexicon_key(w) for w in engine.spec.stress.cliticless_words}
    references: dict[str, dict[str, list[str]]] = {
        "wikipron": {}, "wiktionary": {}, "portal_lisbon": {}}
    text = bench._fetch(bench._PT_UNIFIED_URL, "portuguese_pronunciation_lexicon.jsonl")
    for line in text.splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        word = lb.lexicon_key(row["word"])
        if row.get("pos") in lb.CLOSED_CLASS_POS:
            closed.add(word)
        source, where = bench.pt_unified_source(row), row.get("region")
        readings = [r.strip() for r in (row.get("ipa_narrow") or "").split(",") if r.strip()]
        if source == "infopedia+wiktionary" and where == region:
            readings, name = [lb.infopedia_to_spec(r) for r in readings], "wiktionary"
        elif source == "wiktionary" and where in WIKTIONARY_REGIONS:
            name = "wiktionary"
        elif source == "portal" and where == PORTAL_LISBON:
            name = "portal_lisbon"
        else:
            continue
        references[name].setdefault(word, []).extend(readings)
    for word, ipa in bench.load_wikipron(code, sys.maxsize):
        references["wikipron"].setdefault(lb.lexicon_key(word), []).append(ipa)
    return frozenset(closed), references


def screen_infopedia(bench, engine, code: str, kept: list[lb.Candidate],
                     norm: Callable[[str], str]):
    """The Infopédia words that pass the four tests of the module docstring,
    and one ``(candidate, rules, stage, reason)`` row per screened word."""
    closed, references = infopedia_references(bench, engine, code)

    def same(a: str, b: str) -> bool:
        return norm(a) == norm(b)

    def form(ipa: str) -> str:
        return bench.normalize(ipa, strip_stress=False, broad=True)

    passed, screened = [], []
    for c in kept:
        rules = engine.transcribe_word(c.headword)
        issues = lb.open_rule_bugs(code, c.headword, rules, c.ipa, same)
        sources = lb.corroborating_sources(c.word, c.ipa, references, form)
        for stage, reason in (
                ("same headword", lb.other_reading_reason(rules, c.ipa)),
                ("closed class", lb.closed_class_reason(c.headword, closed)),
                ("open rule bug", ", ".join(f"o2i#{n}" for n in issues) or None),
                ("uncorroborated", None if sources else "no second source agrees")):
            if reason is not None:
                screened.append((c, rules, stage, reason))
                break
        else:
            passed.append(c)
            screened.append((c, rules, "kept", "+".join(sources)))
    return passed, screened


#: dataset -> (loader, licence of the gold, the board dataset that holds it,
#: the screen of the words that pass the leads, or ``None``).
SOURCES = {
    "wikipron": (load_wikipron, "CC-BY-SA-4.0", "wikipron", None),
    "infopedia": (load_infopedia, "CC-BY-SA-4.0", "portuguese_unified", screen_infopedia),
}


def gold_url(bench, dataset: str, code: str) -> str:
    if dataset == "wikipron":
        return bench._WIKIPRON_BASE + bench._WIKIPRON_FILES[code]
    return bench._PT_UNIFIED_URL


#: Words listed per lead in the report; ``--held-out`` lists every word.
LEAD_EXAMPLES = 5


def held_out_rows(leads: list[lb.Lead]) -> list[str]:
    """One ``word<TAB>pattern<TAB>position<TAB>engine<TAB>gold`` row per held-out
    word, naming the largest lead that holds it."""
    first: dict[str, lb.Lead] = {}
    for lead in leads:                      # largest first
        for word in lead.words:
            first.setdefault(word, lead)
    return [f"{w}\t{l.pattern}\t{l.position}\t{l.engine}\t{l.gold}"
            for w, l in sorted(first.items())]


def build(code: str, dataset: str, cache: Path, min_lead: int, out_root: Path,
          command: str, held_out_file: Path | None = None,
          screened_file: Path | None = None) -> dict:
    bench = o2i_harness.load_benchmark(cache)
    loader, licence, board_dataset, screen = SOURCES[dataset]
    tier = bench.provenance_for(board_dataset, code)
    if tier not in ALLOWED_TIERS or not bench.can_gate_promotion(tier):
        raise SystemExit(f"{dataset}/{code} is on tier {tier!r}, which cannot supply entries")
    pairs, readings_excluded = loader(bench, code)

    golds: dict[str, list[str]] = {}
    for headword, gold in pairs:
        golds.setdefault(headword, []).append(gold)
    casings: dict[str, set[str]] = {}
    for headword in golds:
        casings.setdefault(lb.lexicon_key(headword), set()).add(headword)

    engine = orthography2ipa.G2P(code, expose_ambiguous_endings=False)
    spec = engine.spec
    inventory = phoneme_inventory(spec)
    extra = bench._prosody_marks(code)

    def norm(ipa: str) -> str:
        return bench.normalize(ipa, strip_stress=True, broad=True, extra_strip=extra)

    def usable(gold: str):
        for ipa in lb.storage_forms(gold):
            if is_ipa_string(ipa) and all(
                    t in inventory for t in inventory_tokenize(ipa, spec)):
                return ipa
        return None

    excluded = Counter()
    candidates: list[lb.Candidate] = []
    right = 0
    for headword, readings in golds.items():
        word = lb.lexicon_key(headword)
        if not lb.WORD_RE.match(headword):
            excluded["not a single word"] += 1
            continue
        if len(casings[word]) > 1:
            excluded["two source headwords differ only in case"] += 1
            continue
        try:
            hyp = norm(engine.transcribe_word(headword))
        except Exception:
            hyp = ""
        if not hyp:
            excluded["the engine gives no output"] += 1
            continue
        normed = [norm(g) for g in readings]
        if any(bench.levenshtein(hyp, g) == 0 for g in normed):
            right += 1
            continue
        ipa = lb.first_usable(readings, usable)
        if ipa is None:
            excluded["no gold reading is IPA-only and inside the inventory"] += 1
            continue
        candidates.append(lb.Candidate(headword, word, hyp, norm(ipa), ipa))

    leads = lb.find_leads(candidates, bench.align, min_lead)
    held = lb.held_out_words(leads)
    kept = [c for c in candidates if c.word not in held]
    screened: list[tuple[lb.Candidate, str, str, str]] = []
    if screen is not None:
        kept, screened = screen(bench, engine, code, kept, norm)
    entries = {c.word: c.ipa for c in kept}
    reasons = {c.word: lb.reason_for(c.headword) for c in kept}
    used = set(reasons.values()) - {"unclassified"}
    meta = {
        "code": code,
        "source": dataset,
        "source_url": gold_url(bench, dataset, code),
        "tier": tier,
        "licence": licence,
        "build_command": command,
        "o2i_version": VERSION_STR,
        "stress": "source" if any(m in ipa for ipa in entries.values()
                                  for m in STRESS_MARKS) else "rules",
        "reasons": reasons,
        "reason_basis": {r: lb.REASON_BASIS[r] for r in sorted(used)},
    }
    tsv, meta_file = lb.write_lexicon(out_root / code, dataset, entries, meta)
    if held_out_file is not None:
        held_out_file.write_text("\n".join(held_out_rows(leads)) + "\n", encoding="utf-8")
    if screened_file is not None:
        screened_file.write_text("word\tstage\treason\trules\treading\n" + "".join(
            f"{c.word}\t{stage}\t{why}\t{rules}\t{c.ipa}\n"
            for c, rules, stage, why in sorted(screened, key=lambda d: d[0].word)),
            encoding="utf-8")
    stages: dict[str, Counter] = {}
    for _, _, stage, why in screened:
        stages.setdefault(stage, Counter())[why] += 1
    return {
        "code": code,
        "dataset": dataset,
        "tier": tier,
        "licence": licence,
        "o2i_version": VERSION_STR,
        "harness_sha256": o2i_harness.harness_sha256(cache),
        "gold_rows": len(pairs),
        "gold_readings_excluded": dict(readings_excluded),
        "gold_headwords": len(golds),
        "rules_right": right,
        "excluded": dict(excluded),
        "rules_wrong_candidates": len(candidates),
        "min_lead_size": min_lead,
        "leads": [{"pattern": l.pattern, "position": l.position, "engine": l.engine,
                   "gold": l.gold, "size": len(l.words), "examples": l.words[:LEAD_EXAMPLES]}
                  for l in leads],
        "held_out_words": len(held),
        "screen": {stage: dict(reasons) for stage, reasons in stages.items()},
        "entries": len(entries),
        "entries_per_reason": dict(Counter(reasons.values())),
        "tsv": str(tsv.relative_to(ROOT)) if tsv.is_relative_to(ROOT) else str(tsv),
        "meta": str(meta_file.relative_to(ROOT)) if meta_file.is_relative_to(ROOT) else str(meta_file),
    }


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("code")
    ap.add_argument("dataset", choices=sorted(SOURCES))
    ap.add_argument("--cache", type=Path, default=ROOT / ".cache")
    ap.add_argument("--min-lead", type=int, default=10,
                    help="the smallest group of words that is a lead (default 10)")
    ap.add_argument("--out", type=Path, default=ROOT / "o2i_lexicons" / "data")
    ap.add_argument("--report", type=Path, help="write the build report here")
    ap.add_argument("--held-out", type=Path,
                    help="write each held-out word and its largest lead here")
    ap.add_argument("--screened", type=Path,
                    help="write each word that the source's screen tests, and its result, here")
    args = ap.parse_args(argv)
    command = "python scripts/build_lexicon.py " + shlex.join(
        [args.code, args.dataset, "--min-lead", str(args.min_lead)])
    report = build(args.code, args.dataset, args.cache, args.min_lead, args.out, command,
                   args.held_out, args.screened)
    text = json.dumps(report, ensure_ascii=False, indent=1)
    if args.report:
        args.report.write_text(text + "\n", encoding="utf-8")
    summary = {k: v for k, v in report.items() if k != "leads"}
    summary["leads"] = len(report["leads"])
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
