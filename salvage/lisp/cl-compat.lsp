; LISP 64 -- CL-Kompatibilitaets-Helfer (Phase 6, Stufe 1)
;
; Ergaenzt Common-Lisp-vertraute Funktionen/Makros unter NICHT-kollidierenden
; Namen. Beruehrt KEINE .acme-Quelle/Makefile. Laeuft auf dem Host und soll
; (Kommentare zu (* ) konvertiert) auch auf dem echten C64 ladbar sein.
;
; WICHTIG -- Semantik-Fallen (siehe docs/dialect-vs-cl.md): Die nativen NTH/LAST
; weichen von CL ab und werden hier NICHT ueberschrieben (sie sind primitiv).
; CL-konforme Varianten gibt es unter Begleitnamen:
;   nativ  NTH liste n   = Liste ab n-tem Element (1-basiert)
;   CL     NTHCDR n l    = n-ter Tail (0-basiert)  -> hier definiert
;   CL     (nth n l)     = (CAR (NTHCDR n l))
;   nativ  LAST l        = letztes ELEMENT
;   CL     LASTCONS l    = letzte Cons-Zelle       -> hier definiert
; Multiplikation bleibt TIMES ('*' ist Kommentar). Ergaenzt prelude.lsp
; (FIRST/REST/SECOND/THIRD/ENDP/LISTP/EVENP/ODDP sind dort).

; ---- erweiterte C*R-Familie ----
(DE CADDR (X) (CAR (CDDR X)))
(DE CDDDR (X) (CDR (CDDR X)))
(DE CADDDR (X) (CAR (CDDDR X)))

; ---- funcall ----
(DE FUNCALL L (APPLY (CAR L) (CDR L)))

; ---- CL-konforme Listen-Helfer (Begleitnamen zu den Fallen) ----
(DE NTHCDR (N L)
  (COND ((ZEROP N) L)
        ((ATOM L) L)
        (T (NTHCDR (SUB1 N) (CDR L)))))

(DE LASTCONS (L)
  (COND ((ATOM L) L)
        ((ATOM (CDR L)) L)
        (T (LASTCONS (CDR L)))))

(DE BUTLAST (L)
  (COND ((ATOM L) NIL)
        ((ATOM (CDR L)) NIL)
        (T (CONS (CAR L) (BUTLAST (CDR L))))))

; ---- Suchen / Filtern ----
(DE FIND (X L)
  (COND ((ATOM L) NIL)
        ((EQL X (CAR L)) (CAR L))
        (T (FIND X (CDR L)))))

(DE POSITION (X L) (CL-POS X L 0))
(DE CL-POS (X L N)
  (COND ((ATOM L) NIL)
        ((EQL X (CAR L)) N)
        (T (CL-POS X (CDR L) (ADD1 N)))))

(DE REMOVE-IF (F L)
  (COND ((ATOM L) NIL)
        ((APPLY* F (CAR L)) (REMOVE-IF F (CDR L)))
        (T (CONS (CAR L) (REMOVE-IF F (CDR L))))))

(DE REMOVE-IF-NOT (F L)
  (COND ((ATOM L) NIL)
        ((APPLY* F (CAR L)) (CONS (CAR L) (REMOVE-IF-NOT F (CDR L))))
        (T (REMOVE-IF-NOT F (CDR L)))))

; ---- Makros: incf/decf/let*/dotimes/dolist ----
; (Hinweis: ohne gensym -- DOTIMES/DOLIST benutzen die Marke LOOP, daher nicht
;  mehrfach im selben PROG-Rumpf verschachteln.)

(DM INCF L (LIST 'SETQ (CADR L) (LIST 'ADD1 (CADR L))))
(DM DECF L (LIST 'SETQ (CADR L) (LIST 'SUB1 (CADR L))))

; LET* als GESCHACHTELTE LET: jeder Init wird im aeusseren Scope ausgewertet
; (CL-Semantik). Wichtig -- ein PROG-mit-NIL-Init + SETQ wuerde
; (LET* ((S (F S))) ...) faelschlich (F NIL) rechnen.
(DM LET* L
  (COND ((NULL (CADR L)) (CONS 'PROGN (CDDR L)))
        (T (LIST (LIST 'LAMBDA (LIST (CAR (CAR (CADR L))))
                   (CONS 'LET* (CONS (CDR (CADR L)) (CDDR L))))
                 (CADR (CAR (CADR L)))))))

(DM DOTIMES L
  (CONS 'PROG
    (CONS (LIST (CAR (CADR L)))
      (APPEND
        (LIST (LIST 'SETQ (CAR (CADR L)) 0)
              'LOOP
              (LIST 'COND
                (LIST (LIST 'NOT (LIST 'LESSP (CAR (CADR L)) (CADR (CADR L))))
                      '(RETURN NIL))))
        (CDDR L)
        (LIST (LIST 'SETQ (CAR (CADR L)) (LIST 'ADD1 (CAR (CADR L))))
              '(GO LOOP))))))

(DM DOLIST L
  (CONS 'PROG
    (CONS (LIST (CAR (CADR L)) 'CL-REST)
      (APPEND
        (LIST (LIST 'SETQ 'CL-REST (CADR (CADR L)))
              'LOOP
              (LIST 'COND (LIST '(ATOM CL-REST) '(RETURN NIL)))
              (LIST 'SETQ (CAR (CADR L)) '(CAR CL-REST)))
        (CDDR L)
        (LIST '(SETQ CL-REST (CDR CL-REST))
              '(GO LOOP))))))

; ---- setf-light: generalisierte Zuweisung (CL-zentral) ----
; Unterstützte Places: Variable, (CAR x), (CDR x), (GET sym ind)/(GETPROP sym ind).
; Hinweis: bei CAR/CDR liefert setf den Cons (nicht den Wert) -- für Seiteneffekt.
(DE GET (S I) (GETPROP S I))            ; CL-Name als Alias auf GETPROP

; Generischer Place-Pfad: traegt der Kopf der Place-Form eine SETF-FN-Property
; (z. B. von DEFSTRUCT registrierte Akzessoren), wird (setf-fn args... wert)
; emittiert -- CLs "setf functions" im Kleinen.
(DM SETF L
  (COND ((ATOM (CADR L)) (LIST 'SETQ (CADR L) (CADDR L)))
        ((EQ (CAR (CADR L)) 'CAR) (LIST 'RPLACA (CADR (CADR L)) (CADDR L)))
        ((EQ (CAR (CADR L)) 'CDR) (LIST 'RPLACD (CADR (CADR L)) (CADDR L)))
        ((OR (EQ (CAR (CADR L)) 'GET) (EQ (CAR (CADR L)) 'GETPROP))
         (LIST 'PUTPROP (CADR (CADR L)) (CADDR (CADR L)) (CADDR L)))
        ((AND (ATOM (CAR (CADR L))) (GETPROP (CAR (CADR L)) 'SETF-FN))
         (CONS (GETPROP (CAR (CADR L)) 'SETF-FN)
               (APPEND (CDR (CADR L)) (LIST (CADDR L)))))
        (T (ERROR '(SETF-UNSUPPORTED-PLACE)))))

; ---- weitere CL-Bibliothek (reduce/every/some/count) ----
(DE REDUCE-AUX (F ACC L)
  (COND ((NULL L) ACC) (T (REDUCE-AUX F (FUNCALL F ACC (CAR L)) (CDR L)))))
(DE REDUCE (F L)                         ; Linksfaltung, nicht-leere Liste
  (COND ((NULL L) (FUNCALL F)) (T (REDUCE-AUX F (CAR L) (CDR L)))))

(DE EVERY (P L)
  (COND ((NULL L) T) ((FUNCALL P (CAR L)) (EVERY P (CDR L))) (T NIL)))

(DE SOME-AUX (R P L) (COND (R R) (T (SOME P L))))
(DE SOME (P L)
  (COND ((NULL L) NIL) (T (SOME-AUX (FUNCALL P (CAR L)) P (CDR L)))))

(DE COUNT (X L)
  (COND ((NULL L) 0)
        ((EQL X (CAR L)) (1+ (COUNT X (CDR L))))
        (T (COUNT X (CDR L)))))

; ---- CASE / ECASE (keyed conditional) ----
; Schluessel wird genau EINMAL ausgewertet (LAMBDA-Bindung an CL-KEY, wie LET*).
; Anders als DOTIMES/DOLIST (feste Marke LOOP) ist CASE damit verschachtelbar.
; Klausel = (key-designator form...). key-designator: T/OTHERWISE = Default;
; ein Atom = (EQL key atom); eine Liste = Mitgliedschaft (EQL) in der Liste.
(DE CL-EQL-MEMBER (X L)
  (COND ((NULL L) NIL)
        ((EQL X (CAR L)) T)
        (T (CL-EQL-MEMBER X (CDR L)))))

(DE CL-CASE-TEST (KD)              ; Klausel-Schluessel -> COND-Test (Expansionszeit)
  (COND ((EQ KD 'T) 'T)
        ((EQ KD 'OTHERWISE) 'T)
        ((ATOM KD) (LIST 'EQL 'CL-KEY (LIST 'QUOTE KD)))
        (T (LIST 'CL-EQL-MEMBER 'CL-KEY (LIST 'QUOTE KD)))))

(DE CL-CASE-CLAUSES (CLS)
  (COND ((NULL CLS) NIL)
        (T (CONS (CONS (CL-CASE-TEST (CAR (CAR CLS))) (CDR (CAR CLS)))
                 (CL-CASE-CLAUSES (CDR CLS))))))

(DM CASE L                        ; (CASE key clause...)
  (LIST (LIST 'LAMBDA '(CL-KEY)
              (CONS 'COND (CL-CASE-CLAUSES (CDDR L))))
        (CADR L)))

(DM ECASE L                       ; wie CASE, aber Fehler wenn keine Klausel passt
  (LIST (LIST 'LAMBDA '(CL-KEY)
              (CONS 'COND
                    (APPEND (CL-CASE-CLAUSES (CDDR L))
                            (LIST '(T (ERROR (QUOTE ECASE-NO-MATCH)))))))
        (CADR L)))

; ---- Hilfsfunktionen / plist / alist ----
(DE IDENTITY (X) X)

(DE GETF (PLIST KEY)              ; Wert zu KEY in einer Property-Liste, sonst NIL
  (COND ((NULL PLIST) NIL)
        ((EQL (CAR PLIST) KEY) (CADR PLIST))
        (T (GETF (CDDR PLIST) KEY))))

(DE ACONS (KEY VAL ALIST) (CONS (CONS KEY VAL) ALIST))

(DE PAIRLIS (KEYS VALS ALIST)     ; (key . val)-Paare vor ALIST haengen
  (COND ((NULL KEYS) ALIST)
        (T (CONS (CONS (CAR KEYS) (CAR VALS))
                 (PAIRLIS (CDR KEYS) (CDR VALS) ALIST)))))

; ---- Listen-Konstruktoren / Kopierer (CL) ----
; Hinweis: LAST und NTH folgen hier der LISP-64-Dialektsemantik (LAST = letztes
; Element; NTH = (NTH liste n)); der CL-konforme Schnitt ist bewusst P2 -- daher
; hier NICHT umdefiniert.

(DE COPY-LIST (L)                 ; flache Kopie der obersten Ebene (dotted-safe)
  (COND ((ATOM L) L)
        (T (CONS (CAR L) (COPY-LIST (CDR L))))))

(DE COPY-TREE (X)                 ; rekursive Kopie aller Conses
  (COND ((ATOM X) X)
        (T (CONS (COPY-TREE (CAR X)) (COPY-TREE (CDR X))))))

(DE COPY-ALIST (AL)              ; kopiert Top-Level UND jedes (key . val)-Paar
  (COND ((NULL AL) NIL)
        (T (CONS (CONS (CAR (CAR AL)) (CDR (CAR AL)))
                 (COPY-ALIST (CDR AL))))))

(DE REVAPPEND (L TAIL)           ; (reverse L) vor TAIL gehaengt
  (COND ((NULL L) TAIL)
        (T (REVAPPEND (CDR L) (CONS (CAR L) TAIL)))))

(DE CL-LIST*-AUX (L)
  (COND ((NULL (CDR L)) (CAR L))
        (T (CONS (CAR L) (CL-LIST*-AUX (CDR L))))))
(DE LIST* L (CL-LIST*-AUX L))    ; (LIST* a b rest) -> (a b . rest)

(DE MAKE-LIST (N)                ; Liste aus N NIL-Elementen
  (COND ((ZEROP N) NIL)
        (T (CONS NIL (MAKE-LIST (SUB1 N))))))

(DE ADJOIN (X L)                 ; X voranstellen, falls nicht schon (EQL) enthalten
  (COND ((CL-EQL-MEMBER X L) L)
        (T (CONS X L))))

(DE SUBST (NEW OLD TREE)         ; OLD (EQL) durch NEW im Baum ersetzen
  (COND ((EQL TREE OLD) NEW)
        ((ATOM TREE) TREE)
        (T (CONS (SUBST NEW OLD (CAR TREE))
                 (SUBST NEW OLD (CDR TREE))))))

; ---- Zahlen-Helfer (CL) ----
; MINUSP/ZEROP/ABS/MOD sind nativ bzw. im prelude; hier die fehlenden.
; (MOD = REMAINDER im Dialekt; REM hier konsistent dazu definiert.)
(DE PLUSP (X) (GREATERP X 0))
(DE REM (X Y) (REMAINDER X Y))
(DE SIGNUM (X)                   ; -1 / 0 / 1
  (COND ((MINUSP X) (DIFFERENCE 0 1))
        ((ZEROP X) 0)
        (T 1)))
(DE EXPT (B E)                   ; ganzzahlige Potenz, E >= 0
  (COND ((ZEROP E) 1)
        (T (TIMES B (EXPT B (SUB1 E))))))
(DE CL-MAX-AUX (BEST R)
  (COND ((NULL R) BEST)
        ((GREATERP (CAR R) BEST) (CL-MAX-AUX (CAR R) (CDR R)))
        (T (CL-MAX-AUX BEST (CDR R)))))
(DE MAX L (CL-MAX-AUX (CAR L) (CDR L)))   ; variadisch, >= 1 Argument
(DE CL-MIN-AUX (BEST R)
  (COND ((NULL R) BEST)
        ((LESSP (CAR R) BEST) (CL-MIN-AUX (CAR R) (CDR R)))
        (T (CL-MIN-AUX BEST (CDR R)))))
(DE MIN L (CL-MIN-AUX (CAR L) (CDR L)))
(DE CL-GCD-AUX (A B) (COND ((ZEROP B) A) (T (CL-GCD-AUX B (REMAINDER A B)))))
(DE GCD (A B) (CL-GCD-AUX (ABS A) (ABS B)))
(DE LCM (A B)
  (COND ((ZEROP A) 0)
        ((ZEROP B) 0)
        (T (ABS (TIMES (QUOTIENT A (GCD A B)) B)))))

; ---- Higher-order-Ergaenzungen ----
(DE MAPCON (F L)                 ; wie MAPLIST, aber Ergebnisse via NCONC
  (COND ((NULL L) NIL)
        (T (NCONC (FUNCALL F L) (MAPCON F (CDR L))))))
(DE NOTANY (P L) (NOT (SOME P L)))
(DE NOTEVERY (P L) (NOT (EVERY P L)))
(DE DELETE-IF (P L) (REMOVE-IF P L))   ; funktional (nicht destruktiv) im Subset

; ---- Typ-Praedikate / TYPEP / RASSOC ----
; CONSP/LISTP/NUMBERP/STRINGP/ATOM/NULL sind nativ; SYMBOLP fehlt.
(DE SYMBOLP (X)                  ; Symbol = Atom, das weder Zahl noch String ist (NIL/T inkl.)
  (COND ((NULL X) T)
        ((NUMBERP X) NIL)
        ((STRINGP X) NIL)
        ((ATOM X) T)
        (T NIL)))

(DE TYPEP (X TY)                 ; einfache TYPEP fuer die Kern-Typsymbole
  (CASE TY
    ((NUMBER) (NUMBERP X))
    ((SYMBOL) (SYMBOLP X))
    ((STRING) (STRINGP X))
    ((CONS) (CONSP X))
    ((LIST) (LISTP X))
    ((ATOM) (ATOM X))
    ((NULL) (NULL X))
    (T NIL)))

(DE RASSOC (V AL)               ; Paar mit (CDR . V) suchen (EQL)
  (COND ((NULL AL) NIL)
        ((EQL V (CDR (CAR AL))) (CAR AL))
        (T (RASSOC V (CDR AL)))))
