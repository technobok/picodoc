"""Tests for string parsing in parser context — interp strings, code sections."""

from __future__ import annotations

from picodoc.ast import CodeSection, InterpString, MacroCall, RawString, Text
from tests.conftest import assert_call


class TestInterpStringParts:
    def test_simple_string(self, parse_source):
        doc = parse_source('#p"Hello"\n')
        call = doc.children[0]
        assert isinstance(call.body, InterpString)
        assert len(call.body.parts) == 1
        assert call.body.parts[0].value == "Hello"

    def test_string_with_escape(self, parse_source):
        doc = parse_source('#p"tab:\\there"\n')
        call = doc.children[0]
        assert isinstance(call.body, InterpString)
        # STRING_TEXT("tab:") + STRING_ESCAPE(\t) + STRING_TEXT("here") → coalesced
        assert call.body.parts[0].value == "tab:\there"

    def test_string_with_newline_escape(self, parse_source):
        doc = parse_source('#p"Line one.\\nLine two."\n')
        call = doc.children[0]
        assert isinstance(call.body, InterpString)
        assert call.body.parts[0].value == "Line one.\nLine two."

    def test_empty_string(self, parse_source):
        doc = parse_source('#p""\n')
        call = doc.children[0]
        assert isinstance(call.body, InterpString)
        assert call.body.parts == ()


class TestCodeSections:
    def test_simple_code_section(self, parse_source):
        doc = parse_source('#p"Hello, \\[#version]!"\n')
        call = doc.children[0]
        assert isinstance(call.body, InterpString)
        parts = call.body.parts
        assert len(parts) == 3
        assert isinstance(parts[0], Text)
        assert parts[0].value == "Hello, "
        assert isinstance(parts[1], CodeSection)
        assert isinstance(parts[2], Text)
        assert parts[2].value == "!"

    def test_code_section_body(self, parse_source):
        doc = parse_source('#p"\\[#version]"\n')
        call = doc.children[0]
        cs = call.body.parts[0]
        assert isinstance(cs, CodeSection)
        assert len(cs.body) == 1
        assert isinstance(cs.body[0], MacroCall)
        assert cs.body[0].name == "version"

    def test_code_section_with_complex_call(self, parse_source):
        doc = parse_source('#p"\\[#url link="x" text="y"]"\n')
        call = doc.children[0]
        cs = call.body.parts[0]
        assert isinstance(cs, CodeSection)
        assert len(cs.body) == 1
        assert isinstance(cs.body[0], MacroCall)
        assert_call(cs.body[0], "url", num_args=2, bracketed=False)


class TestRawStrings:
    def test_raw_string(self, parse_source):
        doc = parse_source('#p"""raw \\n content"""\n')
        call = doc.children[0]
        assert isinstance(call.body, RawString)
        assert call.body.value == "raw \\n content"

    def test_raw_string_multiline(self, parse_source):
        doc = parse_source('#p"""\n    line one\n    line two\n    """\n')
        call = doc.children[0]
        assert isinstance(call.body, RawString)
        assert "line one" in call.body.value
        assert "line two" in call.body.value


class TestStringSpans:
    def test_interp_string_span(self, parse_source):
        doc = parse_source('#p"text"\n')
        call = doc.children[0]
        assert isinstance(call.body, InterpString)
        # Span starts at opening quote
        assert call.body.span.start.column == 3

    def test_raw_string_span(self, parse_source):
        doc = parse_source('#p"""raw"""\n')
        call = doc.children[0]
        assert isinstance(call.body, RawString)
        assert call.body.span.start.column == 3
