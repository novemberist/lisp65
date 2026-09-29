;; Optional Workbench IDE comfort tier. Load only after IDE:
;;   (load-lib "ide")
;;   (load-lib "idex")
;; L65M publishes this later definition into the existing hook symbol.

(defun %ide-x (kind state a b)
  (cond ((eq kind 'apply)
         (%ide-apply-rare-edit-command state a))
        ((eq kind 'motion)
         (cond ((eq a 1011)
                (%ide-mini-start
                 state 'search "Search: " ""
                 (%ide-mini-history-input 'search "") nil))
               ((eq a 1013)
                (%ide-execute-command-key state))
               (t state)))
        ((eq kind 'mini)
         (cond ((eq a 'execute-command)
                (%ide-execute-command-submit state b))
               ((or (eq a 'search) (eq a 'search-next))
                (%ide-mini-search-submit state a b))
               (t state)))
        (t state)))
