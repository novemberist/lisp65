; lisp65 — lcc: der selbst-gehostete Bytecode-Compiler (Self-Hosting, Lane K; Start 2026-07-05).
; Plan: docs/self-hosting-plan.md. Ziel-ABI: docs/bytecode-abi.md (P0, GEPINNT); Byte-Orakel:
; scripts/lcc-oracle.py (byte-exakt gegen bytecode_p0_compiler.py, make-check-Gate).
;
; STAND P3 (Closures) auf P2: lambda-als-Wert wird als HELPER-Fn kompiliert; freie Variablen
; werden transitiv über die EBENEN-Liste aufgelöst (resolve_uv-Analog: äußeres Local via=0,
; äußere Upvalue via=1), die Creation-Site pusht die Upvalue-Werte + OP_CLOSURE(63); Zugriff
; im Rumpf via OP_UPVAL(64), setq freier Variablen via OP_SETUPVAL(65). Helper-Referenzen
; stehen als MARKER-Literale (%lcc-helper <idx>) in der littab — der Lauf-Harness ersetzt sie
; beim Registrieren durch MK_BCODE(di) (OP_CLOSURE/funcall nehmen BCODE-Immediates direkt).
; Capture-frei -> PUSHLIT <marker> (Fast-Path wie C). Immediate-Lambda ((lambda ..) args)
; wird wie let gelowert (Referenz-Verhalten).
; VORHER (P2): Ausdrücke (P0) + BINDUNGEN (let/let*/lokales setq, Slot-Vergabe monoton — kein
; Slot-Reuse nach Scope-Ende, wie die Referenz) + AUFRUFE (CALLPRIM-Tabelle, generisches CALL
; mit Callee-Symbol-Literal, funcall/apply via PRIMS) + Params (PUSHARG0-2/PUSHARGN) +
; GLOBALS wie der C-Compiler (Read → CALLPRIM 19, setq → CALLPRIM 20; der Python-Referenz-
; Compiler kennt keine Globals → im Byte-Orakel ausgespart, Semantik prüft P2 auf der VM).
;
; Repräsentationen:
;   st   = (bytes-rev . laenge)                Emissions-Zustand, O(1)-Append
;   cs   = (st lits-rev maxslot fnsbox)        Compiler-Zustand; fnsbox = mutierbare Helper-Liste
;   lvls  = ((name slot kind) ...)              Umgebung EINER Ebene; kind = a (Param) | l (Local)
;   lvls = ((lvls . uvbox) ...)                 Ebenen, jüngste zuerst; uvbox = (uvs-rev . n),
;                                              uv = (name src via)  [via: 0=Local, 1=Upvalue]
; Branch-Patching: die frisch emittierte acc-Zelle IST das Offset-Byte -> (rplaca zelle d).

; ---- Opcodes (ABI-Wahrheit src/vm.h; Byte-Orakel prüft) ----
; GERAETE-GRENZE (vom P5-Fixpunkt-Test erzwungen): Code-Objekte <= 255 B (dir_len uint8)
; -> grosse cond-Dispatches sind in Haelften gesplittet (t-Klausel = Tail-Call in Teil 2).
(defun %lcc-op (name)
  (cond ((eq name 'pushi8) 1) ((eq name 'add) 2) ((eq name 'ret) 5) ((eq name 'pushlit) 6)
        ((eq name 'sub) 14) ((eq name 'mul) 15) ((eq name 'div) 16) ((eq name 'mod) 17)
        ((eq name 'less) 18) ((eq name 'greater) 19) ((eq name 'remainder) 24)
        ((eq name 'jmprel) 28) ((eq name 'jfalserel) 29) ((eq name 'eq) 30)
        ((eq name 'not) 42) ((eq name 'pushnil) 43) ((eq name 'pusht) 44)
        (t (%lcc-op2 name nil))))

; Der zweite Dispatcher traegt zwei explizit getrennte Tails, damit beide Codeobjekte
; unter dem 255-B-Limit bleiben, ohne einen weiteren Stdlib-/Symbol-Eintrag zu verbrauchen.
(defun %lcc-op2 (name prim)
  (if prim
      (cond ((eq name 'symbol-value) 19) ((eq name 'set-symbol-value) 20)
            ((eq name '%disk-poke) 21) ((eq name '%disk-write-sector) 22)
            (t nil))
      (cond ((eq name 'cons) 51) ((eq name 'car) 52) ((eq name 'cdr) 53)
            ((eq name 'consp) 54) ((eq name 'eql) 55)
            ((eq name 'pushargn) 56) ((eq name 'loadl) 57) ((eq name 'storel) 58)
            ((eq name 'drop) 59) ((eq name 'call) 60) ((eq name 'callprim) 61)
            ((eq name 'tailcall) 62) ((eq name 'closure) 63) ((eq name 'upval) 64)
            ((eq name 'setupval) 65)
            (t nil))))

; CALLPRIM-Tabelle (== PRIMS in src/compile.c; ABI §4a, IDs gepinnt)
(defun %lcc-prim (name)
  (cond ((eq name 'stringp) 0) ((eq name 'string->list) 1) ((eq name 'list->string) 2)
        ((eq name 'string-length) 3) ((eq name 'string-ref) 4)
        ((eq name 'symbolp) 5) ((eq name 'numberp) 6)
        ((eq name 'apply) 7) ((eq name 'funcall) 8)
        ((eq name 'screen-size) 9) ((eq name 'screen-clear) 10)
        ((eq name 'screen-put-char) 11) ((eq name 'screen-write-string) 12)
        ((eq name 'read-key) 13) ((eq name 'poll-key) 14)
        ((eq name '%disk-read-sector) 15) ((eq name '%disk-byte) 16)
        ((eq name '%disk-load-file) 17) ((eq name '%disk-load-lib) 18)
        (t (%lcc-op2 name t))))

; ---- Selbsttragende Helfer (length/reverse/consp/null sind KEINE Treewalk-Prims!) ----
(defun %lcc-len (l) (if l (+ 1 (%lcc-len (cdr l))) 0))
(defun %lcc-rev-into (l acc) (if l (%lcc-rev-into (cdr l) (cons (car l) acc)) acc))
(defun %lcc-rev (l) (%lcc-rev-into l nil))
(defun %lcc-consp (x)
  (if x (if (numberp x) nil (if (symbolp x) nil (if (stringp x) nil t))) nil))
(defun %lcc-equal (a b)
  (if (eql a b)
      t
      (if (%lcc-consp a)
          (if (%lcc-consp b)
              (if (%lcc-equal (car a) (car b)) (%lcc-equal (cdr a) (cdr b)) nil)
              nil)
          nil)))

; ---- cs-Accessoren/Konstruktor ----
(defun %lcc-cs (st lits maxslot fns) (cons st (cons lits (cons maxslot (cons fns nil)))))
(defun %lcc-st (cs) (car cs))
(defun %lcc-lits (cs) (car (cdr cs)))
(defun %lcc-max (cs) (car (cdr (cdr cs))))
(defun %lcc-fns (cs) (car (cdr (cdr (cdr cs)))))   ; mutierbare Box (fns-rev . zaehler)

; ---- Emission ----
(defun %lcc-emit-st (st b) (cons (cons b (car st)) (+ (cdr st) 1)))
(defun %lcc-emit (cs b)
  (%lcc-cs (%lcc-emit-st (%lcc-st cs) b) (%lcc-lits cs) (%lcc-max cs) (%lcc-fns cs)))
(defun %lcc-emit-op (cs name) (%lcc-emit cs (%lcc-op name)))
(defun %lcc-emit2 (cs name b) (%lcc-emit (%lcc-emit-op cs name) b))

; ---- Literal-Tabelle (Dedup STRUKTURELL wie die Referenz) ----
(defun %lcc-lit-find (lits-rev o n)
  (if lits-rev
      (if (%lcc-equal (car lits-rev) o)
          (- n 1)
          (%lcc-lit-find (cdr lits-rev) o (- n 1)))
      nil))

; littab-Slot vergeben/wiederfinden OHNE Emission: -> (cs . index)
(defun %lcc-lit-slot (cs o)
  ((lambda (n)
     ((lambda (hit)
        (if hit
            (cons cs hit)
            (cons (%lcc-cs (%lcc-st cs) (cons o (%lcc-lits cs)) (%lcc-max cs) (%lcc-fns cs)) n)))
      (%lcc-lit-find (%lcc-lits cs) o n)))
   (%lcc-len (%lcc-lits cs))))

(defun %lcc-push-lit (cs o)
  ((lambda (r) (%lcc-emit2 (car r) 'pushlit (cdr r)))
   (%lcc-lit-slot cs o)))

(defun %lcc-push-value (cs o)
  (cond ((eq o nil) (%lcc-emit-op cs 'pushnil))
        ((eq o 't) (%lcc-emit-op cs 'pusht))
        ((numberp o)
         (if (and (> o -129) (< o 128))
             (%lcc-emit2 cs 'pushi8 (if (< o 0) (+ o 256) o))
             (%lcc-push-lit cs o)))
        (t (%lcc-push-lit cs o))))

; ---- Umgebung EINER Ebene: ((name slot kind) ...) ----
(defun %lcc-env-find (e name)
  (if e
      (if (eq (car (car e)) name) (car e) (%lcc-env-find (cdr e) name))
      nil))

; ---- Ebenen (P3): lvls = ((lvls . uvbox) ...), jüngste zuerst; uvbox = (uvs-rev . n),
; uv = (name src via kind). Mutation der uvbox via rplaca/rplacd (Sammlung wächst beim
; Auflösen mitten in der Rumpf-Kompilierung — das C-Analog ist cc_lvl[]). ----
(defun %lcc-top-env (lvls) (car (car lvls)))
(defun %lcc-uvbox (lvl) (cdr lvl))
(defun %lcc-with-top-env (lvls e) (cons (cons e (%lcc-uvbox (car lvls))) (cdr lvls)))

(defun %lcc-uv-index (uvs name n)
  (if uvs
      (if (eq (car (car uvs)) name) (- n 1) (%lcc-uv-index (cdr uvs) name (- n 1)))
      nil))

(defun %lcc-uv-add (box name src via kind)
  ((lambda (n)
     (progn
       (rplaca box (cons (cons name (cons src (cons via (cons kind nil)))) (car box)))
       (rplacd box (+ n 1))
       n))
   (cdr box)))

; resolve_uv-Analog (transitiv): name als Upvalue der OBERSTEN Ebene auflösen -> Index oder nil.
; Dedup in der uvbox; äußeres Local (Ebene darunter) -> via=0 (+kind fuer die Creation-Site);
; tiefer -> rekursiv als Upvalue der äußeren Ebene -> via=1.
(defun %lcc-resolve-uv (name lvls)
  (if (cdr lvls)
      ((lambda (box)
         ((lambda (hit)
            (if hit
                hit
                ((lambda (e)
                   (if e
                       (%lcc-uv-add box name (car (cdr e)) 0 (car (cdr (cdr e))))
                       ((lambda (up)
                          (if up (%lcc-uv-add box name up 1 'l) nil))
                        (%lcc-resolve-uv name (cdr lvls)))))
                 (%lcc-env-find (%lcc-top-env (cdr lvls)) name))))
          (%lcc-uv-index (car box) name (cdr box))))
       (%lcc-uvbox (car lvls)))
      nil))

; Slot-Zugriff nach Art (emit_arg-Analog): Param slot<3 -> PUSHARG0+slot, sonst PUSHARGN;
; Local -> LOADL.
(defun %lcc-emit-slot (cs slot kind)
  (if (eq kind 'a)
      (if (< slot 3)
          (%lcc-emit cs (+ 11 slot))
          (%lcc-emit2 cs 'pushargn slot))
      (%lcc-emit2 cs 'loadl slot)))

; Variablen-Zugriff: lokale Ebene -> Slot; freie Var -> Upvalue (transitiv, OP_UPVAL);
; sonst GLOBAL-Read (PUSHLIT sym + CALLPRIM 19 1; wie src/compile.c).
(defun %lcc-var (cs lvls name)
  ((lambda (e)
     (if e
         (%lcc-emit-slot cs (car (cdr e)) (car (cdr (cdr e))))
         ((lambda (uvi)
            (if uvi
                (%lcc-emit2 cs 'upval uvi)
                (%lcc-emit (%lcc-emit (%lcc-emit-op (%lcc-push-lit cs name) 'callprim) 19) 1)))
          (%lcc-resolve-uv name lvls))))
   (%lcc-env-find (%lcc-top-env lvls) name)))

; ---- Lowering: and/or/cond/when/unless -> if/let/progn-Formen (== Referenz-Compiler ==
; == unsere prelude-macros!). or/cond-Einzelklausel binden den Testwert per gensym-Temp
; (die Referenz vergibt dafuer einen echten Slot). list/gensym sind Treewalk-Prims. ----
(defun %lcc-lower-and (args)
  (if args
      (if (cdr args)
          (list 'if (car args) (cons 'and (cdr args)) nil)
          (car args))
      't))

(defun %lcc-lower-or (args)
  (if args
      (if (cdr args)
          ((lambda (tmp)
             (list 'let (list (list tmp (car args)))
                   (list 'if tmp tmp (cons 'or (cdr args)))))
           (gensym))
          (car args))
      nil))

(defun %lcc-lower-when (args) (list 'if (car args) (cons 'progn (cdr args)) nil))
(defun %lcc-lower-unless (args) (list 'if (car args) nil (cons 'progn (cdr args))))

(defun %lcc-lower-cond (cls)
  (if cls
      ((lambda (cl rest)
         (if (eq (car cl) 't)
             (if (cdr cl) (cons 'progn (cdr cl)) 't)   ; t-Klausel = direktes else (Referenz!)
             (if (cdr cl)
             (list 'if (car cl) (cons 'progn (cdr cl)) (cons 'cond rest))
             ((lambda (tmp)
                (list 'let (list (list tmp (car cl)))
                      (list 'if tmp tmp (cons 'cond rest))))
              (gensym)))))
       (car cls) (cdr cls))
      nil))

; ---- Sequenz/progn ----
(defun %lcc-seq (cs lvls body)
  (if body
      (if (cdr body)
          (%lcc-seq (%lcc-emit-op (%lcc-expr cs lvls (car body)) 'drop) lvls (cdr body))
          (%lcc-expr cs lvls (car body)))
      (%lcc-push-value cs nil)))

; ---- if (rel8-Patching) ----
(defun %lcc-if (cs lvls args)
  ((lambda (cs2)
     ((lambda (hole1 len1)
        ((lambda (cs4)
           ((lambda (hole2 len2)
              ((lambda (cs5)
                 (progn
                   (rplaca hole1 (- len2 len1))
                   (rplaca hole2 (- (cdr (%lcc-st cs5)) len2))
                   cs5))
               (%lcc-expr cs4 lvls (if (cdr (cdr args)) (car (cdr (cdr args))) nil))))
            (car (%lcc-st cs4)) (cdr (%lcc-st cs4))))
         (%lcc-emit (%lcc-emit-op (%lcc-expr cs2 lvls (car (cdr args))) 'jmprel) 0)))
      (car (%lcc-st cs2)) (cdr (%lcc-st cs2))))
   (%lcc-emit (%lcc-emit-op (%lcc-expr cs lvls (car args)) 'jfalserel) 0)))

; ---- do/do*/dotimes/dolist NATIV (C-Phase Fix (b), d097468): echte Schleife via
; Rückwärts-JMPREL = KONSTANTER Stack. Die Makro-Templates (funcall-Rekursion) fraßen
; ~15 VM-Slots je Iteration, und Blob-Makros existieren am Gerät (noch) nicht.
; JMPREL ist int8: Test+Result+Körper+Steps über ~120 B brechen LAUT ab.
; do = parallele Binds/Steps (Werte erst alle pushen, dann rückwärts STOREL);
; do* = sequentiell. dotimes/dolist = Zucker (Count/Liste via gensym-Temp EINMAL evaluiert). ----
(defun %lcc-expr-do (cs lvls op args)   ; Dispatch-Stufe (255-B-Gate: sf2 war 263 B)
  (cond ((eq op 'do)   (%lcc-do cs lvls args nil))
        ((eq op 'do*)  (%lcc-do cs lvls args t))
        ((eq op 'dotimes) (%lcc-do cs lvls (%lcc-lower-dotimes (car args) (cdr args)) nil))
        (t (%lcc-do cs lvls (%lcc-lower-dolist (car args) (cdr args)) nil))))
(defun %lcc-do-p (op)
  (cond ((eq op 'do) t) ((eq op 'do*) t) ((eq op 'dotimes) t) ((eq op 'dolist) t) (t nil)))
(defun %lcc-do-norm (bs)
  (if bs
      (cons (if (%lcc-consp (car bs)) (car bs) (cons (car bs) nil))
            (%lcc-do-norm (cdr bs)))
      nil))
(defun %lcc-do-body (cs lvls body)
  (if body
      (%lcc-do-body (%lcc-emit-op (%lcc-expr cs lvls (car body)) 'drop) lvls (cdr body))
      cs))
(defun %lcc-storel-name (cs lvls name)
  (%lcc-emit2 cs 'storel (car (cdr (%lcc-env-find (%lcc-top-env lvls) name)))))
(defun %lcc-do-steps (cs lvls bs star)
  (if bs
      (if (cdr (cdr (car bs)))
          ((lambda (cs2)
             (%lcc-do-steps (if star (%lcc-storel-name cs2 lvls (car (car bs))) cs2)
                            lvls (cdr bs) star))
           (%lcc-expr cs lvls (car (cdr (cdr (car bs))))))
          (%lcc-do-steps cs lvls (cdr bs) star))
      cs))
(defun %lcc-do-store-rev (cs lvls bs)
  (if bs
      ((lambda (cs2)
         (if (cdr (cdr (car bs))) (%lcc-storel-name cs2 lvls (car (car bs))) cs2))
       (%lcc-do-store-rev cs lvls (cdr bs)))
      cs))
(defun %lcc-do-loop (cs1 lvls2 bs endc body star top)
  (let ((cs2 (%lcc-emit (%lcc-emit-op (%lcc-expr cs1 lvls2 (car endc)) 'jfalserel) 0)))
    (let ((hbody (car (%lcc-st cs2))) (lbody (cdr (%lcc-st cs2))))
      (let ((cs3 (%lcc-emit (%lcc-emit-op
                             (%lcc-seq cs2 lvls2 (if (cdr endc) (cdr endc) (cons nil nil)))
                             'jmprel) 0)))
        (let ((hexit (car (%lcc-st cs3))) (lexit (cdr (%lcc-st cs3))))
          (let ((cs5 (if star
                         (%lcc-do-steps (%lcc-do-body cs3 lvls2 body) lvls2 bs t)
                         (%lcc-do-store-rev (%lcc-do-steps (%lcc-do-body cs3 lvls2 body)
                                                           lvls2 bs nil)
                                            lvls2 bs))))
            (let ((cs6 (%lcc-emit-op cs5 'jmprel)))
              (let ((d (- top (+ (cdr (%lcc-st cs6)) 1))))
                (if (< d -127) (%lcc-error-do-body-too-big) nil)
                (let ((cs7 (%lcc-emit cs6 (mod d 256))))
                  (rplaca hbody (- lexit lbody))
                  (rplaca hexit (- (cdr (%lcc-st cs7)) lexit))
                  cs7)))))))))
(defun %lcc-do (cs lvls args star)
  (let ((bs (%lcc-do-norm (car args))))
    (let ((r (%lcc-let-binds cs lvls lvls bs star)))
      (%lcc-do-loop (car r) (cdr r) bs (car (cdr args))
                    (cdr (cdr args)) star (cdr (%lcc-st (car r)))))))
(defun %lcc-lower-dotimes (spec body)
  (let ((v (car spec)) (n (gensym)))
    (cons (list (list v 0 (list '+ v 1)) (list n (car (cdr spec))))
          (cons (cons (list '>= v n)
                      (if (cdr (cdr spec)) (cons (car (cdr (cdr spec))) nil) nil))
                body))))
(defun %lcc-lower-dolist (spec body)
  (let ((xs (gensym)))
    (cons (list (list xs (car (cdr spec)) (list 'cdr xs)))
          (cons (cons (list 'eq xs nil)
                      (if (cdr (cdr spec)) (cons (car (cdr (cdr spec))) nil) nil))
                (cons (cons 'let (cons (list (list (car spec) (list 'car xs))) body)) nil)))))

; ---- let/let*: Inits + STOREL auf fortlaufende Slots (monoton, kein Reuse) ----
; star=nil: Inits im AUSSEN-lvls (paralleles let); star=t: im wachsenden lvls (let*).
; Rückgabe (cs . lvls-mit-Bindungen).
(defun %lcc-let-binds (cs lvls0 lvls bs star)
  (if bs
      ((lambda (name init)
         ((lambda (slot)
            ((lambda (cs2)
               (%lcc-let-binds
                (%lcc-cs (%lcc-st cs2) (%lcc-lits cs2) (+ slot 1) (%lcc-fns cs2))
                lvls0
                (%lcc-with-top-env lvls
                                   (cons (cons name (cons slot (cons 'l nil)))
                                         (%lcc-top-env lvls)))
                (cdr bs) star))
             (%lcc-emit2 (%lcc-expr cs (if star lvls lvls0) init) 'storel slot)))
          (%lcc-max cs)))
       (if (%lcc-consp (car bs)) (car (car bs)) (car bs))
       (if (%lcc-consp (car bs)) (car (cdr (car bs))) nil))
      (cons cs lvls)))

(defun %lcc-let (cs lvls args star)
  ((lambda (r)
     (%lcc-seq (car r) (cdr r) (cdr args)))
   (%lcc-let-binds cs lvls lvls (car args) star)))

; ---- setq: lokal/Param -> expr + STOREL + LOADL (Wert nachladen, wie die Referenz);
; ungebunden -> GLOBAL (PUSHLIT sym, expr, CALLPRIM 20 2; wie src/compile.c). ----
(defun %lcc-setq (cs lvls args)
  ((lambda (e)
     (if e
         (%lcc-emit2 (%lcc-emit2 (%lcc-expr cs lvls (car (cdr args)))
                                 'storel (car (cdr e)))
                     'loadl (car (cdr e)))
         ((lambda (uvi)
            (if uvi
                (%lcc-emit2 (%lcc-emit2 (%lcc-expr cs lvls (car (cdr args)))
                                        'setupval uvi)
                            'upval uvi)
                (%lcc-emit (%lcc-emit (%lcc-emit-op (%lcc-expr (%lcc-push-lit cs (car args)) lvls (car (cdr args)))
                                                    'callprim)
                                      20)
                           2)))
          (%lcc-resolve-uv (car args) lvls))))
   (%lcc-env-find (%lcc-top-env lvls) (car args))))

; ---- Aufrufe: erst Args, dann CALLPRIM pid n bzw. CALL <callee-lit> n ----
(defun %lcc-args (cs lvls args n)
  (if args
      (%lcc-args (%lcc-expr cs lvls (car args)) lvls (cdr args) (+ n 1))
      (cons cs n)))

(defun %lcc-call (cs lvls op args)
  ((lambda (r)
     ((lambda (pid)
        (if pid
            (%lcc-emit (%lcc-emit2 (car r) 'callprim pid) (cdr r))
            ((lambda (rl)
               (%lcc-emit (%lcc-emit2 (car rl) 'call (cdr rl)) (cdr r)))
             (%lcc-lit-slot (car r) op))))
      (%lcc-prim op)))
   (%lcc-args cs lvls args 0)))

; ---- P3: lambda als WERT -> Helper-Fn kompilieren + Creation-Site emittieren ----
; Helper landet in der fns-Box (Sammel-Reihenfolge = Abschluss-Reihenfolge: innerste zuerst
; -> der Lauf-Harness kann in dieser Reihenfolge assemblieren, Marker zeigen stets rueckwaerts).
; Referenz-Semantik: Rumpf non-tail + RET (compile_lambda_helper nutzt compile_sequence).
(defun %lcc-emit-uv-values (cs uvs)
  (if uvs
      ((lambda (uv)
         (%lcc-emit-uv-values
          (if (eq (car (cdr (cdr uv))) 1)
              (%lcc-emit2 cs 'upval (car (cdr uv)))
              (%lcc-emit-slot cs (car (cdr uv)) (car (cdr (cdr (cdr uv))))))
          (cdr uvs)))
       (car uvs))
      cs))

(defun %lcc-lambda (cs lvls form)
  ((lambda (params body)
     ((lambda (nargs uvbox)
        ((lambda (cs2)
           ; Helper-fn abschliessen + in die Box (idx = Zaehler VOR dem Anhaengen)
           ((lambda (fnobj box)
              ((lambda (idx)
                 (progn
                   (rplaca box (cons fnobj (car box)))
                   (rplacd box (+ idx 1))
                   ; Creation-Site im AEUSSEREN cs: Upvalue-Werte pushen + CLOSURE/PUSHLIT
                   ((lambda (marker uvs n)
                      (if (> n 0)
                          ((lambda (cs3)
                             ((lambda (r)
                                (%lcc-emit (%lcc-emit2 (car r) 'closure (cdr r)) n))
                              (%lcc-lit-slot cs3 marker)))
                           (%lcc-emit-uv-values cs uvs))
                          (%lcc-push-lit cs marker)))
                    (cons '%lcc-helper (cons idx nil))
                    (%lcc-rev (car uvbox))
                    (cdr uvbox))))
               (cdr box)))
            (%lcc-finish (%lcc-emit-op (%lcc-seq cs2
                                                 (cons (cons (%lcc-params-env params 0 nil) uvbox) lvls)
                                                 body)
                                       'ret)
                         nargs)
            (%lcc-fns cs)))
         ; frisches inneres cs: eigener st/lits/maxslot, GETEILTE fns-Box
         (%lcc-cs (cons nil 0) nil nargs (%lcc-fns cs))))
      (%lcc-len params) (cons nil 0)))
   (car (cdr form)) (cdr (cdr form))))

; Immediate-Lambda ((lambda (p..) body) a..) == (let ((p a)..) body) (Referenz-Lowering).
(defun %lcc-imm-binds (ps as acc)
  (if ps
      (%lcc-imm-binds (cdr ps) (if as (cdr as) nil)
                      (cons (cons (car ps) (cons (if as (car as) nil) nil)) acc))
      (%lcc-rev acc)))

; ---- P4: Makro-Expansion + quasiquote-Lowering ----
; lcc laeuft AUF einem Lisp-System (Harness: Treewalk) -> Makros werden expandiert, indem
; der TRAEGER gefragt wird: (function-kind op)='macro + (macroexpand-1 form). Am Geraet (P6)
; ersetzt funcall-auf-kompilierten-BCODE-Expander dieselbe Naht (docs/self-hosting-plan.md).
(defun %lcc-macro-p (op)
  (if (symbolp op) (eq (function-kind op) 'macro) nil))

; quasiquote -> cons/append-Formen. NESTED (CL-Semantik, d = Tiefe): inneres ` erhöht,
; , senkt; nur bei d=1 wird ausgewertet, sonst wird die Syntax als Daten REBUILT
; (Spiegel des Treewalk-qq in eval.c — Drift-Wache via Makro-Korpus). Für d=1-Eingaben
; ohne nested-` ist die Ausgabe BYTE-IDENTISCH zur alten einstufigen Fassung (Byte-Orakel).
(defun %lcc-qq-d (x d)
  (cond ((if (%lcc-consp x) (eq (car x) 'unquote) nil)
         (if (= d 1)
             (car (cdr x))
             (list 'list (list 'quote 'unquote) (%lcc-qq-d (car (cdr x)) (- d 1)))))
        ((if (%lcc-consp x) (eq (car x) 'quasiquote) nil)
         (list 'list (list 'quote 'quasiquote) (%lcc-qq-d (car (cdr x)) (+ d 1))))
        ((%lcc-consp x)
         (if (if (%lcc-consp (car x)) (eq (car (car x)) 'unquote-splicing) nil)
             (if (= d 1)
                 (list 'append (car (cdr (car x))) (%lcc-qq-d (cdr x) d))
                 (list 'cons
                       (list 'list (list 'quote 'unquote-splicing)
                             (%lcc-qq-d (car (cdr (car x))) (- d 1)))
                       (%lcc-qq-d (cdr x) d)))
             (list 'cons (%lcc-qq-d (car x) d) (%lcc-qq-d (cdr x) d))))
        (t (list 'quote x))))
(defun %lcc-lower-qq (x) (%lcc-qq-d x 1))

; ---- Ausdrucks-Dispatch ----
(defun %lcc-expr (cs lvls form)
  (cond ((numberp form) (%lcc-push-value cs form))
        ((eq form nil) (%lcc-push-value cs nil))
        ((eq form 't) (%lcc-push-value cs 't))
        ((symbolp form) (%lcc-var cs lvls form))
        ((%lcc-consp form)
         (%lcc-expr-form cs lvls (car form) (cdr form) form))
        (t (%lcc-push-lit cs form))))   ; String-Literal u. ae.

; Dispatch-Kaskade (Objektgroessen-Splits, je <=255 B): form -> sf1 -> sf2 -> ops -> ops2
(defun %lcc-expr-form (cs lvls op args form)
  (cond ((%lcc-consp op)
         (if (eq (car op) 'lambda)
             (%lcc-expr cs lvls
                        (cons 'let (cons (%lcc-imm-binds (car (cdr op)) args nil)
                                    (cdr (cdr op)))))
             (%lcc-push-value cs nil)))
        ((eq op 'lambda) (%lcc-lambda cs lvls form))
        ((eq op 'quote) (%lcc-push-value cs (car args)))
        ((eq op 'progn) (%lcc-seq cs lvls args))
        ((eq op 'if)    (%lcc-if cs lvls args))
        ((eq op 'let)   (%lcc-let cs lvls args nil))
        ((eq op 'let*)  (%lcc-let cs lvls args t))
        ((eq op 'setq)  (%lcc-setq cs lvls args))
        (t (%lcc-expr-sf2 cs lvls op args form))))

(defun %lcc-expr-sf2 (cs lvls op args form)
  (cond ((eq op 'and)   (%lcc-expr cs lvls (%lcc-lower-and args)))
        ((eq op 'or)    (%lcc-expr cs lvls (%lcc-lower-or args)))
        ((eq op 'cond)  (%lcc-expr cs lvls (%lcc-lower-cond args)))
        ((eq op 'when)  (%lcc-expr cs lvls (%lcc-lower-when args)))
        ((eq op 'unless) (%lcc-expr cs lvls (%lcc-lower-unless args)))
        ((eq op 'quasiquote) (%lcc-expr cs lvls (%lcc-lower-qq (car args))))
        ((%lcc-do-p op) (%lcc-expr-do cs lvls op args))
        ((eq op 'function)
         (if (%lcc-consp (car args))
             (%lcc-lambda cs lvls (car args))
             (%lcc-push-lit cs (car args))))
        (t (%lcc-expr-ops cs lvls op args form))))

; Teil 2 des expr-Dispatches (Objektgroessen-Split): Opcode-Formen, Makros, generischer Call.
; Exakt-2-Args-Prädikat für den Opcode-Fastpath der VARIADISCHEN Ops.
(defun %lcc-2args-p (args)
  (if (%lcc-consp args)
      (if (%lcc-consp (cdr args)) (eq (cdr (cdr args)) nil) nil)
      nil))

; Variadische Ops: Opcode-Name NUR als Fastpath-Kandidat (Arity-Guard in %lcc-expr-ops).
(defun %lcc-vop (op)
  (cond ((eq op '+) 'add) ((eq op '-) 'sub) ((eq op '*) 'mul) ((eq op '/) 'div)
        ((eq op '<) 'less) ((eq op '>) 'greater) ((eq op '=) 'eq) (t nil)))

; Opcode-Fastpath NUR bei exakt 2 Args — variadisch/unär geht als GENERISCHER Call an die
; variadische Bridge (Ein-Suite) bzw. das C-Prim (Träger-Brücke): EINE Semantik, kein
; stilles Arg-Verwerfen mehr ((- 9 2 3) war 7 statt 4 — Fund des M3-HW-Selftests).
; eq/eql bleiben ungeguardet: exakt-2 ist dort auch die Prim-Semantik (Extra-Args ignoriert).
(defun %lcc-expr-ops (cs lvls op args form)
  ((lambda (vop)
     (cond ((if vop (%lcc-2args-p args) nil) (%lcc-binary cs lvls args vop))
           (vop (%lcc-call cs lvls op args))
           ((eq op 'eq)  (%lcc-binary cs lvls args 'eq))
           ((eq op 'eql) (%lcc-binary cs lvls args 'eql))
           (t (%lcc-expr-ops2 cs lvls op args form))))
   (%lcc-vop op)))

(defun %lcc-expr-ops2 (cs lvls op args form)
  (cond ((eq op 'mod) (%lcc-binary cs lvls args 'mod))
        ((eq op 'remainder) (%lcc-binary cs lvls args 'remainder))
        ((eq op 'cons) (%lcc-binary cs lvls args 'cons))
        ((eq op 'car)  (%lcc-unary cs lvls args 'car))
        ((eq op 'cdr)  (%lcc-unary cs lvls args 'cdr))
        ((eq op 'consp) (%lcc-unary cs lvls args 'consp))
        ((eq op 'not)  (%lcc-unary cs lvls args 'not))
        ((eq op 'null) (%lcc-unary cs lvls args 'not))
        ((%lcc-macro-p op) (%lcc-expr cs lvls (macroexpand-1 form)))
        (t (%lcc-call cs lvls op args))))

(defun %lcc-binary (cs lvls args opname)
  (%lcc-emit-op (%lcc-expr (%lcc-expr cs lvls (car args)) lvls (car (cdr args))) opname))

(defun %lcc-unary (cs lvls args opname)
  (%lcc-emit-op (%lcc-expr cs lvls (car args)) opname))

; ---- Tail-Kompilierung (NUR defun-Kontext; Referenz: defun_tail=True) ----
; Regeln (empirisch gegen den Referenz-Compiler abgelesen, 2026-07-05):
;  - generischer CALL in Tail-Position -> TAILCALL(62) OHNE folgendes RET (auch Fremdaufrufe)
;  - CALLPRIM/Opcode-Formen in Tail-Position -> normal + RET
;  - if in Tail-Position: KEIN JMPREL — jeder Zweig terminiert selbst (RET/TAILCALL)
;  - progn/let/let*: nur die LETZTE Form ist Tail-Position
(defun %lcc-sf-p (op)
  (cond ((eq op 'quote) t) ((eq op 'progn) t) ((eq op 'if) t) ((eq op 'let) t)
        ((eq op 'let*) t) ((eq op 'setq) t) ((eq op 'function) t) ((eq op 'lambda) t) ((eq op 'quasiquote) t)
        ((eq op 'and) t) ((eq op 'or) t) ((eq op 'cond) t)
        ((eq op 'when) t) ((eq op 'unless) t)
        ((eq op 'do) t) ((eq op 'do*) t) ((eq op 'dotimes) t) ((eq op 'dolist) t) (t nil)))

(defun %lcc-opform-p (op)
  (cond ((eq op '+) t) ((eq op '-) t) ((eq op '*) t) ((eq op '/) t)
        ((eq op '<) t) ((eq op '>) t) ((eq op '=) t) ((eq op 'eq) t) ((eq op 'eql) t)
        ((eq op 'mod) t) ((eq op 'remainder) t) ((eq op 'cons) t) ((eq op 'car) t)
        ((eq op 'cdr) t) ((eq op 'consp) t) ((eq op 'not) t) ((eq op 'null) t) (t nil)))

; op faellt unter die generische CALL-Regel (kein Special/Opcode/Prim)?
(defun %lcc-callform-p (op)
  (if (%lcc-sf-p op) nil (if (%lcc-opform-p op) nil (if (%lcc-prim op) nil t))))

(defun %lcc-tailcall (cs lvls op args)
  ((lambda (r)
     ((lambda (rl)
        (%lcc-emit (%lcc-emit2 (car rl) 'tailcall (cdr rl)) (cdr r)))
      (%lcc-lit-slot (car r) op)))
   (%lcc-args cs lvls args 0)))

(defun %lcc-tail-seq (cs lvls body)
  (if body
      (if (cdr body)
          (%lcc-tail-seq (%lcc-emit-op (%lcc-expr cs lvls (car body)) 'drop) lvls (cdr body))
          (%lcc-tail cs lvls (car body)))
      (%lcc-emit-op (%lcc-push-value cs nil) 'ret)))

(defun %lcc-tail-let (cs lvls args star)
  ((lambda (r)
     (%lcc-tail-seq (car r) (cdr r) (cdr args)))
   (%lcc-let-binds cs lvls lvls (car args) star)))

; tail-if: Zweige terminieren selbst -> nur EIN Patch (JFALSEREL zum else-Beginn).
(defun %lcc-tail-if (cs lvls args)
  ((lambda (cs2)
     ((lambda (hole1 len1)
        ((lambda (cs3)
           (progn
             (rplaca hole1 (- (cdr (%lcc-st cs3)) len1))
             (%lcc-tail cs3 lvls (if (cdr (cdr args)) (car (cdr (cdr args))) nil))))
         (%lcc-tail cs2 lvls (car (cdr args)))))
      (car (%lcc-st cs2)) (cdr (%lcc-st cs2))))
   (%lcc-emit (%lcc-emit-op (%lcc-expr cs lvls (car args)) 'jfalserel) 0)))

(defun %lcc-tail (cs lvls form)
  (if (%lcc-consp form)
      ((lambda (op args)
         (cond ((%lcc-consp op)
                (if (eq (car op) 'lambda)
                    (%lcc-tail cs lvls
                               (cons 'let (cons (%lcc-imm-binds (car (cdr op)) args nil)
                                           (cdr (cdr op)))))
                    (%lcc-emit-op (%lcc-expr cs lvls form) 'ret)))
               ((eq op 'if)    (%lcc-tail-if cs lvls args))
               ((eq op 'progn) (%lcc-tail-seq cs lvls args))
               ((eq op 'let)   (%lcc-tail-let cs lvls args nil))
               ((eq op 'let*)  (%lcc-tail-let cs lvls args t))
               (t (%lcc-tail2 cs lvls op args form))))
       (car form) (cdr form))
      (%lcc-emit-op (%lcc-expr cs lvls form) 'ret)))

; Teil 2 des tail-Dispatches (Objektgroessen-Split): Lowerings, Makros, Tailcall/RET.
(defun %lcc-tail2 (cs lvls op args form)
  (cond ((eq op 'and)   (%lcc-tail cs lvls (%lcc-lower-and args)))
        ((eq op 'or)    (%lcc-tail cs lvls (%lcc-lower-or args)))
        ((eq op 'cond)  (%lcc-tail cs lvls (%lcc-lower-cond args)))
        ((eq op 'when)  (%lcc-tail cs lvls (%lcc-lower-when args)))
        ((eq op 'unless) (%lcc-tail cs lvls (%lcc-lower-unless args)))
        ((eq op 'quasiquote) (%lcc-tail cs lvls (%lcc-lower-qq (car args))))
        ; do-Familie VOR macro-p: das native Lowering (konstanter Stack) gewinnt gegen
        ; etwaige Alt-Makros gleichen Namens (stdlib-control-Templates, funcall-Rekursion).
        ((%lcc-do-p op) (%lcc-emit-op (%lcc-expr-do cs lvls op args) 'ret))
        ((%lcc-macro-p op) (%lcc-tail cs lvls (macroexpand-1 form)))
        ((%lcc-callform-p op) (%lcc-tailcall cs lvls op args))
        (t (%lcc-emit-op (%lcc-expr cs lvls form) 'ret))))

; ---- Params -> lvls ((name slot a) ...), Slots 0.. ----
(defun %lcc-params-env (ps slot acc)
  (if ps
      (%lcc-params-env (cdr ps) (+ slot 1)
                       (cons (cons (car ps) (cons slot (cons 'a nil))) acc))
      acc))

; ---- Öffentliche Naht: (lambda (params) body...) -> CodeObject-Bausteine ----
; Rückgabe: (nargs nlocals flags littab bytes) — littab/bytes in Vergabe-/Emissions-Reihenfolge.
(defun %lcc-finish (cs nargs)
  (cons nargs
        (cons (- (%lcc-max cs) nargs)
              (cons 0
                    (cons (%lcc-rev (%lcc-lits cs))
                          (cons (%lcc-rev (car (%lcc-st cs))) nil))))))

; (defun name (params) body...) -> Tail-Modus (TAILCALL/selbst-terminierende Zweige)
(defun %lcc-compile-defun (params body fns)
  ((lambda (nargs)
     (%lcc-finish (%lcc-tail-seq (%lcc-cs (cons nil 0) nil nargs fns)
                                 (cons (cons (%lcc-params-env params 0 nil) (cons nil 0)) nil)
                                 body)
                  nargs))
   (%lcc-len params)))

; Ausgabe: LISTE der Fns in Assemblier-Reihenfolge — Helper (innerste zuerst), MAIN ZULETZT.
; Helper-Referenzen in littabs sind Marker (%lcc-helper <idx>), idx = Position in dieser Liste.
(defun lcc-compile-obj (form)
  ((lambda (fns)
     ((lambda (main)
        (%lcc-rev (cons main (car fns))))
      (if (eq (car form) 'defun)
          (%lcc-compile-defun (car (cdr (cdr form))) (cdr (cdr (cdr form))) fns)
          (%lcc-compile-lambda form fns))))
   (cons nil 0)))

(defun %lcc-compile-lambda (form fns)
  ((lambda (params body)
     ((lambda (nargs)
        (%lcc-finish (%lcc-emit-op (%lcc-seq (%lcc-cs (cons nil 0) nil nargs fns)
                                             (cons (cons (%lcc-params-env params 0 nil) (cons nil 0)) nil)
                                             body)
                                   'ret)
                     nargs))
      (%lcc-len params)))
   (car (cdr form)) (cdr (cdr form))))

; Komfort-Nähte für Ausdrücke (P0-kompatibel): (lambda () expr)
(defun lcc-compile (form)
  (car (cdr (cdr (cdr (cdr (lcc-compile-obj (cons 'lambda (cons nil (cons form nil))))))))))

(defun lcc-lits (form)
  (car (cdr (cdr (cdr (lcc-compile-obj (cons 'lambda (cons nil (cons form nil)))))))))

; ---- P6: lcc-first-REPL-Kern (docs/lcc-device-design.md) ----
; (lcc-run form): defmacro -> Expander als Lambda KOMPILIEREN, anonym installieren und via
; %set-macro (C-Naht, Konvergenz-M2) als BCODE-Makro ans Symbol — KEIN eval_env mehr im
; defmacro-Pfad; defun -> kompilieren + unter dem Namen installieren (lcc-install = die
; C-Naht); Ausdruck -> als (lambda () form) kompilieren, anonym installieren, funcall
; (BCODE-Wert; eval->vm-Brücke führt aus).
(defun %lcc-wrap (form) (cons 'lambda (cons nil (cons form nil))))

(defun lcc-run (form)
  (cond ((if (%lcc-consp form) (eq (car form) 'defmacro) nil)
         (%set-macro (car (cdr form))
                     (lcc-install (lcc-compile-obj (cons 'lambda (cdr (cdr form)))) nil)))
        ((if (%lcc-consp form) (eq (car form) 'defun) nil)
         (lcc-install (lcc-compile-obj form) (car (cdr form))))
        ; Ausdruck: name=t = TRANSIENTES Main (lcc-install laesst es sofort laufen und gibt
        ; den WERT zurueck — kein funcall, kein Region-/Directory-Leck je Eingabe; M4-Fund).
        (t (lcc-install (lcc-compile-obj (%lcc-wrap form)) t))))
