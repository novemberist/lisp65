; Bytecode-Lisp LOAD for the MEGA65 F011 Rule-B path.
; C provides only sector/buffer primitives; the 1581 directory policy lives here.

(defun %load-fold-code (code)
  (let ((c (if (> code 127) (- code 128) code)))
    (if (and (>= c 97) (<= c 122))
        (- c 32)
        c)))

(defun %load-name-code-at (codes index)
  (if codes
      (if (> index 0)
          (%load-name-code-at (cdr codes) (1- index))
          (%load-fold-code (car codes)))
      32))

(defun %load-entry-byte (base offset)
  (%disk-byte (+ base offset)))

(defun %load-entry-used-p (base)
  (not (= (mod (%load-entry-byte base 2) 8) 0)))

(defun %load-name-match-at (codes base index)
  (if (= index 16)
      t
      (if (= (%load-fold-code (%load-entry-byte base (+ 5 index)))
             (%load-name-code-at codes index))
          (%load-name-match-at codes base (1+ index))
          nil)))

(defun %load-entry-match-p (codes base)
  (if (%load-entry-used-p base)
      (%load-name-match-at codes base 0)
      nil))

(defun %load-from-entry (base)
  (%disk-load-file (%load-entry-byte base 3) (%load-entry-byte base 4)))

(defun %load-scan-entries (codes entry)
  (if (= entry 8)
      nil
      (let ((base (* entry 32)))
        (if (%load-entry-match-p codes base)
            (%load-from-entry base)
            (%load-scan-entries codes (1+ entry))))))

; fuel begrenzt die Sektorkette (Schutz gegen zyklische/korrupte Verzeichnisse -> kein Hang).
; WICHTIG: Kettenende per (> next-track 0) pruefen, NICHT per Truthiness: nur NIL ist falsch,
; die Fixnum 0 (MKFIX(0)=1) ist truthy -> (if next-track ...) wuerde am Kettenende (track 0)
; endlos weiterrekursieren (TCO'd) und Muell-Sektoren lesen (= der Hang bei fehlender Datei).
(defun %disk-directory-link-valid-p (track sector next-track next-sector)
  (if (= next-track 0)
      t
      (if (= next-track 40)
          (if (< next-sector 40)
              (not (and (= next-track track) (= next-sector sector)))
              nil)
          nil)))

(defun %load-scan-directory (codes track sector fuel)
  (if (> fuel 0)
      (if (%disk-read-sector track sector)
          (let ((loaded (%load-scan-entries codes 0)))
            (if loaded
                loaded
                (let ((next-track (%disk-byte 0))
                      (next-sector (%disk-byte 1)))
                  (if (%disk-directory-link-valid-p
                       track sector next-track next-sector)
                      (if (> next-track 0)
                          (%load-scan-directory codes next-track next-sector (1- fuel))
                          nil)
                      nil))))
          nil)
      nil))

(defun load (name)
  (if (stringp name)
      ; T40/S0 is the 1581 header/link root, never an entry sector.
      (%load-scan-directory (string->list name) 40 3 64)
      nil))
