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

## Licence

The code is Apache-2.0. Each data file keeps the licence of its source, which its `.meta.json` sidecar states.
