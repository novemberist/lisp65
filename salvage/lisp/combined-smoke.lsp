; combined-smoke -- laedt ALLE Bibliotheken gemeinsam und testet Cross-Feature.
;
; Zweck: empirisch belegen, dass die Praefix-Konvention Namenskollisionen
; vermeidet (docs/modularization.md) -- prelude/lib-macros/cl-compat/lib-loop/
; lib-struct/lib-clos/lib-seq/lib-modules/editor-core/lib-paredit/lib-ide
; koexistieren und zusammen funktionieren.
;
; Lauf: alle Libs in Reihenfolge + diese Datei (siehe run-tests.sh "combined").

; ---- defstruct INNERHALB loop ----
(defstruct pt x y)
(setq pts (loop for i from 1 to 3 collect (make-pt :x i :y (times i 10))))
(check (loop for p in pts sum (pt-x p)) 6)          ; 1+2+3
(check (loop for p in pts sum (pt-y p)) 60)          ; 10+20+30

; ---- seq.sort von structs nach Slot ----
(defun pt-x< (a b) (lessp (pt-x a) (pt-x b)))
(setq shuffled (list (make-pt :x 3) (make-pt :x 1) (make-pt :x 2)))
(check (mapcar (quote pt-x) (sort shuffled (quote pt-x<))) (quote (1 2 3)))

; ---- clos-Methode nutzt format ----
(defclass animal () name)
(defmethod speak ((a animal)) (format "~A spricht" (slot-value a (quote name))))
(setq rexi (make-instance (quote animal) :name (quote rex)))
(check (speak rexi) "REX spricht")

; ---- nach clos-Last laufen loop/seq/format weiter ----
(check (loop for x in (quote (5 2 8 1)) count (greaterp x 3)) 2)
(check (sort (quote (3 1 2)) (quote lessp)) (quote (1 2 3)))
(check (format "~3D|~A" 7 (quote ok)) "  7|OK")

; ---- require/provide koexistiert ----
(provide (quote demo))
(check (provided-p (quote demo)) t)

; ---- error-model greift ueber alle Libs ----
(check (handler-case (error "x") (error (c) (condition-type c))) (quote user-error))

; ---- paredit/ide-Kommando ueber Keymap, parallel zu allem anderen ----
(check (fb-chars (ed-dispatch *ide-keymap* "C-)" (fb-mk (unpack "(a b) c") 2)))
       (unpack "(a b c)"))

(check-report)
