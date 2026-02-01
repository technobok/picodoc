"""Test interpreted strings, code mode, and nesting."""

import pytest

from picodoc.errors import LexError
from picodoc.tokens import TokenType

from .conftest import assert_types, find_tokens


class TestBasicInterpString:
    def test_simple_string(self, lex):
        tokens = lex('"hello"')
        assert_types(
            tokens,
            [TokenType.STRING_START, TokenType.STRING_TEXT, TokenType.STRING_END],
        )
        assert tokens[1].value == "hello"

    def test_empty_string(self, lex):
        tokens = lex('""')
        assert_types(tokens, [TokenType.STRING_START, TokenType.STRING_END])

    def test_string_with_escape(self, lex):
        tokens = lex('"hello\\nworld"')
        assert_types(
            tokens,
            [
                TokenType.STRING_START,
                TokenType.STRING_TEXT,
                TokenType.STRING_ESCAPE,
                TokenType.STRING_TEXT,
                TokenType.STRING_END,
            ],
        )
        assert tokens[1].value == "hello"
        assert tokens[2].value == "\n"
        assert tokens[3].value == "world"

    def test_string_with_only_escape(self, lex):
        tokens = lex('"\\t"')
        assert_types(
            tokens,
            [TokenType.STRING_START, TokenType.STRING_ESCAPE, TokenType.STRING_END],
        )

    def test_string_preserves_brackets(self, lex):
        """Unescaped [ and ] inside strings are just text (not structural)."""
        tokens = lex('"a]b"')
        text_tokens = find_tokens(tokens, TokenType.STRING_TEXT)
        combined = "".join(t.value for t in text_tokens)
        assert combined == "a]b"

    def test_unescaped_lbracket_is_text(self, lex):
        """[ without backslash inside string is just text."""
        tokens = lex('"a[b"')
        text_tokens = find_tokens(tokens, TokenType.STRING_TEXT)
        combined = "".join(t.value for t in text_tokens)
        assert combined == "a[b"


class TestCodeMode:
    def test_simple_code_mode(self, lex):
        tokens = lex('"hello \\[#name]"')
        types = [t.type for t in tokens]
        assert TokenType.CODE_OPEN in types
        assert TokenType.CODE_CLOSE in types
        # Inside code mode: HASH, IDENTIFIER
        code_open_idx = types.index(TokenType.CODE_OPEN)
        code_close_idx = types.index(TokenType.CODE_CLOSE)
        inner = tokens[code_open_idx + 1 : code_close_idx]
        inner_types = [t.type for t in inner]
        assert TokenType.HASH in inner_types
        assert TokenType.IDENTIFIER in inner_types

    def test_code_mode_with_bracketed_call(self, lex):
        tokens = lex('"\\[#url link="x" text="y"]"')
        types = [t.type for t in tokens]
        assert TokenType.CODE_OPEN in types
        assert TokenType.CODE_CLOSE in types

    def test_code_mode_nested_brackets(self, lex):
        """Nested brackets inside code mode should work."""
        tokens = lex('"\\[[#a]]"')
        types = [t.type for t in tokens]
        assert TokenType.CODE_OPEN in types
        assert TokenType.CODE_CLOSE in types
        # The inner [ ] should be LBRACKET / RBRACKET
        assert TokenType.LBRACKET in types
        assert TokenType.RBRACKET in types

    def test_code_mode_with_string_inside(self, lex):
        """Nested string inside code mode inside a string."""
        tokens = lex('"\\[#b"bold"]"')
        types = [t.type for t in tokens]
        # Should have: STRING_START, CODE_OPEN, HASH, IDENTIFIER, STRING_START,
        # STRING_TEXT, STRING_END, CODE_CLOSE, STRING_END
        assert types.count(TokenType.STRING_START) == 2
        assert types.count(TokenType.STRING_END) == 2

    def test_code_mode_version_example(self, lex):
        """Example from spec: "Hello, \\[#version]!" """
        tokens = lex('"Hello, \\[#version]!"')
        types = [t.type for t in tokens]
        assert types == [
            TokenType.STRING_START,
            TokenType.STRING_TEXT,
            TokenType.CODE_OPEN,
            TokenType.HASH,
            TokenType.IDENTIFIER,
            TokenType.CODE_CLOSE,
            TokenType.STRING_TEXT,
            TokenType.STRING_END,
        ]
        assert tokens[1].value == "Hello, "
        assert tokens[4].value == "version"
        assert tokens[6].value == "!"


class TestUnterminatedString:
    def test_unterminated(self, lex):
        with pytest.raises(LexError, match="unterminated"):
            lex('"hello')

    def test_unterminated_with_escape(self, lex):
        with pytest.raises(LexError, match=r"unterminated|unexpected end"):
            lex('"hello\\')
