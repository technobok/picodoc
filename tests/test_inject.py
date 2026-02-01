"""Tests for CLI head-item injection (CSS, JS, meta tags)."""

from picodoc.ast import Document, MacroCall, Text
from picodoc.inject import inject_head_items
from picodoc.tokens import Position, Span

_SPAN = Span(Position(1, 1, 0), Position(1, 1, 0))


def _empty_doc() -> Document:
    return Document((), _SPAN)


def _doc_with_title() -> Document:
    from picodoc.ast import Body

    title = MacroCall(
        "title",
        (),
        Body((Text("Hello", _SPAN),), _SPAN),
        False,
        _SPAN,
    )
    return Document((title,), _SPAN)


class TestCssInjection:
    def test_single_css_produces_link(self) -> None:
        doc = inject_head_items(_empty_doc(), ["style.css"], [], [])
        assert len(doc.children) == 1
        node = doc.children[0]
        assert isinstance(node, MacroCall)
        assert node.name == "link"
        args = {a.name: a.value for a in node.args}
        assert isinstance(args["rel"], Text)
        assert args["rel"].value == "stylesheet"
        assert isinstance(args["href"], Text)
        assert args["href"].value == "style.css"

    def test_multiple_css_files(self) -> None:
        doc = inject_head_items(_empty_doc(), ["a.css", "b.css"], [], [])
        assert len(doc.children) == 2
        assert all(isinstance(c, MacroCall) and c.name == "link" for c in doc.children)

    def test_css_renders_to_html(self) -> None:
        from picodoc.render import render

        doc = inject_head_items(_doc_with_title(), ["style.css"], [], [])
        html = render(doc)
        assert '<link rel="stylesheet" href="style.css">' in html


class TestJsInjection:
    def test_single_js_produces_script(self) -> None:
        doc = inject_head_items(_empty_doc(), [], ["app.js"], [])
        assert len(doc.children) == 1
        node = doc.children[0]
        assert isinstance(node, MacroCall)
        assert node.name == "script"
        args = {a.name: a.value for a in node.args}
        assert isinstance(args["src"], Text)
        assert args["src"].value == "app.js"

    def test_js_renders_to_html(self) -> None:
        from picodoc.render import render

        doc = inject_head_items(_doc_with_title(), [], ["app.js"], [])
        html = render(doc)
        assert '<script src="app.js"></script>' in html


class TestMetaInjection:
    def test_single_meta_produces_meta(self) -> None:
        doc = inject_head_items(_empty_doc(), [], [], [("viewport", "width=device-width")])
        assert len(doc.children) == 1
        node = doc.children[0]
        assert isinstance(node, MacroCall)
        assert node.name == "meta"
        args = {a.name: a.value for a in node.args}
        assert isinstance(args["name"], Text)
        assert args["name"].value == "viewport"
        assert isinstance(args["content"], Text)
        assert args["content"].value == "width=device-width"

    def test_meta_renders_to_html(self) -> None:
        from picodoc.render import render

        doc = inject_head_items(_doc_with_title(), [], [], [("viewport", "width=device-width")])
        html = render(doc)
        assert '<meta name="viewport" content="width=device-width">' in html


class TestNoopPassthrough:
    def test_empty_injection_returns_same_doc(self) -> None:
        original = _doc_with_title()
        result = inject_head_items(original, [], [], [])
        assert result is original

    def test_injected_items_prepended(self) -> None:
        doc = inject_head_items(_doc_with_title(), ["s.css"], ["a.js"], [("k", "v")])
        assert len(doc.children) == 4
        assert doc.children[0].name == "link"
        assert doc.children[1].name == "script"
        assert doc.children[2].name == "meta"
        assert doc.children[3].name == "title"


class TestCombinedInjection:
    def test_css_js_meta_all_render(self) -> None:
        from picodoc.render import render

        doc = inject_head_items(
            _doc_with_title(),
            ["style.css"],
            ["app.js"],
            [("author", "Test")],
        )
        html = render(doc)
        assert '<link rel="stylesheet" href="style.css">' in html
        assert '<script src="app.js"></script>' in html
        assert '<meta name="author" content="Test">' in html
        assert "<h1>Hello</h1>" in html
