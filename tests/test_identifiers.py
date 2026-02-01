"""Test identifier lexing, special characters, and boundaries."""

from picodoc.tokens import TokenType, is_ident_char

from .conftest import assert_types, assert_values


class TestIsIdentChar:
    def test_letters(self):
        assert is_ident_char("a")
        assert is_ident_char("Z")

    def test_digits(self):
        assert is_ident_char("0")
        assert is_ident_char("9")

    def test_dot(self):
        assert is_ident_char(".")

    def test_special_chars(self):
        for ch in "!$%&*+-/@^_~":
            assert is_ident_char(ch), f"Expected '{ch}' to be ident_char"

    def test_non_ident(self):
        for ch in '#[]\\:=?" \t\n':
            assert not is_ident_char(ch), f"Expected '{ch}' to NOT be ident_char"

    def test_parens_not_ident(self):
        assert not is_ident_char("(")
        assert not is_ident_char(")")

    def test_comma_not_ident(self):
        assert not is_ident_char(",")


class TestIdentifierLexing:
    def test_simple_word(self, lex):
        tokens = lex("hello")
        assert_types(tokens, [TokenType.IDENTIFIER])
        assert_values(tokens, ["hello"])

    def test_dotted_name(self, lex):
        tokens = lex("env.mode")
        assert_types(tokens, [TokenType.IDENTIFIER])
        assert_values(tokens, ["env.mode"])

    def test_special_char_names(self, lex):
        tokens = lex("**")
        assert_types(tokens, [TokenType.IDENTIFIER])
        assert_values(tokens, ["**"])

    def test_dash_alias(self, lex):
        tokens = lex("---")
        assert_types(tokens, [TokenType.IDENTIFIER])
        assert_values(tokens, ["---"])

    def test_underscore_alias(self, lex):
        tokens = lex("__")
        assert_types(tokens, [TokenType.IDENTIFIER])
        assert_values(tokens, ["__"])

    def test_identifier_with_digits(self, lex):
        tokens = lex("h2")
        assert_types(tokens, [TokenType.IDENTIFIER])
        assert_values(tokens, ["h2"])

    def test_identifier_ends_at_colon(self, lex):
        tokens = lex("title:")
        assert_types(tokens, [TokenType.IDENTIFIER, TokenType.COLON])
        assert tokens[0].value == "title"

    def test_identifier_ends_at_equals(self, lex):
        tokens = lex("name=")
        assert_types(tokens, [TokenType.IDENTIFIER, TokenType.EQUALS])

    def test_identifier_ends_at_space(self, lex):
        tokens = lex("hello world")
        assert_types(tokens, [TokenType.IDENTIFIER, TokenType.WS, TokenType.IDENTIFIER])

    def test_identifier_ends_at_bracket(self, lex):
        tokens = lex("name]")
        assert_types(tokens, [TokenType.IDENTIFIER, TokenType.RBRACKET])

    def test_identifier_ends_at_quote(self, lex):
        tokens = lex('name"value"')
        types = [t.type for t in tokens]
        assert types[0] == TokenType.IDENTIFIER
        assert types[1] == TokenType.STRING_START


class TestIdentifierPositions:
    def test_position_tracking(self, lex):
        tokens = lex("abc def")
        assert tokens[0].span.start.column == 1
        assert tokens[0].span.end.column == 4
        assert tokens[2].span.start.column == 5
        assert tokens[2].span.end.column == 8
