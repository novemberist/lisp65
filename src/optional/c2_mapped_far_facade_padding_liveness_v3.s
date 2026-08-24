; Liveness successor for the fixed 98-byte mapped Far facade.  The new
; nine-byte retirement entry and this one-byte always-visible neutral target
; consume the predecessor's ten explicit padding bytes exactly.

	.section .lisp65_c2_mapped_far_facade.padding,"ax",@progbits
	.globl __lisp65_c2_mapped_far_facade_padding_contract_bytes
	.equ __lisp65_c2_mapped_far_facade_padding_contract_bytes, 0

	.globl __lisp65_c2_mapped_far_facade_padding
	.type __lisp65_c2_mapped_far_facade_padding,@object
__lisp65_c2_mapped_far_facade_padding:
	.size __lisp65_c2_mapped_far_facade_padding, .-__lisp65_c2_mapped_far_facade_padding

	.section .lisp65_c2_mapped_far_facade.retired_stub,"ax",@progbits
	.globl c2_retired_continuation_stub
	.type c2_retired_continuation_stub,@function
c2_retired_continuation_stub:
	; A restored stale indirect call is refused as a state-free no-op.  RTS is
	; valid for the observed void overlay entry and cannot mutate retired data.
	rts
	.size c2_retired_continuation_stub, .-c2_retired_continuation_stub
