; Signed 15-bit ASH for tagged Lisp fixnums.
;
; llvm-mos C ABI:
;   argument 0 tagged value: A/X
;   argument 1 tagged count: __rc2/__rc3
;   tagged result: A/X
;
; The C caller proves both operands are fixnums.  This leaf additionally
; enforces the public count range [-14,14] and checked left-shift range.  It
; writes VM_TYPEERROR (3) and returns NIL when either check fails.  Keeping the
; loop outside LTO prevents the optimizer from materializing a variable-shift
; state machine in the resident VM dispatch core.

	.zeropage	__rc2
	.zeropage	__rc3
	.zeropage	__rc4
	.zeropage	__rc5

	.section	.lisp65_resident_island,"ax",@progbits
	.globl	lisp65_ash_tagged
	.type	lisp65_ash_tagged,@function
lisp65_ash_tagged:
	sta	__rc4
	stx	__rc5

	; Decode the tagged count into a positive magnitude in Y and select the
	; shift direction.  Legal nonnegative encodings are $0001..$001d; legal
	; negative encodings are $ffe5..$ffff.
	lda	__rc3
	bne	.Lash_negative
	lda	__rc2
	cmp	#$1f
	bcs	.Lash_fail
	lsr
	tay
	bra	.Lash_untag_left

.Lash_negative:
	cmp	#$ff
	bne	.Lash_fail
	lda	__rc2
	cmp	#$e5
	bcc	.Lash_fail
	eor	#$ff
	lsr
	inc
	tay

	; Untag the signed value once, then perform Y arithmetic right shifts.
	lda	__rc5
	cmp	#$80
	ror
	sta	__rc5
	ror	__rc4
.Lash_right_loop:
	cpy	#0
	beq	.Lash_retag
	lda	__rc5
	cmp	#$80
	ror
	sta	__rc5
	ror	__rc4
	dey
	bra	.Lash_right_loop

.Lash_untag_left:
	lda	__rc5
	cmp	#$80
	ror
	sta	__rc5
	ror	__rc4
.Lash_left_loop:
	cpy	#0
	beq	.Lash_retag
	; Before each left shift x must be in [-8192,8191], i.e. its high byte is
	; $00..$1f or $e0..$ff.
	lda	__rc5
	cmp	#$20
	bcc	.Lash_left_step
	cmp	#$e0
	bcc	.Lash_fail
.Lash_left_step:
	asl	__rc4
	rol	__rc5
	dey
	bra	.Lash_left_loop

.Lash_retag:
	asl	__rc4
	rol	__rc5
	inc	__rc4
	lda	__rc4
	ldx	__rc5
	ldz	#0
	rts

.Lash_fail:
	lda	#3
	sta	vm_status
	lda	#0
	tax
	ldz	#0
	rts
.Lash_end:
	.size	lisp65_ash_tagged, .Lash_end-lisp65_ash_tagged
