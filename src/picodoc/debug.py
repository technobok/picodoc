"""--debug AST dump to stderr."""

from __future__ import annotations

import sys
from typing import TextIO

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


def dump_ast(doc: Document, *, file: TextIO = sys.stderr) -> None:
    """Print a human-readable AST tree to *file*."""
    _dump_document(doc, 0, file)


def _indent(depth: int) -> str:
    return "  " * depth


def _dump_document(doc: Document, depth: int, f: TextIO) -> None:
    f.write(f"{_indent(depth)}Document\n")
    for child in doc.children:
        if isinstance(child, MacroCall):
            _dump_macro(child, depth + 1, f)
        elif isinstance(child, Paragraph):
            _dump_paragraph(child, depth + 1, f)


def _dump_macro(node: MacroCall, depth: int, f: TextIO) -> None:
    bracket = "[#...]" if node.bracketed else "#"
    f.write(f"{_indent(depth)}MacroCall {bracket}{node.name}\n")
    for arg in node.args:
        _dump_arg(arg, depth + 1, f)
    if node.body is not None:
        _dump_body(node.body, depth + 1, f)


def _dump_arg(arg: NamedArg, depth: int, f: TextIO) -> None:
    f.write(f"{_indent(depth)}Arg {arg.name}=")
    _dump_value_inline(arg.value, f)
    f.write("\n")


def _dump_value_inline(
    value: Text | InterpString | RawString | MacroCall | RequiredMarker,
    f: TextIO,
) -> None:
    if isinstance(value, Text):
        f.write(f"Text({value.value!r})")
    elif isinstance(value, RawString):
        f.write(f"RawString({value.value!r})")
    elif isinstance(value, InterpString):
        f.write("InterpString(")
        for part in value.parts:
            if isinstance(part, Text):
                f.write(f"Text({part.value!r})")
            elif isinstance(part, CodeSection):
                f.write("Code[...]")
        f.write(")")
    elif isinstance(value, MacroCall):
        f.write(f"MacroCall(#{value.name})")
    elif isinstance(value, RequiredMarker):
        f.write("?")


def _dump_body(body: Body | InterpString | RawString, depth: int, f: TextIO) -> None:
    if isinstance(body, Body):
        f.write(f"{_indent(depth)}Body\n")
        for child in body.children:
            _dump_child(child, depth + 1, f)
    elif isinstance(body, InterpString):
        f.write(f"{_indent(depth)}InterpString\n")
        for part in body.parts:
            if isinstance(part, Text):
                f.write(f"{_indent(depth + 1)}Text({part.value!r})\n")
            elif isinstance(part, CodeSection):
                f.write(f"{_indent(depth + 1)}CodeSection\n")
                for child in part.body:
                    _dump_child(child, depth + 2, f)
    elif isinstance(body, RawString):
        f.write(f"{_indent(depth)}RawString({body.value!r})\n")


def _dump_child(child: Text | Escape | MacroCall, depth: int, f: TextIO) -> None:
    if isinstance(child, Text):
        f.write(f"{_indent(depth)}Text({child.value!r})\n")
    elif isinstance(child, Escape):
        f.write(f"{_indent(depth)}Escape({child.value!r})\n")
    elif isinstance(child, MacroCall):
        _dump_macro(child, depth, f)


def _dump_paragraph(para: Paragraph, depth: int, f: TextIO) -> None:
    f.write(f"{_indent(depth)}Paragraph\n")
    for child in para.body:
        _dump_child(child, depth + 1, f)
