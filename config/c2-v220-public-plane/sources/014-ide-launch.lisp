; IDE autoload seam -- RESIDENT in the core (NOT in the loadable ide library).
; (edit) is the resident entry point: it loads the ide library on demand and
; then calls Codex's launcher (ide), which creates a scratch buffer and starts
; the command loop.
;
; WHY RESIDENT: Codex's (ide) lives in ide-ui.lisp and therefore in the
; extracted ide library. An entry point IN the library cannot load itself.
; (edit) must remain in the core.
;
; LATE BINDING: the bytecode compiler does NOT reject calls to unknown
; functions (only unbound variables), so it emits a symbolic CALL resolved at
; runtime through dir_find. Thus (edit) may reference the ide library's (ide)
; even though it exists only after (load-lib "ide"). Idempotence:
; function-kind returns nil for an unbound symbol, meaning ide-run is not
; loaded yet.
;
; This keeps the resident baseline lean; the editor arrives on demand as
; bytecode from disk at full speed. See docs/library-modularization-strategy.md
; and docs/editor-architecture.md.
;
; HANDOFF (Codex): this file belongs in the CORE profile
; (p0-stdlib-core-subset). The core therefore also needs the screen/key
; bridges for the command loop AND load-lib/function-kind for disk loading.
; ide-buffer and ide-ui belong in the ide library instead.

(defun ide-loaded-p ()
  (if (function-kind 'ide-run) 't nil))

(defun edit ()
  (progn
    (if (ide-loaded-p) 't (load-lib "ide"))
    (ide)))
