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
| `pt-PT` | `o2i_lexicons/data/pt-PT/infopedia.tsv` | The Infopédia rows of [portuguese-unified-pronunciation-lexicon](https://huggingface.co/datasets/TigreGotico/portuguese-unified-pronunciation-lexicon), from the Porto Editora dictionary | lexicon-derived | CC BY-SA 4.0 |

Stress on the en-GB entries comes from the orthography2ipa rules, not from the source. WikiPron scrapes Wiktionary with stress removed (`"stress": False` in its `data/scrape/lib/scrape.py`), so the published file holds no stress mark. The sidecar records this as `"stress": "rules"`, and the orthography2ipa stress rules mark each entry on output, as they mark an entry of `word_exceptions`.

The pt-PT entries are the Infopédia rows of the dataset: the rows with an `infopedia_url`, including the rows that Infopédia and Wiktionary share with the same reading. Infopédia transcribes the European Portuguese standard, and the orthography2ipa `pt-PT` spec models that standard. A lexicon on `pt-PT` does not reach its child lects, such as `pt-PT-x-lisbon`.

The entries carry the stress marks of Infopédia (`"stress": "source"`). Infopédia writes three sounds with other symbols than the spec does, and the build writes the spec's symbols:

| Infopédia | Spec | Sound |
| :--- | :--- | :--- |
| `ə` | `ɨ` | the reduced vowel, an allophone of `ɨ` in the spec |
| `r` | `ɾ` | the tap |
| `ʀ` | `ʁ` | the strong rhotic |

A reading that writes `r` where the spelling has the strong rhotic (an initial `r`, `rr`, or `r` after `n`, `l` or `s`) is left out, because there `r` is not the tap. Infopédia writes an optional vowel as `(ə)`. The dataset gives both forms, and the entry takes the full form, as the spec writes the vowel. The rows that the corrections overlay of the orthography2ipa board lists are left out: they contradict a written accent, lack the stress mark, or transcribe another headword.

A word that the rules get wrong, and that no lead holds out, must pass four more tests before it becomes a pt-PT entry. `build_lexicon.py --screened` lists each word with the test it fails, or with the sources that agree with it.

1. The reading is of the same headword. An Infopédia row can transcribe a neighbouring headword or a cut reading. The first syllable must start with a consonant of the same class, and the consonants differ by at most one edit plus one per four consonants. The syllable count is the same, or differs by one where a vowel deletes or a glide forms. The reading ends on the same consonant class and keeps a final coda. This test also drops some correct loanwords, such as *kiwi* and *pipeline*.
2. The word is not a one-letter headword, an interjection spelled as a vowel and ⟨h⟩ (*ah*, *eh*, *oh*), or a closed-class word. A dictionary reads these as a letter name or a stressed citation form, which would replace the reduced article *o* [u] in every sentence. A closed-class word is one that the spec reads unstressed (`stress.cliticless_words`), or that a row of the dataset tags as a preposition, conjunction, determiner, pronoun or contraction.
3. The only difference from the rules is not an open orthography2ipa defect, such as ⟨ã⟩ read [ã] (*afã*, *fã*). Such an entry would hide the defect. `lexicon_build.OPEN_RULE_BUGS` lists each defect by its issue number.
4. A second source gives the same reading: WikiPron pt-PT, a pt.wiktionary reading for European Portuguese or with no region, or the Lisbon reading of the Portal da Língua Portuguesa. The stress is compared only where both readings mark it, and WikiPron marks none.

## Build, measure and prune

The scripts run the installed orthography2ipa. They score with the board harness of orthography2ipa at the git tag of that version, which they check out once under `.cache/o2i-harness/`. They read gold files from `.cache/gold/`.

```bash
python scripts/build_lexicon.py en-GB wikipron --report build-report.json
python scripts/build_lexicon.py pt-PT infopedia --report build-report.json
python scripts/measure.py en-GB ipadict:en-GB cmudict:en
python scripts/measure.py pt-PT wikipron:pt-PT
python scripts/prune_check.py
```

`build_lexicon.py` keeps a word only when the rules get it wrong under the board's scoring. Words that share a spelling pattern and the same error at it form a lead. A lead is a question for the linguistic literature, not a rule. Its words stay out of the lexicon until a cited source states a rule for the pattern, or states that the pattern is lexical. The build report lists each lead.

`measure.py` scores a lexicon on a gold from a different source, with the rules only and with the lexicon. It refuses the gold that supplied the lexicon, and the board dataset that holds that gold. The pt-PT screen keeps only the entries that a second source corroborates, WikiPron pt-PT among them, so a pt-PT measure on WikiPron is not independent of the selection.

`prune_check.py` exits with status 1 when the rules alone now get an entry right. CI runs it on each pull request, and a weekly job removes the stale entries and opens a draft pull request.

## Licence

The code is Apache-2.0. Each data file keeps the licence of its source, which its `.meta.json` sidecar states. The `en-GB` file is CC BY-SA 4.0, the licence of the Wiktionary text it comes from. The `pt-PT` file is CC BY-SA 4.0, the licence that the card of the portuguese-unified dataset states.
