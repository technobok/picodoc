"""PicoDoc parser — converts a token stream into an AST."""

from __future__ import annotations

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
from picodoc.errors import ParseError
from picodoc.lexer import tokenize
from picodoc.tokens import Position, Span, Token, TokenType


class Parser:
    """Recursive descent parser for PicoDoc token streams."""

    def __init__(self, tokens: list[Token], source: str, filename: str) -> None:
        self._tokens = tokens
        self._source = source
        self._filename = filename
        self._pos = 0
        self._bracket_depth = 0

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _peek(self, offset: int = 0) -> Token:
        idx = self._pos + offset
        if idx < len(self._tokens):
            return self._tokens[idx]
        return self._tokens[-1]  # EOF

    def _at(self, *types: TokenType) -> bool:
        return self._peek().type in types

    def _at_eof(self) -> bool:
        return self._peek().type == TokenType.EOF

    def _advance(self) -> Token:
        tok = self._tokens[self._pos]
        if tok.type != TokenType.EOF:
            self._pos += 1
        return tok

    def _expect(self, tt: TokenType, message: str) -> Token:
        tok = self._peek()
        if tok.type != tt:
            raise self._error(message, tok.span)
        return self._advance()

    def _skip_ws(self) -> None:
        if self._at(TokenType.WS):
            self._advance()

    def _prev_end(self) -> Position:
        """End position of the previously consumed token."""
        if self._pos > 0:
            return self._tokens[self._pos - 1].span.end
        return self._tokens[0].span.start

    def _unbr_body_stop(self) -> frozenset[TokenType]:
        """Stop set for unbracketed colon body inline content."""
        if self._bracket_depth > 0:
            return _STOP_NEWLINE_RBRACKET_EOF
        return _STOP_NEWLINE_EOF

    # ------------------------------------------------------------------
    # Document level
    # ------------------------------------------------------------------

    def parse(self) -> Document:
        children: list[MacroCall | Paragraph] = []
        start = self._peek().span.start

        while not self._at_eof():
            block = self._parse_block()
            if block is not None:
                children.append(block)

        end = self._peek().span.end
        return Document(tuple(children), Span(start, end))

    def _parse_block(self) -> MacroCall | Paragraph | None:
        # Skip blank lines
        while not self._at_eof() and self._is_blank_line():
            self._skip_blank_line()

        if self._at_eof():
            return None

        if self._at_block_start():
            return self._parse_macro_block()

        return self._parse_paragraph()

    def _parse_macro_block(self) -> MacroCall:
        if self._at(TokenType.LBRACKET):
            call = self._parse_bracketed_call()
        else:
            call = self._parse_unbracketed_call()

        # Skip optional trailing whitespace
        self._skip_ws()

        # Expect end of line or end of file
        if not self._at(TokenType.NEWLINE, TokenType.EOF):
            raise self._error("unexpected text after macro call", self._peek().span)

        if self._at(TokenType.NEWLINE):
            self._advance()

        return call

    def _parse_paragraph(self) -> Paragraph:
        children: list[Text | Escape | MacroCall] = []
        start = self._peek().span.start

        while not self._at_eof() and not self._is_blank_line() and not self._at_block_start():
            line = self._parse_inline_content(_STOP_NEWLINE_EOF)
            children.extend(line)

            if self._at(TokenType.NEWLINE):
                nl_tok = self._advance()
                # If paragraph continues, insert newline text
                if not self._at_eof() and not self._is_blank_line() and not self._at_block_start():
                    children.append(Text("\n", nl_tok.span))

        children = _coalesce_text(children)
        end = children[-1].span.end if children else start
        return Paragraph(tuple(children), Span(start, end))

    # ------------------------------------------------------------------
    # Macro calls
    # ------------------------------------------------------------------

    def _parse_unbracketed_call(self) -> MacroCall:
        start = self._peek().span.start
        self._advance()  # consume HASH

        name_tok = self._expect(TokenType.IDENTIFIER, "expected macro name after '#'")
        name = name_tok.value

        args: tuple[NamedArg, ...] = ()
        body: Body | InterpString | RawString | None = None

        if self._at(TokenType.STRING_START, TokenType.RAW_STRING):
            # String body without WS: #b"bold"
            body = self._parse_string_body()
        elif self._at(TokenType.COLON):
            # Colon body without WS
            body = self._parse_colon_unbr_body()
        elif self._at(TokenType.WS):
            saved_pos = self._pos
            self._advance()  # consume WS

            if self._is_named_arg_start():
                args = tuple(self._parse_named_args())
                # After args, WS already consumed by arg loop — check for body
                if self._at(TokenType.COLON):
                    body = self._parse_colon_unbr_body()
                elif self._at(TokenType.STRING_START, TokenType.RAW_STRING):
                    body = self._parse_string_body()
            elif self._at(TokenType.COLON):
                body = self._parse_colon_unbr_body()
            elif self._at(TokenType.STRING_START, TokenType.RAW_STRING):
                body = self._parse_string_body()
            else:
                # Nothing useful after WS — restore position
                self._pos = saved_pos

        end = self._prev_end()
        return MacroCall(name, args, body, False, Span(start, end))

    def _parse_bracketed_call(self) -> MacroCall:
        start = self._peek().span.start
        self._advance()  # consume LBRACKET
        self._expect(TokenType.HASH, "expected '#' after '['")

        name_tok = self._expect(TokenType.IDENTIFIER, "expected macro name after '#'")
        name = name_tok.value

        self._bracket_depth += 1

        args: tuple[NamedArg, ...] = ()
        body: Body | InterpString | RawString | None = None

        # Handle no-WS cases first (like [#**"Yes"])
        if self._at(TokenType.STRING_START, TokenType.RAW_STRING):
            body = self._parse_string_body()
        elif self._at(TokenType.COLON):
            body = self._parse_colon_bracket_body()
        elif self._at(TokenType.WS):
            self._advance()  # consume WS

            if self._is_named_arg_start():
                args = tuple(self._parse_named_args())
                # After args, WS consumed by arg loop — check for body
                if self._at(TokenType.COLON):
                    body = self._parse_colon_bracket_body()
                elif self._at(TokenType.STRING_START, TokenType.RAW_STRING):
                    body = self._parse_string_body()
            elif self._at(TokenType.COLON):
                body = self._parse_colon_bracket_body()
            elif self._at(TokenType.STRING_START, TokenType.RAW_STRING):
                body = self._parse_string_body()
            elif not self._at(TokenType.RBRACKET):
                raise self._error(
                    "expected argument, ':' body, string body, or ']'",
                    self._peek().span,
                )

        self._bracket_depth -= 1
        end_tok = self._expect(TokenType.RBRACKET, "expected closing ']'")
        return MacroCall(name, args, body, True, Span(start, end_tok.span.end))

    # ------------------------------------------------------------------
    # Arguments
    # ------------------------------------------------------------------

    def _is_named_arg_start(self) -> bool:
        return self._at(TokenType.IDENTIFIER) and self._peek(1).type == TokenType.EQUALS

    def _parse_named_args(self) -> list[NamedArg]:
        args = [self._parse_named_arg()]
        while self._at(TokenType.WS):
            self._advance()  # consume WS
            if self._is_named_arg_start():
                args.append(self._parse_named_arg())
            else:
                break
        return args

    def _parse_named_arg(self) -> NamedArg:
        name_tok = self._expect(TokenType.IDENTIFIER, "expected argument name")
        name_span = name_tok.span
        self._expect(TokenType.EQUALS, "expected '=' after argument name")
        self._skip_ws()
        value = self._parse_arg_value()
        return NamedArg(name_tok.value, value, name_span, Span(name_span.start, value.span.end))

    def _parse_arg_value(self) -> Text | InterpString | RawString | MacroCall | RequiredMarker:
        if self._at(TokenType.STRING_START):
            return self._parse_interp_string()
        if self._at(TokenType.RAW_STRING):
            return self._parse_raw_string()
        if self._at(TokenType.LBRACKET) and self._peek(1).type == TokenType.HASH:
            return self._parse_bracketed_call()
        if self._at(TokenType.HASH):
            return self._parse_macro_ref()
        if self._at(TokenType.QUESTION):
            tok = self._advance()
            return RequiredMarker(tok.span)
        return self._parse_bareword()

    def _parse_bareword(self) -> Text:
        if not self._at(TokenType.IDENTIFIER, TokenType.TEXT):
            raise self._error("expected argument value", self._peek().span)
        start = self._peek().span.start
        parts: list[str] = []
        while self._at(TokenType.IDENTIFIER, TokenType.TEXT):
            parts.append(self._advance().value)
        value = "".join(parts)
        end = self._prev_end()
        return Text(value, Span(start, end))

    def _parse_macro_ref(self) -> MacroCall:
        start = self._peek().span.start
        self._advance()  # consume HASH
        name_tok = self._expect(TokenType.IDENTIFIER, "expected macro name after '#'")
        return MacroCall(name_tok.value, (), None, False, Span(start, name_tok.span.end))

    # ------------------------------------------------------------------
    # Body
    # ------------------------------------------------------------------

    def _parse_colon_unbr_body(self) -> Body | InterpString | RawString:
        self._advance()  # consume COLON
        self._skip_ws()

        # String after colon
        if self._at(TokenType.STRING_START):
            return self._parse_interp_string()
        if self._at(TokenType.RAW_STRING):
            return self._parse_raw_string()

        # NEWLINE or EOF → paragraph body
        if self._at(TokenType.NEWLINE, TokenType.EOF):
            if self._at(TokenType.NEWLINE):
                self._advance()
            return self._parse_body_paragraph()

        # Inline body: content to end of line (or enclosing bracket)
        start = self._peek().span.start
        children = self._parse_inline_content(self._unbr_body_stop())
        children = _coalesce_text(children)
        end = children[-1].span.end if children else start
        return Body(tuple(children), Span(start, end))

    def _parse_colon_bracket_body(self) -> Body | InterpString | RawString:
        self._advance()  # consume COLON
        self._skip_ws()

        # String after colon
        if self._at(TokenType.STRING_START):
            return self._parse_interp_string()
        if self._at(TokenType.RAW_STRING):
            return self._parse_raw_string()

        # Inline content to matching ]
        start = self._peek().span.start
        children = self._parse_inline_content(_STOP_RBRACKET_EOF)
        children = _coalesce_text(children)
        end = children[-1].span.end if children else start
        return Body(tuple(children), Span(start, end))

    def _parse_string_body(self) -> InterpString | RawString:
        if self._at(TokenType.STRING_START):
            return self._parse_interp_string()
        if self._at(TokenType.RAW_STRING):
            return self._parse_raw_string()
        raise self._error("expected string literal", self._peek().span)

    def _parse_body_paragraph(self) -> Body:
        children: list[Text | Escape | MacroCall] = []
        start = self._peek().span.start

        while not self._at_eof() and not self._is_blank_line():
            line = self._parse_inline_content(self._unbr_body_stop())
            children.extend(line)

            if self._at(TokenType.NEWLINE):
                nl_tok = self._advance()
                # If more body content follows, insert newline text
                if not self._at_eof() and not self._is_blank_line():
                    children.append(Text("\n", nl_tok.span))
            else:
                # Stopped by RBRACKET or EOF — end body paragraph
                break

        children = _coalesce_text(children)
        end = children[-1].span.end if children else start
        return Body(tuple(children), Span(start, end))

    # ------------------------------------------------------------------
    # Inline content
    # ------------------------------------------------------------------

    def _parse_inline_content(self, stop: frozenset[TokenType]) -> list[Text | Escape | MacroCall]:
        result: list[Text | Escape | MacroCall] = []
        text_parts: list[str] = []
        text_start: Position | None = None
        text_end: Position | None = None

        def flush() -> None:
            nonlocal text_start, text_end
            if text_parts:
                value = "".join(text_parts)
                assert text_start is not None
                assert text_end is not None
                result.append(Text(value, Span(text_start, text_end)))
                text_parts.clear()
                text_start = None
                text_end = None

        while not self._at_eof():
            tok = self._peek()

            if tok.type in stop:
                break

            if tok.type == TokenType.HASH:
                flush()
                result.append(self._parse_unbracketed_call())

            elif tok.type == TokenType.LBRACKET and self._peek(1).type == TokenType.HASH:
                flush()
                result.append(self._parse_bracketed_call())

            elif tok.type == TokenType.LBRACKET:
                raise self._error("bare '[' in text \u2014 use \\[ for a literal bracket")

            elif tok.type == TokenType.RBRACKET and TokenType.RBRACKET not in stop:
                raise self._error("bare ']' in text \u2014 use \\] for a literal bracket")

            elif tok.type == TokenType.ESCAPE:
                flush()
                t = self._advance()
                result.append(Escape(t.value, t.span))

            elif tok.type in _TEXT_TOKENS:
                if text_start is None:
                    text_start = tok.span.start
                text_parts.append(tok.value)
                text_end = tok.span.end
                self._advance()

            elif tok.type == TokenType.NEWLINE and TokenType.NEWLINE not in stop:
                # For bracketed body, newlines become text
                if text_start is None:
                    text_start = tok.span.start
                text_parts.append("\n")
                text_end = tok.span.end
                self._advance()

            elif tok.type == TokenType.STRING_START:
                # String in body context — reconstruct as text including quotes
                if text_start is None:
                    text_start = tok.span.start
                text_parts.append('"')
                text_end = tok.span.end
                self._advance()
                while not self._at(TokenType.STRING_END, TokenType.EOF):
                    inner = self._peek()
                    if inner.type in (TokenType.STRING_TEXT, TokenType.STRING_ESCAPE):
                        text_parts.append(inner.value)
                        text_end = inner.span.end
                        self._advance()
                    elif inner.type == TokenType.CODE_OPEN:
                        # Code section inside string-as-text — reconstruct as text
                        text_parts.append(inner.raw)
                        text_end = inner.span.end
                        self._advance()
                        while not self._at(
                            TokenType.CODE_CLOSE,
                            TokenType.STRING_END,
                            TokenType.EOF,
                        ):
                            ct = self._peek()
                            text_parts.append(ct.raw)
                            text_end = ct.span.end
                            self._advance()
                        if self._at(TokenType.CODE_CLOSE):
                            text_parts.append(self._peek().raw)
                            text_end = self._peek().span.end
                            self._advance()
                    else:
                        break
                if self._at(TokenType.STRING_END):
                    if text_start is None:
                        text_start = self._peek().span.start
                    text_parts.append('"')
                    text_end = self._peek().span.end
                    self._advance()

            elif tok.type == TokenType.RAW_STRING:
                # Raw string in body context — include content as text
                if text_start is None:
                    text_start = tok.span.start
                text_parts.append(tok.value)
                text_end = tok.span.end
                self._advance()

            else:
                break

        flush()
        return result

    # ------------------------------------------------------------------
    # Strings
    # ------------------------------------------------------------------

    def _parse_interp_string(self) -> InterpString:
        start_tok = self._advance()  # consume STRING_START

        parts: list[Text | CodeSection] = []
        text_parts: list[str] = []
        text_start: Position | None = None
        text_end: Position | None = None

        def flush() -> None:
            nonlocal text_start, text_end
            if text_parts:
                value = "".join(text_parts)
                assert text_start is not None
                assert text_end is not None
                parts.append(Text(value, Span(text_start, text_end)))
                text_parts.clear()
                text_start = None
                text_end = None

        while not self._at(TokenType.STRING_END, TokenType.EOF):
            tok = self._peek()

            if tok.type in (TokenType.STRING_TEXT, TokenType.STRING_ESCAPE):
                if text_start is None:
                    text_start = tok.span.start
                text_parts.append(tok.value)
                text_end = tok.span.end
                self._advance()

            elif tok.type == TokenType.CODE_OPEN:
                flush()
                parts.append(self._parse_code_section())

            else:
                raise self._error("unexpected token in string", tok.span)

        flush()

        end_tok = self._expect(TokenType.STRING_END, "expected closing '\"'")
        return InterpString(tuple(parts), Span(start_tok.span.start, end_tok.span.end))

    def _parse_raw_string(self) -> RawString:
        tok = self._expect(TokenType.RAW_STRING, "expected raw string")
        return RawString(tok.value, tok.span)

    def _parse_code_section(self) -> CodeSection:
        start = self._peek().span.start
        self._advance()  # consume CODE_OPEN

        children = self._parse_inline_content(_STOP_CODE_CLOSE_EOF)

        end_tok = self._expect(TokenType.CODE_CLOSE, "expected closing ']' for code section")
        return CodeSection(tuple(children), Span(start, end_tok.span.end))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _is_blank_line(self) -> bool:
        if self._at(TokenType.NEWLINE):
            return True
        if self._at(TokenType.WS):
            next_type = self._peek(1).type
            return next_type in (TokenType.NEWLINE, TokenType.EOF)
        return False

    def _skip_blank_line(self) -> None:
        if self._at(TokenType.WS):
            self._advance()
        if self._at(TokenType.NEWLINE):
            self._advance()

    def _at_block_start(self) -> bool:
        """Check if current position looks like the start of a block-level macro."""
        if self._at(TokenType.HASH):
            return True
        return self._at(TokenType.LBRACKET) and self._peek(1).type == TokenType.HASH

    def _error(self, message: str, span: Span | None = None) -> ParseError:
        if span is None:
            span = self._peek().span
        return ParseError(message, span, self._source)


# Module-level constants
_STOP_NEWLINE_EOF: frozenset[TokenType] = frozenset({TokenType.NEWLINE, TokenType.EOF})
_STOP_NEWLINE_RBRACKET_EOF: frozenset[TokenType] = frozenset(
    {TokenType.NEWLINE, TokenType.RBRACKET, TokenType.EOF}
)
_STOP_RBRACKET_EOF: frozenset[TokenType] = frozenset({TokenType.RBRACKET, TokenType.EOF})
_STOP_CODE_CLOSE_EOF: frozenset[TokenType] = frozenset({TokenType.CODE_CLOSE, TokenType.EOF})
_TEXT_TOKENS: frozenset[TokenType] = frozenset(
    {
        TokenType.IDENTIFIER,
        TokenType.TEXT,
        TokenType.WS,
        TokenType.COLON,
        TokenType.EQUALS,
        TokenType.QUESTION,
    }
)


def _coalesce_text(nodes: list) -> list:
    """Coalesce adjacent Text nodes into single nodes."""
    if not nodes:
        return nodes
    result = []
    for node in nodes:
        if isinstance(node, Text) and result and isinstance(result[-1], Text):
            prev = result[-1]
            result[-1] = Text(prev.value + node.value, Span(prev.span.start, node.span.end))
        else:
            result.append(node)
    return result


def parse(source: str, filename: str = "input.pdoc") -> Document:
    """Convenience function: parse source text and return a Document AST."""
    tokens = tokenize(source, filename)
    return Parser(tokens, source, filename).parse()
