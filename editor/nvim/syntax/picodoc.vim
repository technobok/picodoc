" Vim syntax file for PicoDoc (.pdoc)
if exists('b:current_syntax')
  finish
endif

" --- Comments ---------------------------------------------------------------
syn region picodocComment start=/#comment\s*:/ end=/$/ contains=@NoSpell
syn region picodocComment start=/\[#comment\>/ end=/\]/ contains=@NoSpell

" --- Raw strings (triple-quoted, no escapes) --------------------------------
syn region picodocRawString start=/"""/ end=/"""/

" --- Interpreted strings with escapes ---------------------------------------
syn region picodocString start=/"/ skip=/\\"/ end=/"/ contains=picodocStringEscape
syn match picodocStringEscape /\\[\\"\[\]nt]/ contained
syn match picodocStringEscape /\\x\x\{2}/ contained
syn match picodocStringEscape /\\U\x\{8}/ contained

" --- Prose escapes (outside strings) ----------------------------------------
syn match picodocProseEscape /\\[\\#\[\]:=]/
syn match picodocProseEscape /\\x\x\{2}/
syn match picodocProseEscape /\\U\x\{8}/

" --- Macro calls: # prefix + name ------------------------------------------
" Structural macros
syn match picodocStructural /#\%(title\|h[1-6]\|-\{1,3}\|p\|hr\)\>/
" Conditional / expansion-time macros
syn match picodocConditional /#\%(set\|ifeq\|ifne\|ifset\|include\)\>/
" Inline macros
syn match picodocInline /#\%(\*\*\|__\|b\|i\|url\)\>/
" Environment variable pattern
syn match picodocEnv /#env\.[A-Za-z0-9._\-]*/
" Comment macro (hash form — region above handles the full extent)
syn match picodocMacroHash /#/ contained containedin=picodocStructural,picodocConditional,picodocInline,picodocEnv
" Fallback: any other #identifier
syn match picodocMacroName /#[A-Za-z!$%&*+\-/@^_~.][A-Za-z0-9!$%&*+\-/@^_~.]*/

" --- Bracketed calls [#...] ------------------------------------------------
syn region picodocBracketCall matchgroup=picodocBracket start=/\[#/ end=/\]/ transparent contains=TOP

" --- Arguments: name=value --------------------------------------------------
syn match picodocEquals /=/ contained containedin=picodocArgAssign
syn match picodocArgAssign /[A-Za-z][A-Za-z0-9_.-]*=/ contains=picodocArgName,picodocEquals
syn match picodocArgName /[A-Za-z][A-Za-z0-9_.-]*\ze=/ contained

" --- List item alias --------------------------------------------------------
syn match picodocStructural /#\*\>/
syn match picodocStructural /#li\>/

" --- Highlight links --------------------------------------------------------
hi def link picodocComment      Comment
hi def link picodocMacroHash    Keyword
hi def link picodocMacroName    Function
hi def link picodocStructural   Statement
hi def link picodocConditional  Conditional
hi def link picodocInline       Type
hi def link picodocEnv          Macro
hi def link picodocString       String
hi def link picodocRawString    String
hi def link picodocStringEscape SpecialChar
hi def link picodocProseEscape  SpecialChar
hi def link picodocArgName      Identifier
hi def link picodocEquals       Operator
hi def link picodocBracket      Delimiter

let b:current_syntax = 'picodoc'
