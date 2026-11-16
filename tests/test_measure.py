"""measure.py never scores a lexicon on a gold that its build read, and it reads
the lexicons it names and no other."""
import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import orthography2ipa  # noqa: E402

import build_lexicon as bl  # noqa: E402
import measure  # noqa: E402


def hamming(left, right):
    return sum(a != b for a, b in zip(left, right)) + abs(len(left) - len(right))


BENCH = SimpleNamespace(
    normalize=lambda ipa, strip_stress, broad, extra_strip="": ipa.replace("ˈ", ""),
    levenshtein=hamming,
    _prosody_marks=lambda code: "",
    _is_multiword=lambda word: " " in word,
)


def test_infopedia_refuses_the_board_dataset_that_holds_it_and_wikipron():
    # The pt-PT screen keeps an entry that WikiPron pt-PT corroborates.
    assert measure.supplying_datasets("infopedia") == {
        "infopedia", "portuguese_unified", "portuguese_unified_corrected",
        "wikipron", "wikipron_corrected"}


def test_nilc_refuses_the_datasets_of_its_second_sources():
    # The pt-BR build takes pt.wiktionary readings from portuguese_unified and
    # keeps an entry that WikiPron pt-BR corroborates.
    assert measure.supplying_datasets("nilc") == {
        "nilc", "nilc_corrected", "portuguese_unified", "portuguese_unified_corrected",
        "wikipron", "wikipron_corrected"}


def recording_bench(read):
    """A harness whose dataset reads append the board dataset's name to *read*."""
    return SimpleNamespace(
        _PT_UNIFIED_URL="https://example.org/portuguese_unified.jsonl",
        _PT_UNIFIED_REGIONS={"pt-PT": "pt-PT"},
        _fetch=lambda url, name: read.append(
            "portuguese_unified" if url.endswith("portuguese_unified.jsonl") else url) or "",
        load_wikipron=lambda code, limit: read.append("wikipron") or [],
        pt_unified_source=lambda row: "",
    )


def test_the_second_sources_are_the_datasets_the_screens_read():
    read = []
    engine = SimpleNamespace(spec=SimpleNamespace(stress=SimpleNamespace(cliticless_words=())))
    bl.infopedia_references(recording_bench(read), engine, "pt-PT")
    assert set(read) == {"portuguese_unified", "wikipron"}
    assert set(read) <= measure.supplying_datasets("infopedia")
    read.clear()
    bl.nilc_references(recording_bench(read), "pt-BR", {})
    assert set(read) == {"portuguese_unified", "wikipron"}
    assert set(read) <= measure.supplying_datasets("nilc")


def test_wikipron_refuses_itself():
    assert measure.supplying_datasets("wikipron") == {"wikipron", "wikipron_corrected"}


def test_score_reads_the_lexicon_it_is_given():
    # One sound of three differs from the gold: PER 1/3.
    assert measure.score(BENCH, [("colonel", "kit")], "en-GB", {"colonel": "kat"}) == (1, 1 / 3)


def test_score_takes_the_best_gold_of_a_word():
    pairs = [("colonel", "kit"), ("colonel", "ˈkat")]
    assert measure.score(BENCH, pairs, "en-GB", {"colonel": "kat"}) == (1, 0.0)


def test_score_averages_over_the_words():
    pairs = [("colonel", "kat"), ("lieutenant", "kit")]
    lexicon = {"colonel": "kat", "lieutenant": "kat"}
    assert measure.score(BENCH, pairs, "en-GB", lexicon) == (2, 1 / 6)


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
def test_a_process_wide_lexicon_does_not_reach_the_rules_row(tmp_path):
    source = tmp_path / "en-GB.tsv"
    source.write_text("colonel\tˈkɜːnəl\n", encoding="utf-8")
    pairs = [("colonel", "ˈkɜːnəl")]
    orthography2ipa.register_lexicon("en-GB", str(source))
    try:
        assert orthography2ipa.G2P("en-GB").transcribe_word("colonel") == "ˈkɜːnəl"
        _covered, per = measure.score(BENCH, pairs, "en-GB", {})
    finally:
        orthography2ipa.clear_lexicons()
    assert per > 0


def write_kind(root, code, source, entries, meta):
    root.mkdir(parents=True, exist_ok=True)
    (root / f"{source}.tsv").write_text("".join(f"{w}\t{i}\n" for w, i in entries.items()),
                                        encoding="utf-8")
    (root / f"{source}.meta.json").write_text(json.dumps(meta), encoding="utf-8")


@pytest.fixture
def packaged(tmp_path, monkeypatch):
    """An exception file and a patch file of *code* under a temporary data tree,
    and a harness whose golds are *golds*."""
    import o2i_lexicons
    monkeypatch.setattr(o2i_lexicons, "DATA_DIR", tmp_path)
    monkeypatch.setattr(measure.o2i_harness, "harness_sha256", lambda cache: "0" * 64)

    def make(code, source, exceptions, patches, golds):
        write_kind(tmp_path / code, code, source, exceptions, {"source": source})
        write_kind(tmp_path / "patches" / code, code, source, patches, {"source": source})
        bench = SimpleNamespace(**vars(BENCH), provenance_for=lambda dataset, tag: "expert-human",
                                DATASETS={d: (lambda tag, limit, d=d: golds[d],) for d in golds})
        monkeypatch.setattr(measure.o2i_harness, "load_benchmark", lambda cache: bench)
        return tmp_path
    return make


def test_measure_scores_each_kind_of_lexicon(packaged):
    # The gold reads both words as the lexicons do, so each lexicon brings
    # its own overlap word to PER 0.
    gold = [("colonel", "kɜːnəl"), ("yacht", "jɒt")]
    root = packaged("en-GB", "wikipron", {"colonel": "kɜːnəl"},
                    {"cringes": "kɹɪndʒɪz", "yacht": "jɒt"}, {"ipadict": gold})
    report = measure.measure("en-GB", [("ipadict", "en-GB")], root)
    assert report["lexicon_entries"] == {"exception": 1, "patch": 2, "both": 3}
    row = report["rows"][0]
    assert {kind: (row[kind]["overlap_words"], row[kind]["overlap_per_with_lexicon"])
            for kind in ("exception", "patch", "both")} == {
        "exception": (1, 0.0), "patch": (1, 0.0), "both": (2, 0.0)}
    assert row["both"]["per_with_lexicon"] == 0.0


@pytest.mark.parametrize("dataset", ["portuguese_unified", "wikipron", "wikipron_corrected"])
def test_measure_refuses_a_second_source_of_the_pt_br_build(packaged, dataset):
    root = packaged("pt-BR", "nilc", {"foto": "ˈfɔtu"}, {}, {dataset: [("foto", "ˈfɔtu")]})
    with pytest.raises(SystemExit, match=f"the build of the pt-BR lexicon read {dataset}"):
        measure.measure("pt-BR", [(dataset, "pt-BR")], root)


def installed_copy(tmp_path):
    """A copy of the package code, with no data, in a directory of its own."""
    site = tmp_path / "site"
    shutil.copytree(ROOT / "o2i_lexicons", site / "o2i_lexicons",
                    ignore=shutil.ignore_patterns("data", "__pycache__"))
    return site


@pytest.mark.parametrize("script", ["measure", "prune_check"])
def test_the_scripts_import_the_checkout_before_an_installed_copy(tmp_path, script):
    # As `python scripts/<script>.py` runs: the scripts directory first, then
    # an installed copy of the package, then the rest.
    site = installed_copy(tmp_path)
    code = (f"import sys; sys.path[:0] = [{str(SCRIPTS)!r}, {str(site)!r}]; "
            f"import {script}, o2i_lexicons; print(o2i_lexicons.__file__)")
    out = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True,
                         check=True).stdout
    assert out.strip() == str(ROOT / "o2i_lexicons" / "__init__.py")


@pytest.mark.parametrize("script, argv", [("measure", ["en-GB", "ipadict:en-GB"]),
                                          ("prune_check", [])])
def test_the_scripts_refuse_an_installed_copy(tmp_path, script, argv):
    # Another module imported an installed copy first, so the checkout's
    # package never loads.
    site = installed_copy(tmp_path)
    code = (f"import sys; sys.path.insert(0, {str(site)!r}); import o2i_lexicons; "
            f"sys.path.insert(0, {str(SCRIPTS)!r}); import o2i_harness; "
            "o2i_harness.load_benchmark = lambda cache: sys.exit('read the benchmark'); "
            f"import {script}; {script}.main({argv!r})")
    result = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True)
    assert (result.returncode, result.stderr.strip()) == (
        1, f"o2i_lexicons was imported from {site / 'o2i_lexicons'}, not from this checkout")
