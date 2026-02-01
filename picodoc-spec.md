# Markup language

## Brief

- design a new markup language
- primary and perhaps only target is html
- project name: PicoDoc, file extension .pdoc
- aim to have a regular simple syntax 
- consider using asciidoc as inspiration for simple markup without attempting
  to reimplement its complicated syntax
- the parser should be strict rather than accepting. Want to 'fail fast' by
  either erroring with a helpful error message or including some obvious error
  in the output that can be used for debugging the source

## Document and Lexical structure

- document character encoding is always UTF8
- document cannot contain NUL (0) characters
- the basic (only?) abstraction would be the macro
- identifiers used in the language consist of one or more letters, digits, dots
  or special characters: ! $ % & * + - / @ ^ _ ~
- macros are invoked by having a hash (#) followed by the macro identifier.
  Hash acts like an operator.
- macros can have 0 or more arguments which all must be named in definitions
  and in calls (not positional; but see exception for 'body' argument which may
  be positional in calls)
- macros can have named parameters and arguments which are of the form: an
  identifier (naming the argument) followed immediately by an equals sign
  (no whitespace before the equals sign), followed by the argument value.
  Whitespace between the equals sign and the value is permitted:
  "name=value" and "name= value" are both valid. "name =value" and
  "name = value" are not (see macro call processing for why)
- in a macro definition, the 'value' of the parameter is a default value, a
  macro call (the default value will be the result of this call, evaluated
  during the resolution pass after all definitions are collected) or a question
  mark ('?') for a required argument
- in a macro call, the 'value' of the argument is one of: a bareword, a string
  literal or another macro call (which would usually be in square brackets to
  delineate its arguments from those of the outer call)
- the return values of all macros are strings/text
- all arguments to macros are strings/text. Since macro calls return text,
  calls can also be used as argument values in other calls
- multiple parameters/arguments (if supplied/required) are whitespace separated
  (no commas)
- there would be many builtin macros (eg  #title (also #h1, also #-), #h2 (also
  #--), #h3 (also #---), #p (paragraph), #b (bold also #**), #i (italic also
  #__), #hr, #url, #comment, #ul, #ol, #* (list item, also #li), #table,
  #tr, #td, #th, #include, #ifeq, #ifne, #ifset
- builtin macros are implemented natively within the evaluator and have
  privileged access to evaluator internals (definition registry, environment,
  expansion context). User-defined macros (#set) operate only on their
  arguments and body. External filter macros receive arguments on stdin.
  Only builtins can query internal state (eg #ifset checking if a macro is
  defined, #include reading files from disk)
- backslash can be used to escape characters to use their literal values.
  Backslash can only be used in the following cases and all other uses will be
  a syntax error; capital H is used to represent a single hex digit which must
  be specified: \# \[ \] \: \= \xHH \UHHHHHHHH
- \xHH is used to specify a Unicode codepoint by the hex value of HH
  (codepoints U+0000 to U+00FF)
- \UHHHHHHHH is used to specify any Unicode codepoint by the hex value of
  HHHHHHHH (8 fixed hex digits, codepoints U+00000000 to U+0010FFFF)
- the question mark ('?') has special meaning only within a macro definition
  ('set'), outside of that it is standard document text. It can not be escaped.
- users can define new macros externally as command line filters. See the
  "External filters" section for the protocol
- global values are defined via the env.* namespace. See the "Global
  environment" section for semantics
- users could also define simple macros inline within the document with set
- a macro with no arguments is essentially a variable/constant
- the namespace for macros is flat. But dots (".") can be used in macro names
  to emulate a namespace for grouping similar macro definitions under the same
  prefix. The "fully qualified" name must always be used to invoke a macro
- optionally or to force precedence, a macro call can be surrounded by square
  brackets. 
- arguments can have default values that will be used if not provided at the
  call site (defined after the equals sign following the parameter name in the
  macro definition). Default values are evaluated during the resolution pass
  after all definitions are collected. A default value may be a macro call,
  which will be expanded during resolution (potentially requiring multiple
  expansion passes if the referenced macro itself has dependencies).

## The 'body' parameter/argument

- there is a special 'body' argument. If required in a macro, it must be the
  last parameter specified in the definition and it must not have a default
  value
- in macro definitions (#set), the body parameter is declared by name using
  'body=?' (required) or 'body=default' (with default value). This is the same
  syntax as other parameters
- at call sites, body content is introduced by a colon (':') or by a string
  literal:
  - a colon is required before plain text body content. Whitespace around the
    colon is flexible
  - a string literal (interpreted or raw) may serve as body without a
    preceding colon. A colon before a string literal body is permitted but
    not required, allowing lean syntax for inline calls: #*"bold"
  - after the colon, if text follows on the same line, that text to end of
    line is the body (unbracketed) or to the closing bracket (bracketed)
  - after the colon, if only whitespace or nothing remains on the line, the
    following paragraph is the body
  - in bracketed calls, body extends to the closing bracket and may span
    multiple lines/paragraphs
  - if no colon and no string literal is present, the macro call has no body.
    Any remaining text on the line (unbracketed) is prose, not body content
- a paragraph is a group of contiguous lines of text, ending with a blank line
  or EOF
- paragraph body within square brackets continues until the closing bracket,
  including multiple paragraphs


## Other Arguments

- all non-'body' parameters/arguments must be named in calls (not positional)
- named arguments may appear in both unbracketed and bracketed forms
- parameters with default values can be omitted from calls in which case, their
  default values will be used for the call
- parameters with default values can be overridden by supplying a value at the
  call site
- named argument values may be a single bareword after the equals sign provided
  it is a simple word with no characters that have meaning to the markup
  processor (such as '=' or ':') or any whitespace within it
- any argument value including 'body' can also be specified as a string
  literal.

## String literals

- string literals may be used to express argument values in calls
- there are 2 forms of string literal: interpreted string literals and raw
  string literals
- interpreted string literals start with a single double quote (") and end with
  the same
- text within an interpreted string literal is literal by default. Escape
  sequences are processed but macro calls are NOT automatically scanned for
- to embed macro calls within an interpreted string, use \[ to enter 'code
  mode'. Code mode ends at the matching closing ]. Inside \[...], normal
  macro call syntax applies including nested bracketed calls, named arguments
  and body content. Code mode may span multiple lines
- the \[ escape has a different meaning inside interpreted strings (enter code
  mode) than outside strings (literal '['). This is not a conflict because
  '[' has no special meaning inside strings and does not need escaping
- example: "Dear \[#target], welcome" expands #target but everything else is
  literal text
- any double quote within an interpreted string literal must be escaped to
  prevent ending the string literal definition
- raw string literals begin with 3 or more double quote characters and end with
  the same number of double quote characters
- raw string contents are not processed in any way and can include any text,
  even text that is special to the markup language such as macro calls and
  escapes and a series of double quotes provided it is less in number than
  required for the closing delimiter. All will be left as literal text.
- the empty string literal is always represented by two double quotes (""). It
  is not possible to have an empty raw string literal because counting the
  double quotes in the opening delimiter is not possible because they run on to
  the closing delimiter
- for the same reason, a raw string literal cannot have a double quote
  character within it that is immediately after the opening delimiter or
  immediately before the closing delimiter.
- there are special whitespace handling rules within string literals that are
  handled the same way for both interpreted and raw strings
- if the remainder of the line after the opening delimiter is blank (contains
  only whitespace) then the remainder of that line is not included in the
  result of the string literal
- if the beginning of the line before the closing delimiter is blank (contains
  only whitespace) then that whitespace is not included in the result of the
  string literal
- if the beginning of the line before the closing delimiter is blank (contains
  only whitespace (spaces and tabs)) AND provided that whitespace is present in
  exactly the same combination and number of tabs and spaces on all other lines
  of the string literal, then that amount of whitespace only is stripped from
  all lines in the string literal. This allows indenting within the markup
  language 'code' that does not affect the resulting document.

## Macro call processing

- there are two forms of macro call: unbracketed and bracketed. The parser
  does not need to consult macro definitions to parse either form.

### Unbracketed form

- a macro call begins with '#' followed immediately by the macro identifier.
  The identifier ends at the first non-identifier character. Whitespace, ':',
  '"' and other non-identifier characters all terminate the identifier
- after the identifier, the parser looks at the next token:
  - if the token matches 'identifier=' (no whitespace before '='), it enters
    argument mode and consumes name=value pairs
  - if the token is ':' it enters body mode (plain text or string literal)
  - if the token is a string literal opening ('"' or '"""'), it enters body
    mode with the string literal as body
  - otherwise the call is complete with no arguments and no body. Remaining
    text on the line is prose
- in argument mode, the parser continues consuming name=value pairs until it
  sees ':' (body mode), a string literal opening (body mode) or end of line
  (call complete, no body)
- in body mode with colon: if text follows the colon on the same line, body
  extends to end of line. If only whitespace or nothing follows the colon,
  the following paragraph is the body
- in body mode with string literal: the string literal is the body
- note: if a user mistakenly writes 'name = value' (whitespace before '='),
  the parser will not recognise it as an argument. It will be silently treated
  as prose. The bracketed form catches this as a syntax error

### Bracketed form

- a macro call is enclosed in square brackets: [#identifier ...]
- square brackets can also be used around unbracketed-style calls to force
  precedence or clarify boundaries, eg [#b some text] within a line
- after the identifier, zero or more named arguments may appear as name=value
  pairs, whitespace separated
- argument values may be barewords, string literals, or nested macro calls
  (in their own square brackets)
- a colon (':') or a string literal introduces body content. If neither is
  present, the call has no body
- after the colon, everything until the matching closing square bracket is
  body content, including any linefeeds and multiple paragraphs
- a string literal after the identifier or arguments (with no preceding colon)
  is also body. A colon before a string literal body is permitted
- bare text inside brackets that is not a name=value pair and not preceded by
  a colon or string literal delimiter is a syntax error
- any arguments provided that are not listed in the macro definition are a
  syntax error (detected at evaluation time, not parse time)

### Common rules

- argument values that are string literals may have embedded linefeeds within
  that literal. Argument processing will continue after the closing delimiter.
- invocation of the macro will create a new scope at the call site that
  defines the argument values at that point in time
- local argument names will shadow any definitions outside the macro call that
  have the same name

## Macro definition

- to define a macro, use the #set macro in bracketed form
- the set macro has a required argument called "name" that specifies the name
  of the macro being defined
- it may then specify other arguments which may have default values (after
  equals) or a question mark ('?') for required: name=? or name=default
- if the macro uses the "body" argument, it must also be declared as a
  parameter (body=?) and it must be the last argument
- the 'set' macro is unusual in that the arguments (other than 'name' and
  'body') are not predefined within its definition. The arguments are open
  ended because the names of these arguments themselves will be the names of
  the required arguments in the resulting macro definition
- the body of 'set' (after the colon) contains the template of the macro that
  will be processed in the presence of the local arguments and any referenced
  definitions higher in the call stack and returned to be embedded in place of
  the macro call at the call site
- macro expansion uses recursive multi-pass AST walking. After parsing, the
  evaluator walks the AST expanding macro nodes, marks fully-expanded nodes as
  complete, and re-walks until all nodes are resolved or the depth limit is hit
- a global max recursion depth (configurable via CLI/config) catches infinite
  or excessive expansion. A sensible default (eg 64) is used if not specified
- individual macros may specify a 'depth' parameter in their #set definition
  to limit output re-expansion depth. depth=0 means the macro's output is
  final text and will not be re-parsed for further macro calls. If unset, the
  global limit applies. Depth tracks full call stack depth; self-recursion is
  not considered separately
- out-of-order definition and use is allowed: macros may be used before they
  are defined in the document. The compiler collects all #set definitions in a
  first pass before resolving and expanding
- duplicate macro definitions at the same scope are an immediate error
- #set is restricted to top-level only. It cannot appear inside macro bodies.
  This is consistent with the flat namespace design and avoids scoping
  complexity. This restriction may be relaxed in the future if needed

## Other syntax sugar

- a bare paragraph (ie. not part of a macro call) is assumed to be wrapped in
  an implicit #p call with the paragraph as body content

## Other implementation considerations

- design a treesitter grammar for this markup language, or an LSP?
- implementation of a converter for the markup language is: lexer (source to
  token stream), parser (tokens to AST), evaluator (multi-pass AST walking),
  then renderer (expanded AST to HTML)
- there will be macros for specifying meta, link, script, lang (argument to
  html tag) etc
- the converter app would need to be able to accept, envvars, config or command
  line arguments that can be used to specify externally some macros, can add
  some meta tags, can define some css and js files and inlines that may be
  required in the resulting document

## Built-in macro categories

- built-in macros fall into two categories: expansion-time and render-time
- expansion-time macros are fully resolved during the evaluation phase. They
  transform, produce markup, or disappear from the AST entirely:
  - #set (definition, removed from AST after collection)
  - #table (pipe-delimited form: parses body, emits #tr/#th/#td calls)
  - #ifeq, #ifne, #ifset (return body or empty string)
  - #include (replaced by included file contents)
  - #comment (removed from AST)
- render-time macros survive expansion as structured nodes in the AST. The
  renderer maps them to HTML elements:
  - structural: #title/#h1/#-, #h2/#--, #h3/#---, #h4, #h5, #h6, #p, #hr
  - inline: #b/#**, #i/#__, #url
  - code: #code, #literal
  - lists: #ul, #ol, #*/#li
  - tables: #tr, #td, #th (from explicit form or emitted by #table)
  - document: #meta, #link, #script, #lang
- after expansion completes, the AST contains only text nodes and render-time
  built-in nodes with fully resolved arguments and body
- the renderer walks this structured tree, validates nesting (eg #td only
  inside #tr inside #table), handles HTML escaping, and produces the final
  HTML document with proper structure (doctype, head, body)
- this separation allows alternative renderers for other output formats
  against the same expanded AST

## Lists

- unordered lists use #ul, ordered lists use #ol
- list items use #* (alias #li)
- list macros validate at evaluation time that their body contains only
  list item elements
- nested lists are expressed by nesting #ul/#ol inside a bracketed #* call

Example:
[#ul :
  #*: First item
  #*: Second item
  [#* : Third item with sublist
    [#ul :
      #*: Nested A
      #*: Nested B
    ]
  ]
]

[#ol :
  #*: Step one
  #*: Step two
]

## Tables

- tables support two forms: a simple pipe-delimited format and an explicit
  macro form. Both can coexist
- macro implementations may parse their body content in macro-specific ways.
  The parser treats all bodies as opaque text; complexity lives within the
  macro implementation, not the language syntax

### Simple table form

- the #table macro parses its body as pipe-delimited rows
- the first row is treated as headers (#th), subsequent rows as data (#td)
- cells may contain macro calls which will be expanded in subsequent passes
- the #table macro emits #tr/#th/#td macro calls as its output. These are
  not yet expanded. The multi-pass evaluator picks them up on the next pass
  and expands them, including any embedded macro calls within cells

Example:
#table:
  Name | Age | Status
  Alice | 30 | [#**"active"]
  Bob | 25 | [#**"inactive"]

The #table macro transforms this into:
[#tr : [#th: Name] [#th: Age] [#th: Status]]
[#tr : [#td: Alice] [#td: 30] [#td: [#**"active"]]]
[#tr : [#td: Bob] [#td: 25] [#td: [#**"inactive"]]]

Which is then expanded by subsequent evaluator passes.

### Explicit table form

- for full control over table structure, use #table with #tr, #td, #th
  directly
- allows colspan/rowspan via named arguments, #thead/#tbody structure, and
  arbitrary macro calls in cells

Example:
[#table :
  [#tr : [#th: Name] [#th: Age]]
  [#tr : [#td: Alice] [#td: 30]]
  [#tr : [#td span=2 : Total: 2 people]]
]

## Include

- #include inserts the contents of another file into the document
- the included file is parsed and expanded as if its contents appeared at
  the call site
- #include is a privileged builtin that reads files from disk

Example:
[#include file="header.pdoc"]

## Conditionals

- conditional macros test a condition and return their body if the condition
  is true, or an empty string if false
- no expression language exists in PicoDoc. Conditions are limited to simple
  comparisons via specialised macros
- #ifeq: string equality. Returns body if lhs equals rhs
- #ifne: string inequality. Returns body if lhs does not equal rhs
- #ifset: returns body if the named macro is defined. This is a privileged
  builtin that queries the definition registry
- future extensions may include #iflt, #ifgt, #ifle, #ifge for numeric or
  lexicographic comparison. All follow the same pattern: condition arguments
  plus body, return body or empty string
- complex conditional logic belongs in external filters

Examples:
[#ifeq lhs=[#env.mode] rhs=draft : This document is a draft.]

[#ifne lhs=[#env.mode] rhs=production : Not yet published.]

[#ifset name=env.author : Written by [#env.author].]

## External filters

- external filters allow users to define macros as command line programs in
  any language
- the filter receives a JSON object on stdin containing all named arguments
  (including 'body' if present) and all env.* values:
  {"arg1": "value1", "body": "the body text", "env": {"mode": "draft"}}
- the filter returns PicoDoc markup on stdout. The multi-pass evaluator
  expands any macro calls in the output on subsequent passes. This is
  consistent with how #set and #table work
- a filter that wants to return final HTML can wrap its output in #literal
  to prevent further expansion. A filter returning plain text with no macro
  calls passes through unchanged
- the depth parameter on the filter's macro registration applies: depth=0
  means the output is treated as final text regardless
- filter discovery: the converter checks a filters/ directory alongside the
  document, then a configured filter path, then $PATH. The executable name
  maps to the macro name (or is configured via a registry/config file)
- filter timeout and error handling: a configurable timeout (default eg 5s)
  kills long-running filters. Non-zero exit codes from filters are treated
  as expansion errors with the filter's stderr included in the error message

## Global environment

- the env.* namespace provides global values accessible to all macros
- env values can be defined via:
  - CLI arguments: picodoc -e mode=draft -e author="Alice" input.pdoc
  - config file: key=value pairs under an [env] section
  - document-level #set: [#set name=env.mode : draft]
  - CLI and config values are set before document processing. Document-level
    #set definitions for env.* follow normal #set rules (collected first pass,
    duplicates are errors)
- env values are accessed as zero-argument macros: #env.mode or [#env.mode]
- env values are inherited through nested macro calls. A macro body can
  reference #env.mode and it will resolve from the global environment
- env values cannot be overridden locally within macro bodies. They are
  global and immutable once set. This prevents confusing action-at-a-distance
  where a macro silently changes global state
- for external filters, all env.* values are passed in the JSON payload
  under the "env" key
- CLI-provided env values take precedence over config file values.
  Document-level #set for env.* takes precedence over both (the document
  author has final say)

## Examples

#title: Title to end of line

#-: Title using dash alias

#--: Section heading using dash alias

this is #**"bold this"

this is [#mymacro arg1=a_single_word arg2="a quoted argument"]

[#set name=myvar : this is the myvar macro]

this is a call with a call as an argument: [#mymacro myvar=[#myinnermacro myinnervar=foo]]

url macro (named arguments, no body): [#url link="https://example.com" text="Click here"]

macro with named arguments and body (bracketed): [#code language=python : print("hello")]

macro with named arguments and body (unbracketed): #code language=python : print("hello")

[#code language=python : """
class myclass:
    def __init__(...):
        pass
"""]

#literal """
literal stuff
"""

this is
a paragraph

#p:
this is also
a paragraph

[#p :
this is also
a paragraph]

macro definition with body parameter:
[#set name=greeting target=? body=? : Dear [#target], [#body] Kind regards.]

calling it: [#greeting target=World : thank you for your support.]
