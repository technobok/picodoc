"""Error types with formatted source context."""

from __future__ import annotations

from picodoc.tokens import Position, Span


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


class ParseError(Exception):
    """Raised on the first parse error, with span and source context."""

    def __init__(self, message: str, span: Span, source: str) -> None:
        self.message = message
        self.span = span
        self.source = source
        super().__init__(self.format())

    def format(self, filename: str = "input.pdoc") -> str:
        lines = self.source.splitlines(keepends=True)
        line_idx = self.span.start.line - 1
        col = self.span.start.column

        if 0 <= line_idx < len(lines):
            source_line = lines[line_idx].rstrip("\n").rstrip("\r")
        else:
            source_line = ""

        # Underline the full span when on one line, otherwise to end of line
        if self.span.end.line == self.span.start.line:
            underline_len = max(1, self.span.end.column - col)
        else:
            underline_len = max(1, len(source_line) - col + 1)

        pad = " " * (col - 1)
        carets = "^" * underline_len

        line_num = str(self.span.start.line)
        gutter_width = len(line_num) + 1

        blank_gutter = " " * gutter_width + "|"
        line_gutter = f"{line_num:>{gutter_width - 1}} |"

        return (
            f"error: {self.message}\n"
            f"{' ' * gutter_width}--> {filename}:{self.span.start.line}:{col}\n"
            f"{blank_gutter}\n"
            f"{line_gutter} {source_line}\n"
            f"{blank_gutter} {pad}{carets}"
        )


class EvalError(Exception):
    """Raised on evaluation errors, with span and source context."""

    def __init__(
        self,
        message: str,
        span: Span,
        source: str,
        call_stack: list[str] | None = None,
    ) -> None:
        self.message = message
        self.span = span
        self.source = source
        self.call_stack = call_stack or []
        super().__init__(self.format())

    def format(self, filename: str = "input.pdoc") -> str:
        lines = self.source.splitlines(keepends=True)
        line_idx = self.span.start.line - 1
        col = self.span.start.column

        if 0 <= line_idx < len(lines):
            source_line = lines[line_idx].rstrip("\n").rstrip("\r")
        else:
            source_line = ""

        if self.span.end.line == self.span.start.line:
            underline_len = max(1, self.span.end.column - col)
        else:
            underline_len = max(1, len(source_line) - col + 1)

        pad = " " * (col - 1)
        carets = "^" * underline_len

        line_num = str(self.span.start.line)
        gutter_width = len(line_num) + 1

        blank_gutter = " " * gutter_width + "|"
        line_gutter = f"{line_num:>{gutter_width - 1}} |"

        result = (
            f"error: {self.message}\n"
            f"{' ' * gutter_width}--> {filename}:{self.span.start.line}:{col}\n"
            f"{blank_gutter}\n"
            f"{line_gutter} {source_line}\n"
            f"{blank_gutter} {pad}{carets}"
        )
        if self.call_stack:
            chain = " -> ".join(f"#{name}" for name in self.call_stack)
            result += f"\n  in expansion chain: {chain}"
        return result
