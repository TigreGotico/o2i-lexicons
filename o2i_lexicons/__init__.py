"""Default residual lexicons for orthography2ipa.

A lexicon entry is one of two kinds:

- An exception is a word whose reading no rule can reach, because the
  spelling does not determine it. A cited source states this for its class.
  An exception is always meant to be used.
- A patch is a word that a rule could reach and that the rules of the
  orthography2ipa version in the sidecar get wrong. Each patch names its gap:
  the orthography2ipa pull request or the rule lead that will reach it. The
  patches shrink as rules land.

Each language code has one exception file, ``data/<code>/<source>.tsv``, and
one patch file, ``data/patches/<code>/<source>.tsv``. A patch file can be
empty. Each file is ``word<TAB>ipa`` lines with a ``<source>.meta.json``
sidecar that records where the entries came from (see
:mod:`o2i_lexicons.schema`).

orthography2ipa finds the exception files through the
``orthography2ipa.lexicons`` entry-point group and the patch files through
``orthography2ipa.lexicon_patches``. Each entry point is named for a language
code and loads :func:`tsv_path` or :func:`patch_tsv_path`, which
orthography2ipa calls with that code.
"""
from __future__ import annotations

import json
from pathlib import Path

from o2i_lexicons.version import VERSION_STR

__version__ = VERSION_STR
__all__ = ["DATA_DIR", "PATCH_DIR", "KINDS", "available_codes", "tsv_path", "meta_path",
           "load_meta", "patch_tsv_path", "patch_meta_path", "load_patch_meta"]

#: The packaged ``data/<code>/<source>.tsv`` tree of the exceptions.
DATA_DIR = Path(__file__).parent / "data"

#: The name of the directory under :data:`DATA_DIR` that holds the patches.
PATCH_DIR = "patches"

#: The two kinds of entry.
KINDS = ("exception", "patch")


def _root(kind: str) -> Path:
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}, not {kind!r}")
    return DATA_DIR / PATCH_DIR if kind == "patch" else DATA_DIR


def available_codes(kind: str = "exception") -> list[str]:
    """Return the sorted language codes that have a packaged file of *kind*."""
    root = _root(kind)
    if not root.is_dir():
        return []
    return sorted(d.name for d in root.iterdir()
                  if d.is_dir() and any(d.glob("*.tsv")))


def _tsv(code: str, kind: str) -> Path:
    files = sorted((_root(kind) / code).glob("*.tsv"))
    noun = "lexicon" if kind == "exception" else "patch"
    if not files:
        raise LookupError(f"no packaged {noun} for {code!r}")
    if len(files) > 1:
        raise LookupError(
            f"{code!r} has {len(files)} {noun} files, expected one: "
            + ", ".join(f.name for f in files))
    return files[0]


def tsv_path(code: str) -> Path:
    """Return the packaged exception file for *code*.

    *code* is the directory name exactly as :func:`available_codes` lists it.

    Raises
    ------
    LookupError
        No exception file is packaged for *code*, or more than one is, so the
        default is ambiguous.
    """
    return _tsv(code, "exception")


def patch_tsv_path(code: str) -> Path:
    """Return the packaged patch file for *code*. The file can be empty.

    Raises
    ------
    LookupError
        No patch file is packaged for *code*, or more than one is.
    """
    return _tsv(code, "patch")


def _meta(tsv: Path) -> Path:
    return tsv.with_name(tsv.stem + ".meta.json")


def meta_path(code: str) -> Path:
    """Return the ``.meta.json`` sidecar of the exception file for *code*."""
    return _meta(tsv_path(code))


def patch_meta_path(code: str) -> Path:
    """Return the ``.meta.json`` sidecar of the patch file for *code*."""
    return _meta(patch_tsv_path(code))


def load_meta(code: str) -> dict:
    """Return the parsed sidecar of the exception file for *code*."""
    return json.loads(meta_path(code).read_text(encoding="utf-8"))


def load_patch_meta(code: str) -> dict:
    """Return the parsed sidecar of the patch file for *code*."""
    return json.loads(patch_meta_path(code).read_text(encoding="utf-8"))
