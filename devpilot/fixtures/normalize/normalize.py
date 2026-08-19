"""Normalize a user name for case-insensitive matching."""


def normalize_username(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("username must be a string")
    return value.lower()
