; lib-c64key -- Tastatur-Eingabe-Bruecke (Phase 5, ladbar, KOLLISIONSFREI).
;
; C64-Tastatur-Matrix-Scan rein auf nativem PEEK/POKE: CIA1 PRA ($DC00) selektiert
; eine Spalte (aktiv-LOW), PRB ($DC01) liest die Zeilen (aktiv-LOW). KEIN neues
; OBLIST-Primitiv, KEIN Eingriff in den nativen Baum -> keine Kollision mit Codex
; (s. docs/phase5-native-readiness-audit.md). Spiegelt das Differenzmodell
; tools/host-lisp/cia_keyboard.py; Matrix-/Token-Spec: docs/phase5-keyboard-bridge-spec.md
;
; Liefert: Snapshot-Lesen (8 PRB-Bytes), Tasten-Dekodierung Snapshot -> IDE-Token
; ("e"/"A"/"C-e"/"M-f"/"RET"/" "/...), passend zum ide-session-Keymap.

(SETQ CIA1PRA 56320)        ; $DC00 Spalten-Select (Ausgabe)
(SETQ CIA1PRB 56321)        ; $DC01 Zeilen-Read (Eingabe)

; ---- kleine Bit-Helfer (keine externen Lib-Abhaengigkeiten) ----
(DE key-mask (n) (COND ((ZEROP n) 1) (T (TIMES 2 (key-mask (SUB1 n))))))
(DE kn (n l) (COND ((ZEROP n) (CAR l)) (T (kn (SUB1 n) (CDR l)))))
(DE k2 (a b) (PACK (APPEND (UNPACK a) (UNPACK b))))
(DE k-memb (x l)
  (COND ((NULL l) NIL) ((EQUAL x (CAR l)) T) (T (k-memb x (CDR l)))))

; ---- Matrix: Spalten-Major, MATRIX[col][row] (col=PRA-Bit, row=PRB-Bit) ----
(SETQ KEY-MATRIX
  (QUOTE (
    ("DEL" "RET" "CRSR-LR" "F7" "F1" "F3" "F5" "CRSR-UD")
    ("3" "W" "A" "4" "Z" "S" "E" "LSHIFT")
    ("5" "R" "D" "6" "C" "F" "T" "X")
    ("7" "Y" "G" "8" "B" "H" "U" "V")
    ("9" "I" "J" "0" "M" "K" "O" "N")
    ("+" "P" "L" "-" "." ":" "@" ",")
    ("PND" "*" ";" "HOME" "RSHIFT" "=" "UP" "/")
    ("1" "LEFT" "CTRL" "2" "SPACE" "CBM" "Q" "STOP"))))

(SETQ KEY-SPECIAL
  (QUOTE ("RET" "DEL" "SPACE" "F1" "F3" "F5" "F7" "HOME" "STOP"
          "CRSR-LR" "CRSR-UD" "LEFT" "UP" "PND")))

(DE matrix-ref (c r) (kn r (kn c KEY-MATRIX)))

; ---- Snapshot-Lesen: pro Spalte PRA poken, PRB peeken -> Liste von 8 Bytes ----
(DE key-col-select (c) (LOGXOR 255 (key-mask c)))
(DE read-col (c) (POKE CIA1PRA (key-col-select c)) (PEEK CIA1PRB))
(DE read-snap-aux (c)
  (COND ((GREATERP c 7) NIL) (T (CONS (read-col c) (read-snap-aux (ADD1 c))))))
(DE read-snapshot () (read-snap-aux 0))

; ---- Snapshot-Abfragen (aktiv-LOW: gedrueckt = Bit 0) ----
(DE pressed-p (snap c r) (ZEROP (LOGAND (kn c snap) (key-mask r))))
(DE mod-pos-p (c r)
  (OR (AND (EQ c 1) (EQ r 7))            ; LSHIFT
      (AND (EQ c 6) (EQ r 4))            ; RSHIFT
      (AND (EQ c 7) (EQ r 2))            ; CTRL
      (AND (EQ c 7) (EQ r 5))))          ; CBM

(DE ctrl-p (snap) (pressed-p snap 7 2))
(DE cbm-p (snap) (pressed-p snap 7 5))
(DE shift-p (snap) (OR (pressed-p snap 1 7) (pressed-p snap 6 4)))

; ---- erste gedrueckte Nicht-Modifizierer-Taste finden -> (col . row) | NIL ----
(DE scan-first (snap) (sf snap 0 0))
(DE sf (snap c r)
  (COND ((GREATERP c 7) NIL)
        ((GREATERP r 7) (sf snap (ADD1 c) 0))
        ((AND (pressed-p snap c r) (NOT (mod-pos-p c r))) (CONS c r))
        (T (sf snap c (ADD1 r)))))

; ---- Klein-/Großschreibung eines 1-Zeichen-Tokens ----
(DE key-downcase (s)
  (LET ((c (ASC s)))
    (COND ((AND (GREATERP c 64) (LESSP c 91)) (CHAR (PLUS c 32))) (T s))))

; ---- Snapshot -> IDE-Token (NIL, wenn nur Modifizierer/nichts) ----
(DE decode-key (snap)
  (LET ((hit (scan-first snap)))
    (COND ((NULL hit) NIL)
          (T (apply-mods snap (matrix-ref (CAR hit) (CDR hit)))))))

(DE apply-mods (snap base)
  (COND ((k-memb base KEY-SPECIAL) (COND ((EQUAL base "SPACE") " ") (T base)))
        ((ctrl-p snap) (k2 "C-" (key-downcase base)))
        ((cbm-p snap) (k2 "M-" (key-downcase base)))
        ((shift-p snap) base)                ; Großbuchstabe wie in der Matrix
        (T (key-downcase base))))            ; plain -> klein

; ---- Komfort: einmal scannen -> Token (oder NIL) ----
(DE read-key () (decode-key (read-snapshot)))

; ===========================================================================
; PETSCII -> IDE-Token-Adapter (Quelle B: vor ein spaeteres natives GETKEY).
; Bildet einen PETSCII-Code (wie ihn (GETKEY) liefern wuerde) auf DASSELBE
; IDE-Token ab wie der Matrix-Scan -> beide Quellen konvergieren. Spec:
; docs/phase5-getkey-native-spec.md. Sobald natives GETKEY existiert, ist
; (petscii->token (GETKEY)) der Drop-in.
;   13 -> RET, 20 -> DEL, 32 -> Space, 1..26 -> C-a..C-z (Kernal-CTRL-Codes),
;   druckbar (32..127) -> 1-Zeichen-Token. 0/NIL (leerer Puffer) -> NIL.
; GRENZE: die Commodore-Taste (Meta/M-) ist in PETSCII nicht als Modifizierer
;   erkennbar -> M-x bleibt der Matrix-Scan-Quelle (A) vorbehalten.
; ===========================================================================
(DE pet-printablep (c) (AND (GREATERP c 31) (LESSP c 128)))
(DE petscii->token (c)
  (COND ((NULL c) NIL)
        ((EQ c 0) NIL)                              ; leerer Puffer
        ((EQ c 13) "RET")
        ((EQ c 20) "DEL")
        ((EQ c 32) " ")
        ((AND (GREATERP c 0) (LESSP c 27))          ; 1..26 -> C-a..C-z
         (k2 "C-" (CHAR (PLUS c 96))))
        ((pet-printablep c) (CHAR c))               ; druckbar -> Self-Insert-Token
        (T NIL)))                                   ; Unbekanntes ignorieren
