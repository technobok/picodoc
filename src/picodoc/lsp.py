"""Minimal LSP server for PicoDoc — diagnostics only."""

from __future__ import annotations

from lsprotocol.types import (
    TEXT_DOCUMENT_DID_CHANGE,
    TEXT_DOCUMENT_DID_OPEN,
    Diagnostic,
    DiagnosticSeverity,
    DidChangeTextDocumentParams,
    DidOpenTextDocumentParams,
    Position,
    PublishDiagnosticsParams,
    Range,
    TextDocumentSyncKind,
)
from pygls.lsp.server import LanguageServer

from picodoc.errors import EvalError, LexError, ParseError
from picodoc.eval import evaluate
from picodoc.parser import parse

server = LanguageServer("picodoc-lsp", "0.1.0", text_document_sync_kind=TextDocumentSyncKind.Full)


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


@server.feature(TEXT_DOCUMENT_DID_OPEN)
def did_open(ls: LanguageServer, params: DidOpenTextDocumentParams) -> None:
    _validate(ls, params.text_document.uri)


@server.feature(TEXT_DOCUMENT_DID_CHANGE)
def did_change(ls: LanguageServer, params: DidChangeTextDocumentParams) -> None:
    _validate(ls, params.text_document.uri)


def main() -> None:
    server.start_io()
