# Data format

Each language code has two directories under `o2i_lexicons/data/`. The exceptions are in `<code>/`, and the patches are in `patches/<code>/`. Each directory holds one `<source>.tsv` file and its `<source>.meta.json` sidecar. `<source>` names the dataset that supplied the readings, such as `wikipron`, `infopedia` or `nilc`.

`o2i_lexicons/schema.py` states the contract, and `tests/test_packaged.py` applies it to every packaged file.

## The TSV file

Each line is one `word<TAB>ipa` pair. The file must pass `schema.validate_tsv(text, code)`, which applies these checks:

| Check | Rule |
| :--- | :--- |
| Encoding | UTF-8, with the word and the IPA in Unicode NFC |
| Word | lowercase, one TAB on the line, no duplicate word |
| IPA | IPA characters only, as `orthography2ipa.lexicon.is_ipa_string` accepts them |
| Inventory | each reading cuts into tokens of the phoneme inventory of the o2i spec for the code (`schema.outside_inventory`). A nasal glide counts only after a nasal vowel, as in mãe `ˈmɐ̃j̃`. |
| Order | the words are in sorted order, so that "first entry wins" is deterministic |
| End | the file ends with one newline |

A patch file can be empty. A directory with no TSV file, or with two, makes the loader raise `LookupError`.

The `stress` field of the sidecar says where the stress marks come from. With `source`, each entry carries the stress mark of its source. With `rules`, the file holds no stress mark, and the o2i stress rules place the stress on output. The o2i engine treats an entry the same way as an entry of the spec's `word_exceptions`.

## The sidecar

The sidecar is a JSON object. `schema.validate_meta` requires these keys:

| Key | Content |
| :--- | :--- |
| `kind` | `exception` or `patch`. It must match the directory of the file. |
| `code` | the language code, the same as the directory name |
| `source` | the name of the dataset that supplied the readings |
| `source_url` | where that dataset can be fetched |
| `tier` | the reliability tier of the dataset in the o2i ladder |
| `licence` | the SPDX id of the license of the dataset. The file keeps that license. |
| `build_command` | the command that built the file |
| `o2i_version` | the o2i version whose rules got each entry wrong: the version of the build, or of the last `prune_check.py --write` that removed an entry from the file |
| `stress` | `source` or `rules`, as above |
| `reasons` | a map from each word of the TSV file to its reason class |
| `reason_basis` | a map from each reason class in use, other than `unclassified`, to the evidence for it |
| `citations` | exception files only: a map from each word to its citation |
| `gaps` | patch files only: a map from each word to its gap |

The allowed tiers are `expert-human`, `lexicon-derived`, `crowd-scraped` and `machine-generated`. These are the o2i tiers that can gate a quality decision. A silver set, such as LLM output, cannot supply entries, and neither can the output of a system that o2i benchmarks against.

The reason classes are `loanword`, `proper_noun`, `lexical_stress`, `irregular`, `acronym`, `homograph_default` and `unclassified`. The build assigns `acronym` and `proper_noun` from the capital letters of the source headword. In the `pt-PT` and `pt-BR` files it also assigns three classes from other evidence. A word with a loan spelling, such as ⟨k w y⟩ or a final ⟨t⟩, is `loanword`. A `pt-BR` word that the NILC file tags `N+Pr` on every line is `proper_noun`. Any other exception is `irregular`, because its citation names a source that states its class ([kinds](kinds.md)). The build gives every other word `unclassified`. For an `unclassified` entry, the kind and its note in `citations` or `gaps` carry the reason. Known limit: the `loanword` class rests on the spelling only. A loan in native spelling keeps its other class.

A sidecar can hold more keys, and the schema does not check them. The `en-GB` files have these:

| Key | Content |
| :--- | :--- |
| `source_sha256` | the sha256 of the source file that `source_url` names |
| `agreement_source` | the second source that chooses among the readings of a word: its name, version, URL, sha256, licence, accent, and the comparison that decides agreement |
| `confirmation` | a map from each word of the TSV file to the basis of its entry: `second_source` or `single_reading` |
| `confirmation_basis` | a map from each value of `confirmation` to what it states |

A `second_source` entry agrees with a stressed reading of the second source. A `single_reading` entry is the one reading that the source gives for the word, the second source has no line for the word, and no second source checked the reading. [en-GB](languages/en-GB.md) states the selection.

The `pt-PT` files have `lexical_classes`. It gives the class of each word whose only difference from the rules is lexical, and the second sources that agree with its reading. The `pt-BR` files have `wiktionary_readings`, which lists the words whose reading comes from pt.wiktionary and not from the NILC file.

## Entry points

The package declares one entry point per code in two groups. o2i reads them only when a caller asks for a packaged lexicon.

| Group | Loads | Read by |
| :--- | :--- | :--- |
| `orthography2ipa.lexicons` | `o2i_lexicons:tsv_path` | `packaged_lexicon(code)` |
| `orthography2ipa.lexicon_patches` | `o2i_lexicons:patch_tsv_path` | `packaged_lexicon(code, patches=True)` |

o2i calls the loaded function with the name of the entry point, and the function returns the path of the TSV file. `packaged_lexicon` resolves the code first, so `pt` reaches `pt-PT`, and `pt-br` reaches `pt-BR`. A sub-lect such as `pt-PT-x-lisbon` has no file, and `packaged_lexicon` raises `LookupError` for it.

## Python API

The package also gives direct access to its files:

```python
import o2i_lexicons

o2i_lexicons.available_codes()            # the codes with an exception file
o2i_lexicons.available_codes("patch")     # the codes with a patch file
o2i_lexicons.tsv_path("en-GB")            # the exception file of a code
o2i_lexicons.patch_tsv_path("en-GB")      # the patch file of a code
o2i_lexicons.meta_path("en-GB")           # the sidecar of the exception file
o2i_lexicons.patch_meta_path("en-GB")     # the sidecar of the patch file
o2i_lexicons.load_meta("en-GB")           # that sidecar, parsed
o2i_lexicons.load_patch_meta("en-GB")     # the patch sidecar, parsed
```

`tsv_path` and `patch_tsv_path` raise `LookupError` when no file, or more than one file, is packaged for the code. They also raise it for a code that is not a single directory name, such as `patches/en-GB` or `../en-GB`, so that one function cannot reach the file of the other kind.

---
[← Exceptions and patches](kinds.md) · [Home](index.md) · [en-GB →](languages/en-GB.md)
