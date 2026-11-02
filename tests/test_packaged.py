"""Every lexicon that ships in the package satisfies the contract."""
from importlib.metadata import entry_points

import o2i_lexicons
from o2i_lexicons.schema import validate_meta, validate_tsv

GROUP = "orthography2ipa.lexicons"


def own_entry_points():
    return [ep for ep in entry_points(group=GROUP)
            if ep.dist is not None and ep.dist.name.replace("_", "-") == "o2i-lexicons"]


def test_packaged_files_are_valid():
    problems = {}
    for code in o2i_lexicons.available_codes():
        text = o2i_lexicons.tsv_path(code).read_text(encoding="utf-8")
        words = [line.split("\t", 1)[0] for line in text.splitlines() if line]
        found = [f"tsv line {n}: {r}" for n, r in validate_tsv(text)]
        found += validate_meta(o2i_lexicons.load_meta(code), code, words)
        if found:
            problems[code] = found
    assert problems == {}


def test_each_meta_sits_next_to_its_tsv():
    for code in o2i_lexicons.available_codes():
        assert o2i_lexicons.meta_path(code).is_file(), code


def test_entry_points_name_exactly_the_packaged_codes():
    names = sorted(ep.name for ep in own_entry_points())
    assert names == o2i_lexicons.available_codes()


def test_each_entry_point_returns_its_own_file():
    for ep in own_entry_points():
        provider = ep.load()
        assert provider is o2i_lexicons.tsv_path
        assert provider(ep.name) == o2i_lexicons.tsv_path(ep.name)
        assert provider(ep.name).is_file()
