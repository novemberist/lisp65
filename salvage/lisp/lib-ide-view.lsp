; lib-ide-view -- Viewport-/Screen-Kompositions-Logik der IDE (Phase-8-Vorarbeit).
;
; Letzte Lisp-Schicht-Logik der IDE: WAS im 40x25-Fenster sichtbar ist
; (Scroll-Viewport) und wie sich das Vollbild aus Edit-Region + Modeline +
; Minibuffer zusammensetzt. Reine Logik -- das tatsaechliche Blitten ins
; Screen-/Color-RAM ist der native ASM-Hot-Path; hier liegt nur das
; LOGISCHE Modell (Referenz, gegen die der native Renderer stimmen muss).
;
; Setzt voraus: editor-core, lib-buffers, lib-ide-session.
;
; Lauf: python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/lib-macros.lsp \
;   lisp/cl-compat.lsp lisp/editor-core.lsp lisp/lib-edit-commands.lsp \
;   lisp/lib-buffers.lsp lisp/lib-ide-session.lsp lisp/lib-ide-view.lsp \
;   lisp/ide-view-tests.lsp

; ---- Zeile auf genau WIDTH Zeichen bringen (abschneiden ODER auffuellen) ----
(defun clip (s width)
  (let ((cs (unpack s)))
    (cond ((< (length cs) width) (pack (append cs (spaces (- width (length cs))))))
          (t (pack (take width cs))))))

; ---- Viewport: sichtbare Buffer-Zeilen als Strings ----
; n-te Buffer-Zeile als String, "" jenseits des Dateiendes.
(defun line-at (n lines)
  (let ((tail (drop n lines)))
    (cond ((null tail) "") (t (line->str (car tail))))))
; H Zeilen ab TOP, jede auf WIDTH geclippt (Leerzeilen jenseits EOF).
(defun view-edit-rows (ed top h width)
  (cond ((< h 1) ())
        (t (cons (clip (line-at top (ed-lines ed)) width)
                 (view-edit-rows ed (1+ top) (1- h) width)))))

; ---- Scroll: TOP so anpassen, dass die Cursor-Zeile sichtbar bleibt ----
; EDIT-H = Hoehe der Edit-Region. Liefert das neue TOP.
(defun scroll-top (cur top edit-h)
  (cond ((< cur top) cur)                                ; Cursor ueber dem Fenster
        ((> cur (- (+ top edit-h) 1)) (+ (- cur edit-h) 1)) ; unter dem Fenster
        (t top)))                                        ; bereits sichtbar

; ---- Minibuffer-Zeile (gerendert, sonst leer) ----
(defun mb-line (sess) (cond ((ss-mb sess) (mb-render (ss-mb sess))) (t "")))

; ---- Vollbild komponieren: EDIT-Region + Modeline + Minibuffer ----
; Liefert eine Liste von HEIGHT Strings, jeder WIDTH Zeichen.
; Letzte zwei Zeilen = Modeline und Minibuffer; der Rest = Edit-Region ab TOP.
(defun compose-screen (sess top height width)
  (let ((edit-h (- height 2)))
    (append (view-edit-rows (ss-ed sess) top edit-h width)
            (list (clip (modeline (ss-bs sess)) width)
                  (clip (mb-line sess) width)))))

; ---- Cursor-Position auf dem Schirm (relativ zur Edit-Region) ----
(defun cursor-screen-row (sess top) (- (ed-row (ss-ed sess)) top))
(defun cursor-screen-col (sess) (ed-col (ss-ed sess)))
