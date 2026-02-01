"""Integration test: lex all example .pdoc files and assert no errors."""

from __future__ import annotations

from pathlib import Path

import pytest

from picodoc.lexer import tokenize
from picodoc.tokens import TokenType

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"


def _find_pdoc_files() -> list[Path]:
    """Find all .pdoc files in the examples directory."""
    return sorted(EXAMPLES_DIR.rglob("*.pdoc"))


@pytest.fixture(params=_find_pdoc_files(), ids=lambda p: str(p.relative_to(EXAMPLES_DIR)))
def pdoc_file(request: pytest.FixtureRequest) -> Path:
    return request.param


class TestExampleFiles:
    def test_tokenizes_without_error(self, pdoc_file: Path):
        """Each example file should tokenize without raising any errors."""
        source = pdoc_file.read_text(encoding="utf-8")
        tokens = tokenize(source, filename=str(pdoc_file.name))
        # Must produce at least an EOF token
        assert len(tokens) >= 1
        assert tokens[-1].type == TokenType.EOF

    def test_no_empty_tokens(self, pdoc_file: Path):
        """No token (except EOF) should have an empty value and empty raw."""
        source = pdoc_file.read_text(encoding="utf-8")
        tokens = tokenize(source, filename=str(pdoc_file.name))
        for tok in tokens:
            if tok.type == TokenType.EOF:
                continue
            assert tok.value != "" or tok.raw != "", f"Empty token {tok.type} at {tok.span.start}"

    def test_positions_are_monotonic(self, pdoc_file: Path):
        """Token start offsets should be non-decreasing."""
        source = pdoc_file.read_text(encoding="utf-8")
        tokens = tokenize(source, filename=str(pdoc_file.name))
        prev_offset = -1
        for tok in tokens:
            if tok.type == TokenType.EOF:
                continue
            assert tok.span.start.offset >= prev_offset, (
                f"Non-monotonic offset: {tok.type} at offset {tok.span.start.offset} "
                f"(prev was {prev_offset})"
            )
            prev_offset = tok.span.start.offset
