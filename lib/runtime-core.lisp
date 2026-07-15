(defun runtime-step (state command)
  (if (and (eq state 'hall) (eq command 'north))
      'library
      (if (and (eq state 'library) (eq command 'take-key))
          'armed
          (if (and (eq state 'armed) (eq command 'south))
              'hall-key
              (if (and (eq state 'hall-key) (eq command 'open-door))
                  'treasure
                  state)))))

(defun runtime-main ()
  (if (eq (runtime-step
           (runtime-step
            (runtime-step
             (runtime-step 'hall 'north)
             'take-key)
            'south)
           'open-door)
          'treasure)
      42
      0))
