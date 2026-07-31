from pygments.lexer import RegexLexer
from pygments.token import Comment, Escape, Keyword, Name, Punctuation, String, Text


class PicoDocLexer(RegexLexer):
    # Pygments declares aliases, filenames and tokens as instance attributes on
    # RegexLexer and expects subclasses to set them as plain class attributes.
    # Annotating them ClassVar, as RUF012 suggests, is rejected by the type
    # checker as an invalid override, so the rule is suppressed instead.
    name = "PicoDoc"
    aliases = ["picodoc", "pdoc"]  # noqa: RUF012
    filenames = ["*.pdoc"]  # noqa: RUF012

    tokens = {  # noqa: RUF012
        "root": [
            (r"\[#(?:comment\b|//)", Comment, "bracket_comment"),
            (r"#(?:comment\b|//)[ \t]*:[ \t]*$", Comment, "paragraph_comment"),
            (r"#(?:comment\b|//).*$", Comment.Single),
            (r'""""""', String, "rawstring6"),
            (r'"""""', String, "rawstring5"),
            (r'""""', String, "rawstring4"),
            (r'"""', String, "rawstring3"),
            (r'"', String, "string"),
            (r'\\(?:[#\[\]\\"]|x[0-9a-fA-F]{2}|U[0-9a-fA-F]{8}|[nt])', Escape),
            (r"\[#[\w.*!@~-]+", Keyword, "bracket_macro"),
            (r"#[\w.*!@~-]+", Keyword),
            (r"[\w.]+(?==)", Name.Attribute),
            (r"[:\[\]]", Punctuation),
            (r"[^\S\n]+", Text),
            (r"\n", Text),
            (r".", Text),
        ],
        "string": [
            (r"\\.", Escape),
            (r'"', String, "#pop"),
            (r'[^"\\]+', String),
        ],
        "rawstring3": [
            (r'"""', String, "#pop"),
            (r'[^"]+', String),
            (r'"{1,2}', String),
        ],
        "rawstring4": [
            (r'""""', String, "#pop"),
            (r'[^"]+', String),
            (r'"{1,3}', String),
        ],
        "rawstring5": [
            (r'"""""', String, "#pop"),
            (r'[^"]+', String),
            (r'"{1,4}', String),
        ],
        "rawstring6": [
            (r'""""""', String, "#pop"),
            (r'[^"]+', String),
            (r'"{1,5}', String),
        ],
        "bracket_macro": [
            (r"", Text, "#pop"),
        ],
        "bracket_comment": [
            (r"\]", Comment, "#pop"),
            (r"[^\]]+", Comment),
        ],
        "paragraph_comment": [
            (r"\n[ \t]*\n", Text, "#pop"),
            (r"\n", Comment),
            (r"[^\n]+", Comment),
        ],
    }
