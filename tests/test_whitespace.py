"""Test strip_string_whitespace() and dedent_body_children() in isolation."""

from picodoc.ast import Escape, Text
from picodoc.strings import dedent_body_children, strip_string_whitespace
from picodoc.tokens import Position, Span


class TestNoStripping:
    def test_empty(self):
        assert strip_string_whitespace("") == ""

    def test_single_line(self):
        assert strip_string_whitespace("hello") == "hello"

    def test_multi_line_no_indent(self):
        assert strip_string_whitespace("a\nb\nc") == "a\nb\nc"


class TestBlankFirstLine:
    def test_blank_first_line_discarded(self):
        result = strip_string_whitespace("\nhello")
        assert result == "hello"

    def test_whitespace_only_first_line_discarded(self):
        result = strip_string_whitespace("   \nhello")
        assert result == "hello"

    def test_tab_first_line_discarded(self):
        result = strip_string_whitespace("\t\nhello")
        assert result == "hello"


class TestBlankLastLine:
    def test_blank_last_line_discarded(self):
        result = strip_string_whitespace("hello\n")
        assert result == "hello"

    def test_whitespace_last_line_used_as_prefix(self):
        result = strip_string_whitespace("    hello\n    ")
        assert result == "hello"

    def test_tab_prefix_stripping(self):
        result = strip_string_whitespace("\thello\n\tworld\n\t")
        assert result == "hello\nworld"


class TestIndentStripping:
    def test_common_prefix(self):
        content = "\n    line1\n    line2\n    "
        result = strip_string_whitespace(content)
        assert result == "line1\nline2"

    def test_partial_indent(self):
        """If a non-empty line doesn't have the prefix, no stripping occurs."""
        content = "\n    line1\n  line2\n    "
        result = strip_string_whitespace(content)
        assert result == "    line1\n  line2"

    def test_blank_interior_lines_lenient(self):
        """Blank interior lines should not prevent stripping."""
        content = "\n    line1\n\n    line2\n    "
        result = strip_string_whitespace(content)
        assert result == "line1\n\nline2"

    def test_all_blank(self):
        result = strip_string_whitespace("\n\n")
        assert result == ""

    def test_first_and_last_blank(self):
        result = strip_string_whitespace("\nhello\n")
        assert result == "hello"


class TestMixedScenarios:
    def test_typical_raw_string(self):
        """Simulate the content of a typical indented raw string."""
        content = "\n        def hello():\n            print('hi')\n        "
        result = strip_string_whitespace(content)
        assert result == "def hello():\n    print('hi')"

    def test_no_content_between_delimiters(self):
        """Just blank first + blank last line."""
        result = strip_string_whitespace("\n    ")
        assert result == ""


# --- dedent_body_children tests ---

_DUMMY_SPAN = Span(Position(1, 1, 0), Position(1, 1, 0))


def _text(value: str) -> Text:
    return Text(value, _DUMMY_SPAN)


def _escape(value: str) -> Escape:
    return Escape(value, _DUMMY_SPAN)


class TestDedentBodyChildren:
    def test_basic(self):
        result = dedent_body_children((_text("    hello\n    world"),))
        assert result[0].value == "hello\nworld"

    def test_relative_indent_preserved(self):
        result = dedent_body_children((_text("    hello\n        world"),))
        assert result[0].value == "hello\n    world"

    def test_no_common_prefix(self):
        result = dedent_body_children((_text("hello\nworld"),))
        assert result[0].value == "hello\nworld"

    def test_blank_interior_lines(self):
        result = dedent_body_children((_text("    hello\n\n    world"),))
        assert result[0].value == "hello\n\nworld"

    def test_single_line(self):
        result = dedent_body_children((_text("    hello"),))
        assert result[0].value == "hello"

    def test_tabs(self):
        result = dedent_body_children((_text("\thello\n\tworld"),))
        assert result[0].value == "hello\nworld"

    def test_no_text_nodes(self):
        result = dedent_body_children((_escape("#"),))
        assert result[0].value == "#"

    def test_mixed_content(self):
        children = (_text("    Hello "), _escape("#"), _text(" world\n    More text"))
        result = dedent_body_children(children)
        assert result[0].value == "Hello "
        assert result[1].value == "#"
        assert result[2].value == " world\nMore text"

    def test_empty(self):
        result = dedent_body_children(())
        assert result == ()

    def test_whitespace_only_lines(self):
        result = dedent_body_children((_text("    hello\n  \n    world"),))
        assert result[0].value == "hello\n  \nworld"
