"""Tests for body parsing — inline, paragraph, bracketed, and string bodies."""

from __future__ import annotations

from picodoc.ast import Body, Escape, InterpString, MacroCall, RawString, Text
from tests.conftest import assert_call, body_text


class TestInlineBody:
    def test_simple_text(self, parse_source):
        doc = parse_source("#title: Hello World\n")
        call = doc.children[0]
        assert isinstance(call.body, Body)
        assert body_text(call) == "Hello World"

    def test_body_with_inline_macro(self, parse_source):
        doc = parse_source('#p: Text #b"bold" more.\n')
        call = doc.children[0]
        assert isinstance(call.body, Body)
        children = call.body.children
        assert isinstance(children[0], Text)
        assert isinstance(children[1], MacroCall)
        assert isinstance(children[2], Text)

    def test_body_with_escape(self, parse_source):
        doc = parse_source("#p: A literal \\# in text.\n")
        call = doc.children[0]
        assert isinstance(call.body, Body)
        escapes = [c for c in call.body.children if isinstance(c, Escape)]
        assert len(escapes) == 1
        assert escapes[0].value == "#"

    def test_body_coalesces_text_tokens(self, parse_source):
        """WS, IDENTIFIER, TEXT tokens in body all become Text nodes."""
        doc = parse_source("#p: hello world (yes).\n")
        call = doc.children[0]
        texts = [c for c in call.body.children if isinstance(c, Text)]
        combined = "".join(t.value for t in texts)
        assert combined == "hello world (yes)."

    def test_colon_and_equals_are_text_in_body(self, parse_source):
        """COLON and EQUALS tokens are treated as text in body context."""
        doc = parse_source("#p: key=value and a: thing\n")
        call = doc.children[0]
        assert body_text(call) == "key=value and a: thing"


class TestParagraphBody:
    def test_paragraph_body(self, parse_source):
        doc = parse_source("#p:\nBody line one.\nBody line two.\n\n")
        call = doc.children[0]
        assert isinstance(call.body, Body)
        text = body_text(call)
        assert "Body line one." in text
        assert "Body line two." in text

    def test_paragraph_body_newlines(self, parse_source):
        doc = parse_source("#p:\nLine one.\nLine two.\n\n")
        call = doc.children[0]
        text = body_text(call)
        assert "\n" in text

    def test_paragraph_body_terminated_by_blank_line(self, parse_source):
        doc = parse_source("#p:\nBody text.\n\n#hr\n")
        assert len(doc.children) == 2
        assert_call(doc.children[0], "p", has_body=True)
        assert_call(doc.children[1], "hr")

    def test_paragraph_body_terminated_by_eof(self, parse_source):
        doc = parse_source("#p:\nBody text.")
        call = doc.children[0]
        assert body_text(call) == "Body text."

    def test_paragraph_body_with_inline_macro(self, parse_source):
        doc = parse_source("#p:\nThis has #version in it.\n\n")
        call = doc.children[0]
        macros = [c for c in call.body.children if isinstance(c, MacroCall)]
        assert len(macros) == 1
        assert macros[0].name == "version"


class TestBracketedBody:
    def test_simple_bracket_body(self, parse_source):
        doc = parse_source("[#b : bold text]\n")
        call = doc.children[0]
        assert isinstance(call.body, Body)
        assert body_text(call) == "bold text"

    def test_multiline_bracket_body(self, parse_source):
        doc = parse_source("[#ul :\n  #*: First\n  #*: Second\n]\n")
        call = doc.children[0]
        assert isinstance(call.body, Body)
        items = [c for c in call.body.children if isinstance(c, MacroCall)]
        assert len(items) == 2
        assert items[0].name == "*"
        assert items[1].name == "*"

    def test_bracket_body_preserves_newlines(self, parse_source):
        doc = parse_source("[#p : line1\nline2]\n")
        call = doc.children[0]
        assert isinstance(call.body, Body)
        text = body_text(call)
        assert "line1" in text
        assert "line2" in text

    def test_nested_bracket_body(self, parse_source):
        doc = parse_source("[#b : [#i : nested]]\n")
        outer = doc.children[0]
        inner = outer.body.children[0]
        assert isinstance(inner, MacroCall)
        assert_call(inner, "i", has_body=True, bracketed=True)


class TestStringBody:
    def test_interp_string_body(self, parse_source):
        doc = parse_source('#p"Hello world"\n')
        call = doc.children[0]
        assert isinstance(call.body, InterpString)
        assert call.body.parts[0].value == "Hello world"

    def test_raw_string_body(self, parse_source):
        doc = parse_source('#p"""raw stuff"""\n')
        call = doc.children[0]
        assert isinstance(call.body, RawString)
        assert call.body.value == "raw stuff"

    def test_string_body_after_colon(self, parse_source):
        doc = parse_source('#p: "text"\n')
        call = doc.children[0]
        assert isinstance(call.body, InterpString)

    def test_string_body_after_args(self, parse_source):
        doc = parse_source('[#set name=x "value"]\n')
        call = doc.children[0]
        assert isinstance(call.body, InterpString)

    def test_empty_string_body(self, parse_source):
        doc = parse_source('#p""\n')
        call = doc.children[0]
        assert isinstance(call.body, InterpString)
        assert call.body.parts == ()


class TestBodySpans:
    def test_inline_body_span(self, parse_source):
        doc = parse_source("#title: Hello\n")
        call = doc.children[0]
        assert isinstance(call.body, Body)
        assert call.body.span.start.column == 9  # 'H' of 'Hello'

    def test_macro_call_span(self, parse_source):
        doc = parse_source("#hr\n")
        call = doc.children[0]
        assert call.span.start.line == 1
        assert call.span.start.column == 1
