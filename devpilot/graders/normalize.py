from normalize import normalize_username


def test_hidden_unicode_and_internal_space():
    assert normalize_username("  GRO\u1e9e  ") == "gross"
    assert normalize_username(" Alice Smith ") == "alice smith"


def test_hidden_idempotence():
    value = normalize_username("  Stra\u00dfe \t")
    assert normalize_username(value) == value
