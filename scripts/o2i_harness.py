"""Load the orthography2ipa benchmark harness that matches the installed engine.

The wheel of orthography2ipa does not hold ``scripts/benchmark.py``, which owns
the gold loaders, the tiers and the scoring normalisation of the board. This
module checks out ``scripts/`` and ``orthography2ipa/data/gold/`` from the git
tag of the installed version, with a sparse, shallow clone of a few
megabytes. The scoring here is then the scoring of the board for that exact
version. The checkout holds none of the engine's Python files, so the
installed engine is the one that is measured.

The checkout goes under ``<cache>/o2i-harness/<version>/``. Gold files are
read from ``<cache>/gold/``, which may be a symlink to an existing benchmark
cache.
"""
from __future__ import annotations

import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

from orthography2ipa.version import VERSION_STR

REPO = "https://github.com/TigreGotico/orthography2ipa.git"
SPARSE_PATHS = ("/scripts/", "/orthography2ipa/data/gold/")


def harness_dir(cache: Path, version: str = VERSION_STR) -> Path:
    """Check out the harness for *version* once, and return its ``scripts/``."""
    root = cache / "o2i-harness" / version
    if not (root / "scripts" / "benchmark.py").is_file():
        root.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "-q", "--depth", "1", "--branch", version,
                        "--filter=blob:none", "--no-checkout", REPO, str(root)],
                       check=True)
        subprocess.run(["git", "-C", str(root), "sparse-checkout", "set", "--no-cone",
                        *SPARSE_PATHS], check=True)
        subprocess.run(["git", "-C", str(root), "checkout", "-q"], check=True)
    if (root / "orthography2ipa" / "__init__.py").exists():
        raise RuntimeError(f"{root} holds engine code; the harness would measure it")
    return root / "scripts"


def load_benchmark(cache: Path) -> ModuleType:
    """Import the board harness of the installed orthography2ipa version.

    The harness puts its checkout root first on ``sys.path``. The sparse
    checkout holds no engine code there, so the installed engine is the one
    that is measured.
    """
    scripts = harness_dir(cache)
    sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("o2i_benchmark", scripts / "benchmark.py")
    bench = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bench)
    bench.CACHE_DIR = str(cache / "gold")
    return bench


def harness_sha256(cache: Path) -> str:
    """The sha256 of the fetched ``benchmark.py``, for the build record."""
    data = (harness_dir(cache) / "benchmark.py").read_bytes()
    return hashlib.sha256(data).hexdigest()
