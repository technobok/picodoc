"""Two-pass AST evaluator — collects #set definitions, expands builtins and user macros."""

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
    NamedArg,
    Paragraph,
    RawString,
    RequiredMarker,
    Text,
)
from picodoc.builtins import BUILTINS, resolve_name
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
    call_stack: list[str] = field(default_factory=list)
    max_call_depth: int = 64
    env: dict[str, str] = field(default_factory=dict)


def evaluate(
    doc: Document,
    filename: str = "input.pdoc",
    env: dict[str, str] | None = None,
) -> Document:
    """Expand expansion-time builtins, collect #set, wrap paragraphs."""
    source_dir = Path(filename).parent
    if not source_dir.parts:
        source_dir = Path(".")
    ctx = EvalContext(
        filename=filename,
        source_dir=source_dir,
        include_stack=[str(Path(filename).resolve())],
    )
    if env:
        ctx.env.update(env)
    _collect_definitions(doc.children, ctx)
    expanded = _expand_top_level(doc.children, ctx)
    # Filter to MacroCall nodes — Text/Escape from conditionals are whitespace
    children = tuple(c for c in expanded if isinstance(c, MacroCall))
    result = Document(children, doc.span)
    _validate_nesting(result)
    return result


# ---------------------------------------------------------------------------
# Post-expansion nesting validation
# ---------------------------------------------------------------------------

# child (resolved name) → set of allowed parent names
_NESTING_RULES: dict[str, set[str]] = {
    "tr": {"table"},
    "td": {"tr"},
    "th": {"tr"},
    "*": {"ul", "ol"},
}


def _validate_nesting(doc: Document) -> None:
    """Validate that macro nesting is structurally correct after expansion."""
    for child in doc.children:
        if isinstance(child, MacroCall):
            _validate_node(child, parent_name=None)


def _validate_node(node: MacroCall, parent_name: str | None) -> None:
    name = resolve_name(node.name)
    if name in _NESTING_RULES:
        allowed = _NESTING_RULES[name]
        if parent_name not in allowed:
            allowed_str = " or ".join(f"#{p}" for p in sorted(allowed))
            raise EvalError(
                f"#{node.name} must appear inside {allowed_str}",
                node.span,
                "",
            )
    if isinstance(node.body, Body):
        for child in node.body.children:
            if isinstance(child, MacroCall):
                _validate_node(child, parent_name=name)


# ---------------------------------------------------------------------------
# Pass 1: Definition collection
# ---------------------------------------------------------------------------


def _collect_definitions(
    children: tuple[MacroCall | Paragraph, ...],
    ctx: EvalContext,
) -> None:
    """Scan top-level #set definitions for out-of-order resolution."""
    for child in children:
        if not isinstance(child, MacroCall):
            continue
        name = resolve_name(child.name)
        if name != "set":
            continue
        name_val = _get_arg(child, "name")
        if name_val is None:
            continue
        def_name = _resolve_value(name_val, ctx)
        if def_name in ctx.definitions:
            raise EvalError(
                f"duplicate definition: {def_name}",
                child.span,
                "",
            )
        ctx.definitions[def_name] = child
        if def_name.startswith("env."):
            ctx.env[def_name[4:]] = _extract_def_text(child)


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

    if name.startswith("env."):
        env_key = name[4:]
        if env_key in ctx.env:
            return [Text(ctx.env[env_key], node.span)]
        return []

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

    # User macro expansion
    if name in ctx.definitions and name not in BUILTINS:
        return _expand_user_macro(node, name, ctx)

    # Trailing dot: #version. → expand "version" + Text(".")
    if name.endswith(".") and name[:-1] in ctx.definitions and name[:-1] not in BUILTINS:
        expanded = _expand_user_macro(node, name[:-1], ctx)
        expanded.append(Text(".", node.span))
        return expanded

    # Render-time macro: resolve args and recurse into body
    new_args = _resolve_macro_args(node.args, ctx)
    new_body = _recurse_body(node.body, ctx)
    return [MacroCall(node.name, new_args, new_body, node.bracketed, node.span)]


def _recurse_body(
    body: Body | InterpString | RawString | None,
    ctx: EvalContext,
) -> Body | InterpString | RawString | None:
    if body is None:
        return None
    if isinstance(body, Body):
        expanded = _expand_body_children(body.children, ctx)
        return Body(tuple(expanded), body.span)
    if isinstance(body, InterpString):
        return _expand_interp_string(body, ctx)
    # RawString: no expansion needed
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
# User macro expansion
# ---------------------------------------------------------------------------


def _expand_user_macro(
    node: MacroCall,
    name: str,
    ctx: EvalContext,
) -> list[MacroCall | Text | Escape]:
    """Expand a user-defined macro call."""
    defn = ctx.definitions[name]

    # Extract param declarations (skip name=)
    params: dict[str, tuple[bool, Text | InterpString | RawString | MacroCall | None]] = {}
    for arg in defn.args:
        if arg.name == "name":
            continue
        if isinstance(arg.value, RequiredMarker):
            params[arg.name] = (True, None)
        else:
            params[arg.name] = (False, arg.value)

    # Bind call-site args to params
    bindings: dict[str, list[Text | Escape | MacroCall]] = {}
    for arg in node.args:
        if arg.name in params:
            bindings[arg.name] = _value_to_body_children(arg.value, node.span)

    # Body binding
    if "body" in params and "body" not in bindings and node.body is not None:
        bindings["body"] = _body_to_children(node.body, node.span)

    # Defaults for unbound params
    for param_name, (required, default) in params.items():
        if param_name not in bindings:
            if required:
                raise EvalError(
                    f"missing required argument: {param_name}",
                    node.span,
                    "",
                    call_stack=list(ctx.call_stack),
                )
            if default is not None:
                bindings[param_name] = _value_to_body_children(default, node.span)
            else:
                bindings[param_name] = []

    # Recursion check
    if len(ctx.call_stack) >= ctx.max_call_depth:
        raise EvalError(
            f"macro call depth limit ({ctx.max_call_depth}) exceeded",
            node.span,
            "",
            call_stack=list(ctx.call_stack),
        )

    ctx.call_stack.append(name)
    try:
        # Resolve bindings (expand macro refs in bound values before shadowing)
        resolved_bindings: dict[str, list[Text | Escape | MacroCall]] = {}
        for param_name, raw_values in bindings.items():
            resolved_bindings[param_name] = _expand_body_children(tuple(raw_values), ctx)

        # Scope shadowing: temporarily inject param bindings as definitions
        saved: dict[str, MacroCall] = {}
        shadowed_names: list[str] = []
        for param_name, value in resolved_bindings.items():
            if param_name.startswith("env."):
                raise EvalError(
                    f"cannot shadow environment variable: {param_name}",
                    node.span,
                    "",
                    call_stack=list(ctx.call_stack),
                )
            if param_name in ctx.definitions:
                saved[param_name] = ctx.definitions[param_name]
            body = Body(tuple(value), node.span)
            synthetic = MacroCall(
                "set",
                (NamedArg("name", Text(param_name, node.span), node.span, node.span),),
                body,
                True,
                node.span,
            )
            ctx.definitions[param_name] = synthetic
            shadowed_names.append(param_name)

        try:
            # Expand definition body
            if isinstance(defn.body, Body):
                result = _expand_body_children(defn.body.children, ctx)
            elif isinstance(defn.body, InterpString):
                expanded_interp = _expand_interp_string(defn.body, ctx)
                result = _interp_to_children(expanded_interp)
            elif isinstance(defn.body, RawString):
                result = [Text(defn.body.value, defn.body.span)]
            else:
                result = []
        finally:
            # Restore definitions
            for param_name in shadowed_names:
                if param_name in saved:
                    ctx.definitions[param_name] = saved[param_name]
                else:
                    del ctx.definitions[param_name]
    finally:
        ctx.call_stack.pop()

    return result


def _value_to_body_children(
    value: Text | InterpString | RawString | MacroCall | RequiredMarker,
    span: Span,
) -> list[Text | Escape | MacroCall]:
    """Convert an argument value to body children."""
    if isinstance(value, (Text, Escape)):
        return [value]
    if isinstance(value, MacroCall):
        return [value]
    if isinstance(value, InterpString):
        return _interp_to_children(value)
    if isinstance(value, RawString):
        return [Text(value.value, span)]
    return []


def _body_to_children(
    body: Body | InterpString | RawString,
    span: Span,
) -> list[Text | Escape | MacroCall]:
    """Convert a body to a list of children."""
    if isinstance(body, Body):
        return list(body.children)
    if isinstance(body, InterpString):
        return _interp_to_children(body)
    if isinstance(body, RawString):
        return [Text(body.value, span)]
    return []


def _interp_to_children(
    interp: InterpString,
) -> list[Text | Escape | MacroCall]:
    """Flatten an InterpString to body children."""
    result: list[Text | Escape | MacroCall] = []
    for part in interp.parts:
        if isinstance(part, Text):
            result.append(part)
        elif isinstance(part, CodeSection):
            result.extend(part.body)
    return result


def _expand_interp_string(
    interp: InterpString,
    ctx: EvalContext,
) -> InterpString:
    """Expand code sections within an InterpString."""
    new_parts: list[Text | CodeSection] = []
    for part in interp.parts:
        if isinstance(part, CodeSection):
            expanded = _expand_body_children(part.body, ctx)
            new_parts.append(CodeSection(tuple(expanded), part.span))
        else:
            new_parts.append(part)
    return InterpString(tuple(new_parts), interp.span)


def _resolve_macro_args(
    args: tuple[NamedArg, ...],
    ctx: EvalContext,
) -> tuple[NamedArg, ...]:
    """Resolve macro references in argument values for render-time builtins."""
    new_args: list[NamedArg] = []
    for arg in args:
        if isinstance(arg.value, MacroCall):
            ref = resolve_name(arg.value.name)
            if ref.startswith("env."):
                text = ctx.env.get(ref[4:], "")
                new_value = Text(text, arg.value.span)
                new_args.append(NamedArg(arg.name, new_value, arg.name_span, arg.span))
                continue
            if ref in ctx.definitions:
                text = _extract_def_text(ctx.definitions[ref])
                new_value = Text(text, arg.value.span)
                new_args.append(NamedArg(arg.name, new_value, arg.name_span, arg.span))
                continue
        new_args.append(arg)
    return tuple(new_args)


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
                        if ref.startswith("env."):
                            parts.append(ctx.env.get(ref[4:], ""))
                        elif ref in ctx.definitions:
                            parts.append(_extract_def_text(ctx.definitions[ref]))
        return "".join(parts)
    if isinstance(value, MacroCall):
        ref = resolve_name(value.name)
        if ref.startswith("env."):
            return ctx.env.get(ref[4:], "")
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
    if name.startswith("env."):
        ctx.env[name[4:]] = _extract_def_text(node)
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
    if name.startswith("env."):
        if name[4:] in ctx.env:
            return _get_condition_body(node, ctx)
        return []
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
