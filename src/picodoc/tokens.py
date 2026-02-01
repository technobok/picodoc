"""Token types, data structures, and character classification helpers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    # Structural (single-character)
    HASH = auto()  # #
    LBRACKET = auto()  # [
    RBRACKET = auto()  # ]
    COLON = auto()  # :
    EQUALS = auto()  # =
    QUESTION = auto()  # ?

    # Content
    IDENTIFIER = auto()  # ident_char+ (letters, digits, ., !$%&*+-/@^_~)
    TEXT = auto()  # non-ident, non-special char runs (, ( ) etc.)
    ESCAPE = auto()  # prose escape — value is resolved character

    # Interpreted string sub-tokens
    STRING_START = auto()  # opening "
    STRING_END = auto()  # closing "
    STRING_TEXT = auto()  # literal text segment within string
    STRING_ESCAPE = auto()  # string escape — value is resolved character
    CODE_OPEN = auto()  # \[ entering code mode
    CODE_CLOSE = auto()  # ] exiting code mode (bracket depth hits 0)

    # Raw string (single token, content after whitespace stripping)
    RAW_STRING = auto()

    # Whitespace
    WS = auto()  # horizontal whitespace (spaces/tabs)
    NEWLINE = auto()  # \n or \r\n

    EOF = auto()


@dataclass(frozen=True, slots=True)
class Position:
    """Source position, 1-based line and column, 0-based byte offset."""

    line: int
    column: int
    offset: int


@dataclass(frozen=True, slots=True)
class Span:
    """Source range from start to end position."""

    start: Position
    end: Position


@dataclass(frozen=True, slots=True)
class Token:
    """A single lexer token with resolved value and original source text."""

    type: TokenType
    value: str
    raw: str
    span: Span


# Identifier special characters: ! $ % & * + - / @ ^ _ ~
_IDENT_SPECIAL = frozenset("!$%&*+-/@^_~")


def is_ident_char(ch: str) -> bool:
    """Return True if ch is a valid identifier character."""
    return ch.isalpha() or ch.isdigit() or ch == "." or ch in _IDENT_SPECIAL


def is_hex_digit(ch: str) -> bool:
    """Return True if ch is a hexadecimal digit."""
    return ch in "0123456789abcdefABCDEF"
