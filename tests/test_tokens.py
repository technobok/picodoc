"""Test structural tokens: # [ ] : = ?"""

from picodoc.tokens import TokenType

from .conftest import assert_types


class TestHash:
    def test_single_hash(self, lex):
        tokens = lex("#")
        assert_types(tokens, [TokenType.HASH])
        assert tokens[0].value == "#"

    def test_hash_followed_by_identifier(self, lex):
        tokens = lex("#title")
        assert_types(tokens, [TokenType.HASH, TokenType.IDENTIFIER])

    def test_hash_position(self, lex):
        tokens = lex("#")
        assert tokens[0].span.start.line == 1
        assert tokens[0].span.start.column == 1


class TestBrackets:
    def test_lbracket(self, lex):
        tokens = lex("[")
        assert_types(tokens, [TokenType.LBRACKET])

    def test_rbracket(self, lex):
        tokens = lex("]")
        assert_types(tokens, [TokenType.RBRACKET])

    def test_bracket_pair(self, lex):
        tokens = lex("[]")
        assert_types(tokens, [TokenType.LBRACKET, TokenType.RBRACKET])

    def test_nested_brackets(self, lex):
        tokens = lex("[#a [#b]]")
        types = [t.type for t in tokens]
        assert types[0] == TokenType.LBRACKET
        # [, #, a, WS, [, #, b, ], ]
        assert types[4] == TokenType.LBRACKET


class TestColon:
    def test_single_colon(self, lex):
        tokens = lex(":")
        assert_types(tokens, [TokenType.COLON])
        assert tokens[0].value == ":"

    def test_colon_with_space(self, lex):
        tokens = lex(": ")
        assert_types(tokens, [TokenType.COLON, TokenType.WS])


class TestEquals:
    def test_single_equals(self, lex):
        tokens = lex("=")
        assert_types(tokens, [TokenType.EQUALS])
        assert tokens[0].value == "="


class TestQuestion:
    def test_single_question(self, lex):
        tokens = lex("?")
        assert_types(tokens, [TokenType.QUESTION])
        assert tokens[0].value == "?"

    def test_question_in_set(self, lex):
        tokens = lex("=?")
        assert_types(tokens, [TokenType.EQUALS, TokenType.QUESTION])


class TestWhitespace:
    def test_spaces(self, lex):
        tokens = lex("   ")
        assert_types(tokens, [TokenType.WS])
        assert tokens[0].value == "   "

    def test_tabs(self, lex):
        tokens = lex("\t\t")
        assert_types(tokens, [TokenType.WS])

    def test_mixed_ws(self, lex):
        tokens = lex(" \t ")
        assert_types(tokens, [TokenType.WS])


class TestNewline:
    def test_lf(self, lex):
        tokens = lex("\n")
        assert_types(tokens, [TokenType.NEWLINE])
        assert tokens[0].value == "\n"

    def test_crlf(self, lex):
        tokens = lex("\r\n")
        assert_types(tokens, [TokenType.NEWLINE])
        assert tokens[0].raw == "\r\n"
        assert tokens[0].value == "\n"

    def test_multiple_newlines(self, lex):
        tokens = lex("\n\n")
        assert_types(tokens, [TokenType.NEWLINE, TokenType.NEWLINE])
