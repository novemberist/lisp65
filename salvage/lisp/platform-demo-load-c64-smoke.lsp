; Minimaler C64-SAVE-Format-Smoke fuer platform-demo.lsp.
; Die echten Platform-Primitive werden hier durch kleine Stubs ersetzt, damit
; demo-handle-key ueber den nativen LOAD-Pfad isoliert geprueft werden kann.

(DE PLAY-TONE (VOICE FREQ WAVE) (LIST 'TONE VOICE FREQ WAVE))
(DE LOAD-FILE (NAME) (LIST 'LOAD NAME))
(DE DEMO-DASHBOARD () 'DASH)

(DE PDTONE () (DEMO-HANDLE-KEY 65))
(DE PDLOAD () (DEMO-HANDLE-KEY 76))
(DE PDDASH () (DEMO-HANDLE-KEY 0))
