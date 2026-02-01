"""Renderer unit tests."""

from __future__ import annotations

from picodoc.ast import Body, Document, Escape, InterpString, MacroCall, NamedArg, RawString, Text
from picodoc.render import render
from picodoc.tokens import Position, Span

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


def _doc(*children: MacroCall) -> Document:
    return Document(children, S)


class TestDocumentStructure:
    def test_minimal_document(self) -> None:
        result = render(_doc())
        assert result.startswith("<!DOCTYPE html>\n<html>\n")
        assert '<head>\n<meta charset="utf-8">\n</head>\n' in result
        assert "<body>\n</body>\n" in result
        assert result.endswith("</html>\n")

    def test_charset_meta_always_present(self) -> None:
        result = render(_doc())
        assert '<meta charset="utf-8">' in result


class TestHeadings:
    def test_h1_title(self) -> None:
        result = render(_doc(_call("title", body=_body(_text("Hello")))))
        assert "<h1>Hello</h1>" in result

    def test_h1_alias(self) -> None:
        result = render(_doc(_call("-", body=_body(_text("Alt")))))
        assert "<h1>Alt</h1>" in result

    def test_h1_alias2(self) -> None:
        result = render(_doc(_call("h1", body=_body(_text("H1")))))
        assert "<h1>H1</h1>" in result

    def test_h2(self) -> None:
        result = render(_doc(_call("h2", body=_body(_text("Sub")))))
        assert "<h2>Sub</h2>" in result

    def test_h2_alias(self) -> None:
        result = render(_doc(_call("--", body=_body(_text("S")))))
        assert "<h2>S</h2>" in result

    def test_h3(self) -> None:
        result = render(_doc(_call("h3", body=_body(_text("Sub2")))))
        assert "<h3>Sub2</h3>" in result

    def test_h3_alias(self) -> None:
        result = render(_doc(_call("---", body=_body(_text("S2")))))
        assert "<h3>S2</h3>" in result

    def test_h4_through_h6(self) -> None:
        for level in (4, 5, 6):
            tag = f"h{level}"
            result = render(_doc(_call(tag, body=_body(_text("X")))))
            assert f"<{tag}>X</{tag}>" in result


class TestParagraph:
    def test_simple(self) -> None:
        result = render(_doc(_call("p", body=_body(_text("Hello world")))))
        assert "<p>Hello world</p>" in result

    def test_multiline(self) -> None:
        result = render(_doc(_call("p", body=_body(_text("Line 1\nLine 2")))))
        assert "<p>Line 1\nLine 2</p>" in result


class TestHr:
    def test_void_element(self) -> None:
        result = render(_doc(_call("hr")))
        assert "<hr>" in result
        assert "</hr>" not in result


class TestBold:
    def test_strong(self) -> None:
        result = render(_doc(_call("p", body=_body(_call("b", body=_body(_text("bold")))))))
        assert "<strong>bold</strong>" in result

    def test_star_alias(self) -> None:
        result = render(
            _doc(_call("p", body=_body(_call("**", body=InterpString((_text("bold"),), S)))))
        )
        assert "<strong>bold</strong>" in result


class TestItalic:
    def test_em(self) -> None:
        result = render(_doc(_call("p", body=_body(_call("i", body=_body(_text("italic")))))))
        assert "<em>italic</em>" in result

    def test_underscore_alias(self) -> None:
        result = render(
            _doc(_call("p", body=_body(_call("__", body=InterpString((_text("italic"),), S)))))
        )
        assert "<em>italic</em>" in result


class TestUrl:
    def test_with_text_arg(self) -> None:
        args = (_iarg("link", "https://example.com"), _iarg("text", "Example"))
        result = render(_doc(_call("p", body=_body(_call("url", args)))))
        assert '<a href="https://example.com">Example</a>' in result

    def test_with_body(self) -> None:
        args = (_iarg("link", "https://example.com"),)
        url = _call("url", args, _body(_text("Click")))
        result = render(_doc(_call("p", body=_body(url))))
        assert '<a href="https://example.com">Click</a>' in result


class TestCode:
    def test_inline_with_language(self) -> None:
        args = (_arg("language", "python"),)
        code = _call("code", args, _body(_text("print()")))
        result = render(_doc(_call("p", body=_body(code))))
        assert '<code class="language-python">print()</code>' in result

    def test_inline_without_language(self) -> None:
        code = _call("code", (), _body(_text("mono")))
        result = render(_doc(_call("p", body=_body(code))))
        assert "<code>mono</code>" in result

    def test_block_with_raw_string(self) -> None:
        args = (_arg("language", "python"),)
        code = _call("code", args, RawString("x = 1", S))
        result = render(_doc(code))
        assert '<pre><code class="language-python">x = 1</code></pre>' in result

    def test_html_escaping_in_code(self) -> None:
        code = _call("code", (), _body(_text("<div>")))
        result = render(_doc(_call("p", body=_body(code))))
        assert "<code>&lt;div&gt;</code>" in result


class TestLiteral:
    def test_raw_passthrough(self) -> None:
        lit = _call("literal", body=RawString("<b>raw</b>", S))
        result = render(_doc(lit))
        assert "<b>raw</b>" in result
        # Should NOT be escaped
        assert "&lt;b&gt;" not in result


class TestLists:
    def test_ul(self) -> None:
        items = _body(
            _call("*", body=_body(_text("A"))),
            _call("*", body=_body(_text("B"))),
        )
        result = render(_doc(_call("ul", body=items)))
        assert "<ul>\n<li>A</li>\n<li>B</li>\n</ul>" in result

    def test_ol(self) -> None:
        items = _body(
            _call("*", body=_body(_text("1"))),
            _call("*", body=_body(_text("2"))),
        )
        result = render(_doc(_call("ol", body=items)))
        assert "<ol>\n<li>1</li>\n<li>2</li>\n</ol>" in result

    def test_nested_list(self) -> None:
        inner_ul = _call("ul", body=_body(_call("*", body=_body(_text("Nested")))))
        outer_li = _call("*", body=_body(_text("Item"), inner_ul))
        result = render(_doc(_call("ul", body=_body(outer_li))))
        assert "<li>Item\n<ul>\n<li>Nested</li>\n</ul>\n</li>" in result

    def test_li_alias(self) -> None:
        items = _body(_call("li", body=_body(_text("Alias"))))
        result = render(_doc(_call("ul", body=items)))
        assert "<li>Alias</li>" in result


class TestTables:
    def test_simple_table(self) -> None:
        th = _call("th", body=_body(_text("Name")))
        td = _call("td", body=_body(_text("Alice")))
        tr1 = _call("tr", body=_body(th))
        tr2 = _call("tr", body=_body(td))
        result = render(_doc(_call("table", body=_body(tr1, tr2))))
        assert "<table>\n<tr><th>Name</th></tr>\n<tr><td>Alice</td></tr>\n</table>" in result

    def test_colspan(self) -> None:
        td = _call("td", (_arg("span", "2"),), _body(_text("Wide")))
        tr = _call("tr", body=_body(td))
        result = render(_doc(_call("table", body=_body(tr))))
        assert '<td colspan="2">Wide</td>' in result

    def test_th_colspan(self) -> None:
        th = _call("th", (_arg("span", "3"),), _body(_text("Header")))
        tr = _call("tr", body=_body(th))
        result = render(_doc(_call("table", body=_body(tr))))
        assert '<th colspan="3">Header</th>' in result


class TestDocumentMeta:
    def test_meta_name(self) -> None:
        meta = _call("meta", (_arg("name", "viewport"), _iarg("content", "width=device-width")))
        result = render(_doc(meta))
        assert '<meta name="viewport" content="width=device-width">' in result

    def test_meta_property(self) -> None:
        meta = _call("meta", (_iarg("property", "og:title"), _iarg("content", "Title")))
        result = render(_doc(meta))
        assert '<meta property="og:title" content="Title">' in result

    def test_link(self) -> None:
        link = _call("link", (_arg("rel", "stylesheet"), _iarg("href", "style.css")))
        result = render(_doc(link))
        assert '<link rel="stylesheet" href="style.css">' in result

    def test_script_src(self) -> None:
        script = _call("script", (_iarg("src", "app.js"),))
        result = render(_doc(script))
        assert '<script src="app.js"></script>' in result

    def test_script_inline(self) -> None:
        script = _call("script", body=RawString('console.log("hi");', S))
        result = render(_doc(script))
        assert '<script>\nconsole.log("hi");\n</script>' in result

    def test_lang(self) -> None:
        result = render(_doc(_call("lang", body=_body(_text("en")))))
        assert '<html lang="en">' in result


class TestHtmlEscaping:
    def test_angle_brackets(self) -> None:
        result = render(_doc(_call("p", body=_body(_text("a < b > c")))))
        assert "<p>a &lt; b &gt; c</p>" in result

    def test_ampersand(self) -> None:
        result = render(_doc(_call("p", body=_body(_text("a & b")))))
        assert "<p>a &amp; b</p>" in result

    def test_non_ascii_escape(self) -> None:
        esc = Escape("\xa9", S)
        result = render(_doc(_call("p", body=_body(esc))))
        assert "<p>&#xA9;</p>" in result

    def test_non_ascii_in_text(self) -> None:
        result = render(_doc(_call("p", body=_body(_text("\xa9")))))
        assert "<p>&#xA9;</p>" in result

    def test_em_dash_escape(self) -> None:
        esc = Escape("\u2014", S)
        result = render(_doc(_call("p", body=_body(esc))))
        assert "<p>&#x2014;</p>" in result
