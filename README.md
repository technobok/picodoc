# PicoDoc

A macro-based markup language that compiles to HTML. Designed around a
single core abstraction (the macro), strict parsing with helpful error
messages, and a regular syntax inspired by (but simpler than) AsciiDoc.

**File extension:** `.pdoc`

## Design Philosophy

1. **One abstraction** -- macros are the only construct. Everything from
   headings to bold text to user-defined templates is a macro call.
2. **Named arguments** -- all arguments are named (except the special `body`
   argument which can be positional). No ambiguity about what each value means.
3. **Strict parsing** -- the parser rejects invalid input with clear error
   messages rather than guessing intent. Errors in output are obvious.
4. **UTF-8 only** -- no encoding detection or fallback.
5. **HTML target** -- the primary (and initially only) output format is HTML.

## Syntax Quick Reference

```
# Headings (colon introduces body content)
#title: Document Title
#- : Document Title (alias for #title / #h1)
#h2: Section Heading
#-- : Section Heading (alias for #h2)
#h3: Subsection Heading
#--- : Subsection Heading (alias for #h3)

# Inline formatting (string literal body, no colon needed)
This is #**"bold text" and #__"italic text".

# Named arguments only (no body)
[#url link="https://example.com" text="Click here"]

# Named arguments with body (: separates args from body)
[#code language=python : print("hello")]

# String literals as body (colon optional before string literal)
[#code language=python """
def hello():
    print("world")
"""]

# Defining macros
[#set name=greeting target=? body=? : Dear [#target], [#body] Kind regards.]

# Using defined macros
[#greeting target=World : thank you for your support.]

# Square brackets for grouping / precedence
This has [#b : bold [#__"and italic"]] text.

# Code mode inside interpreted strings (\[...] for macro expansion)
"Dear \[#target], welcome to \[#place]."

# Lists
[#ul :
  #*: First item
  #*: Second item
  #*: Third with [#**"bold"]
]

# Tables (simple pipe-delimited form)
#table:
  Name | Age
  Alice | 30
  Bob | 25

# Paragraphs (bare text auto-wraps in #p)
This is a paragraph that
spans multiple lines.

This is a second paragraph.
```

## Comparison to Similar Languages

### Feature Matrix

| Feature                | PicoDoc        | Typst       | Pollen       | Scribble    | Djot        | AsciiDoc   |
|------------------------|----------------|-------------|--------------|-------------|-------------|------------|
| Command prefix         | `#`            | `#`         | `◊`          | `@`         | (none)      | (various)  |
| Named arguments        | Yes            | Yes         | Via Racket   | Via Racket  | Via attrs   | Partial    |
| User macros            | `#set` + filters | `#let`    | Racket fns   | Racket fns  | AST filters | Limited    |
| Body/content delim     | `:` separator  | `[]`        | `{}`         | `{}`        | N/A         | Blocks     |
| Arg/body separation    | `=` vs `:`     | `()` vs `[]`| `[]` vs `{}` | `[]` vs `{}`| N/A         | Positional |
| Programming language   | No             | Built-in    | Racket       | Racket      | No          | No         |
| Strict parsing         | Yes            | Yes         | Yes          | Yes         | Yes         | Lenient    |
| Primary output         | HTML           | PDF         | Multi        | HTML        | HTML        | Multi      |

### Key Comparisons

**vs Typst:** Typst is the closest sibling -- it also uses `#` as a command
prefix and has named arguments. However, Typst includes a full programming
language (variables, conditionals, loops, functions with return values) and
targets PDF typesetting. Typst cleanly separates arguments `()` from content
`[]` using different delimiters. This language is simpler in scope but should
study Typst's syntax decisions carefully.

**vs Pollen / Scribble:** Both use a command prefix (`◊` / `@`) followed by
optional Racket arguments in `[]` and a text body in `{}`. The syntactic
separation of arguments from body is clearer than this language's approach of
using a special argument name (`body`). However, both require knowledge of
Racket for extensibility; this language's external filter model is more
language-agnostic.

**vs Djot:** Djot is a lightweight markup (Markdown successor) that achieves
extensibility through a clean AST and external filters. It prioritises
readability for simple documents. This language is heavier syntactically but
offers more inline power through macros.

**vs AsciiDoc:** The stated inspiration. AsciiDoc is feature-rich but has
accumulated significant syntactic complexity and inconsistencies. This language
aims for the same expressive power with a more regular grammar.

## Evaluation

### Strengths

1. **Regularity.** One core abstraction (macro) applied uniformly is an elegant
   design. It avoids the proliferation of special syntaxes that plagues
   AsciiDoc and Markdown.

2. **Named arguments.** Eliminates positional ambiguity. Self-documenting at
   the call site.

3. **Strict parsing.** Fail-fast philosophy is the right choice for a new
   language. Much easier to relax rules later than to tighten them.

4. **String literal design.** Raw strings (triple-quote / N-quote) are fully
   opaque with indentation stripping, comparable to Kotlin, Swift, and Python
   multiline strings. Interpreted strings are literal by default with explicit
   code mode (`\[...]`) for embedding macro calls -- no implicit scanning.

5. **External filter extensibility.** Language-agnostic extension via CLI
   filters is a good design. Users can write filters in any language.

6. **Escape rules are minimal and explicit.** Only a defined set of escape
   sequences is allowed; anything else is a syntax error. This prevents subtle
   bugs from unintentional escapes.

### Design Decisions (Resolved)

The following issues were identified during evaluation and have been resolved.

**1. Heading aliases: `#-`, `#--`, `#---`**

The original spec proposed `##` for h2 and `###` for h3, but `#` is not a
valid identifier character. The aliases now use dashes: `#-` (h1/title), `#--`
(h2), `#---` (h3), and so on. These are regular macro identifiers composed
of `-` characters, consistent with the grammar. The visual indentation of
repeated characters pushes lower heading levels to the right. The clash with
`---` being a horizontal rule in other markup languages is accepted.

**2. `\` removed from identifier characters.**

Backslash was listed as a valid identifier character but also serves as the
escape prefix. This created genuine ambiguity: `#\x41` could be macro `\x41`
or escape sequence for `A`. Backslash is now exclusively the escape prefix
and cannot appear in identifiers.

**3. `?` removed from identifier characters.**

The question mark was listed as a valid identifier character but also marks
required arguments in `#set` definitions. In `[#set name=foo arg=?]`, the
parser could not determine whether `?` was a value or a marker without
lookahead into the macro's semantics. `?` is now exclusively the
required-argument marker and cannot appear in identifiers.

**4. Escape sequences: `\xHH` and `\UHHHHHHHH`**

- `\xHH` now specifies a Unicode codepoint (U+0000 to U+00FF), not a "UTF-8
  character." UTF-8 is an encoding; the escape specifies the codepoint, and
  the implementation encodes it as appropriate.
- The full Unicode escape is now `\UHHHHHHHH` (8 fixed hex digits), following
  the C and Python convention. This covers the full Unicode range (U+00000000
  to U+0010FFFF). A fixed digit count was chosen over variable-length
  `\u{H+}` to avoid ambiguity when a hex digit immediately follows the
  escape in document text.

**5. Spelling corrections applied to spec.**

Fixed: "implementation" (was "implimentation"), "reimplement" (was
"reimpliment"), "delimiter" (was "delimeter"), "escapes" (was "excapes"),
"contiguous" (was "continguous"). Example typos (`=p` instead of `#p`) also
corrected.

**6. Macro expansion: recursive multi-pass AST walking.**

Macro expansion uses recursive multi-pass AST walking. After parsing, the
evaluator:

1. **Collects** all `#set` definitions without evaluating them.
2. **Resolves** definitions: evaluates default values (which may themselves
   require expansion passes).
3. **Walks** the AST, expanding macro nodes and marking fully-expanded nodes
   as complete.
4. **Re-walks** until all nodes are resolved or the depth limit is reached.

Key rules:

- **Global max recursion depth** (configurable via CLI/config, sensible default
  e.g. 64) catches infinite or excessive expansion.
- **Per-macro depth** via `depth=N` parameter on `#set`. `depth=0` means the
  macro's output is final text (no re-expansion). Unset inherits the global
  limit. Depth tracks full call stack depth; self-recursion is not treated
  separately.
- **Out-of-order definitions** are allowed: macros may be used before they are
  defined in the document. All definitions are collected before resolution.
- **Duplicate definitions** at the same scope are an immediate error.
- **Default values** are evaluated during the resolution pass (after all
  definitions are collected), not at definition time. Default value evaluation
  may itself require multiple expansion passes.
- **`#set` inside macro bodies**: under discussion. If allowed, definitions
  would be scoped to that expansion and lower scopes, and out-of-order rules
  would apply within the body. Alternatively, `#set` could be restricted to
  top-level only, consistent with the flat namespace.

**7. Identifier character set narrowed.**

Removed `\`, `?`, `<`, `>`, `|`, `'`, `=` from the valid identifier character
set. `\` and `?` had structural roles (escape prefix and required-argument
marker). `=` is now the argument separator. `<`, `>`, `|` could be visually
confusing in markup context. `'` (single quote) is reserved for potential
future use as an alternative string literal delimiter. The valid special
characters in identifiers are now:
`! $ % & * + - / @ ^ _ ~` (plus letters, digits, and dots).

Note: `&` is special in HTML output (`&amp;`, `&lt;`, etc.) so macro names
containing `&` could be confusing when debugging rendered output.

**8. Argument syntax (`=`) and body separator (`:`) with two-form call model.**

The original spec used `:` for both argument naming and body, creating
ambiguity (the parser needed macro definitions to determine where arguments
ended and body began). The new design:

- **`=` is the argument separator**: `name=value` with no whitespace before
  `=` (whitespace after `=` is permitted). Familiar from HTML attributes and
  CLI flags. The no-whitespace-before-`=` rule is what enables one-token
  lookahead: the parser can distinguish `name=value` (argument) from `name`
  (prose) without backtracking.
- **`:` introduces plain text body**: in both call forms, `:` is required
  before plain text body. Whitespace around the colon is flexible. In prose
  text outside of macro calls, `:` is just a character.
- **String literals as body without colon**: a string literal appearing after
  the identifier or arguments is treated as body without requiring a colon.
  A colon before a string literal body is permitted but optional. This
  allows lean inline syntax: `#b"bold"`, `#i"italic"`.
- **Two call forms** make the parser completely independent of macro
  definitions:
  - *Unbracketed*: `#identifier [name=val ...] [: body | "string"]` -- after
    the identifier, the parser looks for `name=value` pairs, `:`, or a
    string literal. If none, the call is complete with no body and remaining
    text is prose.
  - *Bracketed*: `[#identifier name=val : body]` or
    `[#identifier name=val "string"]` -- named arguments before body. Both
    args and body are optional. Bare text inside brackets that is not
    `name=value` and not after `:` or a string literal is a syntax error.
- **Whitespace before `=` is a silent mis-parse in unbracketed form**:
  `#macro name = value` is treated as a no-arg, no-body call followed by
  prose. The bracketed form `[#macro name = value]` catches this as a syntax
  error. This trade-off is accepted to keep the parser definition-independent.
- **`\=` added to valid escape sequences** for the rare case where `=` appears
  in bareword values inside brackets.
- **`body` remains the parameter name** in `#set` definitions (`body=?` for
  required, `body=default` for optional). The `:` syntax is call-site sugar.

### Resolved: `#set` restricted to top-level

`#set` cannot appear inside macro bodies. Consistent with the flat namespace
design and avoids scoping complexity. May be relaxed in a future version.

## Implementation Approach

**Language:** Python (initial reference implementation), with architecture
clean enough to port to Rust later for performance and WASM compilation.

**Architecture:**

```
Source Text
    |
    v
  Lexer -------> Token Stream
    |
    v
  Parser ------> AST (Abstract Syntax Tree)
    |
    v
  Collector ---> Definitions (all #set nodes gathered)
    |
    v
  Resolver ----> Resolved AST (default values evaluated)
    |
    v
  Expander ----> Expanded AST (multi-pass walking until stable)
    |             - expansion-time builtins resolved and removed
    |             - only text nodes + render-time builtin nodes remain
    v
  Renderer ----> HTML Output
                  - maps render-time nodes to HTML elements
                  - validates nesting, handles escaping
                  - wraps in document structure (doctype, head, body)
```

**Key recommendations:**

- **Hand-written recursive descent parser** rather than a parser generator.
  This gives the best error messages and makes the strict-parsing philosophy
  practical. Parser generators tend to produce poor diagnostics.
- **Write a formal grammar (EBNF/PEG) first**, even if the parser is
  hand-written. The grammar serves as the specification and guides all
  implementations.
- **Separate lexing from parsing.** The string literal rules (especially raw
  strings and indentation stripping) are complex enough to warrant a dedicated
  lexer pass.
- **Immutable AST nodes.** Makes macro expansion easier to reason about and
  debug.
- **Comprehensive test suite from day one.** Each syntax feature should have
  positive tests (valid input) and negative tests (expected errors with
  expected messages).

## Project Structure (Proposed)

```
picodoc/
  src/
    lexer.py        # Tokenization
    parser.py       # Token stream -> AST
    ast.py          # AST node definitions
    evaluator.py    # Macro expansion
    renderer.py     # AST -> HTML
    builtins.py     # Built-in macro definitions
    errors.py       # Error types and formatting
    cli.py          # Command-line interface
  tests/
    test_lexer.py
    test_parser.py
    test_evaluator.py
    test_renderer.py
    test_integration.py
    fixtures/       # .pdoc -> .html test pairs
  grammar.ebnf      # Formal grammar specification
  pyproject.toml
  README.md
  ROADMAP.md
```
