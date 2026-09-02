; lib-autoload -- lazy Laden pro Funktion/Datei (granulares Laden).
;
; (AUTOLOAD 'NAME "datei.lsp") registriert nur einen STUB fuer NAME. Beim ERSTEN
; Aufruf von NAME wird die Datei geladen (die NAME mit der echten Definition
; ueberschreibt) und der Aufruf nachgeholt. Wird NAME nie aufgerufen, wird die
; Datei nie geladen -> kein Heap-Verbrauch. Klassischer Lisp-Mechanismus.
; Strategie/Einordnung: docs/granular-loading.md.
;
; Lauf (aus dem Repo-Root, wegen LOAD-Pfaden):
;   python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/lib-autoload.lsp \
;       lisp/autoload-tests.lsp

; Schon geladene Dateien (verhindert doppeltes Laden geteilter Deps).
(SETQ *AUTOLOAD-LOADED* NIL)

; Eine Datei hoechstens einmal laden.
(DE AUTOLOAD-LOAD-ONCE (F)
  (COND ((MEMBER F *AUTOLOAD-LOADED*) NIL)
        (T (SETQ *AUTOLOAD-LOADED* (CONS F *AUTOLOAD-LOADED*))
           (LOAD F))))

; FILE ist ENTWEDER ein einzelner Dateiname (String -> ATOM) ODER eine Liste
; von Dateien (Abhaengigkeiten zuerst). So kann ein Stub eine ganze
; Lade-Kette ziehen (z.B. lib-c64io braucht lib-c64hw + lib-c64fx).
(DE AUTOLOAD-LOAD (FILE)
  (COND ((NULL FILE) NIL)                       ; leere Liste -> fertig
        ((ATOM FILE) (AUTOLOAD-LOAD-ONCE FILE)) ; einzelner Dateiname (String)
        (T (AUTOLOAD-LOAD-ONCE (CAR FILE)) (AUTOLOAD-LOAD (CDR FILE)))))

; Beim ersten Aufruf: Datei(en) laden (definiert NAME neu) + Aufruf nachholen.
(DE AUTOLOAD-FIRE (NAME ARGS)
  (AUTOLOAD-LOAD (GETPROP NAME (QUOTE AUTOLOAD-FILE)))
  (APPLY NAME ARGS))

; Stub installieren: (DE NAME ARGS (AUTOLOAD-FIRE 'NAME ARGS)) -- nospread ARGS
; faengt die ganze Argumentliste. Dateiname auf der Plist gemerkt.
(DE AUTOLOAD (NAME FILE)
  (PUTPROP NAME (QUOTE AUTOLOAD-FILE) FILE)
  (EVAL (LIST (QUOTE DE) NAME (QUOTE ARGS)
              (LIST (QUOTE AUTOLOAD-FIRE) (LIST (QUOTE QUOTE) NAME) (QUOTE ARGS)))))
