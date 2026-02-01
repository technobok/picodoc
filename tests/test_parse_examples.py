"""Integration test: parse all example .pdoc files and verify structure."""

from __future__ import annotations

from pathlib import Path

import pytest

from picodoc.ast import Document, MacroCall, Paragraph
from picodoc.parser import parse

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"


def _find_pdoc_files() -> list[Path]:
    """Find all .pdoc files in the examples directory."""
    return sorted(EXAMPLES_DIR.rglob("*.pdoc"))


@pytest.fixture(params=_find_pdoc_files(), ids=lambda p: str(p.relative_to(EXAMPLES_DIR)))
def pdoc_file(request: pytest.FixtureRequest) -> Path:
    return request.param


class TestParseExampleFiles:
    def test_parses_without_error(self, pdoc_file: Path):
        """Each example file should parse without raising any errors."""
        source = pdoc_file.read_text(encoding="utf-8")
        doc = parse(source, filename=str(pdoc_file.name))
        assert isinstance(doc, Document)

    def test_has_children(self, pdoc_file: Path):
        """Each example file should produce at least one child node."""
        source = pdoc_file.read_text(encoding="utf-8")
        doc = parse(source, filename=str(pdoc_file.name))
        assert len(doc.children) > 0, f"Empty document for {pdoc_file.name}"

    def test_children_are_valid_types(self, pdoc_file: Path):
        """All top-level children must be MacroCall or Paragraph."""
        source = pdoc_file.read_text(encoding="utf-8")
        doc = parse(source, filename=str(pdoc_file.name))
        for child in doc.children:
            assert isinstance(child, (MacroCall, Paragraph)), (
                f"Unexpected child type: {type(child).__name__}"
            )

    def test_spans_are_valid(self, pdoc_file: Path):
        """All top-level node spans should be within source bounds."""
        source = pdoc_file.read_text(encoding="utf-8")
        doc = parse(source, filename=str(pdoc_file.name))
        src_len = len(source)
        for child in doc.children:
            assert child.span.start.offset >= 0
            assert child.span.start.offset <= src_len
            assert child.span.end.offset >= 0
            assert child.span.end.offset <= src_len
            assert child.span.start.offset <= child.span.end.offset
