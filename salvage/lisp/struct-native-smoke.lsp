; lib-struct NATIVE-SMOKE -- minimaler, host-verifizierter Fixture-Satz fuer den
; DEFSTRUCT-Stufe-3-Smoke (GENSYM-FREI; nutzt DM + PACK, kein GENSYM).
;
; In ZWEI Stufen, die zwei getrennte native Voraussetzungen sauber trennen:
;   LESEPFAD  -- braucht NUR DM-Expansion + PACK + PUTPROP + Akzessor-DE.
;   SCHREIBPFAD -- braucht ZUSAETZLICH cl-compat SETF (die "kleine" Abhaengigkeit
;                  aus dem Audit). Faellt der Lesepfad gruen, der Schreibpfad rot,
;                  ist die Ursache eindeutig SETF, nicht DEFSTRUCT.
; Mapping -> native Abhaengigkeit: docs/phase6-stufe3-native-smoke-spec.md
;
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/cl-compat.lsp \
;       lisp/lib-struct.lsp lisp/struct-native-smoke.lsp

(DEFSTRUCT POINT X Y)

; ---- LESEPFAD (DM-Expansion + PACK-Namen + Keyword-Konstruktor + Akzessor) ----
(CHECK (POINT-X (MAKE-POINT (QUOTE :X) 3 (QUOTE :Y) 4)) 3)   ; positioneller Slot 1
(CHECK (POINT-Y (MAKE-POINT (QUOTE :X) 3 (QUOTE :Y) 4)) 4)   ; Slot 2 (NCDR-Walk)
(CHECK (POINT-P (MAKE-POINT (QUOTE :X) 1 (QUOTE :Y) 2)) T)    ; Typpraedikat (Tag)
(CHECK (POINT-P (QUOTE (NOTAPOINT 1 2))) NIL)                 ; Fremd-Tag abgelehnt

; ---- SCHREIBPFAD (zusaetzlich cl-compat SETF -> SETF-FN-Property -> RPLACA) ----
(SETQ P (MAKE-POINT (QUOTE :X) 3 (QUOTE :Y) 4))
(SETF (POINT-X P) 9)
(CHECK (POINT-X P) 9)

(CHECK-REPORT)
