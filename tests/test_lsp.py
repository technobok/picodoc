"""Tests for the LSP server — diagnostics, go-to-definition, hover, completion."""

from __future__ import annotations

import pytest
from lsprotocol.types import (
    CompletionItemKind,
    DiagnosticSeverity,
    MarkupKind,
    Position,
    PublishDiagnosticsParams,
    TextDocumentIdentifier,
    TextDocumentItem,
    TextDocumentPositionParams,
    TextDocumentSyncKind,
)
from pygls.lsp.server import LanguageServer
from pygls.workspace import Workspace

from picodoc.lsp import (
    _analyze,
    _find_macro_at_position,
    _validate,
    completion,
    goto_definition,
    hover,
)


@pytest.fixture
def lsp_env():
    """Create a LanguageServer with an initialized workspace and captured diagnostics."""
    ls = LanguageServer("test", "v0", text_document_sync_kind=TextDocumentSyncKind.Full)
    ws = Workspace(None)
    ls.protocol._workspace = ws

    published: list[PublishDiagnosticsParams] = []

    def capture_diagnostics(params: PublishDiagnosticsParams) -> None:
        published.append(params)

    ls.text_document_publish_diagnostics = capture_diagnostics  # type: ignore[assignment]

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
        put("#doc.title: Hello World\n\nSome body text.")
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


# ---------------------------------------------------------------------------
# Shared analysis helpers
# ---------------------------------------------------------------------------


URI = "file:///test.pdoc"


def _make_params(line: int, character: int) -> TextDocumentPositionParams:
    return TextDocumentPositionParams(
        text_document=TextDocumentIdentifier(uri=URI),
        position=Position(line=line, character=character),
    )


class TestAnalyze:
    def test_collects_set_definitions(self) -> None:
        source = "#set name=greeting: Hello\n#doc.title: #greeting"
        ast, defs = _analyze(source, "test.pdoc")
        assert ast is not None
        assert "greeting" in defs

    def test_handles_lex_error(self) -> None:
        source = r"Hello \z world"
        ast, defs = _analyze(source, "test.pdoc")
        assert ast is None
        assert defs == {}

    def test_handles_parse_error(self) -> None:
        source = "[#b: hello"
        ast, defs = _analyze(source, "test.pdoc")
        assert ast is None
        assert defs == {}


class TestFindMacroAtPosition:
    def test_finds_macro_on_hash(self) -> None:
        source = "#doc.title: Hello"
        ast, _ = _analyze(source, "test.pdoc")
        assert ast is not None
        # cursor on #  (line 0, col 0 in 0-based)
        name = _find_macro_at_position(source, ast, 0, 0)
        assert name == "doc.title"

    def test_finds_macro_on_name(self) -> None:
        source = "#doc.title: Hello"
        ast, _ = _analyze(source, "test.pdoc")
        assert ast is not None
        # cursor on 't' of title (col 5 in 0-based)
        name = _find_macro_at_position(source, ast, 0, 5)
        assert name == "doc.title"

    def test_returns_none_off_macro(self) -> None:
        source = "#doc.title: Hello"
        ast, _ = _analyze(source, "test.pdoc")
        assert ast is not None
        # cursor on 'H' in body (col 12 in 0-based)
        name = _find_macro_at_position(source, ast, 0, 12)
        assert name is None

    def test_finds_bracketed_macro(self) -> None:
        source = "#p: [#b: bold text]"
        ast, _ = _analyze(source, "test.pdoc")
        assert ast is not None
        # [#b is at cols 4,5,6 (0-based). # is at col 5, b at col 6
        name = _find_macro_at_position(source, ast, 0, 5)
        assert name == "b"


# ---------------------------------------------------------------------------
# Go-to-definition
# ---------------------------------------------------------------------------


class TestGotoDefinition:
    def test_jumps_to_set_definition(self, lsp_env) -> None:
        ls, _, put = lsp_env
        source = "#set name=greeting: Hello\n#doc.title: [#greeting]"
        put(source)

        # cursor on "greeting" in the second line's [#greeting]
        # #doc.title: [#greeting]
        # 0         1
        # 0123456789012345
        # line 1, col 14 (0-based) → on the 'g' of greeting
        params = _make_params(1, 14)
        result = goto_definition(ls, params)

        assert result is not None
        # Should point to the #set on line 0
        assert result.range.start.line == 0
        assert result.uri == URI

    def test_returns_none_for_builtin(self, lsp_env) -> None:
        ls, _, put = lsp_env
        put("#doc.title: Hello")
        params = _make_params(0, 0)
        result = goto_definition(ls, params)
        assert result is None

    def test_returns_none_for_no_macro(self, lsp_env) -> None:
        ls, _, put = lsp_env
        put("#doc.title: Hello")
        # cursor on body text
        params = _make_params(0, 14)
        result = goto_definition(ls, params)
        assert result is None

    def test_returns_none_for_broken_document(self, lsp_env) -> None:
        ls, _, put = lsp_env
        put("[#b: unclosed")
        params = _make_params(0, 1)
        result = goto_definition(ls, params)
        assert result is None


# ---------------------------------------------------------------------------
# Hover
# ---------------------------------------------------------------------------


class TestHover:
    def test_hover_builtin(self, lsp_env) -> None:
        ls, _, put = lsp_env
        put("#doc.title: Hello")
        params = _make_params(0, 1)
        result = hover(ls, params)

        assert result is not None
        assert result.contents.kind == MarkupKind.Markdown
        assert "#doc.title" in result.contents.value
        assert "builtin" in result.contents.value

    def test_hover_builtin_with_params(self, lsp_env) -> None:
        ls, _, put = lsp_env
        put("#link to=https://example.com: click")
        params = _make_params(0, 1)
        result = hover(ls, params)

        assert result is not None
        assert "to" in result.contents.value
        assert "optional" in result.contents.value

    def test_hover_alternate(self, lsp_env) -> None:
        ls, _, put = lsp_env
        # #h1 is alternate form of #-
        put("#h1: Hello")
        params = _make_params(0, 0)
        result = hover(ls, params)

        assert result is not None
        assert "#-" in result.contents.value
        assert "builtin" in result.contents.value

    def test_hover_user_macro(self, lsp_env) -> None:
        ls, _, put = lsp_env
        source = "#set name=greeting: Hello\n#doc.title: [#greeting]"
        put(source)
        # cursor on #greeting, line 1
        params = _make_params(1, 14)
        result = hover(ls, params)

        assert result is not None
        assert "greeting" in result.contents.value
        assert "user-defined" in result.contents.value

    def test_hover_returns_none_off_macro(self, lsp_env) -> None:
        ls, _, put = lsp_env
        put("#doc.title: Hello")
        params = _make_params(0, 14)
        result = hover(ls, params)
        assert result is None

    def test_hover_returns_none_broken_doc(self, lsp_env) -> None:
        ls, _, put = lsp_env
        put("[#b: unclosed")
        params = _make_params(0, 1)
        result = hover(ls, params)
        assert result is None


# ---------------------------------------------------------------------------
# Completion
# ---------------------------------------------------------------------------


class TestCompletion:
    def test_includes_builtins(self, lsp_env) -> None:
        ls, _, put = lsp_env
        put("#")
        params = _make_params(0, 1)
        result = completion(ls, params)

        labels = [item.label for item in result.items]
        assert "#doc.title" in labels
        assert "#**" in labels
        assert "#set" in labels

    def test_includes_alternates(self, lsp_env) -> None:
        ls, _, put = lsp_env
        put("#")
        params = _make_params(0, 1)
        result = completion(ls, params)

        labels = [item.label for item in result.items]
        assert "#h1" in labels  # alternate for #-
        assert "#b" in labels  # alternate for #**

        # Check alternate detail
        alt_items = [i for i in result.items if i.label == "#h1"]
        assert len(alt_items) == 1
        assert "same as #-" in alt_items[0].detail

    def test_includes_user_macros(self, lsp_env) -> None:
        ls, _, put = lsp_env
        put("#set name=greeting: Hello\n#doc.title: world")
        params = _make_params(1, 1)
        result = completion(ls, params)

        labels = [item.label for item in result.items]
        assert "#greeting" in labels

        user_items = [i for i in result.items if i.label == "#greeting"]
        assert len(user_items) == 1
        assert user_items[0].kind == CompletionItemKind.Variable

    def test_builtin_detail_shows_params(self, lsp_env) -> None:
        ls, _, put = lsp_env
        put("#")
        params = _make_params(0, 1)
        result = completion(ls, params)

        link_items = [i for i in result.items if i.label == "#>"]
        assert len(link_items) == 1
        assert "to" in link_items[0].detail
        assert "builtin" in link_items[0].detail

    def test_completion_not_incomplete(self, lsp_env) -> None:
        ls, _, put = lsp_env
        put("#")
        params = _make_params(0, 1)
        result = completion(ls, params)
        assert result.is_incomplete is False

    def test_user_macro_with_params(self, lsp_env) -> None:
        ls, _, put = lsp_env
        put("#set name=greet who=?: Hello [#who]!\n#doc.title: hi")
        params = _make_params(1, 1)
        result = completion(ls, params)

        greet_items = [i for i in result.items if i.label == "#greet"]
        assert len(greet_items) == 1
        assert "who" in greet_items[0].detail
        assert "user" in greet_items[0].detail
