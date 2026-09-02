; Tests fuer Quasiquote/Backquote + CL-Stil DEFMACRO (Host-Prototyp).
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/backquote-tests.lsp
;
; Hinweis: '`' ist auf dem Host (PC) verfuegbar; auf dem echten C64 braeuchte
; Quasiquote ein Ersatzzeichen (kein Backtick in PETSCII) -- siehe
; docs/dialect-vs-cl.md. ',' und ',@' sind auf dem C64 vorhanden.

; ---- Quasiquote-Grundfaelle ----
(CHECK `(A B C) '(A B C))                 ; ohne Unquote = wie QUOTE
(CHECK `NN 'NN)                           ; Atom

(SETQ X 5)
(CHECK `(A ,X C) '(A 5 C))                ; Unquote
(CHECK `(,X . ,X) '(5 . 5))               ; gepunktetes Unquote
(CHECK `(A (B ,X) C) '(A (B 5) C))        ; verschachtelt

(SETQ L '(1 2))
(CHECK `(A ,@L C) '(A 1 2 C))            ; Splicing
(CHECK `(,@L ,@L) '(1 2 1 2))           ; mehrfaches Splicing

; ---- DEFMACRO (CL-Stil: Parameter = Operandenformen, Backquote im Body) ----
(DEFMACRO MYINC (V) `(SETQ ,V (ADD1 ,V)))
(SETQ K 10)
(MYINC K)
(CHECK K 11)

(DEFMACRO MYIF (C TH EL) `(COND (,C ,TH) (T ,EL)))
(CHECK (MYIF T 1 2) 1)
(CHECK (MYIF NIL 1 2) 2)

; nospread-DEFMACRO + Splicing der ganzen Argumentliste
(DEFMACRO MYLIST ARGS `(LIST ,@ARGS))
(CHECK (MYLIST 1 2 3) '(1 2 3))

(CHECK-REPORT)
