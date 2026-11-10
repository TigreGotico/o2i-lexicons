# en-GB

The `en-GB` lexicon serves the o2i `en-GB` spec, which models Received Pronunciation (RP). Its file is `wikipron.tsv` in both kind directories.

## Source

The readings come from [WikiPron](https://github.com/CUNY-CL/wikipron), file `eng_latn_uk_broad.tsv`. WikiPron scrapes the British English pronunciations of [Wiktionary](https://en.wiktionary.org/). The data is crowd-written, so its tier is `crowd-scraped`, and its license is CC BY-SA 4.0, the license of the Wiktionary text. The sidecar field `source_url` names the exact file.

WikiPron removes the stress marks when it scrapes, with `"stress": False` in its scrape configuration. So the en-GB files hold no stress mark, and the sidecar gives `"stress": "rules"`. The o2i stress rules place the stress of an entry on output.

## How the build selects a reading

The build keeps a word only when the o2i rules read it wrong under the scoring of the o2i benchmark board. WikiPron often gives a word several readings, some of them in other accents. The build takes an entry only from a reading that fits RP. `ACCENT_SCREENS` in `scripts/build_lexicon.py` lists the tests. One of them refuses a rhotic reading (`lexicon_build.rhotic_segment`). The module docstring of `build_lexicon.py` states how the build chooses among the readings that pass. A word with no reading that passes leaves the lexicon, and `build_lexicon.py --excluded` lists it with its readings.

The build never edits a reading. It chooses among the readings that the source gives.

## Kinds

An en-GB exception is a name or an acronym, because no spelling rule gives the reading of a name. The build finds both classes from the capital letters of the WikiPron headword, and the sidecar field `reason_basis` states the test. The citation of an en-GB exception names where the reading comes from. It does not cite a source for the class.

Every other en-GB entry is a patch. An inflection in -s, -es, -ies, -ed or -ing whose base is a WikiPron headword with no entry has the gap `lead: en-GB inflection morphology`. The rules read the base right, so a morphology rule could read the inflection. Any other patch has the gap `lead: en-GB spelling rules not audited`.

## Known limits

WikiPron gives no part of speech. So a capitalised word that is not a name, such as a proper adjective, can become an exception.

The spec's `word_exceptions` win over the lexicon, so an entry for a word that the spec lists would never apply. `prune_check.py` reports such an entry.

Every en-GB patch names a lead, not an o2i pull request. A patch leaves the package only when an o2i rule change reads its word right.

---
[← Data format](../data-format.md) · [Home](../index.md) · [pt-BR →](pt-BR.md)
