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
    def test_h1(self) -> None:
        result = render(_doc(_call("h1", body=_body(_text("Hello")))))
        assert '<h1 id="hello">Hello</h1>' in result

    def test_h1_alias(self) -> None:
        result = render(_doc(_call("-", body=_body(_text("Alt")))))
        assert '<h1 id="alt">Alt</h1>' in result

    def test_title_in_head(self) -> None:
        result = render(_doc(_call("doc.title", body=_body(_text("My Page")))))
        assert "<title>My Page</title>" in result
        assert "<title>My Page</title>" in result.split("<head>")[1].split("</head>")[0]

    def test_title_not_in_body(self) -> None:
        result = render(_doc(_call("doc.title", body=_body(_text("My Page")))))
        body_section = result.split("<body>")[1].split("</body>")[0]
        assert "<title>" not in body_section

    def test_h2(self) -> None:
        result = render(_doc(_call("h2", body=_body(_text("Sub")))))
        assert '<h2 id="sub">Sub</h2>' in result

    def test_h2_alias(self) -> None:
        result = render(_doc(_call("--", body=_body(_text("S")))))
        assert '<h2 id="s">S</h2>' in result

    def test_h3(self) -> None:
        result = render(_doc(_call("h3", body=_body(_text("Sub2")))))
        assert '<h3 id="sub2">Sub2</h3>' in result

    def test_h3_alias(self) -> None:
        result = render(_doc(_call("---", body=_body(_text("S2")))))
        assert '<h3 id="s2">S2</h3>' in result

    def test_h4_through_h6(self) -> None:
        for level in (4, 5, 6):
            tag = f"h{level}"
            result = render(_doc(_call(tag, body=_body(_text("X")))))
            assert f'<{tag} id="x">X</{tag}>' in result


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


class TestBoldItalic:
    def test_strong_em(self) -> None:
        result = render(_doc(_call("p", body=_body(_call("*_", body=_body(_text("both")))))))
        assert "<strong><em>both</em></strong>" in result

    def test_em_strong(self) -> None:
        result = render(_doc(_call("p", body=_body(_call("_*", body=_body(_text("both")))))))
        assert "<em><strong>both</strong></em>" in result


class TestLink:
    def test_with_body(self) -> None:
        args = (_iarg("to", "https://example.com"),)
        link = _call("link", args, _body(_text("Click")))
        result = render(_doc(_call("p", body=_body(link))))
        assert '<a href="https://example.com">Click</a>' in result

    def test_no_body_uses_to(self) -> None:
        args = (_iarg("to", "https://example.com"),)
        link = _call("link", args)
        result = render(_doc(_call("p", body=_body(link))))
        assert '<a href="https://example.com">https://example.com</a>' in result

    def test_fragment_reference(self) -> None:
        args = (_iarg("to", "section1"),)
        link = _call("link", args, _body(_text("go")))
        result = render(
            _doc(
                _call("h2", body=_body(_text("Section1"))),
                _call("p", body=_body(link)),
            )
        )
        assert '<a href="#section1">go</a>' in result

    def test_path_with_slash_no_fragment(self) -> None:
        args = (_iarg("to", "page/about"),)
        link = _call("link", args)
        result = render(_doc(_call("p", body=_body(link))))
        assert '<a href="page/about">page/about</a>' in result

    def test_alias(self) -> None:
        args = (_iarg("to", "https://example.com"),)
        link = _call(">", args, _body(_text("Click")))
        result = render(_doc(_call("p", body=_body(link))))
        assert '<a href="https://example.com">Click</a>' in result

    def test_body_as_to_external(self) -> None:
        link = _call("link", (), _body(_text("https://example.com")))
        result = render(_doc(_call("p", body=_body(link))))
        assert '<a href="https://example.com">https://example.com</a>' in result

    def test_body_as_to_fragment(self) -> None:
        link = _call("link", (), _body(_text("section")))
        result = render(
            _doc(
                _call("h2", body=_body(_text("Section"))),
                _call("p", body=_body(link)),
            )
        )
        assert '<a href="#section">Section</a>' in result

    def test_no_to_no_body_error(self) -> None:
        import pytest

        from picodoc.errors import RenderError

        link = _call("link")
        doc = _doc(_call("p", body=_body(link)))
        with pytest.raises(RenderError, match="missing link target"):
            render(doc)

    def test_alias_body_as_to(self) -> None:
        link = _call(">", (), _body(_text("https://example.com")))
        result = render(_doc(_call("p", body=_body(link))))
        assert '<a href="https://example.com">https://example.com</a>' in result


class TestCode:
    def test_block_with_body(self) -> None:
        args = (_arg("language", "python"),)
        code = _call("code", args, _body(_text("print()")))
        result = render(_doc(code))
        assert '<pre><code class="language-python">print()</code></pre>' in result

    def test_block_without_language(self) -> None:
        code = _call("code", (), _body(_text("mono")))
        result = render(_doc(code))
        assert "<pre><code>mono</code></pre>" in result

    def test_block_with_raw_string(self) -> None:
        args = (_arg("language", "python"),)
        code = _call("code", args, RawString("x = 1", S))
        result = render(_doc(code))
        assert '<pre><code class="language-python">x = 1</code></pre>' in result

    def test_html_escaping_in_block_code(self) -> None:
        code = _call("code", (), _body(_text("<div>")))
        result = render(_doc(code))
        assert "<pre><code>&lt;div&gt;</code></pre>" in result

    def test_bracketed_no_leading_newline(self, compile_source) -> None:
        result = compile_source("[#code:\nint x;\n]\n")
        assert "<pre><code>int x;\n</code></pre>" in result


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
        assert (
            '<table>\n<thead>\n<tr><th style="text-align: left">Name</th></tr>\n</thead>\n'
            "<tbody>\n<tr><td>Alice</td></tr>\n</tbody>\n</table>" in result
        )

    def test_colspan(self) -> None:
        td = _call("td", (_arg("span", "2"),), _body(_text("Wide")))
        tr = _call("tr", body=_body(td))
        result = render(_doc(_call("table", body=_body(tr))))
        assert '<td colspan="2">Wide</td>' in result

    def test_th_colspan(self) -> None:
        th = _call("th", (_arg("span", "3"),), _body(_text("Header")))
        tr = _call("tr", body=_body(th))
        result = render(_doc(_call("table", body=_body(tr))))
        assert '<th colspan="3" style="text-align: left">Header</th>' in result


class TestTableCols:
    def test_cols_basic(self) -> None:
        th1 = _call("th", body=_body(_text("A")))
        th2 = _call("th", body=_body(_text("B")))
        th3 = _call("th", body=_body(_text("C")))
        td1 = _call("td", body=_body(_text("1")))
        td2 = _call("td", body=_body(_text("2")))
        td3 = _call("td", body=_body(_text("3")))
        tr1 = _call("tr", body=_body(th1, th2, th3))
        tr2 = _call("tr", body=_body(td1, td2, td3))
        table = _call("table", (_arg("cols", "1 2 1"),), _body(tr1, tr2))
        result = render(_doc(table))
        assert "<colgroup>" in result
        assert "</colgroup>" in result
        assert '<col style="width: 25%">' in result
        assert '<col style="width: 50%">' in result

    def test_cols_right_align(self) -> None:
        th1 = _call("th", body=_body(_text("A")))
        th2 = _call("th", body=_body(_text("B")))
        th3 = _call("th", body=_body(_text("C")))
        td1 = _call("td", body=_body(_text("1")))
        td2 = _call("td", body=_body(_text("2")))
        td3 = _call("td", body=_body(_text("3")))
        tr1 = _call("tr", body=_body(th1, th2, th3))
        tr2 = _call("tr", body=_body(td1, td2, td3))
        table = _call("table", (_arg("cols", "1 >2 1"),), _body(tr1, tr2))
        result = render(_doc(table))
        assert '<col style="width: 50%">' in result
        assert '<th style="text-align: right">B</th>' in result
        assert '<td style="text-align: right">2</td>' in result

    def test_cols_left_align_explicit(self) -> None:
        th1 = _call("th", body=_body(_text("A")))
        th2 = _call("th", body=_body(_text("B")))
        td1 = _call("td", body=_body(_text("1")))
        td2 = _call("td", body=_body(_text("2")))
        tr1 = _call("tr", body=_body(th1, th2))
        tr2 = _call("tr", body=_body(td1, td2))
        table = _call("table", (_arg("cols", "<1 2"),), _body(tr1, tr2))
        result = render(_doc(table))
        assert '<col style="width: 33%">' in result
        assert '<th style="text-align: left">A</th>' in result
        assert "text-align: right" not in result

    def test_cols_mismatch_error(self) -> None:
        import pytest

        from picodoc.errors import RenderError

        th1 = _call("th", body=_body(_text("A")))
        th2 = _call("th", body=_body(_text("B")))
        th3 = _call("th", body=_body(_text("C")))
        tr1 = _call("tr", body=_body(th1, th2, th3))
        table = _call("table", (_arg("cols", "1 2"),), _body(tr1))
        with pytest.raises(RenderError, match="cols specifies 2 columns but row 1 has 3 cells"):
            render(_doc(table))

    def test_cols_explicit_form(self) -> None:
        th1 = _call("th", body=_body(_text("Name")))
        th2 = _call("th", body=_body(_text("Age")))
        td1 = _call("td", body=_body(_text("Alice")))
        td2 = _call("td", body=_body(_text("30")))
        tr1 = _call("tr", body=_body(th1, th2))
        tr2 = _call("tr", body=_body(td1, td2))
        table = _call("table", (_arg("cols", "1 >1"),), _body(tr1, tr2))
        result = render(_doc(table))
        assert "<colgroup>" in result
        assert '<col style="width: 50%">' in result
        assert '<th style="text-align: left">Name</th>' in result
        assert '<th style="text-align: right">Age</th>' in result
        assert '<td style="text-align: right">30</td>' in result

    def test_no_cols_unchanged(self) -> None:
        th = _call("th", body=_body(_text("A")))
        tr = _call("tr", body=_body(th))
        table = _call("table", body=_body(tr))
        result = render(_doc(table))
        assert "<colgroup>" not in result


class TestDocumentMeta:
    def test_meta_name(self) -> None:
        meta = _call(
            "doc.meta", (_arg("name", "viewport"), _iarg("content", "width=device-width"))
        )
        result = render(_doc(meta))
        assert '<meta name="viewport" content="width=device-width">' in result

    def test_meta_property(self) -> None:
        meta = _call("doc.meta", (_iarg("property", "og:title"), _iarg("content", "Title")))
        result = render(_doc(meta))
        assert '<meta property="og:title" content="Title">' in result

    def test_link(self) -> None:
        link = _call("doc.link", (_arg("rel", "stylesheet"), _iarg("href", "style.css")))
        result = render(_doc(link))
        assert '<link rel="stylesheet" href="style.css">' in result

    def test_link_with_type_and_sizes(self) -> None:
        link = _call(
            "doc.link",
            (
                _arg("rel", "icon"),
                _iarg("href", "icon.png"),
                _arg("type", "image/png"),
                _arg("sizes", "32x32"),
            ),
        )
        result = render(_doc(link))
        assert '<link rel="icon" href="icon.png" type="image/png" sizes="32x32">' in result

    def test_script_src(self) -> None:
        script = _call("doc.script", (_iarg("src", "app.js"),))
        result = render(_doc(script))
        assert '<script src="app.js"></script>' in result

    def test_script_src_with_type(self) -> None:
        script = _call("doc.script", (_iarg("src", "app.js"), _arg("type", "text/javascript")))
        result = render(_doc(script))
        assert '<script type="text/javascript" src="app.js"></script>' in result

    def test_script_inline(self) -> None:
        script = _call("doc.script", body=RawString('console.log("hi");', S))
        result = render(_doc(script))
        assert '<script>\nconsole.log("hi");\n</script>' in result

    def test_lang(self) -> None:
        result = render(_doc(_call("doc.lang", body=_body(_text("en")))))
        assert '<html lang="en">' in result

    def test_doc_author(self) -> None:
        result = render(_doc(_call("doc.author", body=_body(_text("Jane Doe")))))
        assert '<meta name="author" content="Jane Doe">' in result

    def test_doc_version(self) -> None:
        result = render(_doc(_call("doc.version", body=_body(_text("2.0")))))
        assert '<meta name="version" content="2.0">' in result

    def test_doc_datecreated(self) -> None:
        result = render(_doc(_call("doc.datecreated", body=_body(_text("2025-01-01")))))
        assert '<meta name="datecreated" content="2025-01-01">' in result

    def test_doc_datemodified(self) -> None:
        result = render(_doc(_call("doc.datemodified", body=_body(_text("2025-06-15")))))
        assert '<meta name="datemodified" content="2025-06-15">' in result


class TestWrappers:
    def test_div_basic(self) -> None:
        result = render(_doc(_call("div", body=_body(_call("p", body=_body(_text("Hello")))))))
        assert "<div>\n<p>Hello</p>\n</div>" in result

    def test_div_with_class(self) -> None:
        result = render(
            _doc(_call("div", (_arg("class", "box"),), _body(_call("p", body=_body(_text("Hi"))))))
        )
        assert '<div class="box">\n<p>Hi</p>\n</div>' in result

    def test_div_with_id(self) -> None:
        result = render(
            _doc(_call("div", (_arg("id", "main"),), _body(_call("p", body=_body(_text("Hi"))))))
        )
        assert '<div id="main">\n<p>Hi</p>\n</div>' in result

    def test_div_with_class_and_id(self) -> None:
        result = render(
            _doc(
                _call(
                    "div",
                    (_arg("class", "box"), _arg("id", "main")),
                    _body(_call("p", body=_body(_text("Hi")))),
                )
            )
        )
        assert '<div class="box" id="main">\n<p>Hi</p>\n</div>' in result

    def test_span_inline(self) -> None:
        p = _call("p", body=_body(_call("span", (_arg("class", "hl"),), _body(_text("word")))))
        result = render(_doc(p))
        assert '<span class="hl">word</span>' in result
        # span should NOT have newlines around content
        assert '<span class="hl">\n' not in result

    def test_nested_wrappers(self) -> None:
        inner_div = _call(
            "div", (_arg("class", "inner"),), _body(_call("p", body=_body(_text("Content"))))
        )
        outer_section = _call("section", (_arg("class", "outer"),), _body(inner_div))
        result = render(_doc(outer_section))
        assert '<section class="outer">' in result
        assert '<div class="inner">' in result
        assert "</div>" in result
        assert "</section>" in result

    def test_all_wrapper_tags(self) -> None:
        from picodoc.builtins import WRAPPER_TAGS

        for tag in sorted(WRAPPER_TAGS):
            node = _call(tag, body=_body(_call("p", body=_body(_text("X")))))
            result = render(_doc(node))
            if tag == "span":
                assert "<span><p>X</p></span>" in result
            else:
                assert f"<{tag}>\n<p>X</p>\n</{tag}>" in result


class TestDocBody:
    def test_body_no_attrs(self) -> None:
        doc = _doc(_call("p", body=_body(_text("Hello"))))
        result = render(doc)
        assert "<body>\n" in result

    def test_body_class(self) -> None:
        doc = _doc(
            _call("doc.body", (_arg("class", "dark-theme"),)),
            _call("p", body=_body(_text("Hello"))),
        )
        result = render(doc)
        assert '<body class="dark-theme">' in result

    def test_body_id(self) -> None:
        doc = _doc(
            _call("doc.body", (_arg("id", "main-body"),)),
            _call("p", body=_body(_text("Hello"))),
        )
        result = render(doc)
        assert '<body id="main-body">' in result

    def test_body_class_and_id(self) -> None:
        doc = _doc(
            _call("doc.body", (_arg("class", "dark"), _arg("id", "app"))),
            _call("p", body=_body(_text("Hello"))),
        )
        result = render(doc)
        assert '<body class="dark" id="app">' in result

    def test_body_not_in_head(self) -> None:
        doc = _doc(
            _call("doc.body", (_arg("class", "themed"),)),
            _call("p", body=_body(_text("Hello"))),
        )
        result = render(doc)
        head = result.split("<head>")[1].split("</head>")[0]
        assert "doc.body" not in head
        assert "themed" not in head


class TestDocContent:
    def test_loose_items_wrapped(self) -> None:
        doc = _doc(
            _call("doc.content", (_arg("type", "main"),)),
            _call("p", body=_body(_text("Loose paragraph."))),
        )
        result = render(doc)
        assert "<main>\n<p>Loose paragraph.</p>\n</main>" in result

    def test_wrappers_outside_content(self) -> None:
        doc = _doc(
            _call("doc.content", (_arg("type", "main"),)),
            _call("header", body=_body(_call("h1", body=_body(_text("Site"))))),
            _call("p", body=_body(_text("Loose."))),
            _call("footer", body=_body(_call("p", body=_body(_text("Copyright"))))),
        )
        result = render(doc)
        body = result.split("<body>")[1].split("</body>")[0]
        # header and footer should NOT be inside <main>
        assert "<header>" in body
        assert "<footer>" in body
        assert "<main>\n<p>Loose.</p>\n</main>" in body
        # header appears before main
        assert body.index("<header>") < body.index("<main>")
        # footer appears after main
        assert body.index("</main>") < body.index("<footer>")

    def test_ordering_preserved(self) -> None:
        doc = _doc(
            _call("doc.content", (_arg("type", "main"),)),
            _call("header", body=_body(_call("h1", body=_body(_text("Site"))))),
            _call("p", body=_body(_text("A"))),
            _call("p", body=_body(_text("B"))),
            _call("footer", body=_body(_call("p", body=_body(_text("End"))))),
        )
        result = render(doc)
        body = result.split("<body>")[1].split("</body>")[0]
        # header, main(with 2 paragraphs), footer
        assert body.index("<header>") < body.index("<main>")
        assert body.index("</main>") < body.index("<footer>")
        assert "<p>A</p>" in body
        assert "<p>B</p>" in body

    def test_no_doc_content(self) -> None:
        doc = _doc(
            _call("p", body=_body(_text("Hello"))),
        )
        result = render(doc)
        # Without doc.content, no wrapping
        assert "<main>" not in result
        assert "<p>Hello</p>" in result

    def test_doc_content_with_class_and_id(self) -> None:
        doc = _doc(
            _call(
                "doc.content", (_arg("type", "main"), _arg("class", "content"), _arg("id", "page"))
            ),
            _call("p", body=_body(_text("Text"))),
        )
        result = render(doc)
        assert '<main class="content" id="page">' in result


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


class TestInlineCode:
    def test_tilde_renders_inline_code(self) -> None:
        code = _call("~", (), _body(_text("code")))
        result = render(_doc(_call("p", body=_body(code))))
        assert "<code>code</code>" in result
        assert "<pre>" not in result

    def test_tilde_with_language(self) -> None:
        code = _call("~", (_arg("language", "python"),), _body(_text("print()")))
        result = render(_doc(_call("p", body=_body(code))))
        assert '<code class="language-python">print()</code>' in result
        assert "<pre>" not in result

    def test_tilde_with_raw_string(self) -> None:
        code = _call("~", (), RawString("<div>", S))
        result = render(_doc(_call("p", body=_body(code))))
        assert "<code>&lt;div&gt;</code>" in result
        assert "<pre>" not in result

    def test_tilde_html_escaping(self) -> None:
        code = _call("~", (), _body(_text("<div>")))
        result = render(_doc(_call("p", body=_body(code))))
        assert "<code>&lt;div&gt;</code>" in result


class TestHeadingIds:
    def test_h1_gets_id(self) -> None:
        result = render(_doc(_call("h1", body=_body(_text("Introduction")))))
        assert '<h1 id="introduction">Introduction</h1>' in result

    def test_h2_gets_id(self) -> None:
        result = render(_doc(_call("h2", body=_body(_text("Getting Started")))))
        assert '<h2 id="getting-started">Getting Started</h2>' in result

    def test_h3_gets_id(self) -> None:
        result = render(_doc(_call("h3", body=_body(_text("Details")))))
        assert '<h3 id="details">Details</h3>' in result

    def test_h4_through_h6_get_ids(self) -> None:
        for level in (4, 5, 6):
            tag = f"h{level}"
            result = render(_doc(_call(tag, body=_body(_text("Sub")))))
            assert f'<{tag} id="sub">Sub</{tag}>' in result

    def test_alias_heading_gets_id(self) -> None:
        result = render(_doc(_call("-", body=_body(_text("Top")))))
        assert '<h1 id="top">Top</h1>' in result

    def test_special_chars_become_hyphens(self) -> None:
        result = render(_doc(_call("h1", body=_body(_text("Getting Started!")))))
        assert '<h1 id="getting-started">Getting Started!</h1>' in result

    def test_multiple_special_chars_collapse(self) -> None:
        result = render(_doc(_call("h1", body=_body(_text("a  &  b")))))
        assert 'id="a-b"' in result

    def test_duplicate_heading_text(self) -> None:
        result = render(
            _doc(
                _call("h2", body=_body(_text("Intro"))),
                _call("h2", body=_body(_text("Intro"))),
            )
        )
        assert '<h2 id="intro">Intro</h2>' in result
        assert '<h2 id="intro-2">Intro</h2>' in result

    def test_triple_duplicate(self) -> None:
        result = render(
            _doc(
                _call("h2", body=_body(_text("Same"))),
                _call("h2", body=_body(_text("Same"))),
                _call("h2", body=_body(_text("Same"))),
            )
        )
        assert 'id="same"' in result
        assert 'id="same-2"' in result
        assert 'id="same-3"' in result

    def test_empty_heading_text(self) -> None:
        result = render(_doc(_call("h1", body=_body(_text("")))))
        assert 'id="heading"' in result


class TestDocToc:
    def test_toc_basic_structure(self) -> None:
        doc = _doc(
            _call("doc.toc"),
            _call("h1", body=_body(_text("Chapter One"))),
            _call("h2", body=_body(_text("Section A"))),
            _call("h2", body=_body(_text("Section B"))),
        )
        result = render(doc)
        body = result.split("<body>")[1].split("</body>")[0]
        assert "<ul>" in body
        assert '<a href="#chapter-one">Chapter One</a>' in body
        assert '<a href="#section-a">Section A</a>' in body
        assert '<a href="#section-b">Section B</a>' in body
        assert "</ul>" in body
        assert "<nav" not in body

    def test_toc_in_body_not_head(self) -> None:
        doc = _doc(
            _call("doc.toc"),
            _call("h1", body=_body(_text("Title"))),
        )
        result = render(doc)
        head = result.split("<head>")[1].split("</head>")[0]
        assert "<ul" not in head
        body = result.split("<body>")[1].split("</body>")[0]
        assert "<ul>" in body

    def test_toc_level_default(self) -> None:
        doc = _doc(
            _call("doc.toc"),
            _call("h1", body=_body(_text("H1"))),
            _call("h2", body=_body(_text("H2"))),
            _call("h3", body=_body(_text("H3"))),
            _call("h4", body=_body(_text("H4"))),
        )
        result = render(doc)
        body = result.split("<body>")[1].split("</body>")[0]
        assert '<a href="#h1">H1</a>' in body
        assert '<a href="#h2">H2</a>' in body
        assert '<a href="#h3">H3</a>' in body
        # h4 should NOT be in TOC (default level=3)
        assert '<a href="#h4">' not in body
        # But h4 should still get an id attribute
        assert '<h4 id="h4">H4</h4>' in body

    def test_toc_level_param(self) -> None:
        doc = _doc(
            _call("doc.toc", (_arg("level", "2"),)),
            _call("h1", body=_body(_text("H1"))),
            _call("h2", body=_body(_text("H2"))),
            _call("h3", body=_body(_text("H3"))),
        )
        result = render(doc)
        body = result.split("<body>")[1].split("</body>")[0]
        assert '<a href="#h1">H1</a>' in body
        assert '<a href="#h2">H2</a>' in body
        # h3 should NOT be in TOC
        assert '<a href="#h3">' not in body

    def test_toc_no_headings(self) -> None:
        doc = _doc(
            _call("doc.toc"),
            _call("p", body=_body(_text("Just a paragraph."))),
        )
        result = render(doc)
        body = result.split("<body>")[1].split("</body>")[0]
        # With no headings, TOC renders as empty string
        assert "<ul" not in body

    def test_toc_nested_structure(self) -> None:
        doc = _doc(
            _call("doc.toc"),
            _call("h1", body=_body(_text("Top"))),
            _call("h2", body=_body(_text("Sub"))),
        )
        result = render(doc)
        body = result.split("<body>")[1].split("</body>")[0]
        # Should have nested <ul> for h2 under h1
        assert "<ul>" in body
        assert "</ul>" in body

    def test_toc_inside_nav_wrapper(self) -> None:
        """Wrapping #doc.toc in [#nav id=toc : ...] produces <nav id="toc"><ul>...</ul>\n</nav>."""
        doc = _doc(
            _call(
                "nav",
                (_arg("id", "toc"),),
                body=_body(
                    _call("doc.toc"),
                ),
                bracketed=True,
            ),
            _call("h1", body=_body(_text("Title"))),
        )
        result = render(doc)
        body = result.split("<body>")[1].split("</body>")[0]
        assert '<nav id="toc">' in body
        assert "<ul>" in body
        assert "</nav>" in body

    def test_headings_get_ids_without_toc(self) -> None:
        """Headings always get IDs, even without #doc.toc."""
        doc = _doc(
            _call("h1", body=_body(_text("Title"))),
            _call("h2", body=_body(_text("Section"))),
        )
        result = render(doc)
        assert '<h1 id="title">Title</h1>' in result
        assert '<h2 id="section">Section</h2>' in result


class TestHeadingFeatures:
    def test_heading_number_basic(self) -> None:
        doc = _doc(
            _call("doc.heading.number"),
            _call("h1", body=_body(_text("Intro"))),
            _call("h2", body=_body(_text("Background"))),
            _call("h3", body=_body(_text("Details"))),
        )
        result = render(doc)
        # h1 never gets a number
        assert '<h1 id="intro">Intro</h1>' in result
        assert '<h2 id="background">1. Background</h2>' in result
        assert '<h3 id="details">1.1. Details</h3>' in result

    def test_heading_number_counter_reset(self) -> None:
        doc = _doc(
            _call("doc.heading.number"),
            _call("h2", body=_body(_text("Sub A"))),
            _call("h3", body=_body(_text("Detail"))),
            _call("h2", body=_body(_text("Sub B"))),
            _call("h3", body=_body(_text("Detail 2"))),
        )
        result = render(doc)
        assert '<h2 id="sub-a">1. Sub A</h2>' in result
        assert '<h3 id="detail">1.1. Detail</h3>' in result
        assert '<h2 id="sub-b">2. Sub B</h2>' in result
        # h3 counter resets when h2 increments
        assert '<h3 id="detail-2">2.1. Detail 2</h3>' in result

    def test_heading_number_level_param(self) -> None:
        doc = _doc(
            _call("doc.heading.number", (_arg("level", "2"),)),
            _call("h1", body=_body(_text("Top"))),
            _call("h2", body=_body(_text("Mid"))),
            _call("h3", body=_body(_text("Deep"))),
        )
        result = render(doc)
        # h1 always skipped from numbering
        assert '<h1 id="top">Top</h1>' in result
        assert '<h2 id="mid">1. Mid</h2>' in result
        # h3 beyond level=2, no number
        assert '<h3 id="deep">Deep</h3>' in result

    def test_heading_number_default_level(self) -> None:
        doc = _doc(
            _call("doc.heading.number"),
            _call("h1", body=_body(_text("A"))),
            _call("h2", body=_body(_text("B"))),
            _call("h3", body=_body(_text("C"))),
            _call("h4", body=_body(_text("D"))),
        )
        result = render(doc)
        # h1 skipped, default level=3: h2-h3 get numbers, h4 does not
        assert '<h1 id="a">A</h1>' in result
        assert "1. B" in result
        assert "1.1. C" in result
        assert '<h4 id="d">D</h4>' in result

    def test_heading_anchor_basic(self) -> None:
        doc = _doc(
            _call("doc.heading.anchor"),
            _call("h1", body=_body(_text("Title"))),
            _call("h2", body=_body(_text("Section"))),
        )
        result = render(doc)
        assert '<h1 id="title"><a href="#title">Title</a></h1>' in result
        assert '<h2 id="section"><a href="#section">Section</a></h2>' in result

    def test_heading_anchor_level_param(self) -> None:
        doc = _doc(
            _call("doc.heading.anchor", (_arg("level", "2"),)),
            _call("h1", body=_body(_text("Top"))),
            _call("h2", body=_body(_text("Mid"))),
            _call("h3", body=_body(_text("Deep"))),
        )
        result = render(doc)
        assert '<a href="#top">Top</a>' in result
        assert '<a href="#mid">Mid</a>' in result
        # h3 beyond level=2, no anchor
        assert '<h3 id="deep">Deep</h3>' in result

    def test_heading_anchor_and_number(self) -> None:
        doc = _doc(
            _call("doc.heading.number"),
            _call("doc.heading.anchor"),
            _call("h1", body=_body(_text("Intro"))),
            _call("h2", body=_body(_text("Background"))),
        )
        result = render(doc)
        # h1: anchor wraps body (no number)
        assert '<h1 id="intro"><a href="#intro">Intro</a></h1>' in result
        # h2: number inside anchor wrapper
        assert '<h2 id="background"><a href="#background">1. Background</a></h2>' in result

    def test_heading_beyond_level_unchanged(self) -> None:
        doc = _doc(
            _call("doc.heading.number", (_arg("level", "2"),)),
            _call("doc.heading.anchor", (_arg("level", "2"),)),
            _call("h3", body=_body(_text("Deep"))),
            _call("h4", body=_body(_text("Deeper"))),
        )
        result = render(doc)
        # Beyond configured level: no number, no anchor
        assert '<h3 id="deep">Deep</h3>' in result
        assert '<h4 id="deeper">Deeper</h4>' in result


class TestSmartInternalLinks:
    def test_auto_text_from_heading(self) -> None:
        """Fragment link with no body uses heading text."""
        link = _call("link", (_iarg("to", "background"),))
        doc = _doc(
            _call("h2", body=_body(_text("Background"))),
            _call("p", body=_body(link)),
        )
        result = render(doc)
        assert '<a href="#background">Background</a>' in result

    def test_auto_text_excludes_numbers(self) -> None:
        """Auto-resolved text uses plain heading text, not numbered."""
        link = _call("link", (_iarg("to", "background"),))
        doc = _doc(
            _call("doc.heading.number"),
            _call("h2", body=_body(_text("Background"))),
            _call("p", body=_body(link)),
        )
        result = render(doc)
        # Heading itself gets "1. Background" but link text is plain
        assert "1. Background" in result
        assert '<a href="#background">Background</a>' in result

    def test_explicit_body_preserved(self) -> None:
        """Fragment link with body keeps the provided text."""
        link = _call("link", (_iarg("to", "background"),), _body(_text("see here")))
        doc = _doc(
            _call("h2", body=_body(_text("Background"))),
            _call("p", body=_body(link)),
        )
        result = render(doc)
        assert '<a href="#background">see here</a>' in result

    def test_broken_link_raises(self) -> None:
        """Fragment link to non-existent anchor raises RenderError."""
        import pytest

        from picodoc.errors import RenderError

        link = _call("link", (_iarg("to", "nonexistent"),), _body(_text("click")))
        doc = _doc(_call("p", body=_body(link)))
        with pytest.raises(RenderError, match="broken internal link"):
            render(doc)

    def test_broken_link_no_body_raises(self) -> None:
        """Fragment link with no body to non-existent anchor raises RenderError."""
        import pytest

        from picodoc.errors import RenderError

        link = _call("link", (_iarg("to", "missing"),))
        doc = _doc(_call("p", body=_body(link)))
        with pytest.raises(RenderError, match="broken internal link"):
            render(doc)

    def test_external_link_not_validated(self) -> None:
        """External links are not subject to anchor validation."""
        link = _call("link", (_iarg("to", "https://example.com"),))
        doc = _doc(_call("p", body=_body(link)))
        result = render(doc)
        assert '<a href="https://example.com">https://example.com</a>' in result

    def test_path_link_not_validated(self) -> None:
        """Path links (with /) are not subject to anchor validation."""
        link = _call("link", (_iarg("to", "page/about"),))
        doc = _doc(_call("p", body=_body(link)))
        result = render(doc)
        assert '<a href="page/about">page/about</a>' in result

    def test_body_as_to_fragment(self) -> None:
        """Body text used as fragment target gets heading text replacement."""
        link = _call("link", (), _body(_text("section1")))
        doc = _doc(
            _call("h2", body=_body(_text("Section1"))),
            _call("p", body=_body(link)),
        )
        result = render(doc)
        assert '<a href="#section1">Section1</a>' in result

    def test_body_as_to_fragment_compile(self, compile_source) -> None:
        """Integration test: body-as-to fragment via compile_source."""
        result = compile_source("#--: Section\n\n#p: [#link : section]\n")
        assert '<a href="#section">Section</a>' in result

    def test_macro_block_trailing_ws_string(self, compile_source) -> None:
        """Whitespace after a macro with string body must be preserved."""
        result = compile_source('[#link to="https://example.com"] more text\n')
        assert '<a href="https://example.com">https://example.com</a> more text' in result

    def test_macro_block_trailing_ws_bracketed(self, compile_source) -> None:
        """Whitespace after a macro with bracketed body must be preserved."""
        result = compile_source('[#link to="https://example.com" : Click] more text\n')
        assert '<a href="https://example.com">Click</a> more text' in result

    def test_macro_block_trailing_ws_unbracketed(self, compile_source) -> None:
        """Whitespace after an unbracketed macro with string body must be preserved."""
        result = compile_source('#link"https://example.com" more text\n')
        assert '<a href="https://example.com">https://example.com</a> more text' in result
