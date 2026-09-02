; Lisp-LOAD-Smoke fuer den sichtbaren MEGA65-Bank-4-Backend-Modus.
;
; Laedt lib-platform-mega65-bank4.lsp per Host-LOAD und ruft danach die normale
; Platform-API. Der Geraete-Smoke fuer denselben sichtbaren Framebuffer laeuft
; separat ueber BASIC65+BLOAD/SYS, bis ein MEGA65-LISP64-Interpreter-Startpfad
; belegt ist.
;
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/lib-platform.lsp \
;       lisp/lib-mega65hw.lsp lisp/platform-mega65-bank4-load-tests.lsp

(MEM-RESET)

(LOAD "lisp/lib-platform-mega65-bank4.lsp")

(CHECK (m65-platform-backend) M65-PLATFORM-BACKEND-ROM-SCREEN-BANK4)

(clear-screen M65-BLUE)
(CHECK (PEEK M65-SCREEN-BANK4-BASE) 0)
(CHECK (PEEK (m65-screen-bank4-end)) 0)

(draw-line 0 0 2 0 M65-WHITE)
(CHECK (PEEK M65-SCREEN-BANK4-BASE) 224)

(draw-line 0 0 0 1 M65-BLACK)
(CHECK (PEEK M65-SCREEN-BANK4-BASE) 96)
(CHECK (PEEK (PLUS M65-SCREEN-BANK4-BASE 80)) 0)

(CHECK-REPORT)
