; Shared lexical S-expression scanner for the line editor and IDE.
;
; Each pass is a pure chunk transformer over surface-owned state.  An external
; caller supplies edge=nil; the pass derives min(stop,i+3) once and carries
; that private edge through its tail recursion.  The permanent card gate
; rejects every external non-nil edge.  Partner search therefore cannot hide
; a synchronous pass.
;
; Every public pass consumes at most the supplied budget.  The only admitted
; product budget is three; the card gate rejects a larger call site.  Keeping
; the limit in the pass interface makes the partner search just as resumable
; as the lexical prefix scan.

(defun %sexp-code (source codes i)
  (if (stringp source) (string-ref source i) (car codes)))

(defun %sexp-rest (source codes)
  (if (stringp source) codes (cdr codes)))

; packed = depth*4 + lexical-state
; lexical states: 0 normal, 1 comment, 2 string, 3 escaped-in-string.
(defun %sexp-step (c packed)
  (let* ((state (mod packed 4))
         (depth (/ (- packed state) 4)))
    (if (= state 3)
        (+ (* depth 4) 2)
        (if (= state 2)
            (+ (* depth 4) (if (= c 92) 3 (if (= c 34) 0 2)))
            (if (= state 1)
                packed
                (if (= c 59)
                    (+ (* depth 4) 1)
                    (if (= c 34)
                        (+ (* depth 4) 2)
                        (* (if (= c 40) (+ depth 1)
                               (if (= c 41) (- depth 1) depth)) 4))))))))

; Prefix lexical state for one admitted chunk.
(defun %sexp-scan (source codes stop i packed edge)
  (if (if edge nil 't)
      (%sexp-scan source codes stop i packed
                  (if (< (+ i 3) stop) (+ i 3) stop))
      (if (if (< i edge) (if (stringp source) 't codes) nil)
          (if (= (mod packed 4) 1)
              packed
              (%sexp-scan source (%sexp-rest source codes) stop (+ i 1)
                          (%sexp-step (%sexp-code source codes i) packed) edge))
          packed)))

; Forward partner pass for an opening paren or quote.
(defun %sexp-close (source codes stop i packed kind edge)
  (if (if edge nil 't)
      (%sexp-close source codes stop i packed kind
                   (if (< (+ i 3) stop) (+ i 3) stop))
      (if (if (if (< i edge) (if (stringp source) 't codes) nil) nil 't)
          packed
          (let* ((c (%sexp-code source codes i))
                 (state (mod packed 4))
                 (depth (/ (- packed state) 4)))
            (if (if (= kind 34)
                    (and (= state 2) (= c 34))
                    (and (= state 0) (= c 41) (= depth 1)))
                (- 0 (+ i 1))
                (%sexp-close source (%sexp-rest source codes) stop (+ i 1)
                             (%sexp-step c packed) kind edge))))))

; Prefix replay for a closing paren or quote.  combined packs lexical state
; in the high part and candidate+1 in the low byte.
(defun %sexp-open (source codes stop i combined target kind edge)
  (if (if edge nil 't)
      (%sexp-open source codes stop i combined target kind
                  (if (< (+ i 3) stop) (+ i 3) stop))
      (if (if (if (< i edge) (if (stringp source) 't codes) nil) nil 't)
          combined
          (let* ((packed (/ combined 256))
                 (found (mod combined 256))
                 (state (mod packed 4))
                 (c (%sexp-code source codes i))
                 (next (%sexp-step c packed)))
            (%sexp-open
             source (%sexp-rest source codes) stop (+ i 1)
             (+ (* next 256)
                (if (if (= kind 34)
                        (and (= state 0) (= c 34))
                        (and (= state 0) (= c 40) (= (/ next 4) target)))
                    (+ i 1) found))
             target kind edge)))))

; Convert prefix state plus the delimiter under the cursor into a partner-pass
; kind: 1 forward paren, 2 replay paren, 3 forward quote, 4 replay quote.
(defun %sexp-match (code packed)
  (let* ((state (mod packed 4))
         (depth (/ (- packed state) 4)))
    (if (= code 40)
        (if (= state 0) 1 0)
        (if (= code 41)
            (if (and (= state 0) (> depth 0)) 2 0)
            (if (= code 34)
                (if (= state 0) 3 (if (= state 2) 4 0))
                0)))))

; Paint one owner transition.  old and new are the surface's two highlight
; pairs.  Old cells are restored first, new cells painted second, and cursor
; reverse-video wins when the roles share a cell.  phase=0 is the only public
; entry; recursive phases are private to this helper.
(defun %sexp-paint (source old new origin row columns cursor phase)
  (if (>= phase 4)
      nil
      (let* ((pair (if (< phase 2) old new))
             (index (if pair (if (= (mod phase 2) 0) (car pair) (cdr pair)) nil))
             (attr (if (= index cursor) 129 (if (< phase 2) 1 7))))
        (progn
          (if (and index (and (>= index origin) (< index (+ origin columns))))
              (screen-put-char (- index origin) row
                               (%sexp-code source
                                           (if (stringp source) nil
                                               (nthcdr index source))
                                           index)
                               attr)
              nil)
          (%sexp-paint source old new origin row columns cursor (+ phase 1))))))

; Existing indentation seam.  Keep it lexical-parity-correct: escaped quotes
; do not end a string, comments cut the line, and negative depth is sticky.
(defun %ide-line-net-depth (codes st d)
  (if (< d 0)
      d
      (if codes
          ((lambda (c)
             (if (= st 3)
                 (%ide-line-net-depth (cdr codes) 2 d)
                 (if (= st 2)
                     (%ide-line-net-depth
                      (cdr codes) (if (= c 92) 3 (if (= c 34) 0 2)) d)
                     (if (= st 1)
                         d
                         (if (= c 59)
                             d
                             (if (= c 34)
                                 (%ide-line-net-depth (cdr codes) 2 d)
                                 (%ide-line-net-depth
                                  (cdr codes) 0
                                  (if (= c 40) (+ d 1)
                                      (if (= c 41) (- d 1) d)))))))))
           (car codes))
          d)))
