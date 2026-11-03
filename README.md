# o2i-lexicons

Default residual lexicons for [orthography2ipa](https://github.com/TigreGotico/orthography2ipa).

A lexicon in this package holds only the words that the orthography2ipa rules get wrong and that no rule can fix. Each entry names the gold it came from, the tier and licence of that gold, and a reason class.

The package is enabled in code, never by installing it. An installed package changes no output until the caller enables it.

## Data layout

Each language has one directory, `o2i_lexicons/data/<code>/`. It holds two files:

| File | Content |
| :--- | :--- |
| `<source>.tsv` | One `word<TAB>ipa` pair per line. UTF-8, NFC, lowercase words, sorted, no duplicate word. |
| `<source>.meta.json` | The source dataset, its URL, tier and licence, the build command, the orthography2ipa version whose rules got each entry wrong, where the stress of the entries comes from, and the reason class of each word. |

`o2i_lexicons/schema.py` states the contract, and the tests apply it to every packaged file.

A reason class is one of `loanword`, `proper_noun`, `lexical_stress`, `irregular`, `acronym` or `homograph_default`. Each of these claims a linguistic fact, so the sidecar states the evidence for each class in use. A word that has no evidence other than the data is `unclassified`.

Only a gold that can gate a quality decision in orthography2ipa can supply entries. A silver set (LLM-generated or engine-pinned) never does, and neither does the output of a system that orthography2ipa benchmarks against.

`stress` is `source` when the entries carry the stress marks of their source. It is `rules` when the source has no stress marks: the file then holds none, and the orthography2ipa stress rules place the stress on output.

## How orthography2ipa uses a lexicon

The package declares one entry point per language code in the group `orthography2ipa.lexicons`. Each entry point loads `o2i_lexicons.tsv_path`, and orthography2ipa calls it with the code. The entry point only makes the lexicon discoverable. The transcription is a function of the spec and the input, never of the environment, so the caller enables the lexicon in code:

```python
import orthography2ipa as o2i

o2i.use_packaged_lexicons()            # every installed packaged lexicon
o2i.use_packaged_lexicons(["en-GB"])   # only these
o2i.clear_lexicons()                   # disable them again
```

A lexicon that the caller registers with `register_lexicon` or `set_lexicon_dir` wins over a packaged one. The `word_exceptions` of a spec win over both. The package's own API:

```python
import o2i_lexicons

o2i_lexicons.available_codes()     # the packaged codes
o2i_lexicons.tsv_path("en-GB")     # the TSV file for a code
o2i_lexicons.load_meta("en-GB")    # its sidecar
```

## Packaged lexicons

| Code | File | Source | Tier | Licence |
| :--- | :--- | :--- | :--- | :--- |
| `en-GB` | `o2i_lexicons/data/en-GB/wikipron.tsv` | [WikiPron](https://github.com/CUNY-CL/wikipron) `eng_latn_uk_broad.tsv`, scraped from Wiktionary | crowd-scraped | CC BY-SA 4.0 |

Stress on the en-GB entries comes from the orthography2ipa rules, not from the source. WikiPron scrapes Wiktionary with stress removed (`"stress": False` in its `data/scrape/lib/scrape.py`), so the published file holds no stress mark. The sidecar records this as `"stress": "rules"`, and the orthography2ipa stress rules mark each entry on output, as they mark an entry of `word_exceptions`.

## Build, measure and prune

The scripts run the installed orthography2ipa. They score with the board harness of orthography2ipa at the git tag of that version, which they check out once under `.cache/o2i-harness/`. They read gold files from `.cache/gold/`.

```bash
python scripts/build_lexicon.py en-GB wikipron --report build-report.json
python scripts/measure.py en-GB ipadict:en-GB cmudict:en
python scripts/prune_check.py
```

`build_lexicon.py` keeps a word only when the rules get it wrong under the board's scoring. Words that share a spelling pattern and the same error at it form a lead. A lead is a question for the linguistic literature, not a rule. Its words stay out of the lexicon until a cited source states a rule for the pattern, or states that the pattern is lexical. The build report lists each lead.

`measure.py` scores a lexicon on a gold from a different source, with the rules only and with the lexicon. It refuses the gold that supplied the lexicon.

`prune_check.py` exits with status 1 when the rules alone now get an entry right. CI runs it on each pull request, and a weekly job removes the stale entries and opens a draft pull request.

## Licence

The code is Apache-2.0. Each data file keeps the licence of its source, which its `.meta.json` sidecar states. The `en-GB` file is CC BY-SA 4.0, the licence of the Wiktionary text it comes from.
