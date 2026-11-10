# o2i-lexicons

o2i-lexicons ships pronunciation data for [orthography2ipa](https://github.com/TigreGotico/orthography2ipa) (o2i). Each lexicon holds words that the o2i rules transcribe wrong, with the source of each reading. The package changes no output when you install it. You give a lexicon to an engine in code.

## Install

```bash
uv pip install --prerelease=allow o2i-lexicons
```

The project publishes alpha releases, so the install needs `--prerelease=allow`.

## Usage

```python
from orthography2ipa import G2P, Pipeline, packaged_lexicon

g2p = G2P("pt-BR", pipeline=Pipeline(lexicon=packaged_lexicon("pt-BR")))
print(g2p.transcribe("afeto"))    # aˈfɛtu, where the rules alone give aˈfetu

g2p = G2P("pt-BR", pipeline=Pipeline(lexicon=packaged_lexicon("pt-BR", patches=True)))
print(g2p.transcribe("colocam"))  # koˈlɔkɐ̃w̃
```

## Exceptions and patches

An exception is a word that no spelling rule can reach, and it carries a citation. `packaged_lexicon(code)` always returns the exceptions. A patch is a word that a rule could reach but that the rules do not read right yet. Each patch records its gap, and a patch leaves the package when its rule lands. You get the patches only with `patches=True`. [docs/kinds.md](docs/kinds.md) states the full contract.

## Languages

| Code | Source | Page |
| :--- | :--- | :--- |
| `en-GB` | [WikiPron](https://github.com/CUNY-CL/wikipron), from Wiktionary, checked against [Britfone](https://github.com/JoseLlarena/Britfone) 3.0.1 | [docs/languages/en-GB.md](docs/languages/en-GB.md) |
| `pt-BR` | the NILC Aeiouadô training file | [docs/languages/pt-BR.md](docs/languages/pt-BR.md) |
| `pt-PT` | the Infopédia rows of portuguese-unified-pronunciation-lexicon | [docs/languages/pt-PT.md](docs/languages/pt-PT.md) |

## Documentation

[docs/index.md](docs/index.md) is the entry point. It links the file format, the build scripts and the rules for contributors.

## License

The code is Apache-2.0. Each data file keeps the license of its source, which its `.meta.json` sidecar names. The three data sets are CC BY-SA 4.0, and the pt-BR files also keep the BSD notice of the NILC data in `LICENSE.nilc`.
