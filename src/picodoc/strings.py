"""Whitespace stripping for string literals and body content."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from picodoc.ast import Escape, MacroCall, Text


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


def dedent_body_children(
    children: tuple[Text | Escape | MacroCall, ...],
) -> tuple[Text | Escape | MacroCall, ...]:
    """Strip the longest common leading whitespace from body children.

    Walks Text nodes tracking line starts. Computes the minimum common
    whitespace prefix across all non-blank lines, then strips that prefix
    from every line start. Returns a new tuple with modified Text nodes.
    """
    from picodoc.ast import Text as TextNode

    if not children:
        return children

    # --- Pass 1: compute common prefix ---
    prefix: str | None = None  # None = not yet set
    at_line_start = True

    for node in children:
        if not isinstance(node, TextNode):
            at_line_start = False
            continue
        val = node.value
        p = 0
        while p < len(val):
            if at_line_start:
                # Find end of this line
                nl_pos = val.find("\n", p)
                line_end = nl_pos if nl_pos >= 0 else len(val)
                line = val[p:line_end]

                if _is_blank(line) and nl_pos >= 0:
                    # Skip blank lines (only newline-terminated ones;
                    # unterminated ws means the line continues in the
                    # next non-Text node and is NOT blank)
                    p = nl_pos + 1
                    at_line_start = True
                    continue

                # Measure leading whitespace
                ws_len = 0
                while ws_len < len(line) and line[ws_len] in " \t":
                    ws_len += 1
                ws = line[:ws_len]

                if prefix is None:
                    prefix = ws
                else:
                    # Compute common prefix
                    common = min(len(prefix), len(ws))
                    for i in range(common):
                        if prefix[i] != ws[i]:
                            common = i
                            break
                    prefix = prefix[:common]

                at_line_start = False

            # Advance to next newline
            nl_pos = val.find("\n", p)
            if nl_pos >= 0:
                p = nl_pos + 1
                at_line_start = True
            else:
                break

    # Nothing to strip
    if not prefix:
        return children

    prefix_len = len(prefix)

    # --- Pass 2: strip prefix from Text nodes ---
    result = list(children)
    at_line_start = True

    for idx, node in enumerate(result):
        if not isinstance(node, TextNode):
            at_line_start = False
            continue

        val = node.value
        parts: list[str] = []
        p = 0
        ls = at_line_start

        while p < len(val):
            if ls:
                # Check if line is blank
                nl_pos = val.find("\n", p)
                line_end = nl_pos if nl_pos >= 0 else len(val)
                line = val[p:line_end]

                if _is_blank(line) and nl_pos >= 0:
                    # Copy blank line as-is (only newline-terminated;
                    # unterminated ws continues in the next node)
                    parts.append(line)
                    parts.append("\n")
                    p = nl_pos + 1
                    ls = True
                    continue

                # Non-blank line: skip prefix
                skip = min(prefix_len, len(val) - p)
                p += skip
                ls = False
                continue

            if val[p] == "\n":
                parts.append("\n")
                p += 1
                ls = True
            else:
                parts.append(val[p])
                p += 1

        at_line_start = ls
        new_val = "".join(parts)
        if new_val != val:
            result[idx] = TextNode(new_val, node.span)

    return tuple(result)
