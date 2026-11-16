# Contributing

The build scripts write every packaged file. A rebuild writes the TSV file and its sidecar again from the source. So a hand edit to a data file does not survive the next build. Make each change in the scripts, then rebuild the files that the change touches.

## Add or correct an entry

1. Find why the build gives the entry. Run the build with `--screened` and `--excluded`, and read the lines of the word.
2. Change the rule of the build that decides the word. A reading that a hand check finds wrong goes into `lexicon_build.KNOWN_SOURCE_DEFECTS`, with the reason. A homograph with two readings by sense goes into `lexicon_build.HOMOGRAPHS`. A new class or citation goes into `scripts/entry_kinds.py`.
3. Add a test that fails before the change and passes after it.
4. Rebuild the files of the code with the command in their `build_command` field. [Building and pruning](building.md) lists the input files.
5. Run `python -m pytest -q tests` and `python scripts/prune_check.py`.
6. Open a pull request to `dev`. Give it a conventional commit title, such as `fix(pt-PT): ...`, because the release workflow reads the title.

Never take a reading from the output of a language model, or from a system that o2i benchmarks against. The schema refuses a source on a tier that cannot gate a quality decision in o2i.

## Exception or patch

An entry is a patch unless a source shows that no spelling rule can reach it. That is the default, because a rule is better than a list: a rule also reads the words that no list holds.

An exception needs a citation. The citation names a source that states, for the class of the word, that the spelling cannot give the reading. It gives the page or the section. The dataset that supplies the reading is not a citation for the class. A frequency count or a pattern in a dataset is not a citation either. It is a lead, and it opens a search for a source.

A patch needs a gap. The gap names what keeps the rules from the word. It is an o2i pull request, a spec rule that misfires, or a lead that the note states. Write the gap so that a reader can find the rule that will retire the patch. When that rule lands, the prune job removes the patch.

When a source shows that a rule can reach a whole group of words, the right change is the rule in [orthography2ipa](https://github.com/TigreGotico/orthography2ipa), not more entries. The patches of that group then leave the package through the prune job.

---
[← Building and pruning](building.md) · [Home](index.md)
