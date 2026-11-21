# o2i-lexicons: agent guide

<!-- agent-hint
covers: what the repository holds, how to set it up and test it, and the rules its tests enforce
source: `pyproject.toml`, `o2i_lexicons/schema.py`, `tests/`
generated: no
verify: python -m pytest -q tests
see: `docs/index.md`, `docs/contributing.md`
-->

`o2i-lexicons` ships per-language pronunciation lexicons for orthography2ipa. Each lexicon holds words that the o2i rules transcribe wrong, as exceptions (no spelling rule reaches them) and patches (a rule could reach them).

The documentation starts at [docs/index.md](docs/index.md).

## Repository map

| Path | Holds |
|---|---|
| `o2i_lexicons/__init__.py`, `schema.py` | The loader, the entry-point functions and the file validation |
| `o2i_lexicons/data/<code>/` | The exception TSV file and its `.meta.json` sidecar |
| `o2i_lexicons/data/patches/<code>/` | The patch TSV file and its sidecar |
| `scripts/` | The build, measure and prune scripts ([building.md](docs/building.md)) |
| `tests/` | The schema, build, loader and packaging tests |

## Setup and tests

```bash
unset VIRTUAL_ENV
uv venv --python 3.11 .venv
uv pip install --python .venv --prerelease=allow -e '.[test]'
.venv/bin/python -m pytest -q tests
.venv/bin/python scripts/prune_check.py
```

Use uv, never pip. `prune_check.py` exits 1 when an entry is stale. Run it against the latest o2i alpha.

## Hard rules

1. A packaged file is build output. Change the build, then rebuild the file with its `build_command` ([contributing.md](docs/contributing.md)).
2. Each TSV file passes `schema.validate_tsv`: sorted, lowercase words, IPA from the spec inventory ([data-format.md](docs/data-format.md)).
3. An exception carries a citation. A patch carries a gap ([kinds.md](docs/kinds.md)).
4. No word is in both the exception file and the patch file of a code ([kinds.md](docs/kinds.md#how-the-build-assigns-a-kind)).
5. A source must sit on a tier that can gate a quality decision. Never take a reading from a language model or from a system that o2i benchmarks against ([data-format.md](docs/data-format.md)).
6. A rule beats a list. When a source shows a rule reaches a group of words, fix o2i and let the prune job remove the patches ([contributing.md](docs/contributing.md#exception-or-patch)).
7. A pull request title follows conventional commits, because the release workflow reads it ([contributing.md](docs/contributing.md)).

## Before you push

1. Run the full test suite and `scripts/prune_check.py`.
2. If you add a docs page, list it in `docs/index.md`, give it an `agent-hint` comment after its H1, and add a footer with the index, previous and next links.
