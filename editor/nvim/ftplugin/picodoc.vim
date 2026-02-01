" Filetype plugin for PicoDoc (.pdoc)
if exists('b:did_ftplugin')
  finish
endif
let b:did_ftplugin = 1

setlocal commentstring=#comment:\ %s
setlocal shiftwidth=2
setlocal expandtab
setlocal softtabstop=2
setlocal iskeyword+=.,-,*,!,$,%,&,+,/,@-@,^,~

let b:undo_ftplugin = 'setlocal commentstring< shiftwidth< expandtab< softtabstop< iskeyword<'
