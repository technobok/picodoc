"""Tests for document structure — paragraphs, blank lines, mixed blocks."""

from __future__ import annotations

from picodoc.ast import MacroCall, Paragraph, Text
from tests.conftest import assert_call


class TestEmptyDocument:
    def test_empty(self, parse_source):
        doc = parse_source("")
        assert doc.children == ()

    def test_only_newlines(self, parse_source):
        doc = parse_source("\n\n\n")
        assert doc.children == ()

    def test_only_whitespace_lines(self, parse_source):
        doc = parse_source("  \n\t\n  \n")
        assert doc.children == ()


class TestParagraphs:
    def test_single_paragraph(self, parse_source):
        doc = parse_source("Hello world.\n")
        assert len(doc.children) == 1
        assert isinstance(doc.children[0], Paragraph)
        text = "".join(c.value for c in doc.children[0].body if isinstance(c, Text))
        assert text == "Hello world."

    def test_paragraph_no_trailing_newline(self, parse_source):
        doc = parse_source("Hello world.")
        assert len(doc.children) == 1
        assert isinstance(doc.children[0], Paragraph)

    def test_multiline_paragraph(self, parse_source):
        doc = parse_source("Line one.\nLine two.\n\n")
        assert len(doc.children) == 1
        para = doc.children[0]
        assert isinstance(para, Paragraph)
        text = "".join(c.value for c in para.body if isinstance(c, Text))
        assert "Line one." in text
        assert "\n" in text
        assert "Line two." in text

    def test_two_paragraphs(self, parse_source):
        doc = parse_source("First para.\n\nSecond para.\n")
        assert len(doc.children) == 2
        assert isinstance(doc.children[0], Paragraph)
        assert isinstance(doc.children[1], Paragraph)


class TestParagraphTermination:
    def test_paragraph_terminated_by_hash(self, parse_source):
        doc = parse_source("Some text.\n#hr\n")
        assert len(doc.children) == 2
        assert isinstance(doc.children[0], Paragraph)
        assert isinstance(doc.children[1], MacroCall)

    def test_paragraph_terminated_by_bracket_hash(self, parse_source):
        doc = parse_source("Some text.\n[#b : bold]\n")
        assert len(doc.children) == 2
        assert isinstance(doc.children[0], Paragraph)
        assert isinstance(doc.children[1], MacroCall)

    def test_paragraph_terminated_by_blank_line(self, parse_source):
        doc = parse_source("Para one.\n\nPara two.\n")
        assert len(doc.children) == 2
        assert isinstance(doc.children[0], Paragraph)
        assert isinstance(doc.children[1], Paragraph)


class TestMixedBlocks:
    def test_macro_then_paragraph(self, parse_source):
        doc = parse_source("#title: Hello\n\nSome text.\n")
        assert len(doc.children) == 2
        assert isinstance(doc.children[0], MacroCall)
        assert isinstance(doc.children[1], Paragraph)

    def test_paragraph_between_macros(self, parse_source):
        doc = parse_source("#h2: Title\n\nSome paragraph.\n\n#hr\n")
        assert len(doc.children) == 3
        assert_call(doc.children[0], "h2", has_body=True)
        assert isinstance(doc.children[1], Paragraph)
        assert_call(doc.children[2], "hr")

    def test_multiple_macros(self, parse_source):
        doc = parse_source("#h2: A\n\n#h3: B\n\n#hr\n")
        assert len(doc.children) == 3
        assert all(isinstance(c, MacroCall) for c in doc.children)

    def test_blank_lines_between_blocks(self, parse_source):
        doc = parse_source("\n\n#hr\n\n\n#hr\n\n")
        assert len(doc.children) == 2
        assert_call(doc.children[0], "hr")
        assert_call(doc.children[1], "hr")


class TestParagraphInlineContent:
    def test_paragraph_with_inline_macro(self, parse_source):
        doc = parse_source('This has #b"bold" text.\n\n')
        para = doc.children[0]
        assert isinstance(para, Paragraph)
        macros = [c for c in para.body if isinstance(c, MacroCall)]
        assert len(macros) == 1
        assert macros[0].name == "b"

    def test_paragraph_with_bracket_call(self, parse_source):
        doc = parse_source('Visit [#url link="x" text="y"] today.\n\n')
        para = doc.children[0]
        assert isinstance(para, Paragraph)
        macros = [c for c in para.body if isinstance(c, MacroCall)]
        assert len(macros) == 1
        assert macros[0].name == "url"


class TestDocumentSpans:
    def test_document_span(self, parse_source):
        doc = parse_source("#hr\n")
        assert doc.span.start.line == 1
        assert doc.span.start.column == 1

    def test_paragraph_span(self, parse_source):
        doc = parse_source("Hello.\n")
        para = doc.children[0]
        assert para.span.start.line == 1
        assert para.span.start.column == 1
