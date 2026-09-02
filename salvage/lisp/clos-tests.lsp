; Tests fuer Mini-CLOS (Single-Dispatch, Host-Prototyp).
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/cl-compat.lsp \
;         lisp/lib-clos.lsp lisp/clos-tests.lsp

(DEFCLASS SHAPE () NAME)
(DEFCLASS CIRCLE (SHAPE) RADIUS)
(DEFCLASS SQUARE (SHAPE) SIDE)

(DEFMETHOD AREA ((C CIRCLE))
  (TIMES 3 (TIMES (SLOT-VALUE C 'RADIUS) (SLOT-VALUE C 'RADIUS))))   ; pi~=3
(DEFMETHOD AREA ((S SQUARE))
  (TIMES (SLOT-VALUE S 'SIDE) (SLOT-VALUE S 'SIDE)))
(DEFMETHOD DESCRIBE-IT ((S SHAPE)) 'A-SHAPE)   ; auf der Superklasse

(SETQ C (MAKE-INSTANCE 'CIRCLE :RADIUS 10 :NAME 'C1))
(SETQ SQ (MAKE-INSTANCE 'SQUARE :SIDE 5))

; ---- Dispatch auf die konkrete Klasse ----
(CHECK (AREA C) 300)
(CHECK (AREA SQ) 25)
(CHECK (CLASS-OF C) 'CIRCLE)

; ---- ererbter Slot + ererbter Methoden-Dispatch (CIRCLE -> SHAPE) ----
(CHECK (SLOT-VALUE C 'NAME) 'C1)
(CHECK (DESCRIBE-IT C) 'A-SHAPE)
(CHECK (DESCRIBE-IT SQ) 'A-SHAPE)

; ---- Slot setf-faehig ----
(SETF (SLOT-VALUE C 'RADIUS) 1)
(CHECK (AREA C) 3)
(SETF (SLOT-VALUE C 'NAME) 'NEU)
(CHECK (SLOT-VALUE C 'NAME) 'NEU)

; ---- Methoden-Redefinition gewinnt ----
(DEFMETHOD AREA ((S SQUARE)) 999)
(CHECK (AREA SQ) 999)

; ---- spezifischere Methode schlaegt allgemeinere ----
(DEFMETHOD WHO ((S SHAPE)) 'SHAPE)
(DEFMETHOD WHO ((C CIRCLE)) 'CIRCLE)
(CHECK (WHO C) 'CIRCLE)     ; CIRCLE-Methode, nicht SHAPE
(CHECK (WHO SQ) 'SHAPE)     ; SQUARE erbt SHAPE-Methode

; ---- T-Fallback (Nicht-Instanz dispatcht ueber Klasse T) ----
(DEFMETHOD GREET ((X T)) 'HELLO)
(CHECK (GREET 42) 'HELLO)
(CHECK (GREET C) 'HELLO)

; ---- fehlende Slots -> NIL ----
(SETQ S2 (MAKE-INSTANCE 'SHAPE))
(CHECK (SLOT-VALUE S2 'NAME) NIL)

(CHECK-REPORT)
