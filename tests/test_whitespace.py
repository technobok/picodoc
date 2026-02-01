"""Test strip_string_whitespace() in isolation."""

from picodoc.strings import strip_string_whitespace


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
