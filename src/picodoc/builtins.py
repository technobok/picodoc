"""Builtin macro registry — alias resolution and parameter declarations."""

from __future__ import annotations

from dataclasses import dataclass

# Alias map: alternate name -> canonical name
ALIASES: dict[str, str] = {
    "-": "h1",
    "--": "h2",
    "---": "h3",
    "----": "h4",
    "-----": "h5",
    "------": "h6",
    "//": "comment",
    ">": "link",
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
    expansion_time: bool = False  # True = cannot be shadowed by user macros


def _make_builtins() -> dict[str, BuiltinDef]:
    defs: dict[str, BuiltinDef] = {}

    def d(
        name: str,
        params: tuple[ParamDecl, ...] = (),
        *,
        has_body: bool = False,
        expansion_time: bool = False,
    ) -> None:
        defs[name] = BuiltinDef(name, params, has_body, expansion_time)

    # Structural
    d("h1", has_body=True)
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
    d("*_", has_body=True)
    d("_*", has_body=True)
    d("link", (ParamDecl("to", False),), has_body=True)

    # Code / literal
    d("code", (ParamDecl("language", False),), has_body=True)
    d("~", (ParamDecl("language", False),), has_body=True)
    d("literal", has_body=True)

    # Lists
    d("ul", has_body=True)
    d("ol", has_body=True)
    d("*", has_body=True)

    # Tables
    d("table", (ParamDecl("cols", False),), has_body=True, expansion_time=True)
    d("tr", has_body=True)
    d("td", (ParamDecl("span", False),), has_body=True)
    d("th", (ParamDecl("span", False),), has_body=True)

    # Wrapper / container
    d("div", (ParamDecl("class", False), ParamDecl("id", False)), has_body=True)
    d("section", (ParamDecl("class", False), ParamDecl("id", False)), has_body=True)
    d("span", (ParamDecl("class", False), ParamDecl("id", False)), has_body=True)
    d("nav", (ParamDecl("class", False), ParamDecl("id", False)), has_body=True)
    d("header", (ParamDecl("class", False), ParamDecl("id", False)), has_body=True)
    d("footer", (ParamDecl("class", False), ParamDecl("id", False)), has_body=True)
    d("main", (ParamDecl("class", False), ParamDecl("id", False)), has_body=True)
    d("article", (ParamDecl("class", False), ParamDecl("id", False)), has_body=True)
    d("aside", (ParamDecl("class", False), ParamDecl("id", False)), has_body=True)

    # Document
    d(
        "doc.meta",
        (ParamDecl("name", False), ParamDecl("property", False), ParamDecl("content", True)),
    )
    d(
        "doc.link",
        (
            ParamDecl("rel", True),
            ParamDecl("href", True),
            ParamDecl("type", False),
            ParamDecl("sizes", False),
        ),
    )
    d("doc.script", (ParamDecl("src", False), ParamDecl("type", False)), has_body=True)
    d("doc.title", has_body=True)
    d("doc.lang", has_body=True)
    d("doc.author", has_body=True)
    d("doc.version", has_body=True)
    d("doc.datecreated", has_body=True)
    d("doc.datemodified", has_body=True)
    d(
        "doc.content",
        (
            ParamDecl("type", True),
            ParamDecl("class", False),
            ParamDecl("id", False),
        ),
    )
    d("doc.body", (ParamDecl("class", False), ParamDecl("id", False)))
    d("doc.toc", (ParamDecl("level", False),))
    d("doc.heading.number", (ParamDecl("level", False),))
    d("doc.heading.anchor", (ParamDecl("level", False),))

    # Expansion-time
    d("comment", has_body=True, expansion_time=True)
    d("set", (ParamDecl("name", True),), has_body=True, expansion_time=True)
    d("ifeq", (ParamDecl("lhs", True), ParamDecl("rhs", True)), has_body=True, expansion_time=True)
    d("ifne", (ParamDecl("lhs", True), ParamDecl("rhs", True)), has_body=True, expansion_time=True)
    d("ifset", (ParamDecl("name", True),), has_body=True, expansion_time=True)
    d("include", (ParamDecl("literal", False),), has_body=True, expansion_time=True)

    return defs


BUILTINS: dict[str, BuiltinDef] = _make_builtins()

WRAPPER_TAGS: frozenset[str] = frozenset(
    {
        "div",
        "section",
        "span",
        "nav",
        "header",
        "footer",
        "main",
        "article",
        "aside",
    }
)

BLOCK_MACROS: frozenset[str] = frozenset(
    {
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "p",
        "hr",
        "ul",
        "ol",
        "table",
        "div",
        "section",
        "nav",
        "header",
        "footer",
        "main",
        "article",
        "aside",
        "code",
    }
)
