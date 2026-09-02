; LISP 64 -- DEFSTRUCT-light (Host-Prototyp, Phase-6-Stufe-3-Bibliothek)
;
; Ein Makro, das aus (DEFSTRUCT NAME slot...) Konstruktor, Akzessoren, Praedikat
; und Kopierer generiert. Erzeugter Code ist klein; der Generator lebt PC-seitig
; (beim Cross-Compile null residenter RAM) -- siehe docs/optional-feature-tier.md.
;
; Repraesentation (light): eine Liste (NAME v1 v2 ... vn). CAR = Typ-Tag.
; Akzessoren sind ueber die SETF-FN-Property setf-faehig (braucht cl-compat SETF).
;
; (DEFSTRUCT POINT X Y) erzeugt:
;   (MAKE-POINT a b)   -> (POINT a b)        ; positionell
;   (POINT-X p)        -> Lesen   ; (SETF (POINT-X p) v) -> Schreiben
;   (POINT-P obj)      -> Typpraedikat
;   (COPY-POINT p)     -> flache Kopie
;
; Konstruktor ist KEYWORD-basiert (CL-konform): (MAKE-POINT :X 3 :Y 4), fehlende
; Slots -> NIL. Nutzt die Host-Keyword-Literale.
; GRENZE (Prototyp): keine Slot-Defaults, keine Vererbung (:include).

; (CDR (CDR ... VAR)) mit I CDRs als Form
(DE DS-NCDR (I VAR)
  (COND ((EQ I 0) VAR)
        (T (LIST 'CDR (DS-NCDR (SUB1 I) VAR)))))

; Laufzeit-Helfer: Wert zu KEY aus einer Keyword-Plist (Default NIL)
(DE DS-GETF (PLIST KEY)
  (COND ((NULL PLIST) NIL)
        ((EQ (CAR PLIST) KEY) (CADR PLIST))
        (T (DS-GETF (CDDR PLIST) KEY))))

; Keyword fuer einen Slot: SLOT -> :SLOT (interniert, via ':-Symbol)
(DE DS-KW (SLOT) (PACK (LIST ': SLOT)))

; (DS-GETF DS-KW ':SLOT) je Slot, fuer den LIST-Konstruktor-Rumpf
(DE DS-KW-GETTERS (SLOTS)
  (COND ((NULL SLOTS) NIL)
        (T (CONS (LIST 'DS-GETF 'DS-KW (LIST 'QUOTE (DS-KW (CAR SLOTS))))
                 (DS-KW-GETTERS (CDR SLOTS))))))

(DE DS-CONSTRUCTOR (NAME SLOTS)
  (LIST 'DE (PACK (LIST 'MAKE- NAME)) 'DS-KW
        (CONS 'LIST (CONS (LIST 'QUOTE NAME) (DS-KW-GETTERS SLOTS)))))

(DE DS-PRED (NAME)
  (LIST 'DE (PACK (LIST NAME '-P)) (LIST 'X)
        (LIST 'AND '(CONSP X) (LIST 'EQ '(CAR X) (LIST 'QUOTE NAME)))))

(DE DS-COPIER (NAME)
  (LIST 'DE (PACK (LIST 'COPY- NAME)) (LIST 'X)
        (LIST 'CONS '(CAR X) (LIST 'APPEND '(CDR X) NIL))))

; Definitionen fuer einen Slot an Position I (1-basiert in der Liste):
;   Leser NAME-SLOT, Setter SET-NAME-SLOT, SETF-FN-Registrierung
(DE DS-ONE-SLOT (NAME SLOT I)
  (PROG (ACC SET)
    (SETQ ACC (PACK (LIST NAME '- SLOT)))
    (SETQ SET (PACK (LIST 'SET- NAME '- SLOT)))
    (RETURN
      (LIST
        (LIST 'DE ACC (LIST 'X) (LIST 'CAR (DS-NCDR I 'X)))
        (LIST 'DE SET (LIST 'X 'V) (LIST 'RPLACA (DS-NCDR I 'X) 'V))
        (LIST 'PUTPROP (LIST 'QUOTE ACC) (LIST 'QUOTE 'SETF-FN) (LIST 'QUOTE SET))))))

(DE DS-SLOTDEFS (NAME SLOTS I)
  (COND ((NULL SLOTS) NIL)
        (T (APPEND (DS-ONE-SLOT NAME (CAR SLOTS) I)
                   (DS-SLOTDEFS NAME (CDR SLOTS) (ADD1 I))))))

(DM DEFSTRUCT L
  (CONS 'PROGN
    (CONS (DS-CONSTRUCTOR (CADR L) (CDDR L))
      (CONS (DS-PRED (CADR L))
        (CONS (DS-COPIER (CADR L))
          (DS-SLOTDEFS (CADR L) (CDDR L) 1))))))
