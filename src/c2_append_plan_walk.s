; C2-lite append phase-plan walker.
;
; llvm-mos C ABI:
;   argument 0 canonical plan pointer: __rc2/__rc3
;   argument 1 context pointer: __rc4/__rc5
;   uint8_t result: A (1 only when every named slot succeeds)
;
; The leaf owns no status or rollback policy.  It reads one of the two linked,
; zero-terminated plan arrays and calls the generic Session seam for every
; byte.  The context and cursor live only on the hardware stack across that
; call; no resident state or GC root is introduced.

	.zeropage	__rc2
	.zeropage	__rc3
	.zeropage	__rc4
	.zeropage	__rc5
	.zeropage	__rc6
	.zeropage	__rc7
	.zeropage	__rc8

	.section	.lisp65_resident_island,"ax",@progbits
	.globl	c2_append_plan_walk
	.type	c2_append_plan_walk,@function
c2_append_plan_walk:
	; The caller passes the canonical plan itself; no second selector table or
	; magic plan id may drift from those linked bytes.
	; Preserve the C context before reusing its ABI registers for the cursor.
	ldy	__rc4
	sty	__rc6
	ldy	__rc5
	sty	__rc7

	; Copy the canonical plan from argument zero into the private cursor.
	ldy	__rc2
	sty	__rc4
	ldy	__rc3
	sty	__rc5

.Lnext:
	ldz	#0
	lda	(__rc4),z
	beq	.Lsuccess
	sta	__rc8
	inw	__rc4

	; c2_overlay_call is ordinary C and may use every imaginary register.
	; Preserve only the four bytes that define the remaining walk.
	lda	__rc4
	pha
	lda	__rc5
	pha
	lda	__rc6
	pha
	lda	__rc7
	pha

	lda	__rc6
	sta	__rc2
	lda	__rc7
	sta	__rc3
	lda	__rc8
	jsr	c2_overlay_call
	tax

	pla
	sta	__rc7
	pla
	sta	__rc6
	pla
	sta	__rc5
	pla
	sta	__rc4

	txa
	beq	.Lfail
	bra	.Lnext
.Lsuccess:
	lda	#1
	ldz	#0
	rts
.Lfail:
	lda	#0
	ldz	#0
	rts
.Lc2_append_plan_walk_end:
	.size	c2_append_plan_walk, .Lc2_append_plan_walk_end-c2_append_plan_walk
