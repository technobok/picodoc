"""Builtin macro registry — alias resolution and parameter declarations."""

from __future__ import annotations

from dataclasses import dataclass

# Alias map: alternate name -> canonical name
ALIASES: dict[str, str] = {
    "-": "title",
    "h1": "title",
    "--": "h2",
    "---": "h3",
    "**": "b",
    "__": "i",
    "li": "*",
}


def resolve_name(name: str) -> str:
    """Resolve an alias to its canonical name."""
    return ALIASES.get(name, name)


@dataclass(frozen=True, slots=True)
class ParamDecl:
    """Parameter declaration for a builtin macro."""

    name: str
    required: bool


@dataclass(frozen=True, slots=True)
class BuiltinDef:
    """Definition of a builtin macro."""

    name: str
    params: tuple[ParamDecl, ...]
    has_body: bool


def _make_builtins() -> dict[str, BuiltinDef]:
    defs: dict[str, BuiltinDef] = {}

    def d(name: str, params: tuple[ParamDecl, ...] = (), *, has_body: bool = False) -> None:
        defs[name] = BuiltinDef(name, params, has_body)

    # Structural
    d("title", has_body=True)
    d("h2", has_body=True)
    d("h3", has_body=True)
    d("h4", has_body=True)
    d("h5", has_body=True)
    d("h6", has_body=True)
    d("p", has_body=True)
    d("hr")

    # Inline
    d("b", has_body=True)
    d("i", has_body=True)
    d("url", (ParamDecl("link", True), ParamDecl("text", False)), has_body=True)

    # Code / literal
    d("code", (ParamDecl("language", False),), has_body=True)
    d("literal", has_body=True)

    # Lists
    d("ul", has_body=True)
    d("ol", has_body=True)
    d("*", has_body=True)

    # Tables
    d("table", has_body=True)
    d("tr", has_body=True)
    d("td", (ParamDecl("span", False),), has_body=True)
    d("th", (ParamDecl("span", False),), has_body=True)

    # Document
    d("meta", (ParamDecl("name", False), ParamDecl("property", False), ParamDecl("content", True)))
    d("link", (ParamDecl("rel", True), ParamDecl("href", True)))
    d("script", (ParamDecl("src", False),), has_body=True)
    d("lang", has_body=True)

    # Expansion-time
    d("comment", has_body=True)
    d("set", (ParamDecl("name", True),), has_body=True)
    d("ifeq", (ParamDecl("lhs", True), ParamDecl("rhs", True)), has_body=True)
    d("ifne", (ParamDecl("lhs", True), ParamDecl("rhs", True)), has_body=True)
    d("ifset", (ParamDecl("name", True),), has_body=True)
    d("include", (ParamDecl("file", True),))

    return defs


BUILTINS: dict[str, BuiltinDef] = _make_builtins()
