# o2i-lexicons documentation

o2i-lexicons ships per-language lexicons for [orthography2ipa](https://github.com/TigreGotico/orthography2ipa) (o2i). The [README](../README.md) shows how to install the package and give a lexicon to an engine. These pages hold the detail.

Read the pages in this order:

1. [Exceptions and patches](kinds.md): the two kinds of entry, which kind wins, and how the package drops a patch when its rule lands.
2. [Data format](data-format.md): the TSV files, the `.meta.json` sidecars, the entry points and the Python API.
3. [en-GB](languages/en-GB.md): the WikiPron data, the Britfone check and the Received Pronunciation target.
4. [pt-BR](languages/pt-BR.md): the NILC data and the map to the `pt-BR` norm.
5. [pt-PT](languages/pt-PT.md): the Infopédia data and the map to the `pt-PT` norm.
6. [Building and pruning](building.md): the build, measure and prune scripts, their inputs, and the CI jobs.
7. [Rule leads](leads.md): the spelling patterns that the patch gaps name, with their evidence, and the leads that wait for a source.
8. [Contributing](contributing.md): how to add or correct an entry, and when an entry is a patch.

The o2i side of the contract is in the o2i [lexicon guide](https://github.com/TigreGotico/orthography2ipa/blob/dev/docs/guide/lexicon.md).
