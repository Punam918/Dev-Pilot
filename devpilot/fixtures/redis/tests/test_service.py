import pytest
from service import redis_url


def test_compose_default():
    assert redis_url() == "redis://redis:6379/0"


def test_explicit_host():
    assert redis_url("cache") == "redis://cache:6379/0"


def test_custom_port():
    assert redis_url("cache", 6380) == "redis://cache:6380/0"


def test_rejects_invalid_port():
    with pytest.raises(ValueError):
        redis_url(port=0)
