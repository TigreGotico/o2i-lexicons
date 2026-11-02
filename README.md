# o2i-lexicons

Default residual lexicons for [orthography2ipa](https://github.com/TigreGotico/orthography2ipa).

A lexicon in this package holds only the words that the orthography2ipa rules get wrong and that no rule can fix. Each entry names the gold it came from, the tier and licence of that gold, and a reason class.

The package is opt-in. orthography2ipa without it behaves exactly as it does without any lexicon.

## Licence

The code is Apache-2.0. Each data file keeps the licence of its source, which its `.meta.json` sidecar states.
