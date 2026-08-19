from service import redis_url


def test_hidden_override_and_boundary():
    assert redis_url("cache.internal", 65535) == "redis://cache.internal:65535/0"
    assert redis_url(port=1) == "redis://redis:1/0"


def test_hidden_default_is_stable():
    assert redis_url() == redis_url() == "redis://redis:6379/0"
