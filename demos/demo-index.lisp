; lisp65 demo index.
;
; This source file is also packed as "dindex" on the demo D81.  It is meant
; for inspection and quick lookup from the REPL.
;
; Typical command pattern:
;
;   (compile-file "dsimp" "fsimp")
;   (load "fsimp")
;   (demo-simplify-run)

(defun demo-index ()
  '((dsimp fsimp demo-simplify-run "symbolic simplifier")
    (dstr fstr demo-strings-run "string pipeline")
    (dlam flam demo-lambda-run "higher-order lambda")
    (dscr fscr demo-screen-run "screen output")
    (dadv fadv demo-adv-run "state-machine adventure")
    (dide fide demo-ide-run "ide buffer edit")
    (dnum fnum demo-numbers-run "fixnum arithmetic")))

(defun demo-expected-result ()
  42)
