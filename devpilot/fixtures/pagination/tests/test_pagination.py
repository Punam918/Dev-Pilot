import pytest
from pagination import paginate


def test_first_page():
    assert paginate([1, 2, 3, 4], 1, 2) == [1, 2]


def test_last_partial_page():
    assert paginate([1, 2, 3], 2, 2) == [3]


def test_empty_input():
    assert paginate([], 1, 3) == []


def test_invalid_page():
    with pytest.raises(ValueError):
        paginate([1], 0, 1)


def test_invalid_page_size():
    with pytest.raises(ValueError):
        paginate([1], 1, 0)
