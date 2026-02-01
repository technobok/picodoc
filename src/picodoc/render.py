"""HTML renderer — converts an expanded AST to an HTML document."""

from __future__ import annotations

from picodoc.ast import (
    Body,
    CodeSection,
    Document,
    Escape,
    InterpString,
    MacroCall,
    RawString,
    Text,
)
from picodoc.builtins import resolve_name


def render(doc: Document) -> str:
    """Render an expanded AST to a complete HTML document."""
    lang: str | None = None
    head_items: list[MacroCall] = []
    body_items: list[MacroCall] = []

    for child in doc.children:
        if not isinstance(child, MacroCall):
            continue
        name = resolve_name(child.name)
        if name == "lang":
            lang = _body_text(child.body)
        elif name in ("meta", "link", "script"):
            head_items.append(child)
        else:
            body_items.append(child)

    parts: list[str] = ["<!DOCTYPE html>\n"]
    if lang:
        parts.append(f'<html lang="{_escape_attr(lang)}">\n')
    else:
        parts.append("<html>\n")
    parts.append("<head>\n")
    parts.append('<meta charset="utf-8">\n')
    for item in head_items:
        parts.append(_render_head_item(item))
        parts.append("\n")
    parts.append("</head>\n")
    parts.append("<body>\n")
    for item in body_items:
        rendered = _render_node(item)
        if rendered:
            parts.append(rendered)
            parts.append("\n")
    parts.append("</body>\n")
    parts.append("</html>\n")

    return "".join(parts)


# ---------------------------------------------------------------------------
# HTML escaping
# ---------------------------------------------------------------------------


def _escape_html(text: str) -> str:
    """Escape text for HTML body content. Also encodes non-ASCII as entities."""
    result: list[str] = []
    for ch in text:
        if ch == "&":
            result.append("&amp;")
        elif ch == "<":
            result.append("&lt;")
        elif ch == ">":
            result.append("&gt;")
        elif ord(ch) > 0x7F:
            result.append(f"&#x{ord(ch):X};")
        else:
            result.append(ch)
    return "".join(result)


def _escape_attr(text: str) -> str:
    """Escape text for HTML attribute values."""
    result: list[str] = []
    for ch in text:
        if ch == "&":
            result.append("&amp;")
        elif ch == "<":
            result.append("&lt;")
        elif ch == ">":
            result.append("&gt;")
        elif ch == '"':
            result.append("&quot;")
        elif ord(ch) > 0x7F:
            result.append(f"&#x{ord(ch):X};")
        else:
            result.append(ch)
    return "".join(result)


# ---------------------------------------------------------------------------
# Body / child rendering helpers
# ---------------------------------------------------------------------------


def _body_text(body: Body | InterpString | RawString | None) -> str:
    """Extract plain text from a body (for #lang, etc.)."""
    if body is None:
        return ""
    if isinstance(body, Body):
        return "".join(c.value for c in body.children if isinstance(c, (Text, Escape)))
    if isinstance(body, InterpString):
        return "".join(p.value for p in body.parts if isinstance(p, Text))
    if isinstance(body, RawString):
        return body.value
    return ""


def _render_body(body: Body | InterpString | RawString | None) -> str:
    """Render a macro body to HTML."""
    if body is None:
        return ""
    if isinstance(body, Body):
        return "".join(_render_child(c) for c in body.children)
    if isinstance(body, InterpString):
        return _render_interp_string(body)
    if isinstance(body, RawString):
        return _escape_html(body.value)
    return ""


def _render_interp_string(s: InterpString) -> str:
    parts: list[str] = []
    for part in s.parts:
        if isinstance(part, Text):
            parts.append(_escape_html(part.value))
        elif isinstance(part, CodeSection):
            for child in part.body:
                parts.append(_render_child(child))
    return "".join(parts)


def _render_child(child: Text | Escape | MacroCall) -> str:
    """Render a single body child node."""
    if isinstance(child, Text):
        return _escape_html(child.value)
    if isinstance(child, Escape):
        return _render_escape(child)
    if isinstance(child, MacroCall):
        return _render_node(child)
    return ""


def _render_escape(esc: Escape) -> str:
    if ord(esc.value) > 0x7F:
        return f"&#x{ord(esc.value):X};"
    return _escape_html(esc.value)


def _get_arg_text(node: MacroCall, name: str) -> str | None:
    """Get a named argument's text value."""
    for arg in node.args:
        if arg.name == name:
            return _arg_value_text(arg.value)
    return None


def _arg_value_text(value: Text | InterpString | RawString | object) -> str:
    """Extract plain text from an argument value node."""
    if isinstance(value, Text):
        return value.value
    if isinstance(value, InterpString):
        return "".join(p.value for p in value.parts if isinstance(p, Text))
    if isinstance(value, RawString):
        return value.value
    return ""


# ---------------------------------------------------------------------------
# Node rendering dispatcher
# ---------------------------------------------------------------------------


def _render_node(node: MacroCall) -> str:
    name = resolve_name(node.name)
    match name:
        case "title":
            return f"<h1>{_render_body(node.body)}</h1>"
        case "h2":
            return f"<h2>{_render_body(node.body)}</h2>"
        case "h3":
            return f"<h3>{_render_body(node.body)}</h3>"
        case "h4":
            return f"<h4>{_render_body(node.body)}</h4>"
        case "h5":
            return f"<h5>{_render_body(node.body)}</h5>"
        case "h6":
            return f"<h6>{_render_body(node.body)}</h6>"
        case "p":
            return f"<p>{_render_body(node.body)}</p>"
        case "hr":
            return "<hr>"
        case "b":
            return f"<strong>{_render_body(node.body)}</strong>"
        case "i":
            return f"<em>{_render_body(node.body)}</em>"
        case "url":
            return _render_url(node)
        case "code":
            return _render_code(node)
        case "literal":
            return _render_literal(node)
        case "ul":
            return _render_list(node, "ul")
        case "ol":
            return _render_list(node, "ol")
        case "*":
            return _render_li(node)
        case "table":
            return _render_table(node)
        case "tr":
            return _render_tr(node)
        case "td":
            return _render_td(node)
        case "th":
            return _render_th(node)
        case _:
            return _render_body(node.body)


# ---------------------------------------------------------------------------
# Render-time builtins
# ---------------------------------------------------------------------------


def _render_url(node: MacroCall) -> str:
    link = _get_arg_text(node, "link") or ""
    text = _get_arg_text(node, "text")

    if text is not None:
        body_html = _escape_html(text)
    elif node.body is not None:
        body_html = _render_body(node.body)
    else:
        body_html = _escape_html(link)

    return f'<a href="{_escape_attr(link)}">{body_html}</a>'


def _render_code(node: MacroCall) -> str:
    lang = _get_arg_text(node, "language")
    cls = f' class="language-{_escape_attr(lang)}"' if lang else ""

    if isinstance(node.body, RawString):
        # Block code
        content = _escape_html(node.body.value)
        return f"<pre><code{cls}>{content}</code></pre>"
    else:
        # Inline code
        content = _render_body(node.body)
        return f"<code{cls}>{content}</code>"


def _render_literal(node: MacroCall) -> str:
    if isinstance(node.body, RawString):
        return node.body.value
    return _render_body(node.body)


def _render_list(node: MacroCall, tag: str) -> str:
    parts: list[str] = [f"<{tag}>\n"]
    if isinstance(node.body, Body):
        for child in node.body.children:
            if isinstance(child, MacroCall):
                parts.append(_render_node(child))
                parts.append("\n")
    parts.append(f"</{tag}>")
    return "".join(parts)


def _render_li(node: MacroCall) -> str:
    if not isinstance(node.body, Body):
        return f"<li>{_render_body(node.body)}</li>"

    # Separate inline content from nested block lists
    inline: list[Text | Escape | MacroCall] = []
    blocks: list[MacroCall] = []
    seen_block = False

    for child in node.body.children:
        if isinstance(child, MacroCall) and resolve_name(child.name) in ("ul", "ol"):
            blocks.append(child)
            seen_block = True
        elif not seen_block:
            inline.append(child)

    inline_html = "".join(_render_child(c) for c in inline).strip()

    if blocks:
        block_html = "\n".join(_render_node(b) for b in blocks)
        return f"<li>{inline_html}\n{block_html}\n</li>"
    return f"<li>{inline_html}</li>"


def _render_table(node: MacroCall) -> str:
    parts: list[str] = ["<table>\n"]
    if isinstance(node.body, Body):
        for child in node.body.children:
            if isinstance(child, MacroCall):
                parts.append(_render_node(child))
                parts.append("\n")
    parts.append("</table>")
    return "".join(parts)


def _render_tr(node: MacroCall) -> str:
    parts: list[str] = ["<tr>"]
    if isinstance(node.body, Body):
        for child in node.body.children:
            if isinstance(child, MacroCall):
                parts.append(_render_node(child))
    parts.append("</tr>")
    return "".join(parts)


def _render_td(node: MacroCall) -> str:
    span = _get_arg_text(node, "span")
    body_html = _render_body(node.body)
    if span:
        return f'<td colspan="{_escape_attr(span)}">{body_html}</td>'
    return f"<td>{body_html}</td>"


def _render_th(node: MacroCall) -> str:
    span = _get_arg_text(node, "span")
    body_html = _render_body(node.body)
    if span:
        return f'<th colspan="{_escape_attr(span)}">{body_html}</th>'
    return f"<th>{body_html}</th>"


# ---------------------------------------------------------------------------
# Head items
# ---------------------------------------------------------------------------


def _render_head_item(node: MacroCall) -> str:
    name = resolve_name(node.name)

    if name == "meta":
        meta_name = _get_arg_text(node, "name")
        prop = _get_arg_text(node, "property")
        content = _get_arg_text(node, "content") or ""
        if prop:
            return f'<meta property="{_escape_attr(prop)}" content="{_escape_attr(content)}">'
        if meta_name:
            return f'<meta name="{_escape_attr(meta_name)}" content="{_escape_attr(content)}">'
        return ""

    if name == "link":
        rel = _get_arg_text(node, "rel") or ""
        href = _get_arg_text(node, "href") or ""
        return f'<link rel="{_escape_attr(rel)}" href="{_escape_attr(href)}">'

    if name == "script":
        src = _get_arg_text(node, "src")
        if src:
            return f'<script src="{_escape_attr(src)}"></script>'
        if isinstance(node.body, RawString):
            return f"<script>\n{node.body.value}\n</script>"
        if node.body is not None:
            return f"<script>\n{_render_body(node.body)}\n</script>"
        return "<script></script>"

    return ""
