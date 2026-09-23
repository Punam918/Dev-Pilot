import pytest
from normalize import normalize_username


def test_ascii():
    assert normalize_username("ALICE") == "alice"


def test_whitespace():
    assert normalize_username(" Alice \n") == "alice"


def test_unicode_casefold():
    assert normalize_username("Stra\u00dfe") == "strasse"


def test_empty():
    assert normalize_username("") == ""


def test_type_check():
    with pytest.raises(TypeError):
        normalize_username(42)
