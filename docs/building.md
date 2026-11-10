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
| `--michaelis` | `michaelis-snapshot.jsonl` | a crawl of the Michaelis dictionary, which is all rights reserved and not public |

The build keeps a word only when the rules read it wrong under the board's scoring. Words that share a spelling pattern and the same error at that pattern form a lead. A lead is a question for the linguistic literature, not a rule. Its words stay out of the lexicon until a cited source states a rule for the pattern, or states that the pattern is lexical. `--min-lead` sets the smallest group that is a lead, and its default is 10.

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
python scripts/measure.py pt-PT ep_dialects:pt-PT wikipron:pt-PT
```

`measure.py` scores a lexicon on a gold from another source, with the rules only and with the lexicon. It reads the exception file of the code. It also gives the score on the overlap, the gold words that the lexicon holds. It refuses the gold that supplied the lexicon, the board dataset that holds that gold, and its corrections overlay.

Some golds that `measure.py` accepts are not fully independent of the build. The pt-PT build uses WikiPron pt-PT as a second source. The pt-BR build uses WikiPron pt-BR and the pt.wiktionary rows of portuguese-unified as second sources. `ep_dialects` is a small expert-human set of European Portuguese sentences that no build reads.

## Prune

```bash
python scripts/prune_check.py            # exits 1 when an entry is stale
python scripts/prune_check.py --write    # removes the stale patches in place
```

[Exceptions and patches](kinds.md) states what a stale entry means for each kind. `--report` writes the stale words as JSON.

## Tests and CI

Run the test suite with `python -m pytest -q tests`. It validates every packaged file against the schema and checks the build helpers.

| Workflow | When | What it does |
| :--- | :--- | :--- |
| Build Tests | each pull request to `dev` or `master` | runs the test suite on Python 3.11 to 3.14 |
| Prune Check | each pull request to `dev` | runs `prune_check.py` against the latest o2i alpha |
| Prune Stale Entries | once a week, and on request | runs `prune_check.py --write` and opens a draft pull request |
| License Check | each pull request to `dev` | checks the licenses of the installed dependencies |
| Release Alpha and Propose Stable | each merge to `dev` | publishes an alpha release to PyPI |

## Known limits

The sidecar records only the base name of each input file, with no version or hash. The pt-PT `source_url` names the main branch of the dataset, not a revision. The Michaelis snapshot is not public, so nobody outside the project can rebuild the pt-BR files.

---
[← pt-PT](languages/pt-PT.md) · [Home](index.md) · [Contributing →](contributing.md)
