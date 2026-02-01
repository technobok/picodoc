"""Test prose escapes, string escapes, hex/unicode, and invalid escapes."""

import pytest

from picodoc.errors import LexError
from picodoc.tokens import TokenType

from .conftest import assert_types


class TestProseEscapes:
    def test_backslash(self, lex):
        tokens = lex("\\\\")
        assert_types(tokens, [TokenType.ESCAPE])
        assert tokens[0].value == "\\"
        assert tokens[0].raw == "\\\\"

    def test_hash(self, lex):
        tokens = lex("\\#")
        assert_types(tokens, [TokenType.ESCAPE])
        assert tokens[0].value == "#"

    def test_lbracket(self, lex):
        tokens = lex("\\[")
        assert_types(tokens, [TokenType.ESCAPE])
        assert tokens[0].value == "["

    def test_rbracket(self, lex):
        tokens = lex("\\]")
        assert_types(tokens, [TokenType.ESCAPE])
        assert tokens[0].value == "]"

    def test_colon(self, lex):
        tokens = lex("\\:")
        assert_types(tokens, [TokenType.ESCAPE])
        assert tokens[0].value == ":"

    def test_equals(self, lex):
        tokens = lex("\\=")
        assert_types(tokens, [TokenType.ESCAPE])
        assert tokens[0].value == "="


class TestHexEscapes:
    def test_prose_hex(self, lex):
        tokens = lex("\\xA9")
        assert_types(tokens, [TokenType.ESCAPE])
        assert tokens[0].value == "\u00a9"  # copyright symbol
        assert tokens[0].raw == "\\xA9"

    def test_prose_hex_lowercase(self, lex):
        tokens = lex("\\xff")
        assert tokens[0].value == "\u00ff"

    def test_prose_unicode(self, lex):
        tokens = lex("\\U00002014")
        assert_types(tokens, [TokenType.ESCAPE])
        assert tokens[0].value == "\u2014"  # em dash
        assert tokens[0].raw == "\\U00002014"

    def test_prose_unicode_zero(self, lex):
        tokens = lex("\\U00000041")
        assert tokens[0].value == "A"

    def test_string_hex(self, lex):
        tokens = lex('"\\xA9"')
        escape_tokens = [t for t in tokens if t.type == TokenType.STRING_ESCAPE]
        assert len(escape_tokens) == 1
        assert escape_tokens[0].value == "\u00a9"

    def test_string_unicode(self, lex):
        tokens = lex('"\\U00002014"')
        escape_tokens = [t for t in tokens if t.type == TokenType.STRING_ESCAPE]
        assert len(escape_tokens) == 1
        assert escape_tokens[0].value == "\u2014"


class TestStringEscapes:
    def test_backslash_in_string(self, lex):
        tokens = lex('"\\\\"')
        escape_tokens = [t for t in tokens if t.type == TokenType.STRING_ESCAPE]
        assert len(escape_tokens) == 1
        assert escape_tokens[0].value == "\\"

    def test_quote_in_string(self, lex):
        tokens = lex('"\\""')
        escape_tokens = [t for t in tokens if t.type == TokenType.STRING_ESCAPE]
        assert len(escape_tokens) == 1
        assert escape_tokens[0].value == '"'

    def test_newline_in_string(self, lex):
        tokens = lex('"\\n"')
        escape_tokens = [t for t in tokens if t.type == TokenType.STRING_ESCAPE]
        assert escape_tokens[0].value == "\n"

    def test_tab_in_string(self, lex):
        tokens = lex('"\\t"')
        escape_tokens = [t for t in tokens if t.type == TokenType.STRING_ESCAPE]
        assert escape_tokens[0].value == "\t"


class TestInvalidEscapes:
    def test_invalid_prose_escape(self, lex):
        with pytest.raises(LexError, match="invalid escape sequence"):
            lex("\\q")

    def test_invalid_string_escape(self, lex):
        with pytest.raises(LexError, match="invalid string escape sequence"):
            lex('"\\q"')

    def test_incomplete_hex(self, lex):
        with pytest.raises(LexError, match="incomplete escape"):
            lex("\\xA")

    def test_invalid_hex_digit(self, lex):
        with pytest.raises(LexError, match="invalid hex digit"):
            lex("\\xGG")

    def test_incomplete_unicode(self, lex):
        with pytest.raises(LexError, match="incomplete escape"):
            lex("\\U0000")

    def test_backslash_at_eof(self, lex):
        with pytest.raises(LexError, match="unexpected end of input"):
            lex("\\")

    def test_backslash_at_eof_in_string(self, lex):
        with pytest.raises(LexError, match="unexpected end of input"):
            lex('"\\')

    def test_prose_escape_n_is_invalid(self, lex):
        """\\n is not valid in prose context (only in strings)."""
        with pytest.raises(LexError, match="invalid escape sequence"):
            lex("\\n")

    def test_prose_escape_t_is_invalid(self, lex):
        with pytest.raises(LexError, match="invalid escape sequence"):
            lex("\\t")

    def test_prose_escape_quote_is_invalid(self, lex):
        with pytest.raises(LexError, match="invalid escape sequence"):
            lex('\\"')
