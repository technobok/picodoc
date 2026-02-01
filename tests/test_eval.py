"""Evaluator unit tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from picodoc.ast import (
    Body,
    Document,
    Escape,
    InterpString,
    MacroCall,
    NamedArg,
    Paragraph,
    RawString,
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
