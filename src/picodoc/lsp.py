"""LSP server for PicoDoc — diagnostics, go-to-definition, hover, completion."""

from __future__ import annotations

from lsprotocol.types import (
    TEXT_DOCUMENT_COMPLETION,
    TEXT_DOCUMENT_DEFINITION,
    TEXT_DOCUMENT_DID_CHANGE,
    TEXT_DOCUMENT_DID_OPEN,
    TEXT_DOCUMENT_HOVER,
    CompletionItem,
    CompletionItemKind,
    CompletionList,
    CompletionOptions,
    Diagnostic,
    DiagnosticSeverity,
    DidChangeTextDocumentParams,
    DidOpenTextDocumentParams,
    Hover,
    Location,
    MarkupContent,
    MarkupKind,
    Position,
    PublishDiagnosticsParams,
    Range,
    TextDocumentPositionParams,
    TextDocumentSyncKind,
)
from pygls.lsp.server import LanguageServer

from picodoc.ast import Document, MacroCall, Paragraph, RequiredMarker
from picodoc.builtins import ALIASES, BUILTINS, resolve_name
from picodoc.errors import EvalError, LexError, ParseError
from picodoc.eval import evaluate
from picodoc.parser import parse

server = LanguageServer(
    "picodoc-lsp",
    "0.1.0",
    text_document_sync_kind=TextDocumentSyncKind.Full,
)


# ---------------------------------------------------------------------------
# Shared analysis helpers
# ---------------------------------------------------------------------------


def _analyze(source: str, filename: str) -> tuple[Document | None, dict[str, MacroCall]]:
    """Parse source and collect user-defined macro definitions.

    Returns (ast, definitions).  If parsing fails, ast is None and definitions
    is empty — LSP must be resilient to broken documents.
    """
    try:
        ast = parse(source, filename)
    except (LexError, ParseError):
        return None, {}

    definitions: dict[str, MacroCall] = {}
    for child in ast.children:
        if not isinstance(child, MacroCall):
            continue
        if resolve_name(child.name) != "set":
            continue
        for arg in child.args:
            if arg.name == "name":
                from picodoc.ast import InterpString, RawString, Text

                if isinstance(arg.value, (Text, RawString)):
                    definitions[arg.value.value] = child
                elif isinstance(arg.value, InterpString):
                    # Simple case: all-text interp string
                    parts = []
                    for part in arg.value.parts:
                        if isinstance(part, Text):
                            parts.append(part.value)
                    if parts:
                        definitions["".join(parts)] = child
                break
    return ast, definitions


def _find_macro_at_position(source: str, ast: Document, line_0: int, col_0: int) -> str | None:
    """Find the macro name at the given 0-based cursor position.

    Walks the AST looking for MacroCall nodes whose name the cursor is on.
    Returns the resolved name, or None.
    """
    # Convert to 1-based for comparison with Span positions
    line_1 = line_0 + 1
    col_1 = col_0 + 1

    def _search(nodes: tuple[MacroCall | Paragraph | object, ...]) -> str | None:
        for node in nodes:
            if not isinstance(node, MacroCall):
                if isinstance(node, Paragraph):
                    result = _search_body(node.body)
                    if result is not None:
                        return result
                continue
            result = _check_macro(node)
            if result is not None:
                return result
        return None

    def _search_body(
        children: tuple[object, ...],
    ) -> str | None:
        for child in children:
            if isinstance(child, MacroCall):
                result = _check_macro(child)
                if result is not None:
                    return result
        return None

    def _check_macro(node: MacroCall) -> str | None:
        # A macro call like #name starts with # at span.start, then the name
        # follows immediately. The name occupies columns start.column to
        # start.column + len(name). The # is at start.column itself.
        # We consider the cursor "on the macro name" if it's on the # or
        # anywhere in the name text.
        start = node.span.start
        if start.line == line_1:
            # The # is at start.column, and the name runs from
            # start.column+1 to start.column+len(node.name).
            # For bracketed calls [#name ...], the [ is at start.column,
            # # is at start.column+1, name from start.column+2.
            hash_col = start.column + 1 if node.bracketed else start.column
            name_end_col = hash_col + len(node.name)  # exclusive
            if hash_col <= col_1 <= name_end_col:
                return node.name

        # Also recurse into body
        from picodoc.ast import Body

        if isinstance(node.body, Body):
            result = _search_body(node.body.children)
            if result is not None:
                return result
        # Recurse into arg values that are macro calls
        for arg in node.args:
            if isinstance(arg.value, MacroCall):
                result = _check_macro(arg.value)
                if result is not None:
                    return result
        return None

    return _search(ast.children)


# ---------------------------------------------------------------------------
# Hover formatting helpers
# ---------------------------------------------------------------------------


def _format_builtin_hover(name: str) -> str:
    """Format hover markdown for a builtin macro."""
    defn = BUILTINS[name]
    lines: list[str] = [f"**#{defn.name}** (builtin)"]

    # Show aliases
    aliases = [alias for alias, canonical in ALIASES.items() if canonical == name]
    if aliases:
        alias_str = ", ".join(f"`#{a}`" for a in sorted(aliases))
        lines.append(f"\nAliases: {alias_str}")

    # Parameters
    if defn.params:
        lines.append("\nParameters:")
        for p in defn.params:
            req = "required" if p.required else "optional"
            lines.append(f"- `{p.name}` ({req})")

    # Body
    if defn.has_body:
        lines.append("\nAccepts body content.")

    return "\n".join(lines)


def _format_user_hover(name: str, defn: MacroCall) -> str:
    """Format hover markdown for a user-defined macro."""
    lines: list[str] = [f"**#{name}** (user-defined)"]

    # Show parameters (skip name= arg)
    params: list[str] = []
    for arg in defn.args:
        if arg.name == "name":
            continue
        if isinstance(arg.value, RequiredMarker):
            params.append(f"`{arg.name}` (required)")
        else:
            params.append(f"`{arg.name}` (optional)")

    if params:
        lines.append("\nParameters:")
        for p in params:
            lines.append(f"- {p}")

    if defn.body is not None:
        lines.append("\nHas body content.")

    # Show definition location
    loc = defn.span.start
    lines.append(f"\nDefined at line {loc.line}, column {loc.column}.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------


def _validate(ls: LanguageServer, uri: str) -> None:
    """Run the PicoDoc pipeline and publish diagnostics."""
    doc = ls.workspace.get_text_document(uri)
    source = doc.source
    filename = uri.rsplit("/", 1)[-1] if "/" in uri else uri
    diagnostics: list[Diagnostic] = []

    try:
        ast = parse(source, filename)
    except LexError as exc:
        line = exc.position.line - 1
        col = exc.position.column - 1
        diagnostics.append(
            Diagnostic(
                range=Range(
                    start=Position(line=line, character=col),
                    end=Position(line=line, character=col + 1),
                ),
                message=exc.message,
                severity=DiagnosticSeverity.Error,
                source="picodoc",
            )
        )
    except ParseError as exc:
        start_line = exc.span.start.line - 1
        start_col = exc.span.start.column - 1
        end_line = exc.span.end.line - 1
        end_col = exc.span.end.column - 1
        diagnostics.append(
            Diagnostic(
                range=Range(
                    start=Position(line=start_line, character=start_col),
                    end=Position(line=end_line, character=end_col),
                ),
                message=exc.message,
                severity=DiagnosticSeverity.Error,
                source="picodoc",
            )
        )
    else:
        try:
            evaluate(ast, filename)
        except EvalError as exc:
            start_line = exc.span.start.line - 1
            start_col = exc.span.start.column - 1
            end_line = exc.span.end.line - 1
            end_col = exc.span.end.column - 1
            message = exc.message
            if exc.call_stack:
                chain = " -> ".join(f"#{name}" for name in exc.call_stack)
                message += f" (in expansion: {chain})"
            diagnostics.append(
                Diagnostic(
                    range=Range(
                        start=Position(line=start_line, character=start_col),
                        end=Position(line=end_line, character=end_col),
                    ),
                    message=message,
                    severity=DiagnosticSeverity.Warning,
                    source="picodoc",
                )
            )

    ls.text_document_publish_diagnostics(
        PublishDiagnosticsParams(uri=uri, diagnostics=diagnostics)
    )


# ---------------------------------------------------------------------------
# Document sync
# ---------------------------------------------------------------------------


@server.feature(TEXT_DOCUMENT_DID_OPEN)
def did_open(ls: LanguageServer, params: DidOpenTextDocumentParams) -> None:
    _validate(ls, params.text_document.uri)


@server.feature(TEXT_DOCUMENT_DID_CHANGE)
def did_change(ls: LanguageServer, params: DidChangeTextDocumentParams) -> None:
    _validate(ls, params.text_document.uri)


# ---------------------------------------------------------------------------
# Go-to-definition
# ---------------------------------------------------------------------------


@server.feature(TEXT_DOCUMENT_DEFINITION)
def goto_definition(ls: LanguageServer, params: TextDocumentPositionParams) -> Location | None:
    uri = params.text_document.uri
    doc = ls.workspace.get_text_document(uri)
    source = doc.source
    filename = uri.rsplit("/", 1)[-1] if "/" in uri else uri

    ast, definitions = _analyze(source, filename)
    if ast is None:
        return None

    name = _find_macro_at_position(source, ast, params.position.line, params.position.character)
    if name is None:
        return None

    resolved = resolve_name(name)
    defn = definitions.get(resolved)
    if defn is None:
        return None

    start = defn.span.start
    end = defn.span.end
    return Location(
        uri=uri,
        range=Range(
            start=Position(line=start.line - 1, character=start.column - 1),
            end=Position(line=end.line - 1, character=end.column - 1),
        ),
    )


# ---------------------------------------------------------------------------
# Hover
# ---------------------------------------------------------------------------


@server.feature(TEXT_DOCUMENT_HOVER)
def hover(ls: LanguageServer, params: TextDocumentPositionParams) -> Hover | None:
    uri = params.text_document.uri
    doc = ls.workspace.get_text_document(uri)
    source = doc.source
    filename = uri.rsplit("/", 1)[-1] if "/" in uri else uri

    ast, definitions = _analyze(source, filename)
    if ast is None:
        return None

    name = _find_macro_at_position(source, ast, params.position.line, params.position.character)
    if name is None:
        return None

    resolved = resolve_name(name)

    if resolved in BUILTINS:
        md = _format_builtin_hover(resolved)
    elif resolved in definitions:
        md = _format_user_hover(resolved, definitions[resolved])
    else:
        return None

    return Hover(contents=MarkupContent(kind=MarkupKind.Markdown, value=md))


# ---------------------------------------------------------------------------
# Completion
# ---------------------------------------------------------------------------


@server.feature(
    TEXT_DOCUMENT_COMPLETION,
    CompletionOptions(trigger_characters=["#"]),
)
def completion(ls: LanguageServer, params: TextDocumentPositionParams) -> CompletionList:
    uri = params.text_document.uri
    doc = ls.workspace.get_text_document(uri)
    source = doc.source
    filename = uri.rsplit("/", 1)[-1] if "/" in uri else uri

    _, definitions = _analyze(source, filename)

    items: list[CompletionItem] = []

    # Builtin macros
    for name, defn in sorted(BUILTINS.items()):
        params_str = ", ".join(f"{p.name}{'?' if not p.required else ''}" for p in defn.params)
        detail = f"builtin({params_str})" if params_str else "builtin"
        if defn.has_body:
            detail += " +body"
        items.append(
            CompletionItem(
                label=f"#{name}",
                kind=CompletionItemKind.Function,
                detail=detail,
            )
        )

    # Aliases
    for alias, canonical in sorted(ALIASES.items()):
        items.append(
            CompletionItem(
                label=f"#{alias}",
                kind=CompletionItemKind.Reference,
                detail=f"alias for #{canonical}",
            )
        )

    # User-defined macros
    for name, defn in sorted(definitions.items()):
        params_list: list[str] = []
        for arg in defn.args:
            if arg.name == "name":
                continue
            if isinstance(arg.value, RequiredMarker):
                params_list.append(arg.name)
            else:
                params_list.append(f"{arg.name}?")
        params_str = ", ".join(params_list)
        detail = f"user({params_str})" if params_str else "user"
        items.append(
            CompletionItem(
                label=f"#{name}",
                kind=CompletionItemKind.Variable,
                detail=detail,
            )
        )

    return CompletionList(is_incomplete=False, items=items)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    server.start_io()
