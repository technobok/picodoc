"""Test raw strings, quote counting, and delimiter matching."""

import pytest

from picodoc.errors import LexError
from picodoc.tokens import TokenType


class TestBasicRawString:
    def test_triple_quoted(self, lex):
        tokens = lex('x="""hello"""')
        raw = [t for t in tokens if t.type == TokenType.RAW_STRING]
        assert len(raw) == 1
        assert raw[0].value == "hello"

    def test_four_quoted(self, lex):
        tokens = lex('x=""""hello""""')
        raw = [t for t in tokens if t.type == TokenType.RAW_STRING]
        assert len(raw) == 1
        assert raw[0].value == "hello"

    def test_five_quoted(self, lex):
        tokens = lex('x="""""hello"""""')
        raw = [t for t in tokens if t.type == TokenType.RAW_STRING]
        assert len(raw) == 1
        assert raw[0].value == "hello"


class TestRawStringNoEscapeProcessing:
    def test_backslash_n_literal(self, lex):
        tokens = lex('x="""\\n"""')
        raw = [t for t in tokens if t.type == TokenType.RAW_STRING]
        assert raw[0].value == "\\n"

    def test_hash_literal(self, lex):
        tokens = lex('x="""#doc.title"""')
        raw = [t for t in tokens if t.type == TokenType.RAW_STRING]
        assert raw[0].value == "#doc.title"

    def test_backslash_literal(self, lex):
        tokens = lex('x="""\\\\"""')
        raw = [t for t in tokens if t.type == TokenType.RAW_STRING]
        assert raw[0].value == "\\\\"

    def test_bracket_literal(self, lex):
        tokens = lex('x="""[#url]"""')
        raw = [t for t in tokens if t.type == TokenType.RAW_STRING]
        assert raw[0].value == "[#url]"


class TestRawStringQuotesInside:
    def test_single_quote_inside(self, lex):
        """Triple-quoted raw string with a single " inside."""
        tokens = lex('x="""a"b"""')
        raw = [t for t in tokens if t.type == TokenType.RAW_STRING]
        assert raw[0].value == 'a"b'

    def test_double_quote_inside(self, lex):
        """Triple-quoted raw string with "" inside."""
        tokens = lex('x="""a""b"""')
        raw = [t for t in tokens if t.type == TokenType.RAW_STRING]
        assert raw[0].value == 'a""b'

    def test_triple_inside_quad_delimiter(self, lex):
        """Four-quoted raw string containing triple quotes."""
        tokens = lex('x=""""contains """ three quotes inside.""""')
        raw = [t for t in tokens if t.type == TokenType.RAW_STRING]
        assert '"""' in raw[0].value


class TestRawStringWhitespaceStripping:
    def test_multiline_with_indent_stripping(self, lex):
        source = 'x="""\n    line1\n    line2\n    """'
        tokens = lex(source)
        raw = [t for t in tokens if t.type == TokenType.RAW_STRING]
        assert raw[0].value == "line1\nline2"

    def test_first_blank_line_stripped(self, lex):
        source = 'x="""\nhello\n"""'
        tokens = lex(source)
        raw = [t for t in tokens if t.type == TokenType.RAW_STRING]
        assert raw[0].value == "hello"

    def test_no_stripping_inline(self, lex):
        tokens = lex('x="""hello"""')
        raw = [t for t in tokens if t.type == TokenType.RAW_STRING]
        assert raw[0].value == "hello"


class TestRawStringAdjacentStrings:
    def test_raw_string_space_then_interp_ok(self, lex):
        """After a raw string, a space-separated string needs its own context."""
        tokens = lex('#x"""raw""" y="next"')
        raw = [t for t in tokens if t.type == TokenType.RAW_STRING]
        assert len(raw) == 1
        assert raw[0].value == "raw"

    def test_raw_string_newline_then_interp_ok(self, lex):
        """After a raw string, a newline-separated string needs its own context."""
        tokens = lex('#x"""raw"""\ny="next"')
        raw = [t for t in tokens if t.type == TokenType.RAW_STRING]
        assert len(raw) == 1
        assert raw[0].value == "raw"


class TestRawStringErrors:
    def test_unterminated(self, lex):
        with pytest.raises(LexError, match="unterminated raw string"):
            lex('x="""hello')

    def test_unterminated_not_enough_quotes(self, lex):
        with pytest.raises(LexError, match="unterminated raw string"):
            lex('x=""""hello"""')
