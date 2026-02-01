"""Tests for the LSP server — diagnostic generation."""

from __future__ import annotations

import pytest
from lsprotocol.types import (
    DiagnosticSeverity,
    PublishDiagnosticsParams,
    TextDocumentItem,
    TextDocumentSyncKind,
)
from pygls.lsp.server import LanguageServer
from pygls.workspace import Workspace

from picodoc.lsp import _validate


@pytest.fixture
def lsp_env():
    """Create a LanguageServer with an initialized workspace and captured diagnostics."""
    ls = LanguageServer("test", "v0", text_document_sync_kind=TextDocumentSyncKind.Full)
    ws = Workspace(None)
    ls.protocol._workspace = ws

    published: list[PublishDiagnosticsParams] = []
    ls.text_document_publish_diagnostics = lambda params: published.append(params)

    def put(source: str, uri: str = "file:///test.pdoc") -> None:
        ws.put_text_document(
            TextDocumentItem(uri=uri, language_id="picodoc", version=0, text=source)
        )

    return ls, published, put


# ---------------------------------------------------------------------------
# Lex errors → Error severity
# ---------------------------------------------------------------------------


class TestLexErrors:
    def test_invalid_escape(self, lsp_env) -> None:
        ls, published, put = lsp_env
        put(r"Hello \z world")
        _validate(ls, "file:///test.pdoc")

        assert len(published) == 1
        diags = published[0].diagnostics
        assert len(diags) == 1
        d = diags[0]
        assert d.severity == DiagnosticSeverity.Error
        assert "\\z" in d.message
        assert d.source == "picodoc"
        # \z is at column 7 (1-based) → character 6 (0-based)
        assert d.range.start.line == 0
        assert d.range.start.character == 6


# ---------------------------------------------------------------------------
# Parse errors → Error severity
# ---------------------------------------------------------------------------


class TestParseErrors:
    def test_unclosed_bracket(self, lsp_env) -> None:
        ls, published, put = lsp_env
        put("[#b: hello")
        _validate(ls, "file:///test.pdoc")

        assert len(published) == 1
        diags = published[0].diagnostics
        assert len(diags) == 1
        d = diags[0]
        assert d.severity == DiagnosticSeverity.Error
        assert "closing" in d.message.lower() or "]" in d.message
        assert d.source == "picodoc"


# ---------------------------------------------------------------------------
# Eval errors → Warning severity
# ---------------------------------------------------------------------------


class TestEvalErrors:
    def test_nesting_violation(self, lsp_env) -> None:
        ls, published, put = lsp_env
        put("#td: hello")
        _validate(ls, "file:///test.pdoc")

        assert len(published) == 1
        diags = published[0].diagnostics
        assert len(diags) == 1
        d = diags[0]
        assert d.severity == DiagnosticSeverity.Warning
        assert "td" in d.message.lower() or "tr" in d.message.lower()
        assert d.source == "picodoc"


# ---------------------------------------------------------------------------
# Clean document → empty diagnostics
# ---------------------------------------------------------------------------


class TestCleanDocument:
    def test_valid_document(self, lsp_env) -> None:
        ls, published, put = lsp_env
        put("#title: Hello World\n\nSome body text.")
        _validate(ls, "file:///test.pdoc")

        assert len(published) == 1
        assert published[0].diagnostics == []


# ---------------------------------------------------------------------------
# Position conversion (1-based → 0-based)
# ---------------------------------------------------------------------------


class TestPositionConversion:
    def test_error_on_second_line(self, lsp_env) -> None:
        ls, published, put = lsp_env
        put("Valid first line\n\\z oops")
        _validate(ls, "file:///test.pdoc")

        assert len(published) == 1
        diags = published[0].diagnostics
        assert len(diags) == 1
        d = diags[0]
        # Error is on line 2 (1-based) → LSP line 1 (0-based)
        assert d.range.start.line == 1
        assert d.range.start.character == 0
