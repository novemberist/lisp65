; C2.2 stateless completion-length leaf.
;
; llvm-mos C ABI:
;   uint8_t mode: A
;   uint8_t result: A
;
; The completion domain has no storage authority.  This non-LTO function
; rematerializes one of two constants from the mode on every call:
;   $a2 (PUBLISH)                 -> 48
;   $a1/$a3/$a4 (ACTIVE/RB/CLEAR) -> 64
; Every other mode fails closed with zero.  No memory is read or written.

	.section	.lisp65_rt_c2append_header,"ax",@progbits
	.globl	c2_completion_mode_length
	.type	c2_completion_mode_length,@function
c2_completion_mode_length:
	cmp	#$a1
	bcc	.Linvalid
	cmp	#$a5
	bcs	.Linvalid
	cmp	#$a2
	beq	.Lpublish
	lda	#$40
	ldz	#$00
	rts
.Lpublish:
	lda	#$30
	ldz	#$00
	rts
.Linvalid:
	lda	#$00
	ldz	#$00
	rts
.Lc2_completion_mode_length_end:
	.size	c2_completion_mode_length, .Lc2_completion_mode_length_end-c2_completion_mode_length
