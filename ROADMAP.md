# Roadmap

Implementation plan for the markup language project, organized into phases.
Each phase should be functionally complete and testable before moving to the
next.

## Phase 0: Design Finalization

Resolve the open design questions identified in the evaluation before writing
code. Changing the grammar after implementation begins is expensive.

- [x] Project name: **PicoDoc**, file extension `.pdoc`
- [x] Resolve heading alias syntax: `#-` (h1), `#--` (h2), `#---` (h3), etc.
- [x] Remove `\`, `?`, `=` from identifier character set
- [x] Narrow identifier characters: removed `<`, `>`, `|`, `'` from valid
      set. Remaining special chars: `! $ % & * + - / @ ^ _ ~`
- [x] Argument syntax: `=` for named arguments, `:` for body separator
- [x] Two-form call model: colon always required before body in both forms.
      `name=value` requires no whitespace before `=` (one-token lookahead)
- [x] `\=` added to valid escape sequences
- [x] Define escape sequences: `\xHH` (codepoint U+0000-U+00FF),
      `\UHHHHHHHH` (8 fixed hex digits, full Unicode range)
- [x] Define macro expansion order: recursive multi-pass AST walking with
      global max depth (configurable, default ~64) and per-macro `depth:`
      parameter on `#set` (`depth=N`)
- [x] Out-of-order definitions: macros may be used before defined; all `#set`
      definitions collected in first pass before resolution
- [x] Duplicate definitions at same scope are an immediate error
- [x] Default values evaluated during resolution pass, not at definition time
- [x] List syntax: `#ul`/`#ol` with `#*` (alias `#li`) items
- [x] Table syntax: simple pipe-delimited form (macro parses body, emits
      `#tr`/`#th`/`#td` for re-expansion) and explicit macro form for full
      control. Macro-specific body parsing is an accepted design pattern
- [x] Conditionals: `#ifeq`/`#ifne` (string comparison), `#ifset` (definition
      exists, privileged builtin). Future: `#iflt`/`#ifgt`/`#ifle`/`#ifge`.
      No expression language; complex logic belongs in external filters
- [x] Include: `#include file="..."` (privileged builtin, reads from disk)
- [x] Builtin macros have privileged access to evaluator internals; user
      macros and external filters do not
- [ ] Define external filter protocol (JSON on stdin, text on stdout)
- [ ] Define `env.*` global environment semantics
- [ ] Write formal grammar (EBNF or PEG notation)
- [ ] Create a comprehensive set of example documents that exercise all features
- [x] Fix typos and inconsistencies in the spec (spelling, `=p` examples)

**Exit criteria:** A complete, unambiguous grammar specification and a set of
example documents with expected HTML output.

## Phase 1: Lexer

Build the tokenizer that converts source text into a token stream.

- [ ] Set up Python project structure (pyproject.toml, uv, ruff, ty)
- [ ] Define token types (hash, identifier, equals, colon, string literal,
      raw string literal, square brackets, bareword, whitespace, newline,
      escape sequence, EOF)
- [ ] Implement core lexer with position tracking (line, column) for errors
- [ ] Implement interpreted string literal lexing (escape processing, code
      mode via `\[...]` for macro expansion, no implicit macro scanning)
- [ ] Implement raw string literal lexing (fully opaque, quote counting)
- [ ] Implement whitespace stripping rules for multiline string literals
- [ ] Implement escape sequence processing (`\#`, `\[`, `\]`, `\:`, `\=`,
      `\xHH`, `\UHHHHHHHH`)
- [ ] Error reporting with line/column and context snippet
- [ ] Test suite: valid token sequences, invalid sequences with expected errors

**Exit criteria:** Lexer correctly tokenizes all example documents and rejects
all known invalid inputs with clear error messages.

## Phase 2: Parser

Build the parser that converts the token stream into an AST.

- [ ] Define AST node types (Document, Paragraph, MacroCall, MacroArg,
      StringLiteral, RawStringLiteral, BareText, etc.)
- [ ] Implement recursive descent parser
- [ ] Implement macro call parsing (hash + identifier + arguments)
- [ ] Implement named argument parsing (identifier + equals + value)
- [ ] Implement `body` argument parsing (positional, paragraph, multi-line)
- [ ] Implement square bracket grouping and nesting
- [ ] Implement bare paragraph detection and auto `#p` insertion
- [ ] Greedy argument consumption to end of line
- [ ] Error reporting: unexpected tokens, missing arguments, unknown arguments
- [ ] Test suite: AST structure verification for all example documents

**Exit criteria:** Parser produces correct ASTs for all example documents and
rejects malformed input with helpful messages.

## Phase 3: Built-in Macros and HTML Renderer

Implement the core built-in macros and the HTML output renderer.

- [ ] Define built-in macro registry with parameter declarations
- [ ] Implement structural macros: `#title`/`#h1`/`#-`, `#h2`/`#--`,
      `#h3`/`#---`, `#h4`, `#h5`, `#h6`, `#p`, `#hr`
- [ ] Implement inline macros: `#b`/`#**`, `#i`/`#__`, `#url`
- [ ] Implement `#code` (with language attribute for syntax class)
- [ ] Implement `#literal` (pass-through, no processing)
- [ ] Implement `#comment` (excluded from output)
- [ ] Implement HTML document macros: `#meta`, `#link`, `#script`, `#lang`
- [ ] Implement list macros: `#ul`, `#ol`, `#*`/`#li`
- [ ] Implement table macros: `#table` (with pipe-delimited body parsing),
      `#tr`, `#td`, `#th` (for explicit form)
- [ ] Validate that `#table` output re-expansion works via multi-pass evaluator
- [ ] Implement `#include` (privileged: file reading)
- [ ] Implement `#ifeq`, `#ifne` (string comparison, return body or empty)
- [ ] Implement `#ifset` (privileged: queries definition registry)
- [ ] Implement HTML renderer (AST -> HTML string)
- [ ] Handle HTML escaping of text content (prevent XSS from document text)
- [ ] Implement full HTML document output (doctype, head, body wrapping)
- [ ] Test suite: `.pdoc` input -> expected `.html` output pairs

**Exit criteria:** Can convert the example documents into correct, valid HTML.

## Phase 4: User-Defined Macros (`#set`)

Implement the `#set` macro for user-defined macros within documents.

- [ ] Implement `#set` parsing (dynamic parameter list, optional `depth:`)
- [ ] Implement definition collection pass (gather all `#set` nodes)
- [ ] Implement out-of-order definition resolution
- [ ] Implement duplicate definition detection (same scope = immediate error)
- [ ] Implement default argument values (evaluated during resolution pass,
      after all definitions collected; may require multiple expansion passes)
- [ ] Implement required argument validation (`?` marker)
- [ ] Implement the `body` parameter in user macros
- [ ] Implement flat namespace with dot convention
- [ ] Implement variable/constant macros (zero-argument `#set`)
- [ ] Implement scope shadowing rules
- [ ] Test suite: macro definition, invocation, default values, shadowing,
      out-of-order use, duplicate detection, error cases

**Exit criteria:** User-defined macros work correctly, including out-of-order
definitions, default value resolution, and error cases.

## Phase 5: Evaluator (Multi-Pass Expansion)

Build the multi-pass macro expansion engine that resolves all macro calls in
the AST.

- [ ] Implement multi-pass AST walker (walk, expand, mark complete, re-walk)
- [ ] Implement convergence detection (terminate when no nodes changed)
- [ ] Implement global max recursion depth (configurable via CLI/config,
      default ~64)
- [ ] Implement per-macro `depth:` limit (0 = output is final, no re-expansion)
- [ ] Implement argument binding and scope creation at call sites
- [ ] Implement `env.*` global environment
- [ ] Handle expansion errors (undefined macro, depth limit exceeded, with
      context: which macro, expansion chain)
- [ ] Implement `--debug` flag to dump AST state after each expansion pass
- [ ] Test suite: expansion of nested calls, scope isolation, env inheritance,
      depth limits, convergence, mutual recursion detection

**Exit criteria:** Full pipeline works end-to-end: source -> tokens -> AST ->
collected definitions -> resolved defaults -> expanded AST -> HTML.

## Phase 6: CLI Tool

Build the command-line interface for the converter.

- [ ] Implement CLI with argument parsing (input file, output file, stdout)
- [ ] Accept environment variables as macro definitions (`-e name=value`)
- [ ] Accept config file for default settings
- [ ] Support specifying CSS/JS files to include in output
- [ ] Support adding meta tags from CLI
- [ ] Implement external filter protocol
  - [ ] Filter discovery (PATH, config, local directory)
  - [ ] Filter invocation (JSON on stdin, text on stdout)
  - [ ] Filter timeout and error handling
- [ ] Watch mode for development (recompile on file change)
- [ ] Exit code conventions (0 success, 1 syntax error, 2 runtime error)
- [ ] Test suite: CLI argument parsing, filter invocation, end-to-end

**Exit criteria:** Usable command-line tool that can convert documents and
invoke external filters.

## Phase 7: Editor Support

Provide syntax highlighting and editor integration.

- [ ] Write a tree-sitter grammar for the language
- [ ] Neovim syntax highlighting via tree-sitter
- [ ] VS Code extension with TextMate grammar (simpler, broader reach)
- [ ] Basic LSP server
  - [ ] Diagnostics (syntax errors as you type)
  - [ ] Go-to-definition for user-defined macros
  - [ ] Hover documentation for built-in macros
  - [ ] Completion for macro names and argument names

**Exit criteria:** Syntax highlighting works in at least one editor. LSP
provides diagnostics and completion.

## Phase 8: Documentation and Ecosystem

- [ ] Language reference documentation (ideally written in the language itself)
- [ ] Tutorial / getting started guide
- [ ] Example documents covering common use cases
- [ ] A standard library of useful macros (admonitions, figures, TOC, etc.)
- [ ] Package/distribution (PyPI)
- [ ] Consider Rust port for performance and WASM compilation

## Dependencies Between Phases

```
Phase 0 (Design)
    |
    v
Phase 1 (Lexer) --> Phase 2 (Parser) --> Phase 3 (Built-ins + Renderer)
                                              |
                                              v
                                         Phase 4 (#set) --> Phase 5 (Evaluator)
                                                                |
                                                                v
                                                           Phase 6 (CLI)
                                                                |
                                                                v
                                                           Phase 7 (Editor)
                                                                |
                                                                v
                                                           Phase 8 (Ecosystem)
```

Phase 0 must be complete before any implementation begins. Phases 1-5 are
strictly sequential. Phase 7 can begin in parallel with Phase 6 once the
grammar is stable (after Phase 2).
