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

The package declares one entry point per language code in the group `orthography2ipa.lexicons`. Each entry point loads `o2i_lexicons.tsv_path`, and orthography2ipa calls it with the code. The entry point only makes the lexicon discoverable. The transcription is a function of the spec and the input, never of the environment, so the caller passes the lexicon to the engine:

```python
from orthography2ipa import G2P, Pipeline, packaged_lexicon

engine = G2P("en-GB", pipeline=Pipeline(lexicon=packaged_lexicon("en-GB")))
```

The lexicon belongs to that engine. Another engine in the process does not see it, and an engine with no pipeline runs on the rules. The `word_exceptions` of a spec win over the lexicon. The package's own API:

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
| `pt-BR` | `o2i_lexicons/data/pt-BR/nilc.tsv` | The training file of the NILC Aeiouadô transcriber (`etc/unitex_sample_transcribed.txt`), human-revised by one research team and not independently verified, with some readings from hand-typed pt.wiktionary lines | expert-human | CC BY-SA 4.0 |

Stress on the en-GB entries comes from the orthography2ipa rules, not from the source. WikiPron scrapes Wiktionary with stress removed (`"stress": False` in its `data/scrape/lib/scrape.py`), so the published file holds no stress mark. The sidecar records this as `"stress": "rules"`, and the orthography2ipa stress rules mark each entry on output, as they mark an entry of `word_exceptions`.

The pt-PT entries are the Infopédia rows of the dataset: the rows with an `infopedia_url`, including the rows that Infopédia and Wiktionary share with the same reading. Infopédia transcribes the European Portuguese standard, and the orthography2ipa `pt-PT` spec models that standard. A lexicon on `pt-PT` does not reach its child lects, such as `pt-PT-x-lisbon`.

The entries carry the stress marks of Infopédia (`"stress": "source"`). Infopédia writes three sounds with other symbols than the spec does, and the build writes the spec's symbols:

| Infopédia | Spec | Sound |
| :--- | :--- | :--- |
| `ə` | `ɨ` | the reduced vowel, an allophone of `ɨ` in the spec |
| `r` | `ɾ` | the tap |
| `ʀ` | `ʁ` | the strong rhotic |

A reading that writes `r` where the spelling has the strong rhotic (an initial `r`, `rr`, or `r` after `n`, `l` or `s`) is left out, because there `r` is not the tap. Infopédia writes an optional vowel as `(ə)`. The dataset gives both forms, and the entry takes the full form, as the spec writes the vowel. The rows that the corrections overlay of the orthography2ipa board lists are left out: they contradict a written accent, lack the stress mark, or transcribe another headword.

Infopédia transcribes the Lisbon (Estremenho) speech, and the `pt-PT` spec models the more conservative norm. The `pt-PT-x-lisbon` notes list the Lisbon deltas, and the build treats each one that Infopédia carries:

| Lisbon delta | Infopédia | pt-PT spec | Build |
| :--- | :--- | :--- | :--- |
| ⟨ei⟩, and ⟨e⟩ before ⟨x⟩ | [ɐj] (leite, êxito) | [ej] (leite `ˈlejtɨ`) | writes [ej] where the rules read the vowel as ⟨e⟩, or read an English ⟨a⟩ for [eɪ] (basebol) as [a] or [ɐ]; leaves any other [ɐj] out (rugby), except in a word spelled with ⟨ai ay aj⟩ |
| stressed ⟨e⟩ before a palatal | [ɐ] (espelho, coelho) | [e] or [ɛ], by word | leaves the word out, because the vowel cannot be recovered |
| ⟨ou⟩ | [o] | [o] | nothing to do |
| the strong rhotic and the reduced vowel | [ʀ], [ə] | [ʁ], [ɨ] | writes the spec symbols |

Infopédia marks the nasality of a nasal diphthong once, on the glide (trem `ˈtɾɐj̃`, tensão `tẽˈsɐw̃`). The spec writes the nucleus nasal too, [ɐ̃j̃] and [ɐ̃w̃] (Mateus & d'Andrade 2000), so the build writes `ɐj̃` as `ɐ̃j̃` and `ɐw̃` as `ɐ̃w̃`.

The build compares the rules with the mapped reading, so a word whose only difference was [ɐj] against [ej] is not a rules miss. A reading with a stress mark between a consonant and the vowel after it (yakuza `jakˈuzɐ` for `jaˈkuzɐ`) places the mark inside the onset, and the build takes the next reading of the word or leaves the word out.

Each token of an entry must be in the spec's token inventory. A nasal glide after a nasal vowel counts as inside it when the spec emits that glide in a nasal diphthong (mãe `ˈmɐ̃j̃`), so proibição `pɾuibiˈsɐ̃w̃` can be an entry. `build_lexicon.py --excluded` lists each reading and headword that the build leaves out, with the reason.

Three kinds of word are residual words in pt-PT too, because the spelling cannot show the fact: the height of a stressed mid vowel (orthography2ipa#1824), the value of an ⟨x⟩ before a vowel or at the end of a word ([ʃ] xadrez, [ks] táxi, [z] exame, [s] próximo), and ⟨qu gu⟩ with [w] before ⟨e i⟩ (cinquenta). `lexical_class` finds a word that differs from the rules in these only, and that word never joins a lead. The comparison keeps every difference that the board scores.

An unstressed vowel is a residual class too, in four slots where the rules give a default and a word can take another value: an initial ⟨o⟩ or ⟨ho⟩ before a consonant ([ɔ o u]: odrada [o], honesto [u]), an initial ⟨e⟩ or ⟨he⟩ before a consonant ([i e ɛ]: ebó [e]), ⟨a e o⟩ before a coda ⟨l⟩ (golpada [ɔ]), and ⟨a e o⟩ before a coda stop (adactilia [a]). A fifth slot is the vowel where AO90 dropped a silent ⟨c p⟩ (ativo [a] from activo). Cunha & Cintra (p. 53) state that a learned word keeps this vowel unreduced. The build finds the dropped consonant with `--preao`, the aspell `pt_PT-preao` word list: the form with ⟨c⟩ or ⟨p⟩ restored must be in the list and must not be a pt-PT headword of its own (pacto beside pato). In a slot, the entry may take only a value of the vowel letter that the orthography2ipa lattice ranks at that grapheme (`G2P.ipa_lattice`). The Lisbon [ɐ] for an initial ⟨e⟩ is never a value. A word that differs from the rules in any other place is not a residual word. A reading with two primary stresses has no class.

A word under a cited rule stays a lead: a word that a `PT_LEX_CLOSE_*` or `PT_LEX_OPEN_*` rule lists, a written accent, and a rhizotonic present form of a verb of the first or second conjugation with ⟨e⟩ or ⟨o⟩ in the stem. Cunha & Cintra (pp. 429-433) give the stem vowel of such a form by the models levar, lograr, dever and mover and their stated exceptions, and a noun with the same spelling can have the other height (rogo, gosto). `lexicon_build.rhizotonic_verb_form` finds the form when the source holds its infinitive.

A word that the rules get wrong, and that no lead holds out, must pass four more tests before it becomes a pt-PT entry. A residual word must pass the first three tests only, and it is out when no source agrees with it and pt.wiktionary or WikiPron pt-PT gives the rules' reading: one source against one does not settle the word, so the rules keep it. `build_lexicon.py --screened` lists each word with the test it fails, or with the sources that agree with it. The sidecar field `lexical_classes` names each residual entry, its class, and the second sources that agree with it, or `no second source`.

1. The reading is of the same headword. An Infopédia row can transcribe a neighbouring headword or a cut reading. The first syllable must start with a consonant of the same class, and the consonants differ by at most one edit plus one per four consonants. The syllable count is the same, or differs by one where a vowel deletes or a glide forms. The reading ends on the same consonant class and keeps a final coda. This test also drops some correct loanwords, such as *kiwi* and *pipeline*.
2. The word is not a one-letter headword, an interjection spelled as a vowel and ⟨h⟩ (*ah*, *eh*, *oh*), a closed-class word, or a homograph with two readings by sense (*pola*: the archaic contraction [pulɐ] and the noun [ˈpɔlɐ]), because the lexicon cannot choose by context. A word in the bifonia list of heterophonic homographs is out for the same reason. A dictionary reads these as a letter name or a stressed citation form, which would replace the reduced article *o* [u] in every sentence. A closed-class word is one that the spec reads unstressed (`stress.cliticless_words`), or that a row of the dataset tags as a preposition, conjunction, determiner, pronoun or contraction, or a demonstrative or its contraction with ⟨de em a⟩ (Cunha & Cintra p. 343: *esta*, *neste*, *daquele*, *mesmo*).
3. The only difference from the rules is not an open orthography2ipa defect, such as ⟨ã⟩ read [ã] (*afã*, *fã*). Such an entry would hide the defect. `lexicon_build.OPEN_RULE_BUGS` lists each defect by its issue number. A reading that a hand check found wrong is also left out (`lexicon_build.KNOWN_SOURCE_DEFECTS`), and so is a reading with the Lisbon [ɐ] before a palatal or a Lisbon [ɐj] that has no pt-PT [ej].
4. A second source gives the same reading: a hand-typed pt.wiktionary reading for European Portuguese or with no region, or WikiPron pt-PT where it gives the word exactly one reading. A dataset row merged from Infopédia and pt.wiktionary repeats the Infopédia reading, so its agreement is recorded, but it keeps no entry on its own. WikiPron pt comes from the en.wiktionary `{{pt-IPA}}` template, which lists several variants for many words, and a match against one of them is no evidence. The Lisbon reading of the Portal da Língua Portuguesa is generator output: its agreement is recorded, but it keeps no entry on its own. The stress is compared only where both readings mark it, and WikiPron marks none.

## Build, measure and prune

The scripts run the installed orthography2ipa. They score with the board harness of orthography2ipa at the git tag of that version, which they check out once under `.cache/o2i-harness/`. They read gold files from `.cache/gold/`.

```bash
python scripts/build_lexicon.py en-GB wikipron --report build-report.json
python scripts/build_lexicon.py pt-PT infopedia --homographs heterophonic_homographs.csv \
    --preao preao_words.txt --report build-report.json
python scripts/build_lexicon.py pt-BR nilc --nilc unitex_sample_transcribed.txt \
    --michaelis entries.jsonl --homographs heterophonic_homographs.csv \
    --report build-report.json
python scripts/measure.py en-GB ipadict:en-GB cmudict:en
python scripts/measure.py pt-PT ep_dialects:pt-PT wikipron:pt-PT
python scripts/prune_check.py
```

`build_lexicon.py` keeps a word only when the rules get it wrong under the board's scoring. Words that share a spelling pattern and the same error at it form a lead. A lead is a question for the linguistic literature, not a rule. Its words stay out of the lexicon until a cited source states a rule for the pattern, or states that the pattern is lexical. The build report lists each lead.

`measure.py` scores a lexicon on a gold from a different source, with the rules only and with the lexicon. It refuses the gold that supplied the lexicon, and the board dataset that holds that gold. The pt-PT screen keeps the entries outside the residual classes only when a second source corroborates them, WikiPron pt-PT among them, so a pt-PT measure on WikiPron is not independent of the selection. The residual entries that WikiPron does not corroborate are independent of it. `ep_dialects` is a small expert-human set of European Portuguese sentences that no build reads.

`prune_check.py` exits with status 1 when the rules alone now get an entry right. CI runs it on each pull request, and a weekly job removes the stale entries and opens a draft pull request.

## The pt-BR lexicon

The NILC file transcribes the speech of São Paulo city, so the entries could go under `pt-BR` or under `pt-BR-x-sp`. The file's features fit neither spec without a map:

| Feature | NILC file | `pt-BR` | `pt-BR-x-sp` |
| :--- | :--- | :--- | :--- |
| Strong rhotic | [x] | [ʁ] | [x], [ɣ] between voiced sounds |
| Coda rhotic | [x], [ɣ] before a voiced sound | [ɾ] | [ɾ] |
| Final ⟨r⟩ of an infinitive | kept | dropped | dropped |
| Yod before a final /S/ | none | none | a stressed vowel takes it |
| Final vowels | [ɪ ʊ ə] | [i u ɐ] | [i u ɐ] |

The entries go under `pt-BR`. What the rules cannot reach is lexical: the quality of a stressed mid vowel and the value of ⟨x⟩. Those facts are not São Paulo facts, and the `pt-BR-x-sp` yod contradicts the file. A lexicon on `pt-BR` does not reach its child lects.

`lexicon_build.nilc_to_pt_br` writes each reading in the `pt-BR` norm before the comparison with the rules. A word that differs from the rules only in the São Paulo features is rules-right, so it never becomes an entry.

Three kinds of word are residual words, because the spelling cannot show the fact: the height of a stressed mid vowel (orthography2ipa#1824), ⟨x⟩ as [ks] (táxi, fixo), and ⟨qu gu⟩ with [w] before ⟨e i⟩ (frequente). `lexical_class` finds a word that differs from the rules in these only, and that word never joins a lead. A word under a cited rule stays a lead: a word that a `PT_LEX_CLOSE_*` or `PT_LEX_OPEN_*` rule lists, a written accent, and a vowel before a nasal, which `BR_NASAL_STRESSED_*` closes. Every other shared miss is a rule lead for the specs.

A word that the rules get wrong, and that no lead holds out, must pass the tests of `screen_nilc`. It reads the same headword as the rules, and it is not a closed-class word. It is no homograph: a verb form and a noun or adjective with one spelling can differ in the stressed mid vowel, and a word in the bifonia list of heterophonic homographs is out for the same reason. A second independent source must then give the same reading. That source is a hand-typed pt.wiktionary Brazil line, Michaelis, or WikiPron pt-BR where it gives the word one reading. WikiPron pt-BR is the output of the `{{pt-IPA}}` template, so it counts only as it does for pt-PT. The published Aeiouadô lexicon is machine-generated and never counts.

Michaelis prints a broad notation, so it counts only for the stress and the height of the stressed vowel. `same_stress` aligns two readings sound by sound and asks whether their stressed vowels pair, so a post-tonic glide against a hiatus, the epenthetic [i] and a dropped infinitive ⟨r⟩ are no stress difference. Michaelis is editor-made and its method is unstated, and it has defects of its own. Some entries put the stress mark on the wrong vowel (chato [ʃa′tu], ousadia [owz′adiә]), and some print the reading of another word (erótico [eroz′ivu]). So a Michaelis reading never stands alone, and it never supplies an entry.

The build also mines the words that Michaelis and a hand-typed pt.wiktionary Brazil line hold and the NILC file does not. The reading comes from the pt.wiktionary line, and Michaelis corroborates it. So such a line may differ from the rules only in the height of the stressed vowel, and the entry is the rules' reading with that height. The sidecar field `wiktionary_readings` names these words.

The Michaelis readings are "all rights reserved" and stay out of this repository. A Michaelis agreement keeps an entry, and the entry holds a reading of the NILC file or of pt.wiktionary.

## Licence

The code is Apache-2.0. Each data file keeps the licence of its source, which its `.meta.json` sidecar states. The `en-GB` file is CC BY-SA 4.0, the licence of the Wiktionary text it comes from. The `pt-PT` file is CC BY-SA 4.0, the licence that the card of the portuguese-unified dataset states. The `pt-BR` file is CC BY-SA 4.0, because it holds pt.wiktionary readings beside the NILC readings. The NILC readings are BSD 3-Clause, Copyright (c) 2014, Gustavo Mendonça, and `o2i_lexicons/data/pt-BR/LICENSE.nilc` holds that notice.
