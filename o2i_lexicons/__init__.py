"""Default residual lexicons for orthography2ipa.

Each language code has one directory under ``data/``. It holds one
``<source>.tsv`` file of ``word<TAB>ipa`` lines and a ``<source>.meta.json``
sidecar that records where the entries came from (see :mod:`o2i_lexicons.schema`).

orthography2ipa finds these files through the ``orthography2ipa.lexicons``
entry-point group. Each entry point is named for a language code and loads
:func:`tsv_path`, which orthography2ipa calls with that code.
"""
from __future__ import annotations

import json
from pathlib import Path

from o2i_lexicons.version import VERSION_STR

__version__ = VERSION_STR
__all__ = ["DATA_DIR", "available_codes", "tsv_path", "meta_path", "load_meta"]

#: The packaged ``data/<code>/<source>.tsv`` tree.
DATA_DIR = Path(__file__).parent / "data"


def available_codes() -> list[str]:
    """Return the sorted language codes that have a packaged lexicon."""
    if not DATA_DIR.is_dir():
        return []
    return sorted(d.name for d in DATA_DIR.iterdir()
                  if d.is_dir() and any(d.glob("*.tsv")))


def tsv_path(code: str) -> Path:
    """Return the packaged TSV file for *code*.

    *code* is the directory name exactly as :func:`available_codes` lists it.

    Raises
    ------
    LookupError
        No lexicon is packaged for *code*, or more than one source file is,
        so the default is ambiguous.
    """
    files = sorted((DATA_DIR / code).glob("*.tsv"))
    if not files:
        raise LookupError(f"no packaged lexicon for {code!r}")
    if len(files) > 1:
        raise LookupError(
            f"{code!r} has {len(files)} lexicon files, expected one: "
            + ", ".join(f.name for f in files))
    return files[0]


def meta_path(code: str) -> Path:
    """Return the ``.meta.json`` sidecar of the TSV file for *code*."""
    tsv = tsv_path(code)
    return tsv.with_name(tsv.stem + ".meta.json")


def load_meta(code: str) -> dict:
    """Return the parsed ``.meta.json`` sidecar for *code*."""
    return json.loads(meta_path(code).read_text(encoding="utf-8"))
