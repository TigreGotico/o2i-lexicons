# en-GB

The `en-GB` lexicon serves the o2i `en-GB` spec, which models Received Pronunciation (RP). Its file is `wikipron.tsv` in both kind directories.

## Sources

The readings come from [WikiPron](https://github.com/CUNY-CL/wikipron), file `eng_latn_uk_broad.tsv`. WikiPron scrapes the British English pronunciations of [Wiktionary](https://en.wiktionary.org/). The data is crowd-written, so its tier is `crowd-scraped`, and its license is CC BY-SA 4.0, the license of the Wiktionary text. The sidecar field `source_url` names the file at a fixed WikiPron commit, and `source_sha256` gives its sha256. The build refuses any other file.

WikiPron removes the stress marks when it scrapes, with `"stress": False` in its scrape configuration. So the en-GB files hold no stress mark, and the sidecar gives `"stress": "rules"`. The o2i stress rules place the stress of an entry on output.

A second source chooses among the WikiPron readings of a word: [Britfone](https://github.com/JoseLlarena/Britfone) 3.0.1, file `britfone.main.3.0.1.csv`. Its README calls it a "British English (RP/Standard Southern British) pronunciation dictionary" of more than 16,000 entries, and its license is MIT. The sidecar field `agreement_source` names the file at a fixed Britfone commit, with its sha256, and the build refuses any other file. Britfone gives no entry of its own. It only confirms a WikiPron reading.

Britfone is not fully independent of WikiPron. Its README says that its transcriptions start from cmudict and take the British readings from Wiktionary, Wikipedia and the Collins, Oxford, Cambridge and Macmillan dictionaries.

## How the build selects a reading

The build keeps a word only when the o2i rules read it wrong under the scoring of the o2i benchmark board. The module docstring of `scripts/build_lexicon.py` states the full procedure. For en-GB, a word goes through these steps in order:

1. The word leaves when the spec's `word_exceptions` hold it, because the spec wins over a lexicon.
2. The word needs no entry when the rules give one of its WikiPron readings.
3. The accent screens of `ACCENT_SCREENS` remove each reading that RP does not have. A word whose every reading fails a screen leaves the lexicon.
4. The word leaves when it is a homograph with two readings by sense, such as `bases` or `drawer` (`lexicon_build.HOMOGRAPHS`). An entry cannot choose by sense.
5. The word needs no entry when the rules output agrees with a Britfone reading.
6. When WikiPron gives the word one reading and Britfone has no line for the word, that reading is the entry. Its `confirmation` is `single_reading`.
7. Otherwise the entry is the first reading that agrees with a Britfone reading, in the Britfone order. Its `confirmation` is `second_source`.
8. The word leaves when Britfone has no line for a word with several readings, when Britfone has only weak forms of the word, or when no reading agrees with Britfone. No entry is better than a guess, because an entry overrides the rules. Such a word still counts toward a lead.

The accent screens apply in this order:

| Screen | A reading fails when | Test |
| :--- | :--- | :--- |
| Rhotic | it has an r-coloured vowel, or an /r/ before a consonant or at the end of the word | `lexicon_build.rhotic_segment` |
| RP vowels | it has a vowel outside the RP vowels of Roach (2004, p. 243) | `lexicon_build.rp_vowel_outside` |
| Truncated | it has more than four letters per phone | `lexicon_build.truncated` |

Roach (2004), "British English: Received Pronunciation", *Journal of the International Phonetic Association* 34(2), p. 243, lists the RP vowels. The screen accepts the short vowels, the long vowels, the diphthongs, and the weak close vowels [i] (happy) and [u] (throughout). Roach writes DRESS as [e]. WikiPron and Britfone write [ɛ], and the screen reads it as [e].

A reading agrees with a Britfone reading when the two are the same in one RP notation (`lexicon_build.agrees`). The comparison drops the stress marks and the non-syllabic mark. It reads the Britfone [ɐ] as [ʌ], and it lets an unstressed weak vowel of Britfone match another weak vowel (`lexicon_build.WEAK_VOWELS`). The sidecar field `agreement_source.normalisation` states the same comparison.

The build never edits the sounds of a reading. It chooses among the readings that WikiPron gives. It drops only the non-syllabic mark and the tie bars, which the en-GB spec does not write.

## Confirmation

The sidecar field `confirmation` gives the basis of each entry, and `confirmation_basis` states what each value means:

| Value | Basis |
| :--- | :--- |
| `second_source` | the reading agrees with a stressed reading of Britfone |
| `single_reading` | WikiPron gives the word one reading, and Britfone has no line for the word |

A `single_reading` entry has no second check. It passed the accent screens, and no other source confirmed it. To count the entries of each value:

```bash
python -c "import collections, o2i_lexicons; print(collections.Counter(o2i_lexicons.load_meta('en-GB')['confirmation'].values()))"
```

## Kinds

An en-GB exception is a name or an acronym, because no spelling rule gives the reading of a name. The build finds both classes from the capital letters of the WikiPron headword, and the sidecar field `reason_basis` states the test. The citation of an en-GB exception names where the reading comes from and whether Britfone confirmed it. It does not cite a source for the class.

Every other en-GB entry is a patch. An inflection in -s, -es, -ies, -ed or -ing whose base is a WikiPron headword with no entry has the gap `lead: en-GB inflection morphology`. The rules read the base right, so a morphology rule could read the inflection. Any other patch has the gap `lead: en-GB spelling rules not audited`.

## Known limits

Most en-GB entries are `single_reading`, so no second source checked them.

WikiPron gives no part of speech. So a capitalised word that is not a name, such as a proper adjective, can become an exception.

Every en-GB patch names a lead, not an o2i pull request. A patch leaves the package only when an o2i rule change reads its word right.

---
[← Data format](../data-format.md) · [Home](../index.md) · [pt-BR →](pt-BR.md)
