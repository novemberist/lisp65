; Explicit filler for the fixed-size mapped far facade.
;
; The MAP-CPU root fix makes the two executable wrappers 19 bytes smaller
; than the facade's owned 98-byte contract.  Keep that contract explicit:
; this PROGBITS member is named, measured by the linker, and never entered.

	.section .lisp65_c2_mapped_far_facade.padding,"ax",@progbits
	.globl __lisp65_c2_mapped_far_facade_padding_contract_bytes
	.equ __lisp65_c2_mapped_far_facade_padding_contract_bytes, 19

	.globl __lisp65_c2_mapped_far_facade_padding
	.type __lisp65_c2_mapped_far_facade_padding,@object
__lisp65_c2_mapped_far_facade_padding:
	.fill 19, 1, 0
	.size __lisp65_c2_mapped_far_facade_padding, .-__lisp65_c2_mapped_far_facade_padding
