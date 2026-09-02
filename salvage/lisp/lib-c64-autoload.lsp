; lib-c64-autoload -- granulares Laden der C64-Komfortschicht.
;
; Idee (docs/granular-loading.md): auf dem echten C64 mit winzigem Heap nur die
; Teile laden, die man wirklich benutzt. Die schweren Algorithmen (Bresenham-
; Linie, Kreis, SID-Melodie) sollen erst beim ersten Aufruf in den Heap.
;
; Aufteilung:
;   lib-c64hw  = Konstanten (C64-RED, VIC-BORDER, SID-BASE ...) + kleine Mathe.
;                Wird EAGER geladen, weil diese Konstanten als ARGUMENTE
;                autoloadbarer Funktionen ausgewertet werden -- und Argument-
;                Auswertung passiert VOR dem Aufruf, also bevor ein Stub feuern
;                koennte. (z.B. (border C64-RED): C64-RED muss schon gebunden
;                sein, bevor BORDER laeuft.) lib-c64hw ist klein -> billig.
;   lib-c64fx  = reine High-Level-Algorithmen (Linie/Kreis/Shape/Melodie).
;                Lazy. Braucht lib-c64hw.
;   lib-c64io  = Komfort-Wrapper, die in echte Register poken (border/plot/
;                sprite/sound/play). Lazy. Braucht lib-c64hw + lib-c64fx.
;
; Voraussetzung: lib-autoload.lsp ist geladen (liefert AUTOLOAD + Listen-Deps).
;
; Lauf (aus dem Repo-Root):
;   python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/lib-autoload.lsp \
;       lisp/lib-c64-autoload.lsp lisp/c64-autoload-tests.lsp

; lib-c64hw eager (und im Lade-Register vermerkt, damit die Dep-Listen es
; nicht erneut laden).
(AUTOLOAD-LOAD-ONCE "lisp/lib-c64hw.lsp")

; Abhaengigkeits-Ketten (Deps zuerst; doppelte Eintraege filtert der
; Lade-einmal-Schutz in AUTOLOAD-LOAD-ONCE).
(SETQ *C64FX-DEPS* (QUOTE ("lisp/lib-c64hw.lsp" "lisp/lib-c64fx.lsp")))
(SETQ *C64IO-DEPS*
      (QUOTE ("lisp/lib-c64hw.lsp" "lisp/lib-c64fx.lsp" "lisp/lib-c64io.lsp")))

; ---- lib-c64fx: oeffentliche Einstiegspunkte ----
(AUTOLOAD (QUOTE line-points)   *C64FX-DEPS*)
(AUTOLOAD (QUOTE circle-points) *C64FX-DEPS*)
(AUTOLOAD (QUOTE shape->bytes)  *C64FX-DEPS*)
(AUTOLOAD (QUOTE note->freq)    *C64FX-DEPS*)
(AUTOLOAD (QUOTE melody->freqs) *C64FX-DEPS*)

; ---- lib-c64io: oeffentliche Einstiegspunkte ----
(AUTOLOAD (QUOTE border)      *C64IO-DEPS*)
(AUTOLOAD (QUOTE background)  *C64IO-DEPS*)
(AUTOLOAD (QUOTE plot)        *C64IO-DEPS*)
(AUTOLOAD (QUOTE plot-pt)     *C64IO-DEPS*)
(AUTOLOAD (QUOTE line)        *C64IO-DEPS*)
(AUTOLOAD (QUOTE circle)      *C64IO-DEPS*)
(AUTOLOAD (QUOTE draw-points) *C64IO-DEPS*)
(AUTOLOAD (QUOTE sprite-at)   *C64IO-DEPS*)
(AUTOLOAD (QUOTE sprite-on)   *C64IO-DEPS*)
(AUTOLOAD (QUOTE sprite-off)  *C64IO-DEPS*)
(AUTOLOAD (QUOTE sprite-color) *C64IO-DEPS*)
(AUTOLOAD (QUOTE sound)       *C64IO-DEPS*)
(AUTOLOAD (QUOTE play)        *C64IO-DEPS*)
(AUTOLOAD (QUOTE play-note)   *C64IO-DEPS*)
