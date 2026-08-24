; Explicit successor filler for the fixed 98-byte mapped far facade.
; One new nine-byte abort entry consumes exactly nine predecessor pad bytes.

	.section .lisp65_c2_mapped_far_facade.padding,"ax",@progbits
	.globl __lisp65_c2_mapped_far_facade_padding_contract_bytes
	.equ __lisp65_c2_mapped_far_facade_padding_contract_bytes, 10

	.globl __lisp65_c2_mapped_far_facade_padding
	.type __lisp65_c2_mapped_far_facade_padding,@object
__lisp65_c2_mapped_far_facade_padding:
	.fill 10, 1, 0
	.size __lisp65_c2_mapped_far_facade_padding, .-__lisp65_c2_mapped_far_facade_padding
