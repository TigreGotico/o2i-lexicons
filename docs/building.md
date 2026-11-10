# Building and pruning

The scripts in `scripts/` build a lexicon from a source dataset, measure it on another dataset, and find the entries that the rules now read right. Each script states its exact behaviour in its module docstring, and `--help` lists its options.

## Set up

Work in a clone of the repository, in a virtual environment of your own:

```bash
uv venv --python 3.11 .venv
uv pip install --python .venv --prerelease=allow -e '.[test]'
```

The `test` extra installs pytest and silabificador. The build reads the prefix seams of `silabificador.morphology`.

The scripts run the installed o2i. They score with the benchmark harness of o2i at the git tag of that version. `scripts/o2i_harness.py` fetches the harness once into `.cache/o2i-harness/<version>/`, with a sparse, shallow clone that holds no engine code. The harness downloads each gold file into `.cache/gold/` on first use. `--cache` sets another cache directory.

## Build

The general form of a build is:

```bash
python scripts/build_lexicon.py <code> <dataset> [input files] --report build-report.json
```

The sidecar field `build_command` holds the command that built each packaged file. The build writes the input files by base name only. To read the command of a file:

```bash
python -c "import o2i_lexicons; print(o2i_lexicons.load_meta('pt-PT')['build_command'])"
```

The `pt-PT` and `pt-BR` builds need input files that the harness does not fetch:

| Option | File | Where to get it |
| :--- | :--- | :--- |
| `--homographs` | `heterophonic_homographs.csv` | `bifonia/data/heterophonic_homographs.csv` of [bifonia](https://github.com/TigreGotico/bifonia) |
| `--preao` | `preao_words.txt` | a word list of the aspell `pt_PT-preao` dictionary, the European Portuguese spelling before AO90, one word per line |
| `--nilc` | `unitex_sample_transcribed.txt` | `etc/unitex_sample_transcribed.txt` of [aeiouado_g2p](https://github.com/dash219/aeiouado_g2p), at the commit that the pt-BR `source_url` names |
| `--michaelis` | `michaelis-snapshot.jsonl` | `raw/entries.jsonl` of the private dataset [TigreGotico/michaelis-brazilian-portuguese-transcriptions](https://huggingface.co/datasets/TigreGotico/michaelis-brazilian-portuguese-transcriptions), at revision `d8e5e0e4`; the Michaelis readings are all rights reserved |

The build keeps a word only when the rules read it wrong under the board's scoring. The comparison ignores stress, because some source stress marks contradict the spelling (Infopédia câmera [kɐˈmɨɾɐ]) and WikiPron writes no stress to check them. Words that share a spelling pattern and the same error at that pattern form a lead. A lead is a question for the linguistic literature, not a rule. Its words stay out of the lexicon until a cited source states a rule for the pattern, or states that the pattern is lexical. `--min-lead` sets the smallest group that is a lead, and its default is 10.

The build writes the exception file and the patch file of the code under `--out`, which defaults to `o2i_lexicons/data`. These options write reports:

| Option | Content |
| :--- | :--- |
| `--report` | the build report: the counts per stage and per kind, and each lead with example words |
| `--held-out` | each word that a lead holds out, with its largest lead |
| `--excluded` | each reading and headword that the build leaves out, with the reason |
| `--screened` | each word that the screen of the source tests, with its result |

## Measure

```bash
python scripts/measure.py en-GB ipadict:en-GB cmudict:en
python scripts/measure.py pt-PT ep_dialects:pt-PT
```

`measure.py` scores the lexicons of a code on a gold from another source. It scores the rules only, then the rules with the exceptions, with the patches, and with both. For each lexicon it also gives the score on the overlap, the gold words that the lexicon holds.

It refuses every gold that the build read. That is the source of the lexicon, the board dataset that holds it, each second source in `build_lexicon.SECOND_SOURCES`, and each of those with its corrections overlay. So `wikipron:pt-PT` and `wikipron:pt-BR` are refused. `ep_dialects` is a small expert-human set of European Portuguese sentences that no build reads.

## Prune

```bash
python scripts/prune_check.py            # exits 1 when an entry is stale
python scripts/prune_check.py --write    # removes the stale patches in place
```

[Exceptions and patches](kinds.md) states what a stale entry means for each kind. The check also lists each entry that the spec's `word_exceptions` shadow. `--write` removes a shadowed patch, and a shadowed exception fails the check. `--write` checks each file that it writes against the schema, and exits with status 1 when one fails. `--report` writes the stale words as JSON.

`measure.py` and `prune_check.py` read the files of the checkout, never an installed copy of the package.

## Tests and CI

Run the test suite with `python -m pytest -q tests`. It validates every packaged file against the schema and the spec inventory, and checks the build helpers. The sdist ships `scripts/` and `tests/` beside the package.

| Workflow | When | What it does |
| :--- | :--- | :--- |
| Build Tests | each pull request to `dev` or `master` | runs the test suite on Python 3.11 to 3.14, then installs the built wheel in a clean venv and checks that it ships every data file |
| Prune Check | each pull request to `dev` | runs `prune_check.py` against the latest o2i alpha |
| Prune Stale Entries | once a week, and on request | runs `prune_check.py --write` and the test suite on the pruned files, opens a draft pull request, and starts Build Tests on its branch |
| License Check | each pull request to `dev` | checks the licenses of the installed dependencies |
| Release Alpha and Propose Stable | each merge to `dev` | publishes an alpha release to PyPI |

## Known limits

The sidecar records only the base name of each input file, with no version or hash. The pt-PT `source_url` names the main branch of the dataset, not a revision. The Michaelis snapshot is in a private dataset, so only project members can rebuild the pt-BR files.

---
[← pt-PT](languages/pt-PT.md) · [Home](index.md) · [Contributing →](contributing.md)
