"""PicoDoc markup language compiler."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from picodoc.filters import FilterRegistry

__version__ = "0.1.0"


def compile(
    source: str,
    filename: str = "input.pdoc",
    env: dict[str, str] | None = None,
    filters: FilterRegistry | None = None,
) -> str:
    """Parse, evaluate, and render PicoDoc source to HTML."""
    from picodoc.eval import evaluate
    from picodoc.parser import parse
    from picodoc.render import render

    doc = parse(source, filename)
    doc = evaluate(doc, filename, env=env, filters=filters)
    return render(doc)
