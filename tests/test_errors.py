"""Test error messages, position accuracy, and context snippets."""

import pytest

from picodoc.errors import LexError
from picodoc.lexer import tokenize


class TestErrorPositions:
    def test_invalid_escape_position(self):
        with pytest.raises(LexError) as exc_info:
            tokenize("abc \\q rest")
        err = exc_info.value
        assert err.position.line == 1
        assert err.position.column == 5

    def test_error_on_second_line(self):
        with pytest.raises(LexError) as exc_info:
            tokenize("line one\n\\q")
        err = exc_info.value
        assert err.position.line == 2
        assert err.position.column == 1

    def test_error_in_string(self):
        with pytest.raises(LexError) as exc_info:
            tokenize('"hello\\q"')
        err = exc_info.value
        assert err.position.line == 1

    def test_nul_character(self):
        with pytest.raises(LexError, match="NUL"):
            tokenize("hello\0world")


class TestErrorFormatting:
    def test_format_contains_line(self):
        with pytest.raises(LexError) as exc_info:
            tokenize("some text \\q more text")
        formatted = exc_info.value.format()
        assert "some text \\q more text" in formatted

    def test_format_contains_carets(self):
        with pytest.raises(LexError) as exc_info:
            tokenize("\\q")
        formatted = exc_info.value.format()
        assert "^" in formatted

    def test_format_contains_error_prefix(self):
        with pytest.raises(LexError) as exc_info:
            tokenize("\\q")
        formatted = exc_info.value.format()
        assert formatted.startswith("error:")

    def test_format_contains_position(self):
        with pytest.raises(LexError) as exc_info:
            tokenize("\\q")
        formatted = exc_info.value.format()
        assert "1:1" in formatted

    def test_format_with_custom_filename(self):
        with pytest.raises(LexError) as exc_info:
            tokenize("\\q", filename="test.pdoc")
        formatted = exc_info.value.format("test.pdoc")
        assert "test.pdoc" in formatted

    def test_multiline_error_position(self):
        source = "line1\nline2\n\\q"
        with pytest.raises(LexError) as exc_info:
            tokenize(source)
        formatted = exc_info.value.format()
        assert "3:1" in formatted
