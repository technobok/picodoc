"""AST node types for PicoDoc parsed documents."""

from __future__ import annotations

from dataclasses import dataclass

from picodoc.tokens import Span


@dataclass(frozen=True, slots=True)
class Text:
    """Coalesced text content."""

    value: str
    span: Span


@dataclass(frozen=True, slots=True)
class Escape:
    """Resolved prose escape character."""

    value: str
    span: Span


@dataclass(frozen=True, slots=True)
class RawString:
    """Raw string literal (no escape processing)."""

    value: str
    span: Span


@dataclass(frozen=True, slots=True)
class RequiredMarker:
    """The '?' token in #set parameter definitions."""

    span: Span


@dataclass(frozen=True, slots=True)
class CodeSection:
    """Code mode section \\[...] inside an interpreted string."""

    body: tuple[Text | Escape | MacroCall, ...]
    span: Span


@dataclass(frozen=True, slots=True)
class InterpString:
    """Interpreted string literal with possible code sections."""

    parts: tuple[Text | CodeSection, ...]
    span: Span


@dataclass(frozen=True, slots=True)
class NamedArg:
    """Named argument: name=value."""

    name: str
    value: Text | InterpString | RawString | MacroCall | RequiredMarker
    name_span: Span
    span: Span


@dataclass(frozen=True, slots=True)
class Body:
    """Body content for macro calls (colon-delimited)."""

    children: tuple[Text | Escape | MacroCall, ...]
    span: Span


@dataclass(frozen=True, slots=True)
class MacroCall:
    """A macro invocation: #name or [#name ...]."""

    name: str
    args: tuple[NamedArg, ...]
    body: Body | InterpString | RawString | None
    bracketed: bool
    span: Span


@dataclass(frozen=True, slots=True)
class Paragraph:
    """Bare paragraph — evaluator wraps in implicit #p."""

    body: tuple[Text | Escape | MacroCall, ...]
    span: Span


@dataclass(frozen=True, slots=True)
class Document:
    """Root document node."""

    children: tuple[MacroCall | Paragraph, ...]
    span: Span
