; lib-modules -- einfaches require/provide-Modulsystem (Phase-6-Stufe-3).
;
; Klassisches Lisp-Modulmodell (vor ASDF): KEINE Pakete/Namensraeume, nur
; "Modul schon geladen?"-Buchhaltung ueber LOAD. Namenskollisionen werden per
; Praefix-Konvention vermieden (z. B. MCLOS-/DS-/LOOP-), nicht per Paket.
; Details/Strategie: docs/modularization.md.
;
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/lib-modules.lsp \
;       lisp/module-tests.lsp

(SETQ *PROVIDED* NIL)              ; Liste bereits bereitgestellter Modulnamen
(SETQ *MODULE-DIR* "")             ; Pfad-Praefix (ueberschreibbar)

(DE PROVIDED-P (NAME) (COND ((MEMBER NAME *PROVIDED*) T) (T NIL)))

(DE PROVIDE (NAME)                 ; Modul als geladen markieren (idempotent)
  (COND ((PROVIDED-P NAME) NAME)
        (T (SETQ *PROVIDED* (CONS NAME *PROVIDED*)) NAME)))

; Pfad-Konvention: NAME -> "<dir>NAME.lsp" (PACK mit String-Anteil -> String)
(DE MODULE-FILE (NAME) (PACK (LIST *MODULE-DIR* NAME ".lsp")))

; Lade-Hook -- in Tests ueberschreibbar, real ueber LOAD
(DE LOAD-MODULE (NAME) (LOAD (MODULE-FILE NAME)))

(DE REQUIRE (NAME)                 ; laedt NAME nur, falls noch nicht bereitgestellt
  (COND ((PROVIDED-P NAME) NIL)
        (T (LOAD-MODULE NAME) (PROVIDE NAME) T)))
