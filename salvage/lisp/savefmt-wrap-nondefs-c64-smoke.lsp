; SAVE-format generator smoke for wrapped top-level setup forms.
; The top-level PUTPROP is intentionally not a DE form; the fixture generator
; wraps it into WSETUP so native LOAD can persist it through SAVE format.

(DE WVAL () (GETPROP 'WOBJ 'WPROP))

(PUTPROP 'WOBJ 'WPROP 42)
