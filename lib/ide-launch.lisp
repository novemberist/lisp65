; Auto-Load-Naht fuer die IDE -- RESIDENT im Kern (NICHT in der ladbaren ide-Lib!).
; (edit) ist der residente Einstiegspunkt: er laedt die ide-Lib bei Bedarf und ruft dann Codex'
; Launcher (ide) auf, der einen Scratch-Buffer anlegt + die Command-Loop startet.
;
; WARUM RESIDENT: Codex' (ide) liegt in ide-ui.lisp -> nach dem Auslagern in der ide-Lib. Ein
; Einstieg IN der Lib kann sie nicht selbst laden (Henne-Ei). (edit) muss also im Kern bleiben.
;
; SPAETE BINDUNG: der Bytecode-Compiler wirft KEINEN Fehler bei unbekannten Funktionsaufrufen
; (nur "unbound variable" fuer Variablen) -> Symbol-CALL, zur Laufzeit per dir_find aufgeloest.
; Also darf (edit) das ide-Lib-(ide) referenzieren, obwohl es erst nach (load-lib "ide") existiert.
; Idempotenz: function-kind gibt nil bei ungebundenem Symbol -> ide-run noch nicht geladen.
;
; So bleibt die residente Baseline schlank; der Editor kommt on-demand als Bytecode von Disk
; (voller Speed). Vgl. docs/library-modularization-strategy.md + docs/editor-architecture.md.
;
; HANDOFF (Codex): diese Datei gehoert ins KERN-Profil (p0-stdlib-core-subset). Der Kern braucht
; damit auch die Screen/Key-Bridges (fuer die Command-Loop) UND load-lib/function-kind (Disk).
; ide-buffer/ide-ui wandern dagegen in die ide-Lib.

(defun ide-loaded-p ()
  (if (function-kind 'ide-run) 't nil))

(defun edit ()
  (progn
    (if (ide-loaded-p) 't (load-lib "ide"))
    (ide)))
