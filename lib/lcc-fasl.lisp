; lisp65 — Geräte-FASL-Emitter (B2-Streaming, docs/device-fasl-design.md, Lane K 2026-07-06).
; Emittiert das GEPINNTE Disk-Lib-Containerformat [u16 blob][u16 md][Code-Blob][L65M v1]
; DIREKT in das Bank-4-Datei-Fenster (%fasl-stage/-get; host-testbar via Sim) — der Heap
; hält nur Zähler-Boxen + das EINE gerade kompilierte Objekt (gerätetauglich: 48+384 Zellen).
; Abhängigkeit: lib/lcc.lisp. Prims: %fasl-stage/-stage-get (+ am Gerät %fasl-src/
; %fasl-read-form/%fasl-save; C-Nähte in eval.c/io.c unter LISP65_FASL).
;
; Fenster-Layout (Offsets im Datei-Fenster; FIXNUM-WAND: obj-Encoding = 15-bit signed,
; alle Lisp-sichtbaren Offsets MÜSSEN < 16384 bleiben — v2-Hebel: Area-Prim):
;   [0     ..  8192)  Quelle (%fasl-src staged + Stream-Reader; C-Deckel 0x2000)
;   [8192  .. 14336)  Fasl-Ausgabe (Prefix+Blob+Trailer; 6 KB)
;   [14336 .. 14848)  Entry-Staging   (8 B/Objekt  -> 64 Objekte)
;   [14848 .. 15488)  Node-Staging    (10 B/Node   -> 64 Nodes)
;   [15488 .. 15744)  Patch-Staging   (4 B/Patch   -> 64 Patches)
;   [15744 .. 16384)  String-Staging  (640 B Namen)
; Überläufe brechen LAUT ab (Aufruf einer undefinierten %fasl-error-*-Fn).
;
; v1-Fläche: defuns inkl. Closure-Helfer (BENANNT "<fn>-h<j>" als SYMBOL-Patch — sitzungs-
; unabhängig, dir_find-Loader-Pfad existiert); Littab-Kinds FIX/NIL/T/SYMBOL; ALLE Slots
; gepatcht (Blob-Littab = Nullen, Loader materialisiert via md_lit_node).

; ---- Grundhelfer (autark) ----
(defun %fasl-get (b) (car b))
(defun %fasl-set (b v) (rplaca b v))
(defun %fasl-len2 (l n) (if l (%fasl-len2 (cdr l) (+ n 1)) n))
(defun %fasl-len (l) (%fasl-len2 l 0))
(defun %fasl-app2 (a b) (if a (cons (car a) (%fasl-app2 (cdr a) b)) b))

; ---- Zustand fs = (ocur ne nn np slen . base) — Zähler-Boxen + Output-BASE (immutabel).
; base=8192: Disk-Source-Diagnose (Quelle @ [0..8192), Ausgabe dahinter). base=0: compile-string
; (Quelle ist der Buffer-STRING, [0..) frei -> Ausgabe ab 0 -> save via io_disk_save_named). ----
(defun %fs-ocur (fs) (car fs))
(defun %fs-ne   (fs) (car (cdr fs)))
(defun %fs-nn   (fs) (car (cdr (cdr fs))))
(defun %fs-np   (fs) (car (cdr (cdr (cdr fs)))))
(defun %fs-slen (fs) (car (cdr (cdr (cdr (cdr fs))))))
(defun %fs-base (fs) (car (cdr (cdr (cdr (cdr (cdr fs)))))))
(defun %fasl-fs (base)
  (cons (cons (+ base 4) nil)   ; Ausgabe-Cursor: base + 4 (Prefix wird am Ende gepatcht)
    (cons (cons 0 nil) (cons (cons 0 nil) (cons (cons 0 nil)
      (cons (cons 0 nil) (cons base nil)))))))

; ---- Byte-Schreiber: sequenziell (Ausgabe) + wahlfrei (Staging/Prefix) ----
(defun %fasl-w8 (off v) (if (%fasl-stage off v) nil (%fasl-error-window-overflow)))
(defun %fasl-w16 (off v)
  (let ((lo (mod v 256)))
    (%fasl-w8 off lo)
    (%fasl-w8 (+ off 1) (mod (/ (- v lo) 256) 256))))
(defun %fasl-b (fs v)
  (let ((o (%fasl-get (%fs-ocur fs))))
    (if (> o 14335) (%fasl-error-output-overflow) nil)
    (%fasl-w8 o v)
    (%fasl-set (%fs-ocur fs) (+ o 1))))
(defun %fasl-u16 (fs v)
  (let ((lo (mod v 256)))
    (%fasl-b fs lo)
    (%fasl-b fs (mod (/ (- v lo) 256) 256))))
(defun %fasl-blist (fs l) (if l (progn (%fasl-b fs (car l)) (%fasl-blist fs (cdr l))) nil))
(defun %fasl-zeros (fs n) (if (> n 0) (progn (%fasl-b fs 0) (%fasl-zeros fs (- n 1))) nil))

; ---- String-Staging: Name (Code-Liste) + NUL; liefert name_off ----
(defun %fasl-strw (fs cs off)
  (if cs (progn (%fasl-w8 (+ 15744 off) (car cs)) (%fasl-strw fs (cdr cs) (+ off 1))) off))
(defun %fasl-straddn (fs cs)
  (let ((off (%fasl-get (%fs-slen fs))))
    (let ((end (%fasl-strw fs cs off)))
      (if (> end 638) (%fasl-error-strings-overflow) nil)
      (%fasl-w8 (+ 15744 end) 0)
      (%fasl-set (%fs-slen fs) (+ end 1))
      off)))

; ---- Node-/Patch-Staging (finale Record-Layouts: Node 10 B, Patch 4 B) ----
(defun %fasl-node (fs kind value nameoff)
  (let ((idx (%fasl-get (%fs-nn fs))))
    (if (> idx 63) (%fasl-error-nodes-overflow) nil)
    (let ((a (+ 14848 (* 10 idx))))
      (%fasl-w8 a kind) (%fasl-w8 (+ a 1) 0)
      (%fasl-w16 (+ a 2) value) (%fasl-w16 (+ a 4) 0) (%fasl-w16 (+ a 6) 0)
      (%fasl-w16 (+ a 8) nameoff))
    (%fasl-set (%fs-nn fs) (+ idx 1))
    idx))
(defun %fasl-patchadd (fs boff node)
  (let ((idx (%fasl-get (%fs-np fs))))
    (if (> idx 63) (%fasl-error-patches-overflow) nil)
    (let ((a (+ 15488 (* 4 idx))))
      (%fasl-w16 a boff) (%fasl-w16 (+ a 2) node))
    (%fasl-set (%fs-np fs) (+ idx 1))))

; ---- Entry-Staging (8 B: nameoff u16, bank 0, FLAGS u8, off u16, len u16) ----
; Disk-Lib-v1 ist blobrelativ; der Runtime-Loader bindet die Zielbank beim Commit.
; flags bit0 = MACRO (Codex' Loader-Erweiterung cbe4a8f: registriert T_MACRO(BCODE)).
(defun %fasl-entadd (fs nameoff off len flags)
  (let ((idx (%fasl-get (%fs-ne fs))))
    (if (> idx 63) (%fasl-error-entries-overflow) nil)
    (let ((a (+ 14336 (* 8 idx))))
      (%fasl-w16 a nameoff) (%fasl-w8 (+ a 2) 0) (%fasl-w8 (+ a 3) flags)
      (%fasl-w16 (+ a 4) off) (%fasl-w16 (+ a 6) len))
    (%fasl-set (%fs-ne fs) (+ idx 1))))

; ---- Helfer-Namen "<main>-h<j>" (charset-fest via string->list) ----
(defun %fasl-hname (mainchars j)
  (if (> j 9) (%fasl-error-too-many-helpers) nil)
  (%fasl-app2 mainchars (%fasl-app2 (string->list "-h") (cons (+ 48 j) nil))))

; ---- Literal -> Node (FIX 1, NIL 2, T 3, SYMBOL 4; -1 emittiert als 0xFFFF = kein Name) ----
(defun %fasl-litnode (fs lit mainchars)
  (cond ((if (%lcc-consp lit) (eq (car lit) '%lcc-helper) nil)
         (%fasl-node fs 4 0 (%fasl-straddn fs (%fasl-hname mainchars (car (cdr lit))))))
        ((numberp lit) (%fasl-node fs 1 lit -1))
        ((eq lit nil)  (%fasl-node fs 2 0 -1))
        ((eq lit 't)   (%fasl-node fs 3 0 -1))
        ((symbolp lit) (%fasl-node fs 4 0 (%fasl-straddn fs (string->list (symbol-name lit)))))
        (t (%fasl-error-unsupported-literal))))

; ---- Ein kompiliertes Objekt SOFORT in den Blob streamen + Metadaten stagen ----
(defun %fasl-patchlits (fs lits mainchars boff i)
  (if lits
      (progn (%fasl-patchadd fs (+ boff (+ 7 (* 2 i))) (%fasl-litnode fs (car lits) mainchars))
             (%fasl-patchlits fs (cdr lits) mainchars boff (+ i 1)))
      nil))
(defun %fasl-obj (fs res namechars mainchars flags)
  (let ((nlit (%fasl-len (car (cdr (cdr (cdr res))))))
        (ncode (%fasl-len (car (cdr (cdr (cdr (cdr res)))))))
        (boff (- (%fasl-get (%fs-ocur fs)) (+ (%fs-base fs) 4))))
    (%fasl-entadd fs (%fasl-straddn fs namechars) boff (+ 7 (+ (* 2 nlit) ncode)) flags)
    (%fasl-patchlits fs (car (cdr (cdr (cdr res)))) mainchars boff 0)
    (%fasl-b fs 181)                                   ; CO_MAGIC 0xB5
    (%fasl-b fs (car res))                             ; nargs
    (%fasl-b fs (car (cdr res)))                       ; nlocals
    (%fasl-b fs (car (cdr (cdr res))))                 ; flags
    (%fasl-u16 fs ncode)
    (%fasl-b fs nlit)
    (%fasl-zeros fs (* 2 nlit))                        ; Littab = Nullen (alles gepatcht)
    (%fasl-blist fs (car (cdr (cdr (cdr (cdr res))))))))

; ---- Eine defun-Form: Objekte = (h0 h1 ... main) ----
(defun %fasl-form2 (fs objs mainchars j mflags)   ; mflags nur fuers MAIN (Helfer = Fns)
  (if (cdr objs)
      (progn (%fasl-obj fs (car objs) (%fasl-hname mainchars j) mainchars 0)
             (%fasl-form2 fs (cdr objs) mainchars (+ j 1) mflags))
      (%fasl-obj fs (car objs) mainchars mainchars mflags)))
(defun %fasl-form (fs form)
  (cond ((if (%lcc-consp form) (eq (car form) 'defun) nil)
         (%fasl-form2 fs (lcc-compile-obj form)
                      (string->list (symbol-name (car (cdr form)))) 0 0))
        ; defmacro (FASL v2 via Codex' Macro-Flag): Expander als Lambda kompilieren,
        ; Main-Entry mit flags=1 -> Loader registriert T_MACRO(BCODE).
        ((if (%lcc-consp form) (eq (car form) 'defmacro) nil)
         (%fasl-form2 fs (lcc-compile-obj (cons 'lambda (cdr (cdr form))))
                      (string->list (symbol-name (car (cdr form)))) 0 1))
        (t (%fasl-error-not-a-defun))))
(defun %fasl-forms (fs forms)
  (if forms (progn (%fasl-form fs (car forms)) (%fasl-forms fs (cdr forms))) nil))

; ---- Abschluss: Trailer (Header + Staging-Kopien) + Prefix-Backpatch; liefert Dateilänge ----
(defun %fasl-copy (fs from n)
  (if (> n 0) (progn (%fasl-b fs (%fasl-stage-get from)) (%fasl-copy fs (+ from 1) (- n 1))) nil))
; GERÄTE-REALITÄT: 255-B-Objektgrenze (vm_dir_add lehnt größere STILL ab — HW-Fund B3:
; %fasl-finish war 386 B und fehlte im Boot-Directory) -> Kaskaden-Split wie in lcc.lisp.
(defun %fasl-hdr1 (fs bl ml)   ; Magic "L65M" roh (charset-fest), ver, hdrsize, flags, base, Längen
  (%fasl-b fs 76) (%fasl-b fs 54) (%fasl-b fs 53) (%fasl-b fs 77)
  (%fasl-b fs 1) (%fasl-b fs 38) (%fasl-u16 fs 0)
  (%fasl-u16 fs 0) (%fasl-u16 fs 0)
  (%fasl-u16 fs bl) (%fasl-u16 fs ml))
(defun %fasl-hdr2 (fs ne nn np)   ; Zähler (Index-Sektion v1 leer)
  (%fasl-u16 fs ne) (%fasl-u16 fs 0) (%fasl-u16 fs nn) (%fasl-u16 fs np))
(defun %fasl-hdr3 (fs noff poff soff sb)   ; Offsets (eoff=38 konstant, ioff==noff) + reserved
  (%fasl-u16 fs 38) (%fasl-u16 fs noff) (%fasl-u16 fs noff)
  (%fasl-u16 fs poff) (%fasl-u16 fs soff) (%fasl-u16 fs sb)
  (%fasl-u16 fs 0))
(defun %fasl-copies (fs ne nn np sb)
  (%fasl-copy fs 14336 (* 8 ne))
  (%fasl-copy fs 14848 (* 10 nn))
  (%fasl-copy fs 15488 (* 4 np))
  (%fasl-copy fs 15744 sb))
(defun %fasl-finish (fs)
  (let ((base (%fs-base fs))
        (bl (- (%fasl-get (%fs-ocur fs)) (+ (%fs-base fs) 4)))
        (ne (%fasl-get (%fs-ne fs)))
        (nn (%fasl-get (%fs-nn fs)))
        (np (%fasl-get (%fs-np fs)))
        (sb (%fasl-get (%fs-slen fs))))
    (let ((noff (+ 38 (* 8 ne))))
      (let ((poff (+ noff (* 10 nn))))
        (let ((soff (+ poff (* 4 np))))
          (let ((raw (+ soff sb)))
            (let ((ml (+ raw (mod raw 2))))
              (%fasl-hdr1 fs bl ml)
              (%fasl-hdr2 fs ne nn np)
              (%fasl-hdr3 fs noff poff soff sb)
              (%fasl-copies fs ne nn np sb)
              (%fasl-zeros fs (- ml raw))                   ; align2-Pad (0 oder 1 Byte)
              (%fasl-w16 base bl) (%fasl-w16 (+ base 2) ml)  ; Prefix-Backpatch @ base/base+2
              (+ 4 (+ bl ml)))))))))

; ---- Einstiege ----
; Host-Gate/Programmatisch: Formen-Liste -> Fasl im Fenster @16384; liefert Dateilänge.
(defun fasl-emit-scratch (forms)
  (let ((fs (%fasl-fs 8192)))
    (%fasl-forms fs forms)
    (%fasl-finish fs)))

; 1.1-C1 shelf export.  Emission keeps the established byte-at-a-time staging
; path; only the completed output crosses the resident boundary, once, as a
; detached Buffer through the batched operation 2 carrier.
(defun %c1-compile-source (source)
  (progn
    (%cs-read-open source)
    (let ((fs (%fasl-fs 0)))
      (%fasl-stream-forms fs)
      (let ((length (%fasl-finish fs)))
        (%buffer-alloc 2 length)))))

; One export is sufficient for both resident call sites and reduces the
; checkpoint to one function-cell binding. Mode 0 compiles an eval form; mode
; 1 prepares a persistent source result plus its already-validated slot.
(defun %c1-compile (mode first second)
  (if (= mode 0)
      (%c1-compile-form first)
      (%c1-compile-source first)))
; Gerät: Quelle von Disk lesen (Form für Form, OHNE Auswertung), Fasl in Slot dst schreiben.
(defun %fasl-stream-forms (fs)
  (let ((f (%fasl-read-form)))
    (if (eq f '%fasl-eof) nil
        (progn (%fasl-form fs f) (%fasl-stream-forms fs)))))

(defun compile-error ()
  (symbol-value (quote %compile-error)))

(defun %compile-slot-scan-entries (codes entry)
  (if (= entry 8)
      nil
      (let ((base (* entry 32)))
        (if (%load-entry-match-p codes base)
            (cons (%load-entry-byte base 3) (%load-entry-byte base 4))
            (%compile-slot-scan-entries codes (1+ entry))))))

(defun %compile-slot-find (codes track sector fuel)
  (if (> fuel 0)
      (if (%disk-read-sector track sector)
          (let ((hit (%compile-slot-scan-entries codes 0)))
            (if hit
                hit
                (let ((next-track (%disk-byte 0))
                      (next-sector (%disk-byte 1)))
                  (if (%disk-directory-link-valid-p
                       track sector next-track next-sector)
                      (if (> next-track 0)
                          (%compile-slot-find codes next-track next-sector (1- fuel))
                          nil)
                      nil))))
          nil)
      nil))

(defun %compile-slot-capacity (track sector fuel cap)
  (if (> fuel 0)
      (if (%disk-read-sector track sector)
          (let ((next-track (%disk-byte 0))
                (next-sector (%disk-byte 1)))
            (if (if (= next-track 0)
                    (> next-sector 0)
                    (if (and (<= next-track 80) (< next-sector 40))
                        (not (and (= next-track track) (= next-sector sector)))
                        nil))
                (let ((cap2 (+ cap (if (> next-track 0) 254 (- next-sector 1)))))
                  (if (> next-track 0)
                      (%compile-slot-capacity next-track next-sector (1- fuel) cap2)
                      cap2))
                0))
          0)
      0))

(defun compile-file (src dst)
  (if (> (%fasl-src src) 0)
      (let ((fs (%fasl-fs 8192)))
        (%fasl-stream-forms fs)
        (%fasl-save dst 8192 (%fasl-finish fs)))
      nil))
; WORKBENCH-SLOW-PATH (2026-07-08): Quelle ist der IDE-Buffer-STRING (kein Disk-Source, kein
; disk_dir_find). %cs-read-open setzt den Reader ueber den Arena-String; %fasl-stream-forms liest
; Form fuer Form OHNE Eval und gibt sie an den Emitter. GC-sicher unter Arena: der Reader-Cursor
; IST der Quell-String (== gerooteter compile-string-Arg), nur ein Byte-Index laeuft.
(defun compile-string (source dst)
  (progn
    (set-symbol-value (quote %compile-error) nil)
    (if (stringp source)
        (if (stringp dst)
            (let ((slot (%compile-slot-find (string->list dst) 40 0 64)))
              (if slot
                  (progn
                    (%cs-read-open source)
                    (let ((fs (%fasl-fs 0)))        ; Ausgabe @ base=0 (Quelle ist der String)
                      (%fasl-stream-forms fs)
                      (let ((len (%fasl-finish fs)))
                        (if (> len (%compile-slot-capacity (car slot) (cdr slot) 255 0))
                            (progn (set-symbol-value (quote %compile-error) "too large") nil)
                            (if (%save-staged dst len) ; base=0 -> io_disk_save_named (kein base-Arg)
                                (progn (set-symbol-value (quote %compile-error) nil) 't)
                                (progn (set-symbol-value (quote %compile-error) "save failed") nil))))))
                  (progn (set-symbol-value (quote %compile-error) "slot missing") nil)))
            (progn (set-symbol-value (quote %compile-error) "bad slot") nil))
        (progn (set-symbol-value (quote %compile-error) "bad source") nil))))
