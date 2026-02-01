"""Tests for named argument parsing and all value types."""

from __future__ import annotations

from picodoc.ast import InterpString, MacroCall, RawString, RequiredMarker, Text
from tests.conftest import assert_call


class TestBarewordArgs:
    def test_single_bareword(self, parse_source):
        doc = parse_source("[#set name=version : 1.0]\n")
        call = doc.children[0]
        assert call.args[0].name == "name"
        assert isinstance(call.args[0].value, Text)
        assert call.args[0].value.value == "version"

    def test_bareword_with_dots(self, parse_source):
        doc = parse_source("[#set name=my.var : x]\n")
        assert isinstance(doc.children[0].args[0].value, Text)
        assert doc.children[0].args[0].value.value == "my.var"

    def test_bareword_with_dashes(self, parse_source):
        doc = parse_source("[#set name=project-name : x]\n")
        assert doc.children[0].args[0].value.value == "project-name"


class TestStringArgs:
    def test_interp_string_arg(self, parse_source):
        doc = parse_source('[#url link="https://example.com"]\n')
        assert isinstance(doc.children[0].args[0].value, InterpString)
        parts = doc.children[0].args[0].value.parts
        assert len(parts) == 1
        assert isinstance(parts[0], Text)
        assert parts[0].value == "https://example.com"

    def test_raw_string_arg(self, parse_source):
        doc = parse_source('[#code body="""raw code"""]\n')
        assert isinstance(doc.children[0].args[0].value, RawString)
        assert doc.children[0].args[0].value.value == "raw code"


class TestMacroRefArgs:
    def test_macro_ref_value(self, parse_source):
        doc = parse_source('[#url link=#site-url text="x"]\n')
        call = doc.children[0]
        assert isinstance(call.args[0].value, MacroCall)
        assert call.args[0].value.name == "site-url"
        assert call.args[0].value.args == ()
        assert call.args[0].value.body is None


class TestBracketCallArgs:
    def test_bracket_call_as_value(self, parse_source):
        doc = parse_source("[#outer val=[#inner : x]]\n")
        call = doc.children[0]
        assert isinstance(call.args[0].value, MacroCall)
        assert_call(call.args[0].value, "inner", has_body=True, bracketed=True)


class TestRequiredMarker:
    def test_question_mark_value(self, parse_source):
        doc = parse_source("[#set name=greeting target=?]\n")
        call = doc.children[0]
        assert len(call.args) == 2
        assert isinstance(call.args[1].value, RequiredMarker)

    def test_multiple_required(self, parse_source):
        doc = parse_source("[#set name=x a=? b=?]\n")
        call = doc.children[0]
        assert isinstance(call.args[1].value, RequiredMarker)
        assert isinstance(call.args[2].value, RequiredMarker)


class TestMultipleArgs:
    def test_two_string_args(self, parse_source):
        doc = parse_source('[#url link="http://x" text="click"]\n')
        call = doc.children[0]
        assert_call(call, "url", num_args=2, bracketed=True)
        assert call.args[0].name == "link"
        assert call.args[1].name == "text"

    def test_mixed_arg_types(self, parse_source):
        doc = parse_source("[#set name=greeting target=? body=? : x]\n")
        call = doc.children[0]
        assert_call(call, "set", num_args=3, has_body=True, bracketed=True)
        assert isinstance(call.args[0].value, Text)
        assert isinstance(call.args[1].value, RequiredMarker)
        assert isinstance(call.args[2].value, RequiredMarker)

    def test_unbracketed_multiple_args(self, parse_source):
        doc = parse_source('#meta name=viewport content="width=device-width"\n')
        call = doc.children[0]
        assert_call(call, "meta", num_args=2, bracketed=False)
        assert call.args[0].name == "name"
        assert call.args[1].name == "content"


class TestArgNameSpan:
    def test_name_span(self, parse_source):
        doc = parse_source("[#set name=x]\n")
        arg = doc.children[0].args[0]
        assert arg.name_span.start.column == 7  # 'n' of 'name'

    def test_arg_span_covers_value(self, parse_source):
        doc = parse_source("[#set name=version]\n")
        arg = doc.children[0].args[0]
        # Span covers from 'n' of 'name' to end of 'version'
        assert arg.span.start.column == 7
        assert arg.span.end.column > arg.span.start.column


class TestArgsWithBody:
    def test_args_then_colon_body(self, parse_source):
        doc = parse_source("[#td span=2 : Total]\n")
        call = doc.children[0]
        assert_call(call, "td", num_args=1, has_body=True, bracketed=True)
        assert call.args[0].name == "span"

    def test_args_then_string_body(self, parse_source):
        doc = parse_source('[#set name=motto "Write less."]\n')
        call = doc.children[0]
        assert_call(call, "set", num_args=1, has_body=True, bracketed=True)
        assert isinstance(call.body, InterpString)

    def test_unbracketed_args_then_body(self, parse_source):
        doc = parse_source("#code language=python : print()\n")
        call = doc.children[0]
        assert_call(call, "code", num_args=1, has_body=True, bracketed=False)
