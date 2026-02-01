"""Tests for macro call parsing — unbracketed and bracketed forms."""

from __future__ import annotations

from picodoc.ast import Body, InterpString, MacroCall, RawString, Text
from tests.conftest import assert_call, body_text


class TestUnbracketedNoBody:
    def test_simple_macro(self, parse_source):
        doc = parse_source("#hr\n")
        assert len(doc.children) == 1
        assert_call(doc.children[0], "hr", bracketed=False)

    def test_macro_no_trailing_newline(self, parse_source):
        doc = parse_source("#hr")
        assert len(doc.children) == 1
        assert_call(doc.children[0], "hr", bracketed=False)

    def test_heading_aliases(self, parse_source):
        for name in ("-", "--", "---"):
            doc = parse_source(f"#{name}: Title\n")
            assert_call(doc.children[0], name, has_body=True, bracketed=False)


class TestUnbracketedInlineBody:
    def test_colon_body(self, parse_source):
        doc = parse_source("#title: Welcome to PicoDoc\n")
        call = doc.children[0]
        assert_call(call, "title", has_body=True, bracketed=False)
        assert isinstance(call.body, Body)
        assert body_text(call) == "Welcome to PicoDoc"

    def test_colon_no_ws_before(self, parse_source):
        doc = parse_source("#title:text\n")
        call = doc.children[0]
        assert_call(call, "title", has_body=True, bracketed=False)
        assert body_text(call) == "text"

    def test_comment(self, parse_source):
        doc = parse_source("#comment: This text will not appear.\n")
        assert_call(doc.children[0], "comment", has_body=True)


class TestUnbracketedStringBody:
    def test_string_body_no_ws(self, parse_source):
        doc = parse_source('#b"bold"\n')
        call = doc.children[0]
        assert_call(call, "b", has_body=True, bracketed=False)
        assert isinstance(call.body, InterpString)
        assert len(call.body.parts) == 1
        assert isinstance(call.body.parts[0], Text)
        assert call.body.parts[0].value == "bold"

    def test_string_body_with_ws(self, parse_source):
        doc = parse_source('#p "text"\n')
        call = doc.children[0]
        assert_call(call, "p", has_body=True, bracketed=False)
        assert isinstance(call.body, InterpString)

    def test_raw_string_body(self, parse_source):
        doc = parse_source('#p"""raw content"""\n')
        call = doc.children[0]
        assert_call(call, "p", has_body=True, bracketed=False)
        assert isinstance(call.body, RawString)
        assert call.body.value == "raw content"

    def test_string_body_with_colon(self, parse_source):
        """Colon before string produces string body, not Body wrapping string."""
        doc = parse_source('#p: "text"\n')
        call = doc.children[0]
        assert_call(call, "p", has_body=True, bracketed=False)
        assert isinstance(call.body, InterpString)


class TestBracketedCalls:
    def test_simple_bracketed(self, parse_source):
        doc = parse_source("[#set name=version : 1.0]\n")
        call = doc.children[0]
        assert_call(call, "set", num_args=1, has_body=True, bracketed=True)
        assert call.args[0].name == "name"
        assert isinstance(call.args[0].value, Text)
        assert call.args[0].value.value == "version"
        assert isinstance(call.body, Body)
        assert body_text(call) == "1.0"

    def test_bracketed_no_body(self, parse_source):
        doc = parse_source('[#include file="header.pdoc"]\n')
        call = doc.children[0]
        assert_call(call, "include", num_args=1, has_body=False, bracketed=True)

    def test_bracketed_inline_body(self, parse_source):
        doc = parse_source("[#b : bold text]\n")
        call = doc.children[0]
        assert_call(call, "b", has_body=True, bracketed=True)
        assert isinstance(call.body, Body)
        assert body_text(call) == "bold text"

    def test_bracketed_string_body(self, parse_source):
        doc = parse_source('[#set name=motto "Write less."]\n')
        call = doc.children[0]
        assert_call(call, "set", num_args=1, has_body=True, bracketed=True)
        assert isinstance(call.body, InterpString)


class TestNestedCalls:
    def test_nested_bracket_calls(self, parse_source):
        doc = parse_source("[#b : [#i : text]]\n")
        outer = doc.children[0]
        assert_call(outer, "b", has_body=True, bracketed=True)
        assert isinstance(outer.body, Body)
        inner = outer.body.children[0]
        assert isinstance(inner, MacroCall)
        assert_call(inner, "i", has_body=True, bracketed=True)
        assert body_text(inner) == "text"

    def test_inline_call_in_body(self, parse_source):
        doc = parse_source('#p: This has #b"bold" text.\n')
        call = doc.children[0]
        assert isinstance(call.body, Body)
        children = call.body.children
        assert isinstance(children[0], Text)
        assert children[0].value == "This has "
        assert isinstance(children[1], MacroCall)
        assert_call(children[1], "b", has_body=True, bracketed=False)
        assert isinstance(children[2], Text)
        assert children[2].value == " text."

    def test_multiple_inline_calls(self, parse_source):
        doc = parse_source('#p: A #b"bold" and #i"italic" line.\n')
        call = doc.children[0]
        assert isinstance(call.body, Body)
        macro_calls = [c for c in call.body.children if isinstance(c, MacroCall)]
        assert len(macro_calls) == 2
        assert_call(macro_calls[0], "b", has_body=True)
        assert_call(macro_calls[1], "i", has_body=True)


class TestInlineMacroNoArgs:
    def test_macro_ref_in_body(self, parse_source):
        # Note: '.' and '!' are ident_chars so #version followed by them
        # extends the name. Use comma (not an ident_char) as separator.
        doc = parse_source("#p: The version is #version, ok\n")
        call = doc.children[0]
        assert isinstance(call.body, Body)
        children = call.body.children
        refs = [c for c in children if isinstance(c, MacroCall)]
        assert len(refs) == 1
        assert_call(refs[0], "version", has_body=False, bracketed=False)

    def test_macro_ref_does_not_consume_following_text(self, parse_source):
        doc = parse_source("#p: The #version is cool.\n")
        call = doc.children[0]
        assert isinstance(call.body, Body)
        texts = [c for c in call.body.children if isinstance(c, Text)]
        # "The " + " is cool." — WS after #version is not consumed
        combined = "".join(t.value for t in texts)
        assert combined == "The  is cool."
