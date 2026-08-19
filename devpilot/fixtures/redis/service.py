"""Redis endpoint configuration for a Compose-based API."""
DEFAULT_REDIS_HOST = "localhost"


def redis_url(host: str | None = None, port: int = 6379) -> str:
    if not 1 <= port <= 65535:
        raise ValueError("port must be in 1..65535")
    return f"redis://{host or DEFAULT_REDIS_HOST}:{port}/0"
