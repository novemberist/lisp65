; Tests fuer demo-db (winzige Alist-"Datenbank").
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/cl-compat.lsp \
;       lisp/demo-db.lsp lisp/demo-db-tests.lsp

; ---- Record bauen / lesen ----
(CHECK (rec '(NAME AGE) '(ADA 36)) '((NAME . ADA) (AGE . 36)))
(CHECK (rec-get (rec '(NAME AGE) '(ADA 36)) 'AGE) 36)
(CHECK (rec-get (rec '(NAME AGE) '(ADA 36)) 'CITY) NIL)

; ---- Setzen (Schatten via ACONS) ----
(CHECK (rec-get (rec-set (rec '(AGE) '(36)) 'AGE 37) 'AGE) 37)

; ---- Feld zu Wert (RASSOC) ----
(CHECK (rec-field-of (rec '(NAME AGE) '(ADA 36)) 36) 'AGE)
(CHECK (rec-field-of (rec '(NAME AGE) '(ADA 36)) 99) NIL)

; ---- Tabelle: Abfragen ----
(SETQ PEOPLE (LIST (rec '(NAME ROLE) '(ADA DEV))
                   (rec '(NAME ROLE) '(LISA DEV))
                   (rec '(NAME ROLE) '(GRACE LEAD))))

(CHECK (db-pluck PEOPLE 'NAME) '(ADA LISA GRACE))
(CHECK (db-count PEOPLE 'ROLE 'DEV) 2)
(CHECK (db-count PEOPLE 'ROLE 'LEAD) 1)
(CHECK (db-count PEOPLE 'ROLE 'OPS) 0)
(CHECK (db-pluck (db-where PEOPLE 'ROLE 'DEV) 'NAME) '(ADA LISA))

; ---- Insert erweitert die Tabelle ----
(CHECK (db-count (db-insert PEOPLE (rec '(NAME ROLE) '(MARY DEV))) 'ROLE 'DEV) 3)

(CHECK-REPORT)
