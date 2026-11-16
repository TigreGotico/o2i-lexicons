# Exceptions and patches

Every entry in o2i-lexicons is a word that the o2i rules transcribe wrong. The entry is one of two kinds, and the kind says why the lexicon holds it and when the word leaves.

## Exceptions

An exception is a word whose reading the spelling cannot give, so no spelling rule can reach it. Examples are the height of a stressed mid vowel in Portuguese, the value of ⟨x⟩ in Portuguese, and the reading of an English name. The exceptions of a code are in `o2i_lexicons/data/<code>/`.

Each exception has a note in the `citations` map of its sidecar. The note names the source that supports the class of the word, with the page or section. The reading itself comes from the source dataset of the file. An exception stays in the package while the o2i rules read by spelling.

## Patches

A patch is a word that a rule could reach, but the rules of the recorded o2i version read it wrong. The patches of a code are in `o2i_lexicons/data/patches/<code>/`.

Each patch has a note in the `gaps` map of its sidecar. The gap names what keeps the rules from the word. It can be an o2i pull request, a spec rule that misfires, or a lead that the note states. A lead is a spelling pattern that a group of words shares, together with one error at that pattern. A gap of the form `docs/leads.md § <section>` names a section of the [rule leads](leads.md) page, which lists every lead with its evidence.

## How the build assigns a kind

`scripts/entry_kinds.py` sorts each entry. An entry is an exception when its difference from the rules falls in a class that the spelling cannot show. A cited source must state that class. Every other entry is a patch. An entry with an exception part and a patch part is an exception, because it stays needed after the rule of its patch part lands. The language pages list the classes of each code.

No word is in both files of a code. The tests check this for every code.

## Which reading wins

`packaged_lexicon(code)` returns the exceptions only. `packaged_lexicon(code, patches=True)` returns the exceptions and the patches in one mapping. Inside that mapping, an exception wins over a patch of the same word.

Inside an engine, the `word_exceptions` of the o2i spec win over the lexicon, and the lexicon wins over the rules. An engine with no lexicon, or with `Pipeline(lexicon={})`, runs on the rules alone. The o2i [lexicon guide](https://github.com/TigreGotico/orthography2ipa/blob/dev/docs/guide/lexicon.md) states this contract.

## Which kinds to use

Use the exceptions alone when the rules must decide every word that a rule could reach. Add the patches when you want the source's reading for the words that the rules still miss. A patch rests on its source dataset and its gap, not on a citation. So it has less evidence behind it than an exception. [tugaphone](https://github.com/TigreGotico/tugaphone) reads both kinds for `pt-PT` and `pt-BR`.

## Pruning

`scripts/prune_check.py` transcribes every entry with the rules alone and compares the output with the entry. An entry that the rules now read right is stale. In a file with `"stress": "source"`, the rules must also stress the same vowel as the entry. The module docstring of the script states the exact comparison.

The check also reports an entry whose word the spec's `word_exceptions` hold. Such an entry never applies, because the spec wins over the lexicon. The check treats it as it treats a stale entry.

A stale patch is the expected result: the rule of its gap landed. `prune_check.py --write` removes the patch and its records from the sidecar. A stale exception means that its class is wrong, because the spelling does give its reading. The script lists the word and exits with status 1, also with `--write`, and never removes it. A person decides where the word goes.

The `Prune Check` workflow runs the check on each pull request against the latest o2i alpha. The `Prune Stale Entries` workflow runs once a week. It removes the stale patches, checks the result, and opens a draft pull request. [Building and pruning](building.md) gives the commands.

---
[Home](index.md) · [Data format →](data-format.md)
