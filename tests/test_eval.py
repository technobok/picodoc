"""Evaluator unit tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from picodoc.ast import (
    Body,
    CodeSection,
    Document,
    Escape,
    InterpString,
    MacroCall,
    NamedArg,
    Paragraph,
    RawString,
    RequiredMarker,
    Text,
)
from picodoc.errors import EvalError
from picodoc.eval import EvalContext, evaluate
from picodoc.parser import parse
from picodoc.tokens import Position, Span

# Convenience span for hand-built AST nodes
S = Span(Position(1, 1, 0), Position(1, 1, 0))


def _text(value: str) -> Text:
    return Text(value, S)


def _body(*children: Text | Escape | MacroCall) -> Body:
    return Body(children, S)


def _call(
    name: str,
    args: tuple[NamedArg, ...] = (),
    body: Body | InterpString | RawString | None = None,
    *,
    bracketed: bool = False,
) -> MacroCall:
    return MacroCall(name, args, body, bracketed, S)


def _arg(name: str, value: str) -> NamedArg:
    return NamedArg(name, _text(value), S, S)


def _iarg(name: str, value: str) -> NamedArg:
    return NamedArg(name, InterpString((Text(value, S),), S), S, S)


def _doc(*children: MacroCall | Paragraph) -> Document:
    return Document(children, S)


class TestComment:
    def test_comment_removed(self) -> None:
        doc = _doc(_call("comment", body=_body(_text("hidden"))))
        result = evaluate(doc)
        assert len(result.children) == 0

    def test_comment_in_body_removed(self) -> None:
        doc = _doc(
            _call(
                "ul",
                body=_body(
                    _call("comment", body=_body(_text("hidden"))),
                    _call("*", body=_body(_text("visible"))),
                ),
            )
        )
        result = evaluate(doc)
        ul = result.children[0]
        assert isinstance(ul, MacroCall)
        assert isinstance(ul.body, Body)
        assert len(ul.body.children) == 1
        assert isinstance(ul.body.children[0], MacroCall)
        assert ul.body.children[0].name == "*"


class TestSetCollection:
    def test_set_collected_and_removed(self) -> None:
        doc = _doc(
            _call("set", (_arg("name", "version"),), _body(_text("1.0"))),
            _call("title", body=_body(_text("Hello"))),
        )
        result = evaluate(doc)
        assert len(result.children) == 1
        assert isinstance(result.children[0], MacroCall)
        assert result.children[0].name == "title"

    def test_set_value_available_for_ifset(self) -> None:
        doc = _doc(
            _call("set", (_arg("name", "version"),), _body(_text("1.0"))),
            _call(
                "ifset",
                (_arg("name", "version"),),
                _body(_call("p", body=_body(_text("defined")))),
            ),
        )
        result = evaluate(doc)
        assert len(result.children) == 1
        assert isinstance(result.children[0], MacroCall)
        assert result.children[0].name == "p"

    def test_set_stores_definition(self) -> None:
        """Parse-level test: verify #set is collected into context."""
        source = "[#set name=version : 1.0]\n#title: Hello"
        doc = parse(source)
        result = evaluate(doc)
        assert len(result.children) == 1


class TestIfeq:
    def test_ifeq_true(self) -> None:
        doc = _doc(
            _call(
                "ifeq",
                (_arg("lhs", "a"), _arg("rhs", "a")),
                _body(_call("p", body=_body(_text("match")))),
            ),
        )
        result = evaluate(doc)
        assert len(result.children) == 1
        p = result.children[0]
        assert isinstance(p, MacroCall) and p.name == "p"

    def test_ifeq_false(self) -> None:
        doc = _doc(
            _call(
                "ifeq",
                (_arg("lhs", "a"), _arg("rhs", "b")),
                _body(_call("p", body=_body(_text("match")))),
            ),
        )
        result = evaluate(doc)
        assert len(result.children) == 0


class TestIfne:
    def test_ifne_true(self) -> None:
        doc = _doc(
            _call(
                "ifne",
                (_arg("lhs", "a"), _arg("rhs", "b")),
                _body(_call("p", body=_body(_text("different")))),
            ),
        )
        result = evaluate(doc)
        assert len(result.children) == 1

    def test_ifne_false(self) -> None:
        doc = _doc(
            _call(
                "ifne",
                (_arg("lhs", "a"), _arg("rhs", "a")),
                _body(_call("p", body=_body(_text("different")))),
            ),
        )
        result = evaluate(doc)
        assert len(result.children) == 0


class TestIfset:
    def test_ifset_defined(self) -> None:
        doc = _doc(
            _call("set", (_arg("name", "x"),), _body(_text("val"))),
            _call("ifset", (_arg("name", "x"),), _body(_call("p", body=_body(_text("defined"))))),
        )
        result = evaluate(doc)
        assert len(result.children) == 1

    def test_ifset_undefined(self) -> None:
        doc = _doc(
            _call("ifset", (_arg("name", "x"),), _body(_call("p", body=_body(_text("defined"))))),
        )
        result = evaluate(doc)
        assert len(result.children) == 0


class TestInclude:
    def test_basic_include(self, tmp_path: Path) -> None:
        included = tmp_path / "part.pdoc"
        included.write_text("#p: Included content\n")

        main = tmp_path / "main.pdoc"
        main.write_text('[#include file="part.pdoc"]\n')

        source = main.read_text()
        doc = parse(source, str(main))
        result = evaluate(doc, str(main))

        assert len(result.children) == 1
        p = result.children[0]
        assert isinstance(p, MacroCall) and p.name == "p"

    def test_circular_include(self, tmp_path: Path) -> None:
        a = tmp_path / "a.pdoc"
        b = tmp_path / "b.pdoc"
        a.write_text('[#include file="b.pdoc"]\n')
        b.write_text('[#include file="a.pdoc"]\n')

        source = a.read_text()
        doc = parse(source, str(a))
        with pytest.raises(EvalError, match="circular include"):
            evaluate(doc, str(a))

    def test_depth_limit(self, tmp_path: Path) -> None:
        # Create a chain: a.pdoc includes b.pdoc includes c.pdoc ... exceeding depth
        depth = 18
        for i in range(depth):
            f = tmp_path / f"f{i}.pdoc"
            f.write_text(f'[#include file="f{i + 1}.pdoc"]\n')
        # Last file is normal
        (tmp_path / f"f{depth}.pdoc").write_text("#p: end\n")

        source = (tmp_path / "f0.pdoc").read_text()
        doc = parse(source, str(tmp_path / "f0.pdoc"))
        with pytest.raises(EvalError, match="include depth limit"):
            evaluate(doc, str(tmp_path / "f0.pdoc"))

    def test_missing_file(self, tmp_path: Path) -> None:
        main = tmp_path / "main.pdoc"
        main.write_text('[#include file="missing.pdoc"]\n')

        source = main.read_text()
        doc = parse(source, str(main))
        with pytest.raises(EvalError, match="not found"):
            evaluate(doc, str(main))


class TestTableExpansion:
    def test_pipe_delimited(self) -> None:
        source = "#table:\n  Name | Age\n  Alice | 30\n"
        doc = parse(source)
        result = evaluate(doc)

        table = result.children[0]
        assert isinstance(table, MacroCall) and table.name == "table"
        assert isinstance(table.body, Body)
        rows = [c for c in table.body.children if isinstance(c, MacroCall)]
        assert len(rows) == 2

        # First row: th
        tr1 = rows[0]
        assert tr1.name == "tr"
        assert isinstance(tr1.body, Body)
        cells1 = [c for c in tr1.body.children if isinstance(c, MacroCall)]
        assert all(c.name == "th" for c in cells1)
        assert len(cells1) == 2

        # Second row: td
        tr2 = rows[1]
        cells2 = [c for c in tr2.body.children if isinstance(c, MacroCall)]
        assert all(c.name == "td" for c in cells2)

    def test_no_pipe_passthrough(self) -> None:
        source = "[#table : [#tr : [#td: Cell]]]\n"
        doc = parse(source)
        result = evaluate(doc)

        table = result.children[0]
        assert isinstance(table, MacroCall)
        assert table.name == "table"

    def test_pipe_with_macro_cells(self) -> None:
        source = '#table:\n  Col | Val\n  Bold | [#**"Yes"]\n'
        doc = parse(source)
        result = evaluate(doc)

        table = result.children[0]
        assert isinstance(table.body, Body)
        rows = [c for c in table.body.children if isinstance(c, MacroCall)]
        assert len(rows) == 2

        # Second row, second cell should contain a #** MacroCall
        tr2 = rows[1]
        assert isinstance(tr2.body, Body)
        cells = [c for c in tr2.body.children if isinstance(c, MacroCall)]
        assert len(cells) == 2
        cell2 = cells[1]
        assert isinstance(cell2.body, Body)
        cell2_children = cell2.body.children
        has_bold = any(isinstance(c, MacroCall) and c.name == "**" for c in cell2_children)
        assert has_bold


class TestParagraphWrapping:
    def test_paragraph_becomes_p(self) -> None:
        doc = _doc(Paragraph((_text("Hello world"),), S))
        result = evaluate(doc)

        assert len(result.children) == 1
        p = result.children[0]
        assert isinstance(p, MacroCall) and p.name == "p"
        assert isinstance(p.body, Body)
        assert len(p.body.children) == 1
        assert isinstance(p.body.children[0], Text)
        assert p.body.children[0].value == "Hello world"

    def test_paragraph_with_inline_macro(self) -> None:
        doc = _doc(
            Paragraph(
                (_text("Click "), _call("**", body=InterpString((_text("here"),), S))),
                S,
            )
        )
        result = evaluate(doc)
        p = result.children[0]
        assert isinstance(p, MacroCall) and p.name == "p"
        assert isinstance(p.body, Body)
        assert len(p.body.children) == 2


class TestValueResolution:
    def test_text_value(self) -> None:
        from picodoc.eval import _resolve_value

        ctx = EvalContext(filename="test.pdoc", source_dir=Path("."))
        assert _resolve_value(_text("hello"), ctx) == "hello"

    def test_raw_string_value(self) -> None:
        from picodoc.eval import _resolve_value

        ctx = EvalContext(filename="test.pdoc", source_dir=Path("."))
        assert _resolve_value(RawString("raw text", S), ctx) == "raw text"

    def test_interp_string_value(self) -> None:
        from picodoc.eval import _resolve_value

        ctx = EvalContext(filename="test.pdoc", source_dir=Path("."))
        s = InterpString((_text("hello "), _text("world")), S)
        assert _resolve_value(s, ctx) == "hello world"

    def test_macro_ref_value(self) -> None:
        from picodoc.eval import _resolve_value

        ctx = EvalContext(filename="test.pdoc", source_dir=Path("."))
        ctx.definitions["version"] = _call("set", body=_body(_text("1.0")))
        ref = _call("version")
        assert _resolve_value(ref, ctx) == "1.0"


def _req() -> RequiredMarker:
    return RequiredMarker(S)


def _narg(
    name: str,
    value: Text | InterpString | RawString | MacroCall | RequiredMarker,
) -> NamedArg:
    return NamedArg(name, value, S, S)


def _body_text(node: MacroCall) -> str:
    """Extract concatenated text from a MacroCall's Body children."""
    assert isinstance(node.body, Body)
    return "".join(c.value for c in node.body.children if isinstance(c, (Text, Escape)))


class TestUserMacro:
    def test_simple_variable(self) -> None:
        doc = _doc(
            _call("set", (_arg("name", "version"),), _body(_text("1.0"))),
            _call("p", body=_body(_text("v="), _call("version"))),
        )
        result = evaluate(doc)
        assert _body_text(result.children[0]) == "v=1.0"

    def test_variable_trailing_dot(self) -> None:
        doc = _doc(
            _call("set", (_arg("name", "version"),), _body(_text("1.0"))),
            _call("p", body=_body(_text("v="), _call("version."))),
        )
        result = evaluate(doc)
        assert _body_text(result.children[0]) == "v=1.0."

    def test_macro_with_required_args(self) -> None:
        defn = _call(
            "set",
            (_arg("name", "greeting"), _narg("target", _req()), _narg("body", _req())),
            _body(_text("Dear "), _call("target"), _text(", "), _call("body")),
        )
        wrapper = _call(
            "p",
            body=_body(
                _call(
                    "greeting",
                    (_arg("target", "World"),),
                    _body(_text("hello")),
                    bracketed=True,
                )
            ),
        )
        doc = _doc(defn, wrapper)
        result = evaluate(doc)
        assert _body_text(result.children[0]) == "Dear World, hello"

    def test_macro_with_defaults(self) -> None:
        defn = _call(
            "set",
            (
                _arg("name", "box"),
                _narg("style", _text("default")),
                _narg("body", _req()),
            ),
            _body(_text("("), _call("style"), _text(") "), _call("body")),
        )
        # Call with default style
        call1 = _call("box", (), _body(_text("content")), bracketed=True)
        # Call with explicit style
        call2 = _call("box", (_arg("style", "fancy"),), _body(_text("other")), bracketed=True)
        doc = _doc(
            defn,
            _call("p", body=_body(call1)),
            _call("p", body=_body(call2)),
        )
        result = evaluate(doc)
        assert _body_text(result.children[0]) == "(default) content"
        assert _body_text(result.children[1]) == "(fancy) other"

    def test_out_of_order_definition(self) -> None:
        doc = _doc(
            _call("p", body=_body(_call("project"))),
            _call("set", (_arg("name", "project"),), _body(_text("PicoDoc"))),
        )
        result = evaluate(doc)
        assert _body_text(result.children[0]) == "PicoDoc"

    def test_duplicate_definition(self) -> None:
        doc = _doc(
            _call("set", (_arg("name", "x"),), _body(_text("1"))),
            _call("set", (_arg("name", "x"),), _body(_text("2"))),
        )
        with pytest.raises(EvalError, match="duplicate definition: x"):
            evaluate(doc)

    def test_body_param_binding(self) -> None:
        defn = _call(
            "set",
            (_arg("name", "wrap"), _narg("body", _req())),
            _body(_text("["), _call("body"), _text("]")),
        )
        call = _call("wrap", (), _body(_text("inside")), bracketed=True)
        doc = _doc(defn, _call("p", body=_body(call)))
        result = evaluate(doc)
        assert _body_text(result.children[0]) == "[inside]"

    def test_macro_ref_as_arg_value(self) -> None:
        source = (
            "[#set name=site-url : https://example.com]\n"
            '#p: Visit [#url link=#site-url text="our site"] today.\n'
        )
        doc = parse(source)
        result = evaluate(doc)
        p = result.children[0]
        assert isinstance(p.body, Body)
        # Should contain: Text("Visit "), MacroCall("url" with resolved link), Text(" today.")
        url_node = next(c for c in p.body.children if isinstance(c, MacroCall))
        link_arg = next(a for a in url_node.args if a.name == "link")
        assert isinstance(link_arg.value, Text)
        assert link_arg.value.value == "https://example.com"

    def test_string_literal_body_set(self) -> None:
        defn = _call(
            "set",
            (_arg("name", "motto"),),
            InterpString((_text("Write less, mean more."),), S),
        )
        doc = _doc(defn, _call("p", body=_body(_call("motto"))))
        result = evaluate(doc)
        assert _body_text(result.children[0]) == "Write less, mean more."

    def test_string_code_section(self) -> None:
        defn = _call("set", (_arg("name", "version"),), _body(_text("1.0")))
        interp = InterpString(
            (_text("Hello, "), CodeSection((_call("version"),), S), _text("!")),
            S,
        )
        p = _call("p", (), interp)
        doc = _doc(defn, p)
        result = evaluate(doc)
        # The InterpString body should have expanded code section
        p_node = result.children[0]
        assert isinstance(p_node.body, InterpString)
        cs = next(part for part in p_node.body.parts if isinstance(part, CodeSection))
        assert len(cs.body) == 1
        assert isinstance(cs.body[0], Text)
        assert cs.body[0].value == "1.0"

    def test_nested_user_macro(self) -> None:
        inner = _call(
            "set",
            (_arg("name", "inner"), _narg("x", _req())),
            _body(_text("("), _call("x"), _text(")")),
        )
        outer = _call(
            "set",
            (_arg("name", "outer"), _narg("y", _req())),
            _body(
                _call("inner", (_narg("x", _call("y")),), bracketed=True),
            ),
        )
        call = _call("outer", (_arg("y", "val"),), bracketed=True)
        doc = _doc(inner, outer, _call("p", body=_body(call)))
        result = evaluate(doc)
        assert _body_text(result.children[0]) == "(val)"

    def test_recursion_limit(self) -> None:
        defn = _call(
            "set",
            (_arg("name", "loop"),),
            _body(_call("loop")),
        )
        doc = _doc(defn, _call("p", body=_body(_call("loop"))))
        with pytest.raises(EvalError, match="macro call depth limit"):
            evaluate(doc)

    def test_scope_shadowing(self) -> None:
        doc = _doc(
            _call("set", (_arg("name", "x"),), _body(_text("global"))),
            _call(
                "set",
                (_arg("name", "show"), _narg("x", _req())),
                _body(_call("x")),
            ),
            _call(
                "p",
                body=_body(
                    _call("show", (_arg("x", "local"),), bracketed=True),
                    _text(" "),
                    _call("x"),
                ),
            ),
        )
        result = evaluate(doc)
        # Inside show: x=local. After show: x=global.
        assert _body_text(result.children[0]) == "local global"

    def test_missing_required_arg(self) -> None:
        defn = _call(
            "set",
            (_arg("name", "greet"), _narg("target", _req())),
            _body(_text("Hi "), _call("target")),
        )
        call = _call("greet", (), bracketed=True)
        doc = _doc(defn, _call("p", body=_body(call)))
        with pytest.raises(EvalError, match="missing required argument: target"):
            evaluate(doc)


class TestEnv:
    def test_env_from_evaluate_param(self) -> None:
        doc = _doc(_call("p", body=_body(_text("mode="), _call("env.mode"))))
        result = evaluate(doc, env={"mode": "draft"})
        assert _body_text(result.children[0]) == "mode=draft"

    def test_env_from_set(self) -> None:
        doc = _doc(
            _call("set", (_arg("name", "env.mode"),), _body(_text("draft"))),
            _call("p", body=_body(_call("env.mode"))),
        )
        result = evaluate(doc)
        assert _body_text(result.children[0]) == "draft"

    def test_env_set_overrides_preseeded(self) -> None:
        doc = _doc(
            _call("set", (_arg("name", "env.mode"),), _body(_text("final"))),
            _call("p", body=_body(_call("env.mode"))),
        )
        result = evaluate(doc, env={"mode": "draft"})
        assert _body_text(result.children[0]) == "final"

    def test_env_duplicate_set_error(self) -> None:
        doc = _doc(
            _call("set", (_arg("name", "env.mode"),), _body(_text("a"))),
            _call("set", (_arg("name", "env.mode"),), _body(_text("b"))),
        )
        with pytest.raises(EvalError, match=r"duplicate definition: env\.mode"):
            evaluate(doc)

    def test_env_ifset_preseeded(self) -> None:
        doc = _doc(
            _call(
                "ifset",
                (_arg("name", "env.mode"),),
                _body(_call("p", body=_body(_text("yes")))),
            ),
        )
        result = evaluate(doc, env={"mode": "draft"})
        assert len(result.children) == 1
        assert _body_text(result.children[0]) == "yes"

    def test_env_ifset_unset(self) -> None:
        doc = _doc(
            _call(
                "ifset",
                (_arg("name", "env.missing"),),
                _body(_call("p", body=_body(_text("yes")))),
            ),
        )
        result = evaluate(doc)
        assert len(result.children) == 0

    def test_env_ifeq(self) -> None:
        doc = _doc(
            _call(
                "ifeq",
                (
                    _narg("lhs", _call("env.mode")),
                    _arg("rhs", "draft"),
                ),
                _body(_call("p", body=_body(_text("match")))),
            ),
        )
        result = evaluate(doc, env={"mode": "draft"})
        assert len(result.children) == 1
        assert _body_text(result.children[0]) == "match"

    def test_env_inherited_in_user_macro(self) -> None:
        defn = _call(
            "set",
            (_arg("name", "show-mode"),),
            _body(_call("env.mode")),
        )
        doc = _doc(
            defn,
            _call("p", body=_body(_call("show-mode"))),
        )
        result = evaluate(doc, env={"mode": "draft"})
        assert _body_text(result.children[0]) == "draft"

    def test_env_cannot_be_shadowed(self) -> None:
        defn = _call(
            "set",
            (_arg("name", "bad"), _narg("env.mode", _req())),
            _body(_call("env.mode")),
        )
        call = _call("bad", (_arg("env.mode", "hacked"),), bracketed=True)
        doc = _doc(defn, _call("p", body=_body(call)))
        with pytest.raises(EvalError, match="cannot shadow environment variable"):
            evaluate(doc, env={"mode": "safe"})

    def test_env_undefined_returns_empty(self) -> None:
        doc = _doc(_call("p", body=_body(_text("x"), _call("env.missing"), _text("y"))))
        result = evaluate(doc)
        assert _body_text(result.children[0]) == "xy"


class TestMutualRecursion:
    def test_mutual_recursion_hits_depth_limit(self) -> None:
        ping = _call("set", (_arg("name", "ping"),), _body(_call("pong")))
        pong = _call("set", (_arg("name", "pong"),), _body(_call("ping")))
        doc = _doc(ping, pong, _call("p", body=_body(_call("ping"))))
        with pytest.raises(EvalError, match="macro call depth limit"):
            evaluate(doc)

    def test_mutual_recursion_error_includes_chain(self) -> None:
        ping = _call("set", (_arg("name", "ping"),), _body(_call("pong")))
        pong = _call("set", (_arg("name", "pong"),), _body(_call("ping")))
        doc = _doc(ping, pong, _call("p", body=_body(_call("ping"))))
        with pytest.raises(EvalError) as exc_info:
            evaluate(doc)
        err = exc_info.value
        assert len(err.call_stack) > 1
        assert "ping" in err.call_stack
        assert "pong" in err.call_stack


class TestConvergence:
    def test_user_macro_in_table_cell(self) -> None:
        source = "[#set name=status : Active]\n#table:\n  Name | Status\n  Alice | #status\n"
        doc = parse(source)
        result = evaluate(doc)
        table = result.children[0]
        assert isinstance(table, MacroCall) and table.name == "table"
        assert isinstance(table.body, Body)
        rows = [c for c in table.body.children if isinstance(c, MacroCall)]
        assert len(rows) == 2
        # Second row, second cell should contain "Active"
        tr2 = rows[1]
        assert isinstance(tr2.body, Body)
        cells = [c for c in tr2.body.children if isinstance(c, MacroCall)]
        assert len(cells) == 2
        cell2 = cells[1]
        assert isinstance(cell2.body, Body)
        text = "".join(c.value for c in cell2.body.children if isinstance(c, (Text, Escape)))
        assert text == "Active"

    def test_nested_macro_in_conditional(self) -> None:
        doc = _doc(
            _call("set", (_arg("name", "mode"),), _body(_text("draft"))),
            _call("set", (_arg("name", "label"),), _body(_text("DRAFT"))),
            _call(
                "ifeq",
                (_narg("lhs", _call("mode")), _arg("rhs", "draft")),
                _body(_call("p", body=_body(_call("label")))),
            ),
        )
        result = evaluate(doc)
        assert len(result.children) == 1
        assert _body_text(result.children[0]) == "DRAFT"

    def test_chained_macro_resolution(self) -> None:
        doc = _doc(
            _call("set", (_arg("name", "alpha"),), _body(_text("hello"))),
            _call(
                "set",
                (_arg("name", "beta"),),
                _body(_call("alpha")),
            ),
            _call("p", body=_body(_call("beta"))),
        )
        result = evaluate(doc)
        assert _body_text(result.children[0]) == "hello"


class TestErrorChain:
    def test_depth_error_includes_chain(self) -> None:
        defn = _call("set", (_arg("name", "loop"),), _body(_call("loop")))
        doc = _doc(defn, _call("p", body=_body(_call("loop"))))
        with pytest.raises(EvalError) as exc_info:
            evaluate(doc)
        err = exc_info.value
        assert len(err.call_stack) > 0
        assert "loop" in err.call_stack

    def test_missing_arg_error_includes_chain(self) -> None:
        inner = _call(
            "set",
            (_arg("name", "inner"), _narg("x", _req())),
            _body(_call("x")),
        )
        outer = _call(
            "set",
            (_arg("name", "outer"),),
            _body(_call("inner", (), bracketed=True)),
        )
        doc = _doc(inner, outer, _call("p", body=_body(_call("outer"))))
        with pytest.raises(EvalError) as exc_info:
            evaluate(doc)
        err = exc_info.value
        assert "outer" in err.call_stack


class TestNestingValidation:
    def test_td_outside_tr(self) -> None:
        doc = _doc(_call("td", body=_body(_text("cell"))))
        with pytest.raises(EvalError, match=r"#td must appear inside #tr"):
            evaluate(doc)

    def test_tr_outside_table(self) -> None:
        doc = _doc(_call("tr", body=_body(_call("td", body=_body(_text("cell"))))))
        with pytest.raises(EvalError, match=r"#tr must appear inside #table"):
            evaluate(doc)

    def test_th_outside_tr(self) -> None:
        doc = _doc(_call("th", body=_body(_text("header"))))
        with pytest.raises(EvalError, match=r"#th must appear inside #tr"):
            evaluate(doc)

    def test_li_outside_list(self) -> None:
        doc = _doc(_call("*", body=_body(_text("item"))))
        with pytest.raises(EvalError, match=r"#\* must appear inside #ol or #ul"):
            evaluate(doc)

    def test_td_in_table_not_tr(self) -> None:
        doc = _doc(_call("table", body=_body(_call("td", body=_body(_text("cell"))))))
        with pytest.raises(EvalError, match=r"#td must appear inside #tr"):
            evaluate(doc)

    def test_valid_table_nesting(self) -> None:
        doc = _doc(
            _call(
                "table",
                body=_body(
                    _call("tr", body=_body(_call("td", body=_body(_text("cell"))))),
                ),
            )
        )
        result = evaluate(doc)
        assert len(result.children) == 1

    def test_valid_list_nesting(self) -> None:
        doc = _doc(_call("ul", body=_body(_call("*", body=_body(_text("item"))))))
        result = evaluate(doc)
        assert len(result.children) == 1

    def test_li_alias(self) -> None:
        doc = _doc(_call("ol", body=_body(_call("li", body=_body(_text("item"))))))
        result = evaluate(doc)
        assert len(result.children) == 1

    def test_pipe_table_valid(self) -> None:
        source = "#table:\n  Name | Age\n  Alice | 30\n"
        doc = parse(source)
        result = evaluate(doc)
        assert len(result.children) == 1
        table = result.children[0]
        assert isinstance(table, MacroCall) and table.name == "table"
