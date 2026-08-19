from pagination import paginate


def test_hidden_page_size_one():
    assert paginate(["a", "b", "c"], 2, 1) == ["b"]


def test_hidden_beyond_end_and_large_page():
    assert paginate([1, 2], 8, 3) == []
    assert paginate(list(range(17)), 2, 8) == list(range(8, 16))
