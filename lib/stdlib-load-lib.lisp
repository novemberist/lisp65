; Bytecode-Lisp LOAD-LIB for standalone bytecode libraries on the MEGA65 F011 path.
; Reuses the directory helpers from stdlib-load.lisp; C only stages and registers the blob.

(defun %load-lib-from-entry (base)
  (%disk-load-lib (%load-entry-byte base 3) (%load-entry-byte base 4)))

(defun %load-lib-scan-entries (codes entry)
  (if (= entry 8)
      nil
      (let ((base (* entry 32)))
        (if (%load-entry-match-p codes base)
            (%load-lib-from-entry base)
            (%load-lib-scan-entries codes (1+ entry))))))

; fuel + (> next-track 0)-Terminator wie bei (load): nur NIL ist falsch, die Fixnum 0 ist truthy;
; (if next-track ...) wuerde am Kettenende endlos rekursieren (= Hang bei fehlender Lib). S. stdlib-load.
(defun %load-lib-scan-directory (codes track sector fuel)
  (if (> fuel 0)
      (if (%disk-read-sector track sector)
          (let ((loaded (%load-lib-scan-entries codes 0)))
            (if loaded
                loaded
                (let ((next-track (%disk-byte 0))
                      (next-sector (%disk-byte 1)))
                  (if (%disk-directory-link-valid-p
                       track sector next-track next-sector)
                      (if (> next-track 0)
                          (%load-lib-scan-directory codes next-track next-sector (1- fuel))
                          nil)
                      nil))))
          nil)
      nil))

(defun %load-lib-codes-equal-p (a b)
  (if a
      (if b
          (if (= (car a) (car b))
              (%load-lib-codes-equal-p (cdr a) (cdr b))
              nil)
          nil)
      (if b nil t)))

(defun %load-lib-loaded-p (codes loaded)
  (if loaded
      (if (%load-lib-codes-equal-p codes (car loaded))
          t
          (%load-lib-loaded-p codes (cdr loaded)))
      nil))

(defun %load-lib-note-loaded (codes)
  (set-symbol-value '*loaded-libs* (cons codes (symbol-value '*loaded-libs*))))

(defun load-lib (name)
  (if (stringp name)
      (let ((codes (string->list name)))
        (if (%load-lib-loaded-p codes (symbol-value '*loaded-libs*))
            t
            (if (%disk-load-lib name)
                (progn (%load-lib-note-loaded codes) t)
                ; Missing/invalid volatile shelf: retain the proven 1.0 disk path.
                ; T40/S0 is the 1581 header/link root, never an entry sector.
                (if (%load-lib-scan-directory codes 40 3 64)
                    (progn (%load-lib-note-loaded codes) t)
                    nil))))
      nil))

; load-libs: mehrere (unabhaengige) Libs mit EINEM Aufruf laden -- als einzelne Argumente ODER
; als eine Liste als einziges Argument:
;   (load-libs "strings" "math")      ; variadisch
;   (load-libs '("strings" "math"))   ; Liste
; Laedt JEDE Lib (auch wenn eine fehlt); Rueckgabe t nur, wenn ALLE geladen wurden, sonst nil.
; (let bindet beide Zweige -> head UND tail werden ausgewertet -> alle Libs werden geladen.)
(defun %load-libs-seq (names)
  (if names
      (let ((head (load-lib (car names)))
            (tail (%load-libs-seq (cdr names))))
        (if head tail nil))
      t))

(defun load-libs (&rest names)
  (%load-libs-seq
    (if names
        (if (cdr names)
            names                                  ; >=2 Argumente -> die Namen selbst
            (if (stringp (car names)) names (car names)))  ; 1 Argument: String -> (name); Liste -> auspacken
        nil)))
