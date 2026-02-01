"""Single-pass AST evaluator — expands builtins, collects #set, wraps paragraphs."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from picodoc.ast import (
    Body,
    CodeSection,
    Document,
    Escape,
    InterpString,
    MacroCall,
    Paragraph,
    RawString,
    RequiredMarker,
    Text,
)
from picodoc.builtins import resolve_name
from picodoc.errors import EvalError
from picodoc.tokens import Span


@dataclass
class EvalContext:
    """State carried through evaluation."""

    filename: str
    source_dir: Path
    definitions: dict[str, MacroCall] = field(default_factory=dict)
    include_stack: list[str] = field(default_factory=list)
    max_include_depth: int = 16


def evaluate(doc: Document, filename: str = "input.pdoc") -> Document:
    """Expand expansion-time builtins, collect #set, wrap paragraphs."""
    source_dir = Path(filename).parent
    if not source_dir.parts:
        source_dir = Path(".")
    ctx = EvalContext(
        filename=filename,
        source_dir=source_dir,
        include_stack=[str(Path(filename).resolve())],
    )
    expanded = _expand_top_level(doc.children, ctx)
    # Filter to MacroCall nodes — Text/Escape from conditionals are whitespace
    children = tuple(c for c in expanded if isinstance(c, MacroCall))
    return Document(children, doc.span)


# ---------------------------------------------------------------------------
# Top-level expansion
# ---------------------------------------------------------------------------


def _expand_top_level(
    children: tuple[MacroCall | Paragraph, ...],
    ctx: EvalContext,
) -> list[MacroCall | Text | Escape]:
    result: list[MacroCall | Text | Escape] = []
    for child in children:
        result.extend(_expand_top_node(child, ctx))
    return result


def _expand_top_node(
    node: MacroCall | Paragraph,
    ctx: EvalContext,
) -> list[MacroCall | Text | Escape]:
    if isinstance(node, Paragraph):
        expanded = _expand_body_children(node.body, ctx)
        return [MacroCall("p", (), Body(tuple(expanded), node.span), False, node.span)]
    return _expand_macro(node, ctx)


# ---------------------------------------------------------------------------
# Macro expansion
# ---------------------------------------------------------------------------


def _expand_macro(
    node: MacroCall,
    ctx: EvalContext,
) -> list[MacroCall | Text | Escape]:
    name = resolve_name(node.name)

    if name == "comment":
        return []

    if name == "set":
        return _expand_set(node, ctx)

    if name == "ifeq":
        return _expand_ifeq(node, ctx)

    if name == "ifne":
        return _expand_ifne(node, ctx)

    if name == "ifset":
        return _expand_ifset(node, ctx)

    if name == "include":
        return _expand_include(node, ctx)

    if name == "table":
        return _expand_table(node, ctx)

    # Render-time macro: recurse into body to expand nested builtins
    new_body = _recurse_body(node.body, ctx)
    return [MacroCall(node.name, node.args, new_body, node.bracketed, node.span)]


def _recurse_body(
    body: Body | InterpString | RawString | None,
    ctx: EvalContext,
) -> Body | InterpString | RawString | None:
    if body is None:
        return None
    if isinstance(body, Body):
        expanded = _expand_body_children(body.children, ctx)
        return Body(tuple(expanded), body.span)
    # InterpString and RawString: no expansion needed in Phase 3
    return body


def _expand_body_children(
    children: tuple[Text | Escape | MacroCall, ...],
    ctx: EvalContext,
) -> list[Text | Escape | MacroCall]:
    result: list[Text | Escape | MacroCall] = []
    for child in children:
        if isinstance(child, MacroCall):
            result.extend(_expand_macro(child, ctx))
        else:
            result.append(child)
    return result


# ---------------------------------------------------------------------------
# Value resolution — extract plain text from AST nodes
# ---------------------------------------------------------------------------


def _resolve_value(
    value: Text | InterpString | RawString | MacroCall | RequiredMarker,
    ctx: EvalContext,
) -> str:
    """Resolve an argument value to plain text."""
    if isinstance(value, Text):
        return value.value
    if isinstance(value, RawString):
        return value.value
    if isinstance(value, InterpString):
        parts: list[str] = []
        for part in value.parts:
            if isinstance(part, Text):
                parts.append(part.value)
            elif isinstance(part, CodeSection):
                for child in part.body:
                    if isinstance(child, Text):
                        parts.append(child.value)
                    elif isinstance(child, MacroCall):
                        ref = resolve_name(child.name)
                        if ref in ctx.definitions:
                            parts.append(_extract_def_text(ctx.definitions[ref]))
        return "".join(parts)
    if isinstance(value, MacroCall):
        ref = resolve_name(value.name)
        if ref in ctx.definitions:
            return _extract_def_text(ctx.definitions[ref])
        return ""
    return ""


def _extract_def_text(macro: MacroCall) -> str:
    """Extract plain text from a #set definition's body."""
    if macro.body is None:
        return ""
    if isinstance(macro.body, Body):
        return "".join(c.value for c in macro.body.children if isinstance(c, (Text, Escape)))
    if isinstance(macro.body, InterpString):
        return "".join(p.value for p in macro.body.parts if isinstance(p, Text))
    if isinstance(macro.body, RawString):
        return macro.body.value
    return ""


def _get_arg(
    node: MacroCall, name: str
) -> Text | InterpString | RawString | MacroCall | RequiredMarker | None:
    """Get a named argument value, or None."""
    for arg in node.args:
        if arg.name == name:
            return arg.value
    return None


# ---------------------------------------------------------------------------
# Expansion-time builtins
# ---------------------------------------------------------------------------


def _expand_set(node: MacroCall, ctx: EvalContext) -> list[MacroCall | Text | Escape]:
    name_val = _get_arg(node, "name")
    if name_val is None:
        return []
    name = _resolve_value(name_val, ctx)
    ctx.definitions[name] = node
    return []


def _expand_ifeq(node: MacroCall, ctx: EvalContext) -> list[MacroCall | Text | Escape]:
    lhs_val = _get_arg(node, "lhs")
    rhs_val = _get_arg(node, "rhs")
    if lhs_val is None or rhs_val is None:
        return []
    lhs = _resolve_value(lhs_val, ctx)
    rhs = _resolve_value(rhs_val, ctx)
    if lhs == rhs:
        return _get_condition_body(node, ctx)
    return []


def _expand_ifne(node: MacroCall, ctx: EvalContext) -> list[MacroCall | Text | Escape]:
    lhs_val = _get_arg(node, "lhs")
    rhs_val = _get_arg(node, "rhs")
    if lhs_val is None or rhs_val is None:
        return []
    lhs = _resolve_value(lhs_val, ctx)
    rhs = _resolve_value(rhs_val, ctx)
    if lhs != rhs:
        return _get_condition_body(node, ctx)
    return []


def _expand_ifset(node: MacroCall, ctx: EvalContext) -> list[MacroCall | Text | Escape]:
    name_val = _get_arg(node, "name")
    if name_val is None:
        return []
    name = _resolve_value(name_val, ctx)
    if name in ctx.definitions:
        return _get_condition_body(node, ctx)
    return []


def _get_condition_body(
    node: MacroCall,
    ctx: EvalContext,
) -> list[MacroCall | Text | Escape]:
    if isinstance(node.body, Body):
        return _expand_body_children(node.body.children, ctx)
    return []


def _expand_include(node: MacroCall, ctx: EvalContext) -> list[MacroCall | Text | Escape]:
    file_val = _get_arg(node, "file")
    if file_val is None:
        return []
    filename = _resolve_value(file_val, ctx)
    filepath = ctx.source_dir / filename
    resolved = str(filepath.resolve())

    if len(ctx.include_stack) >= ctx.max_include_depth:
        raise EvalError(
            f"include depth limit ({ctx.max_include_depth}) exceeded",
            node.span,
            "",
        )

    if resolved in ctx.include_stack:
        raise EvalError(
            f"circular include detected: {filename}",
            node.span,
            "",
        )

    try:
        content = filepath.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise EvalError(
            f"included file not found: {filename}",
            node.span,
            "",
        ) from None

    from picodoc.parser import parse

    included_doc = parse(content, str(filepath))

    ctx.include_stack.append(resolved)
    try:
        result = _expand_top_level(included_doc.children, ctx)
    finally:
        ctx.include_stack.pop()

    return result


# ---------------------------------------------------------------------------
# Table pipe-delimited expansion
# ---------------------------------------------------------------------------


def _expand_table(
    node: MacroCall,
    ctx: EvalContext,
) -> list[MacroCall | Text | Escape]:
    if not isinstance(node.body, Body):
        return [MacroCall(node.name, node.args, node.body, node.bracketed, node.span)]

    # Check for pipe characters in text children
    has_pipe = any(isinstance(c, Text) and "|" in c.value for c in node.body.children)

    if not has_pipe:
        # No pipes — recurse into body and pass through for render-time
        new_body = _recurse_body(node.body, ctx)
        return [MacroCall(node.name, node.args, new_body, node.bracketed, node.span)]

    # Parse pipe-delimited rows
    rows = _parse_pipe_rows(node.body, node.span, ctx)

    # Build #tr / #th / #td MacroCall tree
    tr_nodes: list[MacroCall] = []
    for i, row in enumerate(rows):
        cell_tag = "th" if i == 0 else "td"
        cells: list[MacroCall] = []
        for cell_children in row:
            cell_body = Body(tuple(cell_children), node.span)
            cells.append(MacroCall(cell_tag, (), cell_body, True, node.span))
        tr_body = Body(tuple(cells), node.span)
        tr_nodes.append(MacroCall("tr", (), tr_body, True, node.span))

    table_body = Body(tuple(tr_nodes), node.span)
    return [MacroCall("table", (), table_body, node.bracketed, node.span)]


def _parse_pipe_rows(
    body: Body,
    span: Span,
    ctx: EvalContext,
) -> list[list[list[Text | Escape | MacroCall]]]:
    """Parse pipe-delimited body into rows of cells."""
    # rows[i][j] = list of AST children for cell j of row i
    rows: list[list[list[Text | Escape | MacroCall]]] = [[[]]]

    for child in body.children:
        if isinstance(child, Text):
            _split_text_into_rows(child, rows)
        elif isinstance(child, MacroCall):
            expanded = _expand_macro(child, ctx)
            for node in expanded:
                rows[-1][-1].append(node)
        else:
            rows[-1][-1].append(child)

    # Filter empty rows (all cells empty)
    rows = [r for r in rows if any(cell for cell in r)]

    # Trim whitespace from each cell
    for row in rows:
        for cell in row:
            _trim_cell(cell)

    # Remove rows where all cells are empty after trimming
    rows = [r for r in rows if any(cell for cell in r)]

    return rows


def _split_text_into_rows(
    text_node: Text,
    rows: list[list[list[Text | Escape | MacroCall]]],
) -> None:
    """Split a Text node at newlines and pipes, distributing into rows/cells."""
    remaining = text_node.value
    while remaining:
        nl = remaining.find("\n")
        pipe = remaining.find("|")
        if nl == -1 and pipe == -1:
            if remaining:
                rows[-1][-1].append(Text(remaining, text_node.span))
            break
        elif nl >= 0 and (pipe == -1 or nl < pipe):
            before = remaining[:nl]
            if before:
                rows[-1][-1].append(Text(before, text_node.span))
            rows.append([[]])
            remaining = remaining[nl + 1 :]
        else:
            before = remaining[:pipe]
            if before:
                rows[-1][-1].append(Text(before, text_node.span))
            rows[-1].append([])
            remaining = remaining[pipe + 1 :]


def _trim_cell(cell: list[Text | Escape | MacroCall]) -> None:
    """Strip leading/trailing whitespace from Text nodes at cell boundaries."""
    # Trim leading
    while cell and isinstance(cell[0], Text):
        stripped = cell[0].value.lstrip()
        if stripped:
            cell[0] = Text(stripped, cell[0].span)
            break
        else:
            cell.pop(0)
    # Trim trailing
    while cell and isinstance(cell[-1], Text):
        stripped = cell[-1].value.rstrip()
        if stripped:
            cell[-1] = Text(stripped, cell[-1].span)
            break
        else:
            cell.pop()
