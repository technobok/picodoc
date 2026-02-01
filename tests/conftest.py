"""Shared test fixtures and helpers."""

from __future__ import annotations

import pytest

from picodoc.lexer import tokenize
from picodoc.tokens import Token, TokenType


@pytest.fixture
def lex():
    """Return a helper that tokenizes source and returns tokens (excluding EOF)."""

    def _lex(source: str) -> list[Token]:
        tokens = tokenize(source)
        # Strip trailing EOF for convenience
        return [t for t in tokens if t.type != TokenType.EOF]

    return _lex


def assert_types(tokens: list[Token], expected: list[TokenType]) -> None:
    """Assert that the token types match the expected list."""
    actual = [t.type for t in tokens]
    assert actual == expected, f"Expected {expected}, got {actual}"


def assert_values(tokens: list[Token], expected: list[str]) -> None:
    """Assert that the token values match the expected list."""
    actual = [t.value for t in tokens]
    assert actual == expected, f"Expected {expected}, got {actual}"


def find_tokens(tokens: list[Token], tt: TokenType) -> list[Token]:
    """Return all tokens of the given type."""
    return [t for t in tokens if t.type == tt]
