; demo-db -- winzige In-Memory-"Datenbank" ueber Alists (MVP-Pfeiler "kleine,
; symbol-/listenlastige Programme"). Belegt die Alist-Helfer aus cl-compat
; (PAIRLIS/ACONS/RASSOC) plus natives ASSOC end-to-end.
;
;   Record = Alist ((feld . wert) ...)        Tabelle = Liste von Records
;
; Reines Dialekt-Lisp (prelude + cl-compat); host-getestet, spaeter C64-ladbar.
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/cl-compat.lsp \
;       lisp/demo-db.lsp lisp/demo-db-tests.lsp

; ---- Record ----
(DE rec (fields vals) (PAIRLIS fields vals NIL))   ; Record aus Feld-/Wertlisten

(DE rec-get (r field)             ; Wert eines Feldes, sonst NIL
  (PROG (p)
    (SETQ p (ASSOC field r))
    (RETURN (COND (p (CDR p)) (T NIL)))))

(DE rec-set (r field val) (ACONS field val r))      ; neues Feld schattet altes

(DE rec-field-of (r val)          ; Feldname zu einem Wert (RASSOC), sonst NIL
  (PROG (p)
    (SETQ p (RASSOC val r))
    (RETURN (COND (p (CAR p)) (T NIL)))))

; ---- Tabelle ----
(DE db-insert (table r) (CONS r table))

(DE db-where (table field val)    ; alle Records mit field = val (EQUAL)
  (COND ((NULL table) NIL)
        ((EQUAL (rec-get (CAR table) field) val)
         (CONS (CAR table) (db-where (CDR table) field val)))
        (T (db-where (CDR table) field val))))

(DE db-pluck (table field)        ; Werte eines Feldes ueber alle Records
  (COND ((NULL table) NIL)
        (T (CONS (rec-get (CAR table) field) (db-pluck (CDR table) field)))))

(DE db-count (table field val) (LENGTH (db-where table field val)))
