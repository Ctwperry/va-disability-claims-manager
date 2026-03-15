"""
Tests for app.core.json_guard — parse_symptom_log() and parse_evidence_notes().
"""
import pytest


# ── parse_symptom_log ─────────────────────────────────────────────────────────

def test_symptom_log_parses_valid_data():
    from app.core.json_guard import parse_symptom_log
    data = '[{"date":"2024-01-01","source":"STR p.5","complaint":"pain","diagnosis":"LBP","treatment":"ibu"}]'
    result = parse_symptom_log(data)
    assert result == [{"date": "2024-01-01", "source": "STR p.5", "complaint": "pain",
                       "diagnosis": "LBP", "treatment": "ibu"}]


def test_symptom_log_returns_empty_list_for_empty_input():
    from app.core.json_guard import parse_symptom_log
    assert parse_symptom_log("") == []
    assert parse_symptom_log(None) == []


def test_symptom_log_returns_empty_list_for_invalid_json():
    from app.core.json_guard import parse_symptom_log
    assert parse_symptom_log("{not valid json}") == []


def test_symptom_log_returns_empty_list_when_root_is_not_list():
    from app.core.json_guard import parse_symptom_log
    assert parse_symptom_log('{"date": "2024"}') == []
    assert parse_symptom_log('"hello"') == []
    assert parse_symptom_log('42') == []


def test_symptom_log_skips_non_dict_entries():
    from app.core.json_guard import parse_symptom_log
    data = '[{"date": "2024"}, "not a dict", 99, null]'
    result = parse_symptom_log(data)
    assert len(result) == 1
    assert result[0]["date"] == "2024"


def test_symptom_log_coerces_non_string_values_to_str():
    from app.core.json_guard import parse_symptom_log
    data = '[{"date": 20240101, "source": null, "complaint": true}]'
    result = parse_symptom_log(data)
    assert result[0]["date"] == "20240101"
    assert result[0]["source"] == ""
    assert result[0]["complaint"] == "True"


def test_symptom_log_truncates_oversized_strings():
    from app.core.json_guard import parse_symptom_log, MAX_FIELD_LEN
    big = "x" * (MAX_FIELD_LEN + 500)
    data = f'[{{"date": "{big}"}}]'
    result = parse_symptom_log(data)
    assert len(result[0]["date"]) == MAX_FIELD_LEN


# ── parse_evidence_notes ──────────────────────────────────────────────────────

def test_evidence_notes_parses_valid_data():
    from app.core.json_guard import parse_evidence_notes
    data = '{"pages": [{"page_number": 3, "keyword": "pain", "snippet": "text"}], "auto_detected": true}'
    result = parse_evidence_notes(data)
    assert result["auto_detected"] is True
    assert result["pages"][0]["page_number"] == 3


def test_evidence_notes_returns_empty_dict_for_empty_input():
    from app.core.json_guard import parse_evidence_notes
    assert parse_evidence_notes("") == {}
    assert parse_evidence_notes(None) == {}


def test_evidence_notes_returns_empty_dict_for_invalid_json():
    from app.core.json_guard import parse_evidence_notes
    assert parse_evidence_notes("{bad json}") == {}


def test_evidence_notes_returns_empty_dict_when_root_is_not_dict():
    from app.core.json_guard import parse_evidence_notes
    assert parse_evidence_notes("[]") == {}
    assert parse_evidence_notes('"string"') == {}


def test_evidence_notes_replaces_non_list_pages_with_empty_list():
    from app.core.json_guard import parse_evidence_notes
    data = '{"pages": "not a list", "auto_detected": false}'
    result = parse_evidence_notes(data)
    assert result["pages"] == []


def test_evidence_notes_coerces_auto_detected_to_bool():
    from app.core.json_guard import parse_evidence_notes
    data = '{"pages": [], "auto_detected": 1}'
    result = parse_evidence_notes(data)
    assert result["auto_detected"] is True


def test_evidence_notes_skips_non_dict_page_entries():
    from app.core.json_guard import parse_evidence_notes
    data = '{"pages": [{"page_number": 1}, "bad", null, 42], "auto_detected": false}'
    result = parse_evidence_notes(data)
    assert len(result["pages"]) == 1
