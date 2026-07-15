; lisp65 demo 04: a tiny state-machine adventure.
;
; The state is (room has-key door-open).  You can call DEMO-ADV-COMMAND from
; the REPL to poke it by hand, or run the scripted path below.
;
;   (compile-file "dadv" "fadv")
;   (load "fadv")
;   (demo-adv-run)

(defun demo-adv-start ()
  (list 'hall nil nil))

(defun demo-adv-room (state)
  (car state))

(defun demo-adv-key-p (state)
  (car (cdr state)))

(defun demo-adv-door-p (state)
  (car (cdr (cdr state))))

(defun demo-adv-state (room key door)
  (list room key door))

(defun demo-adv-command (state command)
  (if (eq command 'north)
      (if (eq (demo-adv-room state) 'hall)
          (demo-adv-state 'library (demo-adv-key-p state) (demo-adv-door-p state))
          state)
      (if (eq command 'south)
          (if (eq (demo-adv-room state) 'library)
              (demo-adv-state 'hall (demo-adv-key-p state) (demo-adv-door-p state))
              state)
          (if (eq command 'take-key)
              (if (eq (demo-adv-room state) 'library)
                  (demo-adv-state (demo-adv-room state) 't (demo-adv-door-p state))
                  state)
              (if (eq command 'open-door)
                  (if (and (eq (demo-adv-room state) 'hall) (demo-adv-key-p state))
                      (demo-adv-state 'treasure (demo-adv-key-p state) 't)
                      state)
                  state)))))

(defun demo-adv-script (state commands)
  (if commands
      (demo-adv-script (demo-adv-command state (car commands)) (cdr commands))
      state))

(defun demo-adv-score (state)
  (if (and (eq (demo-adv-room state) 'treasure) (demo-adv-door-p state))
      42
      0))

(defun demo-adv-run ()
  (demo-adv-score
   (demo-adv-script (demo-adv-start)
                    (list 'north 'take-key 'south 'open-door))))
