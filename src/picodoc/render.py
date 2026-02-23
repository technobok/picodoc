"""HTML renderer — converts an expanded AST to an HTML document."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from picodoc.ast import (
    Body,
    CodeSection,
    Document,
    Escape,
    InterpString,
    MacroCall,
    NamedArg,
    RawString,
    Text,
)
from picodoc.builtins import WRAPPER_TAGS, resolve_name
from picodoc.tokens import Span

_HEADING_NAMES: frozenset[str] = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})
_HEADING_LEVEL: dict[str, int] = {f"h{i}": i for i in range(1, 7)}

_SLUG_RE = re.compile(r"[^a-z0-9]")
_COLLAPSE_RE = re.compile(r"-{2,}")


@dataclass
class _RenderState:
    heading_ids: dict[int, str] = field(default_factory=dict)
    toc_entries: list[tuple[int, str, str]] = field(default_factory=list)
    toc_level: int = 0


def _slugify(text: str, used: dict[str, int]) -> str:
    """Generate a unique URL-friendly slug from text."""
    slug = text.lower()
    slug = _SLUG_RE.sub("-", slug)
    slug = _COLLAPSE_RE.sub("-", slug)
    slug = slug.strip("-")
    if not slug:
        slug = "heading"
    base = slug
    count = used.get(base, 0)
    if count > 0:
        slug = f"{base}-{count + 1}"
    used[base] = count + 1
    return slug


def _collect_headings(nodes: tuple[MacroCall | object, ...], state: _RenderState) -> None:
    """Walk top-level nodes to find headings and doc.toc, populate state."""
    used: dict[str, int] = {}
    for node in nodes:
        if not isinstance(node, MacroCall):
            continue
        _collect_headings_recursive(node, state, used)


def _collect_headings_recursive(
    node: MacroCall,
    state: _RenderState,
    used: dict[str, int],
) -> None:
    """Recursively find heading and doc.toc nodes."""
    name = resolve_name(node.name)
    if name in _HEADING_NAMES:
        level = _HEADING_LEVEL[name]
        text = _body_text(node.body)
        slug = _slugify(text, used)
        state.heading_ids[id(node)] = slug
        if state.toc_level == 0 or level <= state.toc_level:
            state.toc_entries.append((level, text, slug))
    elif name == "doc.toc":
        level_str = _get_arg_text(node, "level")
        state.toc_level = int(level_str) if level_str else 3

    # Recurse into body children
    if isinstance(node.body, Body):
        for child in node.body.children:
            if isinstance(child, MacroCall):
                _collect_headings_recursive(child, state, used)


def render(doc: Document) -> str:
    """Render an expanded AST to a complete HTML document."""
    lang: str | None = None
    head_items: list[MacroCall] = []
    body_items: list[MacroCall] = []
    content_type: str | None = None
    content_class: str | None = None
    content_id: str | None = None

    for child in doc.children:
        if not isinstance(child, MacroCall):
            continue
        name = resolve_name(child.name)
        if name == "doc.lang":
            lang = _body_text(child.body)
        elif name == "doc.content":
            content_type = _get_arg_text(child, "type")
            content_class = _get_arg_text(child, "class")
            content_id = _get_arg_text(child, "id")
        elif name == "doc.toc":
            body_items.append(child)
        elif name.startswith("doc."):
            head_items.append(child)
        else:
            body_items.append(child)

    # doc.content wrapping: wrap loose top-level items in a container element
    if content_type:
        body_items = _wrap_loose_items(
            body_items,
            content_type,
            content_class,
            content_id,
        )

    # Pre-pass: collect headings and TOC configuration
    state = _RenderState()
    _collect_headings(doc.children, state)

    parts: list[str] = ["<!DOCTYPE html>\n"]
    if lang:
        parts.append(f'<html lang="{_escape_attr(lang)}">\n')
    else:
        parts.append("<html>\n")
    parts.append("<head>\n")
    parts.append('<meta charset="utf-8">\n')
    for item in head_items:
        parts.append(_render_head_item(item, state))
        parts.append("\n")
    parts.append("</head>\n")
    parts.append("<body>\n")
    for item in body_items:
        rendered = _render_node(item, state)
        if rendered:
            parts.append(rendered)
            parts.append("\n")
    parts.append("</body>\n")
    parts.append("</html>\n")

    return "".join(parts)


def _wrap_loose_items(
    body_items: list[MacroCall],
    content_type: str,
    content_class: str | None,
    content_id: str | None,
) -> list[MacroCall]:
    """Wrap loose (non-wrapper) top-level items in a synthetic wrapper."""
    output: list[MacroCall | None] = []
    loose: list[MacroCall] = []
    placeholder_idx: int = -1

    for item in body_items:
        rname = resolve_name(item.name)
        if rname in WRAPPER_TAGS:
            output.append(item)
        else:
            if placeholder_idx == -1:
                placeholder_idx = len(output)
                output.append(None)  # placeholder
            loose.append(item)

    if loose and placeholder_idx >= 0:
        span = loose[0].span
        wrapper_args = _build_content_args(content_type, content_class, content_id, span)
        wrapper_body = Body(tuple(loose), span)
        wrapper = MacroCall(content_type, wrapper_args, wrapper_body, False, span)
        output[placeholder_idx] = wrapper

    return [item for item in output if item is not None]


def _build_content_args(
    tag: str,
    cls: str | None,
    id_val: str | None,
    span: Span,
) -> tuple[NamedArg, ...]:
    """Build NamedArg tuple for a synthetic doc.content wrapper."""
    args: list[NamedArg] = []
    if cls:
        args.append(NamedArg("class", Text(cls, span), span, span))
    if id_val:
        args.append(NamedArg("id", Text(id_val, span), span, span))
    return tuple(args)


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
    """Extract plain text from a body (for #doc.lang, etc.)."""
    if body is None:
        return ""
    if isinstance(body, Body):
        return "".join(c.value for c in body.children if isinstance(c, (Text, Escape)))
    if isinstance(body, InterpString):
        return "".join(p.value for p in body.parts if isinstance(p, Text))
    if isinstance(body, RawString):
        return body.value
    return ""


def _render_body(body: Body | InterpString | RawString | None, state: _RenderState) -> str:
    """Render a macro body to HTML."""
    if body is None:
        return ""
    if isinstance(body, Body):
        return "".join(_render_child(c, state) for c in body.children)
    if isinstance(body, InterpString):
        return _render_interp_string(body, state)
    if isinstance(body, RawString):
        return _escape_html(body.value)
    return ""


def _render_interp_string(s: InterpString, state: _RenderState) -> str:
    parts: list[str] = []
    for part in s.parts:
        if isinstance(part, Text):
            parts.append(_escape_html(part.value))
        elif isinstance(part, CodeSection):
            for child in part.body:
                parts.append(_render_child(child, state))
    return "".join(parts)


def _render_child(child: Text | Escape | MacroCall, state: _RenderState) -> str:
    """Render a single body child node."""
    if isinstance(child, Text):
        return _escape_html(child.value)
    if isinstance(child, Escape):
        return _render_escape(child)
    if isinstance(child, MacroCall):
        return _render_node(child, state)
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
# Heading rendering
# ---------------------------------------------------------------------------


def _render_heading(node: MacroCall, level: int, state: _RenderState) -> str:
    body_html = _render_body(node.body, state)
    slug = state.heading_ids.get(id(node), "")
    if slug:
        return f'<h{level} id="{_escape_attr(slug)}">{body_html}</h{level}>'
    return f"<h{level}>{body_html}</h{level}>"


# ---------------------------------------------------------------------------
# TOC rendering
# ---------------------------------------------------------------------------


def _render_toc(state: _RenderState) -> str:
    """Render the table of contents as a <ul> tree."""
    if not state.toc_entries:
        return ""

    parts: list[str] = []
    stack: list[int] = []  # tracks nesting levels

    for level, text, slug in state.toc_entries:
        if not stack:
            parts.append("<ul>\n")
            stack.append(level)
        elif level > stack[-1]:
            # Open deeper nesting
            while level > stack[-1]:
                parts.append("<ul>\n")
                stack.append(stack[-1] + 1)
        elif level < stack[-1]:
            # Close back up
            while stack and stack[-1] > level:
                parts.append("</li>\n</ul>\n")
                stack.pop()
            # Close the previous <li> at this level
            parts.append("</li>\n")
        else:
            # Same level — close previous <li>
            parts.append("</li>\n")

        escaped_text = _escape_html(text)
        parts.append(f'<li><a href="#{_escape_attr(slug)}">{escaped_text}</a>\n')

    # Close all remaining levels
    while stack:
        parts.append("</li>\n</ul>\n")
        stack.pop()

    return "".join(parts)


# ---------------------------------------------------------------------------
# Node rendering dispatcher
# ---------------------------------------------------------------------------


def _render_node(node: MacroCall, state: _RenderState) -> str:
    name = resolve_name(node.name)
    match name:
        case "h1":
            return _render_heading(node, 1, state)
        case "h2":
            return _render_heading(node, 2, state)
        case "h3":
            return _render_heading(node, 3, state)
        case "h4":
            return _render_heading(node, 4, state)
        case "h5":
            return _render_heading(node, 5, state)
        case "h6":
            return _render_heading(node, 6, state)
        case "p":
            return f"<p>{_render_body(node.body, state)}</p>"
        case "hr":
            return "<hr>"
        case "b":
            return f"<strong>{_render_body(node.body, state)}</strong>"
        case "i":
            return f"<em>{_render_body(node.body, state)}</em>"
        case "link":
            return _render_link(node, state)
        case "code":
            return _render_block_code(node, state)
        case "~":
            return _render_inline_code(node, state)
        case "literal":
            return _render_literal(node)
        case "ul":
            return _render_list(node, "ul", state)
        case "ol":
            return _render_list(node, "ol", state)
        case "*":
            return _render_li(node, state)
        case "table":
            return _render_table(node, state)
        case "tr":
            return _render_tr(node, state)
        case "td":
            return _render_td(node, state)
        case "th":
            return _render_th(node, state)
        case "doc.toc":
            return _render_toc(state)
        case "div" | "section" | "nav" | "header" | "footer" | "main" | "article" | "aside":
            return _render_wrapper(node, name, state)
        case "span":
            return _render_wrapper(node, "span", state, block=False)
        case _:
            return _render_body(node.body, state)


# ---------------------------------------------------------------------------
# Render-time builtins
# ---------------------------------------------------------------------------


def _render_link(node: MacroCall, state: _RenderState) -> str:
    to = _get_arg_text(node, "to") or ""

    # Determine href: if no "://" and no "/", treat as fragment reference
    href = f"#{to}" if "://" not in to and "/" not in to else to
    body_html = _render_body(node.body, state) if node.body is not None else _escape_html(to)

    return f'<a href="{_escape_attr(href)}">{body_html}</a>'


def _render_block_code(node: MacroCall, state: _RenderState) -> str:
    lang = _get_arg_text(node, "language")
    cls = f' class="language-{_escape_attr(lang)}"' if lang else ""
    if isinstance(node.body, RawString):
        content = _escape_html(node.body.value)
    else:
        content = _render_body(node.body, state)
    return f"<pre><code{cls}>{content}</code></pre>"


def _render_inline_code(node: MacroCall, state: _RenderState) -> str:
    lang = _get_arg_text(node, "language")
    cls = f' class="language-{_escape_attr(lang)}"' if lang else ""
    if isinstance(node.body, RawString):
        content = _escape_html(node.body.value)
    else:
        content = _render_body(node.body, state)
    return f"<code{cls}>{content}</code>"


def _render_literal(node: MacroCall) -> str:
    if isinstance(node.body, RawString):
        return node.body.value
    return _body_text(node.body)


def _render_list(node: MacroCall, tag: str, state: _RenderState) -> str:
    parts: list[str] = [f"<{tag}>\n"]
    if isinstance(node.body, Body):
        for child in node.body.children:
            if isinstance(child, MacroCall):
                parts.append(_render_node(child, state))
                parts.append("\n")
    parts.append(f"</{tag}>")
    return "".join(parts)


def _render_li(node: MacroCall, state: _RenderState) -> str:
    if not isinstance(node.body, Body):
        return f"<li>{_render_body(node.body, state)}</li>"

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

    inline_html = "".join(_render_child(c, state) for c in inline).strip()

    if blocks:
        block_html = "\n".join(_render_node(b, state) for b in blocks)
        return f"<li>{inline_html}\n{block_html}\n</li>"
    return f"<li>{inline_html}</li>"


def _render_table(node: MacroCall, state: _RenderState) -> str:
    parts: list[str] = ["<table>\n"]
    if isinstance(node.body, Body):
        for child in node.body.children:
            if isinstance(child, MacroCall):
                parts.append(_render_node(child, state))
                parts.append("\n")
    parts.append("</table>")
    return "".join(parts)


def _render_tr(node: MacroCall, state: _RenderState) -> str:
    parts: list[str] = ["<tr>"]
    if isinstance(node.body, Body):
        for child in node.body.children:
            if isinstance(child, MacroCall):
                parts.append(_render_node(child, state))
    parts.append("</tr>")
    return "".join(parts)


def _render_td(node: MacroCall, state: _RenderState) -> str:
    span = _get_arg_text(node, "span")
    body_html = _render_body(node.body, state)
    if span:
        return f'<td colspan="{_escape_attr(span)}">{body_html}</td>'
    return f"<td>{body_html}</td>"


def _render_th(node: MacroCall, state: _RenderState) -> str:
    span = _get_arg_text(node, "span")
    body_html = _render_body(node.body, state)
    if span:
        return f'<th colspan="{_escape_attr(span)}">{body_html}</th>'
    return f"<th>{body_html}</th>"


def _render_wrapper(node: MacroCall, tag: str, state: _RenderState, *, block: bool = True) -> str:
    cls = _get_arg_text(node, "class")
    id_val = _get_arg_text(node, "id")
    attrs = ""
    if cls:
        attrs += f' class="{_escape_attr(cls)}"'
    if id_val:
        attrs += f' id="{_escape_attr(id_val)}"'
    if block and isinstance(node.body, Body):
        parts: list[str] = []
        for child in node.body.children:
            if isinstance(child, MacroCall):
                parts.append(_render_node(child, state))
                parts.append("\n")
        return f"<{tag}{attrs}>\n{''.join(parts)}</{tag}>"
    return f"<{tag}{attrs}>{_render_body(node.body, state)}</{tag}>"


# ---------------------------------------------------------------------------
# Head items
# ---------------------------------------------------------------------------


def _render_head_item(node: MacroCall, state: _RenderState) -> str:
    name = resolve_name(node.name)

    if name == "doc.title":
        return f"<title>{_render_body(node.body, state)}</title>"

    if name == "doc.meta":
        meta_name = _get_arg_text(node, "name")
        prop = _get_arg_text(node, "property")
        content = _get_arg_text(node, "content") or ""
        if prop:
            return f'<meta property="{_escape_attr(prop)}" content="{_escape_attr(content)}">'
        if meta_name:
            return f'<meta name="{_escape_attr(meta_name)}" content="{_escape_attr(content)}">'
        return ""

    if name == "doc.author":
        content = _body_text(node.body)
        return f'<meta name="author" content="{_escape_attr(content)}">'

    if name == "doc.version":
        content = _body_text(node.body)
        return f'<meta name="version" content="{_escape_attr(content)}">'

    if name == "doc.datecreated":
        content = _body_text(node.body)
        return f'<meta name="datecreated" content="{_escape_attr(content)}">'

    if name == "doc.datemodified":
        content = _body_text(node.body)
        return f'<meta name="datemodified" content="{_escape_attr(content)}">'

    if name == "doc.link":
        rel = _get_arg_text(node, "rel") or ""
        href = _get_arg_text(node, "href") or ""
        type_val = _get_arg_text(node, "type")
        sizes_val = _get_arg_text(node, "sizes")
        attrs = f'rel="{_escape_attr(rel)}" href="{_escape_attr(href)}"'
        if type_val:
            attrs += f' type="{_escape_attr(type_val)}"'
        if sizes_val:
            attrs += f' sizes="{_escape_attr(sizes_val)}"'
        return f"<link {attrs}>"

    if name == "doc.script":
        src = _get_arg_text(node, "src")
        type_val = _get_arg_text(node, "type")
        attrs = ""
        if type_val:
            attrs += f' type="{_escape_attr(type_val)}"'
        if src:
            attrs += f' src="{_escape_attr(src)}"'
            return f"<script{attrs}></script>"
        if isinstance(node.body, RawString):
            return f"<script{attrs}>\n{node.body.value}\n</script>"
        if node.body is not None:
            return f"<script{attrs}>\n{_render_body(node.body, state)}\n</script>"
        return f"<script{attrs}></script>"

    return ""
