"""Integration tests: parse + evaluate + render each example, compare to expected HTML."""

from __future__ import annotations

from pathlib import Path

import pytest

from picodoc.eval import evaluate
from picodoc.parser import parse
from picodoc.render import render

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"

PHASE3_EXAMPLES = [
    ("01-basic-document", "01-basic-document.pdoc", "01-basic-document.html"),
    ("02-inline-formatting", "02-inline-formatting.pdoc", "02-inline-formatting.html"),
    ("05-lists", "05-lists.pdoc", "05-lists.html"),
    ("06-tables", "06-tables.pdoc", "06-tables.html"),
    ("08-code-and-literal", "08-code-and-literal.pdoc", "08-code-and-literal.html"),
    ("09-escaping", "09-escaping.pdoc", "09-escaping.html"),
    ("10-document-meta", "10-document-meta.pdoc", "10-document-meta.html"),
    ("11-include", "11-include/main.pdoc", "11-include/main.html"),
]

PHASE4_EXAMPLES = [
    pytest.param(
        "03-strings",
        "03-strings.pdoc",
        "03-strings.html",
        id="03-strings",
        marks=pytest.mark.skip(reason="Phase 4: user macro expansion"),
    ),
    pytest.param(
        "04-user-macros",
        "04-user-macros.pdoc",
        "04-user-macros.html",
        id="04-user-macros",
        marks=pytest.mark.skip(reason="Phase 4: user macro expansion"),
    ),
    pytest.param(
        "07-conditionals",
        "07-conditionals.pdoc",
        "07-conditionals.html",
        id="07-conditionals",
        marks=pytest.mark.skip(reason="Phase 4: user macro expansion"),
    ),
]


@pytest.mark.parametrize(
    "name,pdoc,html",
    PHASE3_EXAMPLES + PHASE4_EXAMPLES,
    ids=[e[0] for e in PHASE3_EXAMPLES] + [None] * len(PHASE4_EXAMPLES),
)
def test_example(name: str, pdoc: str, html: str) -> None:
    pdoc_path = EXAMPLES_DIR / pdoc
    html_path = EXAMPLES_DIR / html

    source = pdoc_path.read_text(encoding="utf-8")
    expected = html_path.read_text(encoding="utf-8")

    doc = parse(source, str(pdoc_path))
    doc = evaluate(doc, str(pdoc_path))
    result = render(doc)

    assert result == expected
