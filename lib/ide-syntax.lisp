;; lisp65 IDE: schmale SEXP-Helfer fuer Auto-Einrueckung und Delta-Render.
;; Der fruehere Syntax-Overpaint-Pfad ist aus dem Workbench-Profil entfernt:
;; Highlighting war deaktiviert, teuer im Render-Hotpath und belegte mehrere
;; Disk-Lib-Slots. Die aktive Oberflaeche bleibt plain rendering + Einrueckung.

;; CODE-Zeile rendern. Syntax-Overpaint ist im Workbench-Profil entfernt; der
;; produktive Pfad malt nur die Basis-Zeile in Default-Weiss.
(defun %ide-render-code-line-at (text y columns attr)
  ;; HIGHLIGHTING AUS + attr=1: keine Syntaxfarben, nur dieselbe Basisfarbe wie scr_init.
  ;; Das erhaelt den schnellen Bulk-Pad-Pfad; attr=-1 waere zwar "Farbe lassen", kann aber
  ;; im aktuellen screen-write-string-ABI kein Pad-to-EOL ausdruecken.
  (ide-render-line-at text y columns 1))

;; Netto-Klammertiefe EINER Zeile: ( / ) zählen nur außerhalb String/Kommentar; Kommentar
;; bricht ab; d darf negativ werden (Zeilen aus schließenden Klammern). st: 0 normal, 2 String.
(defun %ide-line-net-depth (codes st d)
  (if codes
      ((lambda (c)
         (if (= st 2)
             (%ide-line-net-depth (cdr codes) (if (= c 34) 0 2) d)
             (if (= c 59)
                 d
                 (if (= c 34)
                     (%ide-line-net-depth (cdr codes) 2 d)
                     (%ide-line-net-depth (cdr codes) 0
                                          (if (= c 40) (+ d 1)
                                              (if (= c 41) (- d 1) d)))))))
       (car codes))
      d))

;; Klammertiefe VOR Zeile n = Summe der Netto-Tiefen der Zeilen 0..n-1 (nie negativ).
(defun %ide-depth-above (lines n d)
  (if (and lines (> n 0))
      (%ide-depth-above (cdr lines) (- n 1)
                        (%ide-line-net-depth (string->list (car lines)) 0 d))
      (if (> d 0) d 0)))

;; n Leerzeichen am Punkt einfügen (funktional; ide-insert-char nutzt den O(1)-Zeilen-Cache).
(defun %ide-insert-spaces (buffer n)
  (if (> n 0)
      (%ide-insert-spaces (ide-insert-char buffer 32) (- n 1))
      buffer))

;; RETURN mit Auto-Einrückung: Zeile spalten, dann die NEUE Zeile auf 2×Klammertiefe
;; einrücken (einfache lisp-mode-Tiefenregel; Deckel 10 Ebenen = 20 Spalten). Der Tiefen-
;; Scan läuft NUR bei RETURN (O(Buffer)), nie pro Tastendruck.
(defun ide-split-line-indented (buffer)
  ((lambda (split)
     ((lambda (d)
        (%ide-insert-spaces split (* 2 (if (> d 10) 10 d))))
      (%ide-depth-above (ide-buffer-lines split)
                        (ide-point-line (ide-buffer-point split))
                        0)))
   (ide-split-line buffer)))

;; Suffix ab Spalte from zeichnen + (pad+1) Loesch-Leerzeichen: pad = Zeilen-
;; Schrumpfung (Deletes im Burst), +1 = die Zelle HINTER dem alten Zeilenende —
;; dort stand der Cursor-Block des vorigen Renders (Backspace hinterliess sonst
;; je Taste einen weissen Block; Nutzerbefund 2026-07-06). Rand: Treiber clippt x.
(defun %ide-render-code-suffix-at (text y from pad)
  ((lambda (codes len)
     (progn
       (%ide-render-codes-at (%ide-nth-cell codes from) from y 1)
       (%ide-pad-eol len (+ len (+ pad 1)) y 1)))
   (string->list text)
   (string-length text)))
