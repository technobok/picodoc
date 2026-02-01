"""Synthesize head-item AST nodes from CLI options (CSS, JS, meta tags)."""

from __future__ import annotations

from picodoc.ast import Document, MacroCall, NamedArg, Text
from picodoc.tokens import Position, Span

_CLI_SPAN = Span(Position(0, 0, 0), Position(0, 0, 0))


def inject_head_items(
    doc: Document,
    css_files: list[str],
    js_files: list[str],
    meta_tags: list[tuple[str, str]],
) -> Document:
    """Prepend #link, #script, and #meta nodes to a Document.

    Returns the document unchanged if there is nothing to inject.
    """
    if not css_files and not js_files and not meta_tags:
        return doc

    items: list[MacroCall] = []

    for path in css_files:
        items.append(
            MacroCall(
                "link",
                (
                    NamedArg("rel", Text("stylesheet", _CLI_SPAN), _CLI_SPAN, _CLI_SPAN),
                    NamedArg("href", Text(path, _CLI_SPAN), _CLI_SPAN, _CLI_SPAN),
                ),
                None,
                True,
                _CLI_SPAN,
            )
        )

    for path in js_files:
        items.append(
            MacroCall(
                "script",
                (NamedArg("src", Text(path, _CLI_SPAN), _CLI_SPAN, _CLI_SPAN),),
                None,
                True,
                _CLI_SPAN,
            )
        )

    for name, content in meta_tags:
        items.append(
            MacroCall(
                "meta",
                (
                    NamedArg("name", Text(name, _CLI_SPAN), _CLI_SPAN, _CLI_SPAN),
                    NamedArg("content", Text(content, _CLI_SPAN), _CLI_SPAN, _CLI_SPAN),
                ),
                None,
                True,
                _CLI_SPAN,
            )
        )

    return Document((*items, *doc.children), doc.span)
