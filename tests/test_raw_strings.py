"""Test raw strings, quote counting, and delimiter matching."""

import pytest

from picodoc.errors import LexError
from picodoc.tokens import TokenType

from .conftest import assert_types


class TestBasicRawString:
    def test_triple_quoted(self, lex):
        tokens = lex('"""hello"""')
        assert_types(tokens, [TokenType.RAW_STRING])
        assert tokens[0].value == "hello"

    def test_four_quoted(self, lex):
        tokens = lex('""""hello""""')
        assert_types(tokens, [TokenType.RAW_STRING])
        assert tokens[0].value == "hello"

    def test_five_quoted(self, lex):
        tokens = lex('"""""hello"""""')
        assert_types(tokens, [TokenType.RAW_STRING])
        assert tokens[0].value == "hello"


class TestRawStringNoEscapeProcessing:
    def test_backslash_n_literal(self, lex):
        tokens = lex('"""\\n"""')
        assert tokens[0].value == "\\n"

    def test_hash_literal(self, lex):
        tokens = lex('"""#title"""')
        assert tokens[0].value == "#title"

    def test_backslash_literal(self, lex):
        tokens = lex('"""\\\\"""')
        assert tokens[0].value == "\\\\"

    def test_bracket_literal(self, lex):
        tokens = lex('"""[#url]"""')
        assert tokens[0].value == "[#url]"


class TestRawStringQuotesInside:
    def test_single_quote_inside(self, lex):
        """Triple-quoted raw string with a single " inside."""
        tokens = lex('"""a"b"""')
        assert tokens[0].value == 'a"b'

    def test_double_quote_inside(self, lex):
        """Triple-quoted raw string with "" inside."""
        tokens = lex('"""a""b"""')
        assert tokens[0].value == 'a""b'

    def test_triple_inside_quad_delimiter(self, lex):
        """Four-quoted raw string containing triple quotes."""
        tokens = lex('""""contains """ three quotes inside.""""')
        assert '"""' in tokens[0].value


class TestRawStringWhitespaceStripping:
    def test_multiline_with_indent_stripping(self, lex):
        source = '"""\n    line1\n    line2\n    """'
        tokens = lex(source)
        assert tokens[0].value == "line1\nline2"

    def test_first_blank_line_stripped(self, lex):
        source = '"""\nhello\n"""'
        tokens = lex(source)
        assert tokens[0].value == "hello"

    def test_no_stripping_inline(self, lex):
        tokens = lex('"""hello"""')
        assert tokens[0].value == "hello"


class TestRawStringErrors:
    def test_unterminated(self, lex):
        with pytest.raises(LexError, match="unterminated raw string"):
            lex('"""hello')

    def test_unterminated_not_enough_quotes(self, lex):
        with pytest.raises(LexError, match="unterminated raw string"):
            lex('""""hello"""')
