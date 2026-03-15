"""
Tests for is_known_vasrd_code() in app.services.conditions_service.

The function accepts an optional known_codes list so tests can pass a
fixed list without fighting the LRU cache on load_vasrd_codes().
"""

_SAMPLE_CODES = [
    {"code": "5242", "name": "Cervical spine", "system": "Musculoskeletal"},
    {"code": "9411", "name": "PTSD",           "system": "Mental Health"},
    {"code": "6260", "name": "Tinnitus",       "system": "Sensory"},
]


def test_known_code_returns_true():
    from app.services.conditions_service import is_known_vasrd_code
    assert is_known_vasrd_code("5242", _SAMPLE_CODES) is True


def test_unknown_code_returns_false():
    from app.services.conditions_service import is_known_vasrd_code
    assert is_known_vasrd_code("9999", _SAMPLE_CODES) is False


def test_garbage_string_returns_false():
    from app.services.conditions_service import is_known_vasrd_code
    assert is_known_vasrd_code("foobar", _SAMPLE_CODES) is False


def test_empty_string_returns_true():
    """Empty code is valid — the field is optional."""
    from app.services.conditions_service import is_known_vasrd_code
    assert is_known_vasrd_code("", _SAMPLE_CODES) is True


def test_whitespace_only_returns_true():
    """Whitespace-only is treated as absent."""
    from app.services.conditions_service import is_known_vasrd_code
    assert is_known_vasrd_code("   ", _SAMPLE_CODES) is True


def test_code_is_stripped_before_lookup():
    """Leading/trailing spaces in user input must not cause a false negative."""
    from app.services.conditions_service import is_known_vasrd_code
    assert is_known_vasrd_code("  5242  ", _SAMPLE_CODES) is True


def test_uses_load_vasrd_codes_when_no_list_given(monkeypatch):
    """When called without known_codes, it falls back to load_vasrd_codes()."""
    from app.services import conditions_service

    # Clear LRU cache before replacing the function so any prior real data is gone
    conditions_service.load_vasrd_codes.cache_clear()

    monkeypatch.setattr(
        conditions_service, "load_vasrd_codes",
        lambda: [{"code": "0001", "name": "Test", "system": "Test"}],
    )

    from app.services.conditions_service import is_known_vasrd_code
    assert is_known_vasrd_code("0001") is True
    assert is_known_vasrd_code("9999") is False
