"""Tests for parser error messages and positions."""

from __future__ import annotations

import pytest

from picodoc.ast import Paragraph
from picodoc.errors import ParseError
from picodoc.parser import parse


class TestBareDelimiters:
    def test_bare_lbracket_in_body(self):
        with pytest.raises(ParseError, match="bare '\\[' in text"):
            parse("#p: text [ more\n")

    def test_bare_rbracket_in_body(self):
        with pytest.raises(ParseError, match="bare '\\]' in text"):
            parse("#p: text ] more\n")


class TestMissingParts:
    def test_missing_rbracket(self):
        with pytest.raises(ParseError, match="expected closing '\\]'"):
            parse("[#b : text\n")

    def test_missing_macro_name(self):
        with pytest.raises(ParseError, match="expected macro name"):
            parse("#\n")

    def test_missing_macro_name_in_bracket(self):
        with pytest.raises(ParseError, match="bare '\\[' in text"):
            parse("[foo]\n")

    def test_missing_arg_value(self):
        with pytest.raises(ParseError, match="expected argument value"):
            parse("[#set name=]\n")


class TestTrailingText:
    def test_macro_with_trailing_text_is_paragraph(self):
        """Macro with trailing text falls back to paragraph parsing."""
        doc = parse("#hr extra\n")
        assert len(doc.children) == 1
        assert isinstance(doc.children[0], Paragraph)

    def test_bracketed_with_trailing_text_is_paragraph(self):
        doc = parse("[#set name=x] extra\n")
        assert len(doc.children) == 1
        assert isinstance(doc.children[0], Paragraph)


class TestBracketedErrors:
    def test_bare_text_in_bracketed(self):
        with pytest.raises(ParseError):
            parse("[#b extra text without colon]\n")


class TestErrorPosition:
    def test_error_has_span(self):
        with pytest.raises(ParseError) as exc_info:
            parse("#\n")
        assert exc_info.value.span is not None
        assert exc_info.value.span.start.line == 1

    def test_error_format_contains_arrow(self):
        with pytest.raises(ParseError) as exc_info:
            parse("#\n")
        formatted = exc_info.value.format("test.pdoc")
        assert "-->" in formatted
        assert "test.pdoc" in formatted

    def test_error_format_contains_carets(self):
        with pytest.raises(ParseError) as exc_info:
            parse("#\n")
        formatted = exc_info.value.format()
        assert "^" in formatted


class TestParseErrorFormat:
    def test_format_multiline_span(self):
        """ParseError with a span crossing lines uses end-of-line underline."""
        err = ParseError(
            "test error",
            __import__("picodoc.tokens", fromlist=["Span"]).Span(
                __import__("picodoc.tokens", fromlist=["Position"]).Position(1, 1, 0),
                __import__("picodoc.tokens", fromlist=["Position"]).Position(2, 5, 10),
            ),
            "first line\nsecond line",
        )
        formatted = err.format("test.pdoc")
        assert "error: test error" in formatted
        assert "^" in formatted
