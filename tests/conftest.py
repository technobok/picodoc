"""Shared test fixtures and helpers."""

from __future__ import annotations

import pytest

from picodoc.ast import Body, Document, MacroCall, Paragraph, Text
from picodoc.lexer import tokenize
from picodoc.parser import parse
from picodoc.tokens import Token, TokenType


@pytest.fixture
def lex():
    """Return a helper that tokenizes source and returns tokens (excluding EOF)."""

    def _lex(source: str) -> list[Token]:
        tokens = tokenize(source)
        # Strip trailing EOF for convenience
        return [t for t in tokens if t.type != TokenType.EOF]

    return _lex


@pytest.fixture
def parse_source():
    """Return a helper that parses source and returns a Document."""

    def _parse(source: str, filename: str = "test.pdoc") -> Document:
        return parse(source, filename)

    return _parse


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


def assert_call(
    node: MacroCall,
    name: str,
    num_args: int = 0,
    has_body: bool = False,
    bracketed: bool | None = None,
) -> None:
    """Assert basic properties of a MacroCall node."""
    assert isinstance(node, MacroCall), f"Expected MacroCall, got {type(node).__name__}"
    assert node.name == name, f"Expected name '{name}', got '{node.name}'"
    assert len(node.args) == num_args, f"Expected {num_args} args, got {len(node.args)}"
    if has_body:
        assert node.body is not None, "Expected body, got None"
    else:
        assert node.body is None, f"Expected no body, got {node.body}"
    if bracketed is not None:
        assert node.bracketed == bracketed, f"Expected bracketed={bracketed}, got {node.bracketed}"


def body_text(node: MacroCall | Paragraph) -> str:
    """Extract concatenated text from a node's body (Body or Paragraph)."""
    if isinstance(node, Paragraph):
        children = node.body
    elif isinstance(node, MacroCall) and isinstance(node.body, Body):
        children = node.body.children
    else:
        raise TypeError(f"Cannot extract body text from {type(node).__name__}")
    return "".join(c.value for c in children if isinstance(c, Text))
