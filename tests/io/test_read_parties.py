import json
import logging

import pytest

from wahlwerk.io import read_parties

VALID = {
    "schema": 1,
    "name": "de.test",
    "description": "Two parties for testing.",
    "parties": {
        "cdu": {"name": "Christlich Demokratische Union Deutschlands", "short_name": "CDU"},
        "ssw": {"name": "Südschleswigscher Wählerverband"},
    },
}


def write(tmp_path, content):
    path = tmp_path / "parties.json"
    text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
    path.write_text(text, encoding="utf-8")
    return path


def test_reads_parties_in_file_order(tmp_path):
    cdu, ssw = read_parties(write(tmp_path, VALID))
    assert cdu.id == "cdu"
    assert cdu.short_name == "CDU"
    assert ssw.id == "ssw"
    assert ssw.name == "Südschleswigscher Wählerverband"
    assert ssw.short_name is None


def test_accepts_str_path(tmp_path):
    assert len(read_parties(str(write(tmp_path, VALID)))) == 2


def test_missing_schema_is_rejected(tmp_path):
    content = {k: v for k, v in VALID.items() if k != "schema"}
    with pytest.raises(ValueError, match="schema None is not supported"):
        read_parties(write(tmp_path, content))


def test_unknown_schema_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="schema 2 is not supported"):
        read_parties(write(tmp_path, {**VALID, "schema": 2}))


def test_duplicate_party_key_is_rejected(tmp_path):
    text = """{"schema": 1, "name": "de.test", "parties": {
        "cdu": {"name": "CDU"},
        "cdu": {"name": "Something else"}
    }}"""
    with pytest.raises(ValueError, match="duplicate key 'cdu'"):
        read_parties(write(tmp_path, text))


def test_unknown_top_level_field_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="parties.json"):
        read_parties(write(tmp_path, {**VALID, "version": "2025"}))


def test_unknown_party_field_is_rejected(tmp_path):
    content = {**VALID, "parties": {"cdu": {"name": "CDU", "tags": []}}}
    with pytest.raises(ValueError, match="party 'cdu'"):
        read_parties(write(tmp_path, content))


def test_invalid_slug_is_rejected(tmp_path):
    content = {**VALID, "parties": {"CDU": {"name": "CDU"}}}
    with pytest.raises(ValueError, match="party 'CDU'"):
        read_parties(write(tmp_path, content))


def test_not_an_object_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="expected a JSON object"):
        read_parties(write(tmp_path, "[]"))


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_parties(tmp_path / "nope.json")


def test_logs_what_was_read(tmp_path, caplog):
    path = write(tmp_path, VALID)
    with caplog.at_level(logging.INFO, logger="wahlwerk"):
        read_parties(path)
    assert f"{path}: read 2 parties for de.test" in caplog.text
