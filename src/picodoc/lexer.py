"""PicoDoc lexer — converts source text into a flat token stream."""

from __future__ import annotations

from enum import Enum, auto

from picodoc.errors import LexError
from picodoc.strings import strip_string_whitespace
from picodoc.tokens import Position, Span, Token, TokenType, is_hex_digit, is_ident_char


class _State(Enum):
    NORMAL = auto()
    INTERP_STRING = auto()
    CODE_MODE = auto()
    RAW_STRING = auto()


class Lexer:
    """Tokenize PicoDoc source text into a stream of Token objects."""

    def __init__(self, source: str, filename: str = "input.pdoc") -> None:
        self._source = source
        self._filename = filename
        self._pos = 0
        self._line = 1
        self._col = 1
        self._tokens: list[Token] = []
        self._state_stack: list[tuple[_State, int]] = []  # (state, bracket_depth)
        self._state = _State.NORMAL
        self._bracket_depth = 0

    def tokenize(self) -> list[Token]:
        """Tokenize the full source and return the token list."""
        while self._pos < len(self._source):
            if self._state == _State.NORMAL:
                self._lex_normal()
            elif self._state == _State.INTERP_STRING:
                self._lex_interp_string()
            elif self._state == _State.CODE_MODE:
                self._lex_code_mode()
            elif self._state == _State.RAW_STRING:
                # Raw string is handled inline when entering the state;
                # this branch should not be reached.
                raise self._error("internal error: unexpected RAW_STRING state")

        # Check for unclosed states at EOF
        if self._state == _State.INTERP_STRING:
            raise self._error("unterminated interpreted string")
        if self._state == _State.CODE_MODE:
            raise self._error("unterminated code mode in string")

        self._emit(TokenType.EOF, "", "")
        return self._tokens

    # ------------------------------------------------------------------
    # Position helpers
    # ------------------------------------------------------------------

    def _current_pos(self) -> Position:
        return Position(self._line, self._col, self._pos)

    def _peek(self, offset: int = 0) -> str:
        idx = self._pos + offset
        if idx < len(self._source):
            return self._source[idx]
        return ""

    def _advance(self) -> str:
        ch = self._source[self._pos]
        self._pos += 1
        if ch == "\n":
            self._line += 1
            self._col = 1
        else:
            self._col += 1
        return ch

    def _emit(self, tt: TokenType, value: str, raw: str, start: Position | None = None) -> Token:
        end = self._current_pos()
        if start is None:
            start = end
        tok = Token(tt, value, raw, Span(start, end))
        self._tokens.append(tok)
        return tok

    def _error(self, message: str, pos: Position | None = None) -> LexError:
        if pos is None:
            pos = self._current_pos()
        return LexError(message, pos, self._source)

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    def _push_state(self, state: _State, bracket_depth: int = 0) -> None:
        self._state_stack.append((self._state, self._bracket_depth))
        self._state = state
        self._bracket_depth = bracket_depth

    def _pop_state(self) -> None:
        self._state, self._bracket_depth = self._state_stack.pop()

    # ------------------------------------------------------------------
    # Normal mode
    # ------------------------------------------------------------------

    def _lex_normal(self) -> None:
        ch = self._peek()

        if ch == "\0":
            raise self._error("NUL character in source")

        if ch == "#":
            start = self._current_pos()
            self._advance()
            self._emit(TokenType.HASH, "#", "#", start)
            return

        if ch == "[":
            start = self._current_pos()
            self._advance()
            self._emit(TokenType.LBRACKET, "[", "[", start)
            return

        if ch == "]":
            start = self._current_pos()
            self._advance()
            self._emit(TokenType.RBRACKET, "]", "]", start)
            return

        if ch == ":":
            start = self._current_pos()
            self._advance()
            self._emit(TokenType.COLON, ":", ":", start)
            return

        if ch == "=":
            start = self._current_pos()
            self._advance()
            self._emit(TokenType.EQUALS, "=", "=", start)
            return

        if ch == "?":
            start = self._current_pos()
            self._advance()
            self._emit(TokenType.QUESTION, "?", "?", start)
            return

        if ch == "\\":
            self._lex_prose_escape()
            return

        if ch == '"':
            self._lex_string_open()
            return

        if ch == "\n":
            start = self._current_pos()
            self._advance()
            self._emit(TokenType.NEWLINE, "\n", "\n", start)
            return

        if ch == "\r" and self._peek(1) == "\n":
            start = self._current_pos()
            self._advance()
            self._advance()
            self._emit(TokenType.NEWLINE, "\n", "\r\n", start)
            return

        if ch in " \t":
            self._lex_ws()
            return

        if is_ident_char(ch):
            self._lex_identifier()
            return

        # Anything else is TEXT
        self._lex_text()

    def _lex_ws(self) -> None:
        start = self._current_pos()
        raw = []
        while self._pos < len(self._source) and self._peek() in " \t":
            raw.append(self._advance())
        text = "".join(raw)
        self._emit(TokenType.WS, text, text, start)

    def _lex_identifier(self) -> None:
        start = self._current_pos()
        chars = []
        while self._pos < len(self._source) and is_ident_char(self._peek()):
            chars.append(self._advance())
        text = "".join(chars)
        self._emit(TokenType.IDENTIFIER, text, text, start)

    def _lex_text(self) -> None:
        start = self._current_pos()
        chars = []
        while self._pos < len(self._source):
            ch = self._peek()
            if ch in '#[]\\:=?"' or ch in " \t\n\r" or ch == "\0" or is_ident_char(ch):
                break
            chars.append(self._advance())
        if chars:
            text = "".join(chars)
            self._emit(TokenType.TEXT, text, text, start)

    # ------------------------------------------------------------------
    # Prose escapes
    # ------------------------------------------------------------------

    def _lex_prose_escape(self) -> None:
        start = self._current_pos()
        self._advance()  # consume backslash

        if self._pos >= len(self._source):
            raise self._error("unexpected end of input after '\\'", start)

        ch = self._peek()

        if ch in "\\#[]:=":
            self._advance()
            self._emit(TokenType.ESCAPE, ch, f"\\{ch}", start)
            return

        if ch == "x":
            self._advance()
            value, raw = self._lex_hex_escape(2, start)
            self._emit(TokenType.ESCAPE, value, raw, start)
            return

        if ch == "U":
            self._advance()
            value, raw = self._lex_hex_escape(8, start)
            self._emit(TokenType.ESCAPE, value, raw, start)
            return

        raise self._error(f"invalid escape sequence '\\{ch}'", start)

    def _lex_hex_escape(self, count: int, start: Position) -> tuple[str, str]:
        """Read `count` hex digits and return (resolved char, raw text)."""
        digits = []
        prefix = self._source[start.offset : self._pos]  # e.g. "\\x" or "\\U"
        for i in range(count):
            if self._pos >= len(self._source):
                raise self._error(
                    f"incomplete escape: expected {count} hex digits, got {i}", start
                )
            ch = self._peek()
            if not is_hex_digit(ch):
                raise self._error(f"invalid hex digit '{ch}' in escape sequence", start)
            digits.append(self._advance())
        hex_str = "".join(digits)
        codepoint = int(hex_str, 16)
        if codepoint > 0x10FFFF:
            raise self._error(f"Unicode codepoint U+{hex_str} is out of range", start)
        raw = prefix + hex_str
        return chr(codepoint), raw

    # ------------------------------------------------------------------
    # String opening — decides interp vs raw vs empty
    # ------------------------------------------------------------------

    def _lex_string_open(self) -> None:
        start = self._current_pos()
        quote_count = 0
        while self._pos < len(self._source) and self._peek() == '"':
            self._advance()
            quote_count += 1

        if quote_count == 1:
            # Interpreted string
            self._emit(TokenType.STRING_START, '"', '"', start)
            self._push_state(_State.INTERP_STRING)
            return

        if quote_count == 2:
            # Empty string: "" → STRING_START + STRING_END
            self._emit(TokenType.STRING_START, '"', '"', start)
            self._emit(TokenType.STRING_END, '"', '"', start)
            return

        # 3+ quotes → raw string
        self._lex_raw_string(quote_count, start)

    # ------------------------------------------------------------------
    # Interpreted string mode
    # ------------------------------------------------------------------

    def _lex_interp_string(self) -> None:
        start = self._current_pos()
        ch = self._peek()

        if ch == '"':
            # End of interpreted string
            s = self._current_pos()
            self._advance()
            self._emit(TokenType.STRING_END, '"', '"', s)
            self._pop_state()
            return

        if ch == "\\":
            self._lex_string_escape()
            return

        # Accumulate STRING_TEXT
        chars = []
        text_start = self._current_pos()
        while self._pos < len(self._source):
            c = self._peek()
            if c in '"\\':
                break
            chars.append(self._advance())
        if chars:
            text = "".join(chars)
            self._emit(TokenType.STRING_TEXT, text, text, text_start)
        elif self._pos >= len(self._source):
            raise self._error("unterminated interpreted string", start)

    # ------------------------------------------------------------------
    # String escapes
    # ------------------------------------------------------------------

    def _lex_string_escape(self) -> None:
        start = self._current_pos()
        self._advance()  # consume backslash

        if self._pos >= len(self._source):
            raise self._error("unexpected end of input in string escape", start)

        ch = self._peek()

        # \[ enters code mode
        if ch == "[":
            self._advance()
            self._emit(TokenType.CODE_OPEN, "\\[", "\\[", start)
            self._push_state(_State.CODE_MODE, 1)
            return

        simple = {"\\": "\\", '"': '"', "n": "\n", "t": "\t"}
        if ch in simple:
            self._advance()
            self._emit(TokenType.STRING_ESCAPE, simple[ch], f"\\{ch}", start)
            return

        if ch == "x":
            self._advance()
            value, raw = self._lex_hex_escape(2, start)
            self._emit(TokenType.STRING_ESCAPE, value, raw, start)
            return

        if ch == "U":
            self._advance()
            value, raw = self._lex_hex_escape(8, start)
            self._emit(TokenType.STRING_ESCAPE, value, raw, start)
            return

        raise self._error(f"invalid string escape sequence '\\{ch}'", start)

    # ------------------------------------------------------------------
    # Code mode (inside \[...] within an interpreted string)
    # ------------------------------------------------------------------

    def _lex_code_mode(self) -> None:
        ch = self._peek()

        if ch == "[":
            start = self._current_pos()
            self._advance()
            self._bracket_depth += 1
            self._emit(TokenType.LBRACKET, "[", "[", start)
            return

        if ch == "]":
            start = self._current_pos()
            self._advance()
            self._bracket_depth -= 1
            if self._bracket_depth == 0:
                self._emit(TokenType.CODE_CLOSE, "]", "]", start)
                self._pop_state()
            else:
                self._emit(TokenType.RBRACKET, "]", "]", start)
            return

        # Everything else dispatches like Normal mode (including nested strings)
        self._lex_normal()

    # ------------------------------------------------------------------
    # Raw strings
    # ------------------------------------------------------------------

    def _lex_raw_string(self, delimiter_count: int, start: Position) -> None:
        """Scan for the closing delimiter (delimiter_count quotes) and emit RAW_STRING."""
        content_start = self._pos

        while self._pos < len(self._source):
            if self._peek() == '"':
                # Count consecutive quotes
                run_start = self._pos
                run_count = 0
                while self._pos < len(self._source) and self._peek() == '"':
                    self._advance()
                    run_count += 1
                if run_count == delimiter_count:
                    # Found closing delimiter
                    raw_content = self._source[content_start:run_start]
                    stripped = strip_string_whitespace(raw_content)
                    raw_text = self._source[start.offset : self._pos]
                    self._emit(TokenType.RAW_STRING, stripped, raw_text, start)
                    return
                # Not enough quotes — they become part of content, continue scanning
            else:
                self._advance()

        raise self._error(
            f"unterminated raw string (expected {delimiter_count} closing quotes)", start
        )


def tokenize(source: str, filename: str = "input.pdoc") -> list[Token]:
    """Convenience function: tokenize source text and return token list."""
    return Lexer(source, filename).tokenize()
