import json

import pytest

import o2i_lexicons


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(o2i_lexicons, "DATA_DIR", tmp_path)
    return tmp_path


def write_lexicon(root, code, source, body="cat\tkæt\n", meta=None):
    d = root / code
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{source}.tsv").write_text(body, encoding="utf-8")
    (d / f"{source}.meta.json").write_text(json.dumps(meta or {"code": code}),
                                           encoding="utf-8")


def test_lists_only_directories_that_hold_a_tsv(data_dir):
    write_lexicon(data_dir, "en-GB", "wikipron")
    write_lexicon(data_dir, "da", "nst")
    (data_dir / "fr").mkdir()
    (data_dir / "README").write_text("not a code")
    assert o2i_lexicons.available_codes() == ["da", "en-GB"]


def test_tsv_path_and_meta(data_dir):
    write_lexicon(data_dir, "en-GB", "wikipron", meta={"code": "en-GB", "source": "wikipron"})
    path = o2i_lexicons.tsv_path("en-GB")
    assert path == data_dir / "en-GB" / "wikipron.tsv"
    assert path.read_text(encoding="utf-8") == "cat\tkæt\n"
    assert o2i_lexicons.meta_path("en-GB") == data_dir / "en-GB" / "wikipron.meta.json"
    assert o2i_lexicons.load_meta("en-GB") == {"code": "en-GB", "source": "wikipron"}


def test_unknown_code_raises_lookup_error(data_dir):
    with pytest.raises(LookupError, match="no packaged lexicon for 'xx'"):
        o2i_lexicons.tsv_path("xx")


def test_two_sources_for_one_code_are_ambiguous(data_dir):
    write_lexicon(data_dir, "en-GB", "wikipron")
    write_lexicon(data_dir, "en-GB", "other")
    with pytest.raises(LookupError, match="2 lexicon files"):
        o2i_lexicons.tsv_path("en-GB")


def test_a_wheel_with_no_data_directory_lists_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(o2i_lexicons, "DATA_DIR", tmp_path / "data")
    assert o2i_lexicons.available_codes() == []
