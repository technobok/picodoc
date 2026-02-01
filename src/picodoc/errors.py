"""Lexer error with formatted source context."""

from __future__ import annotations

from picodoc.tokens import Position


class LexError(Exception):
    """Raised on the first lexing error, with position and source context."""

    def __init__(self, message: str, position: Position, source: str) -> None:
        self.message = message
        self.position = position
        self.source = source
        super().__init__(self.format())

    def format(self, filename: str = "input.pdoc") -> str:
        lines = self.source.splitlines(keepends=True)
        line_idx = self.position.line - 1
        col = self.position.column

        # Build the source line (strip trailing newline for display)
        if 0 <= line_idx < len(lines):
            source_line = lines[line_idx].rstrip("\n").rstrip("\r")
        else:
            source_line = ""

        # Compute underline length — at least 1 char, but stay within line
        underline_len = max(1, min(2, len(source_line) - col + 1))

        pad = " " * (col - 1)
        carets = "^" * underline_len

        line_num = str(self.position.line)
        gutter_width = len(line_num) + 1

        blank_gutter = " " * gutter_width + "|"
        line_gutter = f"{line_num:>{gutter_width - 1}} |"

        return (
            f"error: {self.message}\n"
            f"{' ' * gutter_width}--> {filename}:{self.position.line}:{col}\n"
            f"{blank_gutter}\n"
            f"{line_gutter} {source_line}\n"
            f"{blank_gutter} {pad}{carets}"
        )
