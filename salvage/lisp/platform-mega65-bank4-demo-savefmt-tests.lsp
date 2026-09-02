; Host-Tests fuer die MEGA65-Bank-4-LOAD-sichere Demo-Zeichnerkette.

(MEM-RESET)
(DE GETKEY () 0)
(DE LOAD (NAME) (LIST 'LOAD NAME))
; Siehe platform-mega65-bank4-savefmt-tests.lsp: der Host prueft den
; CLEARSCREEN-Kontrollpfad mit kurzer Range, nicht die geraeteseitige 16K-Schleife.
(DE BCL (R) (H 262144 262150 0))

(DEMODASH)
(CHECK (PEEK 262144) 255)
(CHECK (PEEK 262145) 255)
(CHECK (PEEK 262224) 255)
(CHECK (PEEK 262225) 255)
(CHECK (PEEK 262864) 255)
(CHECK (PEEK 262865) 255)
(CHECK (PEEK 262704) 234)

(CHECK-REPORT)
