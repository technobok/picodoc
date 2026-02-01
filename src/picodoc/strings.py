"""Whitespace stripping for string literals."""

from __future__ import annotations


def strip_string_whitespace(content: str) -> str:
    """Apply PicoDoc whitespace stripping rules to string content.

    Algorithm:
    1. Split into lines.
    2. If the first line is blank (whitespace-only), discard it.
    3. If the last line is blank, record its whitespace as common_prefix, discard it.
    4. If common_prefix appears at the start of every non-empty interior line, strip it.
    5. Rejoin with newline.

    Blank interior lines do not prevent stripping (lenient).
    """
    if not content:
        return content

    lines = content.split("\n")

    # Step 2: discard blank first line
    if lines and _is_blank(lines[0]):
        lines = lines[1:]

    if not lines:
        return ""

    # Step 3: check last line
    common_prefix = ""
    if len(lines) >= 1 and _is_blank(lines[-1]):
        common_prefix = lines[-1]
        lines = lines[:-1]

    if not lines:
        return ""

    # Step 4: strip common prefix from all non-empty lines
    if common_prefix:
        # Check that every non-empty line starts with the common prefix
        can_strip = all(line.startswith(common_prefix) or _is_blank(line) for line in lines)
        if can_strip:
            prefix_len = len(common_prefix)
            lines = [line[prefix_len:] if not _is_blank(line) else line for line in lines]

    # Step 5: rejoin
    return "\n".join(lines)


def _is_blank(line: str) -> bool:
    """Return True if line contains only spaces and tabs (or is empty)."""
    return all(ch in " \t" for ch in line)
