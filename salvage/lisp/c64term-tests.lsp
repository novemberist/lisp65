; Tests fuer lib-c64term -- die Phase-5-Ausgabe-Bruecke, gegen das ECHTE 64-KB-
; RAM-Modell der Host-PEEK/POKE (kein Mock): poken, dann zuruecklesen.
;
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/lib-macros.lsp \
;   lisp/cl-compat.lsp lisp/lib-c64hw.lsp lisp/lib-c64fx.lsp lisp/lib-c64io.lsp \
;   lisp/lib-c64term.lsp lisp/editor-core.lsp lisp/lib-edit-commands.lsp \
;   lisp/lib-buffers.lsp lisp/lib-ide-session.lsp lisp/lib-ide-undo.lsp \
;   lisp/lib-ide-view.lsp lisp/c64term-tests.lsp

; ---- Char -> Screen-Code, eindeutige Faelle ----
(CHECK (char->screencode " ") 32)        ; Space
(CHECK (char->screencode "A") 1)         ; 65 -> 1
(CHECK (char->screencode "Z") 26)        ; 90 -> 26
(CHECK (char->screencode "0") 48)        ; Ziffer unveraendert
(CHECK (char->screencode "!") 33)        ; Satzzeichen unveraendert

; ---- term-puts schreibt Screen-Codes ins echte Screen-RAM ($0400) ----
(term-puts 3 2 "HI")
(CHECK (screen-at 3 2) 8)                 ; H=72 -> 8
(CHECK (screen-at 4 2) 9)                 ; I=73 -> 9
; an die korrekte lineare Adresse: $0400 + 2*40 + 3 = 1024+83 = 1107
(CHECK (PEEK 1107) 8)

; ---- term-blit: ein Mehrzeilen-Modell ----
(term-blit (LIST "AB" "CD"))
(CHECK (screen-at 0 0) 1)                 ; A
(CHECK (screen-at 1 0) 2)                 ; B
(CHECK (screen-at 0 1) 3)                 ; C
(CHECK (screen-at 1 1) 4)                 ; D

; ---- Phase-8<->5-Bruecke: eine echte IDE-Frame in Screen-RAM rendern ----
(DE demo-ed (strs) (mk-ed (mapcar (QUOTE str->line) strs) 0 0))
(SETQ APP (app-new (ss-new
  (bs-add (bs-mk () "") "ED" (demo-ed (list "HELLO"))))))
(term-render-app APP 8 4)                 ; 8 breit, 4 hoch (2 Edit + Modeline + MB)
(CHECK (screen-at 0 0) 8)                 ; H
(CHECK (screen-at 1 0) 5)                 ; E=69 -> 5
(CHECK (screen-at 4 0) 15)               ; O=79 -> 15
; Modeline-Zeile (Index 2) beginnt mit "-" (45 -> unveraendert, 32..63)
(CHECK (screen-at 0 2) 45)

(CHECK-REPORT)
