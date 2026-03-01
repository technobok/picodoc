from pygments.lexer import RegexLexer
from pygments.token import Comment, Escape, Keyword, Name, Punctuation, String, Text


class PicoDocLexer(RegexLexer):
    name = "PicoDoc"
    aliases = ["picodoc", "pdoc"]
    filenames = ["*.pdoc"]

    tokens = {
        "root": [
            (r"#//.*$", Comment.Single),
            (r'"{3,}', String, "rawstring"),
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
        "rawstring": [
            (r'"{3,}', String, "#pop"),
            (r'[^"]+', String),
            (r'"', String),
        ],
        "bracket_macro": [
            (r"", Text, "#pop"),
        ],
    }
