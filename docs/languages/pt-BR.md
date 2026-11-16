# pt-BR

The `pt-BR` lexicon serves the o2i `pt-BR` spec. Its file is `nilc.tsv` in both kind directories.

## Source

Most readings come from `etc/unitex_sample_transcribed.txt`, the training file of the NILC [Aeiouadô](https://github.com/dash219/aeiouado_g2p) grapheme-to-phoneme converter. The sidecar field `source_url` names the file at a fixed commit. The o2i ladder places this file on the `expert-human` tier. The Aeiouadô README says that the converter follows the dialect of the city of São Paulo.

Some readings come from hand-typed Brazil lines of [pt.wiktionary](https://pt.wiktionary.org/). The sidecar field `wiktionary_readings` lists those words. The published Aeiouadô lexicon is machine output, and the build never takes a reading from it.

## From the NILC notation to the pt-BR norm

The NILC file transcribes São Paulo speech, and the `pt-BR` spec writes a broader norm. The entries go under `pt-BR` and not under `pt-BR-x-sp`, because the facts that the rules cannot reach are lexical, not regional. `lexicon_build.nilc_to_pt_br` writes each reading in the `pt-BR` norm before the build compares it with the rules:

| Feature | NILC file | `pt-BR` spec |
| :--- | :--- | :--- |
| Strong rhotic | [x] | [ʁ] |
| Coda rhotic | [x], and [ɣ] before a voiced sound | [ɾ] |
| Final ⟨r⟩ of an infinitive | kept | dropped |
| Final vowels | [ɪ ʊ ə] | [i u ɐ] |

A word that differs from the rules only in these features is right under the rules, so it never becomes an entry.

## How the build selects an entry

A word that differs from the rules only in a fact that the spelling cannot show is a residual word. Three facts count: the height of a stressed mid vowel ([orthography2ipa#1824](https://github.com/TigreGotico/orthography2ipa/issues/1824)), ⟨x⟩ as [ks] (táxi, fixo), and ⟨qu gu⟩ with [w] before ⟨e i⟩ (frequente). A residual word never joins a lead.

A residual word stays a lead, with no entry, when a cited o2i rule decides the height of its stressed vowel. That is the case for a word that a `PT_LEX_CLOSE_*` or `PT_LEX_OPEN_*` rule lists, a written accent on ⟨é ê ó ô⟩, and a vowel before a nasal, which `BR_NASAL_STRESSED` closes (`lexicon_build.cited_rule_reason`).

Every other word must pass the tests of `screen_nilc` in `scripts/build_lexicon.py`:

1. The reading is of the same headword as the rules' reading.
2. The word is not a closed-class word.
3. The word is not a homograph with two readings by sense. A verb form and a noun with one spelling can differ in the stressed vowel. A word in the [bifonia](https://github.com/TigreGotico/bifonia) list of heterophonic homographs is out for the same reason.
4. A hand check did not find the reading wrong (`lexicon_build.KNOWN_SOURCE_DEFECTS`).
5. A second source gives the same reading: a pt.wiktionary Brazil line, [Michaelis](https://michaelis.uol.com.br/), or WikiPron pt-BR where it gives the word one reading.

Michaelis prints a broad notation, so it counts only for the stress and the height of the stressed vowel. Some Michaelis entries put the stress on the wrong vowel or print the reading of another word, so a Michaelis reading never supplies an entry. The build also takes the words that Michaelis and a pt.wiktionary Brazil line hold and the NILC file does not. The reading comes from pt.wiktionary, and it may differ from the rules only in the height of the stressed vowel.

## Kinds

| Kind | Classes |
| :--- | :--- |
| Exception | the height of a stressed mid vowel, and the value of ⟨x⟩ |
| Patch | the stem vowel of a verb form that the NILC file tags only as a verb, the ⟨s⟩ of trans- before a vowel, and a loan spelled outside the native system |

The stem vowel of a rhizotonic present form follows the model verbs of Cunha & Cintra (*Nova Gramática do Português Contemporâneo*, pp. 429-433), so a rule can read it. The sidecars give the exact citation or gap of each word.

## Known limits

The sidecars do not record which second source agreed with each entry.

The build reads a Michaelis snapshot that is all rights reserved. The snapshot is not in this repository. It is `raw/entries.jsonl` of the private dataset [TigreGotico/michaelis-brazilian-portuguese-transcriptions](https://huggingface.co/datasets/TigreGotico/michaelis-brazilian-portuguese-transcriptions), so only project members can rebuild the pt-BR files.

A lexicon on `pt-BR` does not reach a child lect such as `pt-BR-x-sp`.

## License

The files are CC BY-SA 4.0, because they hold pt.wiktionary readings beside the NILC readings. The NILC readings are BSD 3-Clause, Copyright (c) 2014, Gustavo Mendonça, and `LICENSE.nilc` beside each file holds that notice.

---
[← en-GB](en-GB.md) · [Home](../index.md) · [pt-PT →](pt-PT.md)
