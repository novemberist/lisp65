; Tests fuer lib-ide-view (Viewport/Scroll + Screen-Komposition).
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/lib-macros.lsp \
;   lisp/cl-compat.lsp lisp/editor-core.lsp lisp/lib-edit-commands.lsp \
;   lisp/lib-buffers.lsp lisp/lib-ide-session.lsp lisp/lib-ide-view.lsp \
;   lisp/ide-view-tests.lsp

(defun ed-from (strs row col) (mk-ed (mapcar (quote str->line) strs) row col))
(defun sess-from (strs row col)
  (ss-new (bs-add (bs-mk () "") "buf" (ed-from strs row col))))

; ---- clip: auffuellen UND abschneiden ----
(check (clip "L0" 5) "L0   ")
(check (clip "hello" 3) "hel")
(check (clip "exact" 5) "exact")
(check (clip "" 3) "   ")

; ---- view-edit-rows: clippt + Leerzeilen jenseits EOF ----
(check (view-edit-rows (ed-from (list "aaa" "bb" "c") 0 0) 0 5 4)
       (list "aaa " "bb  " "c   " "    " "    "))
; mit Scroll-Offset (top=1)
(check (view-edit-rows (ed-from (list "aaa" "bb" "c") 0 0) 1 2 4)
       (list "bb  " "c   "))

; ---- scroll-top: Cursor sichtbar halten ----
(check (scroll-top 0 0 3) 0)            ; oben, sichtbar
(check (scroll-top 2 0 3) 0)            ; letzte sichtbare Zeile -> unveraendert
(check (scroll-top 5 0 3) 3)            ; unter dem Fenster -> runterscrollen
(check (scroll-top 1 3 3) 1)            ; ueber dem Fenster -> hochscrollen
(check (scroll-top 4 2 3) 2)            ; innerhalb [2,5) -> unveraendert

; ---- compose-screen: HEIGHT Zeilen, je WIDTH; letzte zwei = Modeline+Minibuffer ----
(setq *s* (sess-from (list "L0" "L1" "L2" "L3") 0 0))
(setq *scr* (compose-screen *s* 0 5 20))
(check (length *scr*) 5)                                 ; 3 Edit + Modeline + Minibuffer
(check (nth-elem 0 *scr*) (clip "L0" 20))                ; Edit-Zeile 0
(check (nth-elem 2 *scr*) (clip "L2" 20))                ; Edit-Zeile 2 (L3 nicht sichtbar)
(check (nth-elem 3 *scr*) (clip "-- buf   (0,0)" 20))    ; Modeline
(check (nth-elem 4 *scr*) (clip "" 20))                  ; Minibuffer leer
; jede Zeile exakt WIDTH lang
(check (length (unpack (nth-elem 0 *scr*))) 20)
(check (length (unpack (nth-elem 4 *scr*))) 20)

; ---- compose-screen mit gescrolltem Viewport ----
(setq *scr2* (compose-screen *s* 2 4 20))                ; height 4 -> edit-h 2, top 2
(check (nth-elem 0 *scr2*) (clip "L2" 20))
(check (nth-elem 1 *scr2*) (clip "L3" 20))

; ---- Minibuffer aktiv -> letzte Zeile zeigt Prompt+Eingabe ----
(setq *sm* (ide-dispatch (sess-from (list "x") 0 0) "C-x-b"))   ; oeffnet Minibuffer
(setq *sm* (ide-run *sm* (list "a" "b")))
(check (mb-line *sm*) "Switch to buffer: ab")
(check (nth-elem 4 (compose-screen *sm* 0 5 30)) (clip "Switch to buffer: ab" 30))

; ---- Cursor-Position relativ zur Edit-Region ----
(check (cursor-screen-row (sess-from (list "a" "b" "c" "d") 3 2) 1) 2)  ; row 3, top 1 -> 2
(check (cursor-screen-col (sess-from (list "hello") 0 3) 0) 3)

(check-report)
