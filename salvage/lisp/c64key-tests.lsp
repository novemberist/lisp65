; Tests fuer lib-c64key -- Differenztest gegen den CIA-Oracle.
;
; Die Snapshot-Bytes hier sind EXAKT die, die tools/host-lisp/cia_keyboard.py aus
; denselben gedrueckten Tasten erzeugt (--selftest druckt sie). Stimmen die
; Matrizen ueberein, liefern beide Seiten dieselben Token; weicht eine ab, geht
; dieser Smoke ODER der Oracle-Selftest rot. Spec: docs/phase5-keyboard-bridge-spec.md
;
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/lib-macros.lsp \
;   lisp/cl-compat.lsp lisp/lib-c64key.lsp lisp/c64key-tests.lsp

; ---- Bit-Helfer ----
(CHECK (key-mask 0) 1)
(CHECK (key-mask 7) 128)
(CHECK (key-col-select 0) 254)           ; Spalte 0 select: Bit0 LOW
(CHECK (key-col-select 7) 127)           ; Spalte 7 select: Bit7 LOW

; ---- Dekodierung gegen die kanonische Oracle-Szenario-Tabelle ----
; (Snapshot = 8 PRB-Bytes, aktiv-LOW; identisch zu cia_keyboard.py SCENARIOS)
(CHECK (decode-key (QUOTE (255 191 255 255 255 255 255 255))) "e")     ; E
(CHECK (decode-key (QUOTE (255 123 255 255 255 255 255 255))) "A")     ; SHIFT+A
(CHECK (decode-key (QUOTE (255 191 255 255 255 255 255 251))) "C-e")   ; CTRL+E
(CHECK (decode-key (QUOTE (255 255 223 255 255 255 255 223))) "M-f")   ; CBM+F
(CHECK (decode-key (QUOTE (253 255 255 255 255 255 255 255))) "RET")   ; RETURN
(CHECK (decode-key (QUOTE (255 255 255 255 255 255 255 239))) " ")     ; SPACE
(CHECK (decode-key (QUOTE (254 255 255 255 255 255 255 255))) "DEL")   ; DEL
(CHECK (decode-key (QUOTE (255 223 255 255 255 255 255 251))) "C-s")   ; CTRL+S
(CHECK (decode-key (QUOTE (255 255 251 255 255 255 255 223))) "M-d")   ; CBM+D
(CHECK (decode-key (QUOTE (255 255 255 254 255 255 255 255))) "7")     ; Ziffer 7
(CHECK (decode-key (QUOTE (255 255 255 255 255 255 255 251))) NIL)     ; nur CTRL
(CHECK (decode-key (QUOTE (255 255 255 255 255 255 255 255))) NIL)     ; nichts

; ---- read-snapshot-Mechanik gegen das echte RAM-Modell ----
; (Flat-RAM strobt nicht pro Spalte -> alle 8 Spalten lesen denselben PRB-Wert;
;  prueft die Lese-Schleife: 8 Bytes, korrekt von $DC01 gelesen.)
(POKE CIA1PRB 191)
(CHECK (LENGTH (read-snapshot)) 8)
(CHECK (CAR (read-snapshot)) 191)
; und der Spalten-Select hat zuletzt Spalte 7 nach $DC00 geschrieben
(CHECK (PEEK CIA1PRA) 127)

; ---- End-to-End: dekodierter Token ist genau ein ide-session-Keymap-Token ----
(CHECK (decode-key (QUOTE (255 223 255 255 255 255 255 251))) "C-s")   ; cmd-search-forward
(CHECK (decode-key (QUOTE (255 255 255 255 255 255 255 239))) " ")     ; self-insert

; ---- PETSCII -> IDE-Token-Adapter (Quelle B, vor natives GETKEY) ----
(CHECK (petscii->token 5) "C-e")         ; CTRL-Code 5 -> C-e
(CHECK (petscii->token 19) "C-s")        ; 19 -> C-s
(CHECK (petscii->token 11) "C-k")        ; 11 -> C-k (kill-line)
(CHECK (petscii->token 25) "C-y")        ; 25 -> C-y (yank)
(CHECK (petscii->token 13) "RET")        ; CR
(CHECK (petscii->token 20) "DEL")        ; Delete
(CHECK (petscii->token 32) " ")          ; Space
(CHECK (petscii->token 65) "A")          ; druckbar (Großbuchstabe)
(CHECK (petscii->token 97) "a")          ; druckbar (Kleinbuchstabe)
(CHECK (petscii->token 51) "3")          ; Ziffer
(CHECK (petscii->token 0) NIL)           ; leerer Puffer
(CHECK (petscii->token NIL) NIL)         ; nichts

; ---- KONVERGENZ: Matrix-Scan (A) und PETSCII-Adapter (B) -> dasselbe Token ----
(CHECK (decode-key (QUOTE (255 191 255 255 255 255 255 251)))   ; CTRL+E (Matrix)
       (petscii->token 5))                                      ; == C-e (PETSCII)
(CHECK (decode-key (QUOTE (255 223 255 255 255 255 255 251)))   ; CTRL+S (Matrix)
       (petscii->token 19))                                     ; == C-s
(CHECK (decode-key (QUOTE (253 255 255 255 255 255 255 255)))   ; RETURN (Matrix)
       (petscii->token 13))                                     ; == RET
(CHECK (decode-key (QUOTE (255 255 255 255 255 255 255 239)))   ; SPACE (Matrix)
       (petscii->token 32))                                     ; == " "

(CHECK-REPORT)
