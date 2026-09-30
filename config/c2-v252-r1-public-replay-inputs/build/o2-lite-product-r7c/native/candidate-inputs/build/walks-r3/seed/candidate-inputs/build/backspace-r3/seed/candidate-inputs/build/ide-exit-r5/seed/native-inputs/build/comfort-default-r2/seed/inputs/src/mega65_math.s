; lisp65 -- llvm-mos 16-bit arithmetic overrides for the MEGA65 math unit.
;
; llvm-mos C ABI (verified by scripts/mega65-math-override-check.py):
;   argument 0: A/X (little endian)
;   argument 1: __rc2/__rc3
;   argument 2 pointer: __rc4/__rc5
;   uint16_t result: A/X
;
; $d770-$d777 are the shared 32-bit multiplier/divider inputs.  Every access
; below is byte-wide.  P is saved and IRQs are disabled from the first input
; write through the last output read, so an interrupt cannot interleave a
; second math-unit transaction.  Z is left at llvm-mos' required value zero.

	.zeropage	__rc2
	.zeropage	__rc3
	.zeropage	__rc4
	.zeropage	__rc5
	.zeropage	__rc6
	.zeropage	__rc7
	.zeropage	__rc8
	.zeropage	__rc9
	.zeropage	__rc10
	.zeropage	__rc11
	.zeropage	__rc12
	.zeropage	__rc13
	.zeropage	__rc14
	.zeropage	__rc15

	.section	.text.mega65_math_div,"ax",@progbits
	.globl	lisp65_hw_udivhi3
	.type	lisp65_hw_udivhi3,@function
lisp65_hw_udivhi3:
	ldy	#0
	bra	.Ldiv_common
.Ludiv_end:
	.size	lisp65_hw_udivhi3, .Ludiv_end-lisp65_hw_udivhi3

	.globl	lisp65_hw_umodhi3
	.type	lisp65_hw_umodhi3,@function
lisp65_hw_umodhi3:
	ldy	#1
	bra	.Ldiv_common
.Lumod_end:
	.size	lisp65_hw_umodhi3, .Lumod_end-lisp65_hw_umodhi3

	.globl	lisp65_hw_udivmodhi4
	.type	lisp65_hw_udivmodhi4,@function
lisp65_hw_udivmodhi4:
	ldy	#2

.Ldiv_common:
	sta	__rc6
	stx	__rc7
	lda	__rc2
	ora	__rc3
	beq	.Ldiv_zero

	php
	sei
	lda	__rc6
	sta	$d770
	lda	__rc7
	sta	$d771
	stz	$d772
	stz	$d773
	lda	__rc2
	sta	$d774
	lda	__rc3
	sta	$d775
	stz	$d776
	stz	$d777
.Ldiv_wait:
	bit	$d70f
	bmi	.Ldiv_wait
	lda	$d76c
	sta	__rc8
	lda	$d76d
	sta	__rc9

	; Quotient-only calls do not pay for the remainder multiply.
	cpy	#0
	beq	.Ldiv_unlock
	lda	__rc8
	sta	$d770
	lda	__rc9
	sta	$d771
	stz	$d772
	stz	$d773
	lda	__rc2
	sta	$d774
	lda	__rc3
	sta	$d775
	stz	$d776
	stz	$d777
.Lmul_wait_for_rem:
	bit	$d70f
	bvs	.Lmul_wait_for_rem
	sec
	lda	__rc6
	sbc	$d778
	sta	__rc10
	lda	__rc7
	sbc	$d779
	sta	__rc11
.Ldiv_unlock:
	plp
	bra	.Ldiv_result

; Match llvm-mos libcrt exactly: x/0 = 0, x%0 = x.  __udivmodhi4 also
; writes x to the remainder pointer.  No undefined hardware transaction is
; started for this case.
.Ldiv_zero:
	stz	__rc8
	stz	__rc9
	lda	__rc6
	sta	__rc10
	lda	__rc7
	sta	__rc11

.Ldiv_result:
	cpy	#1
	beq	.Lreturn_rem
	cpy	#2
	bne	.Lreturn_quot
	ldz	#0
	lda	__rc10
	sta	(__rc4),z
	ldy	#1
	lda	__rc11
	sta	(__rc4),y
	ldz	#0
.Lreturn_quot:
	lda	__rc8
	ldx	__rc9
	rts
.Lreturn_rem:
	lda	__rc10
	ldx	__rc11
	rts
.Ludivmod_end:
	.size	lisp65_hw_udivmodhi4, .Ludivmod_end-lisp65_hw_udivmodhi4

; Signed semantics are copied from llvm-mos libcrt's divmod.cc IR: take the
; 16-bit absolute bit patterns, call the unsigned helper, then apply quotient
; sign (lhs xor rhs) or remainder sign (lhs).  This preserves x/0=0, x%0=x,
; and the two's-complement INT16_MIN/-1 result without C undefined behavior.
	.section	.text.mega65_math_sdiv,"ax",@progbits
	.globl	lisp65_hw_divhi3
	.type	lisp65_hw_divhi3,@function
lisp65_hw_divhi3:
	ldy	#0
	bra	.Lsigned_common
.Lsdiv_end:
	.size	lisp65_hw_divhi3, .Lsdiv_end-lisp65_hw_divhi3

	.globl	lisp65_hw_modhi3
	.type	lisp65_hw_modhi3,@function
lisp65_hw_modhi3:
	ldy	#1
.Lsigned_common:
	sty	__rc15
	sta	__rc13
	stx	__rc14
	cpy	#0
	bne	.Lmod_sign
	txa
	eor	__rc3
	and	#$80
	bra	.Lsave_sign
.Lmod_sign:
	txa
	and	#$80
.Lsave_sign:
	sta	__rc12

	lda	__rc3
	bpl	.Ldivisor_abs
	lda	__rc2
	eor	#$ff
	clc
	adc	#1
	sta	__rc2
	lda	__rc3
	eor	#$ff
	adc	#0
	sta	__rc3
.Ldivisor_abs:
	lda	__rc14
	bpl	.Ldividend_abs
	lda	__rc13
	eor	#$ff
	clc
	adc	#1
	sta	__rc13
	lda	__rc14
	eor	#$ff
	adc	#0
	sta	__rc14
.Ldividend_abs:
	lda	__rc13
	ldx	__rc14
	ldy	__rc15
	bne	.Lcall_umod
	jsr	lisp65_hw_udivhi3
	bra	.Lapply_sign
.Lcall_umod:
	jsr	lisp65_hw_umodhi3
.Lapply_sign:
	ldy	__rc12
	bmi	.Lnegate_signed
	rts
.Lnegate_signed:
	eor	#$ff
	clc
	adc	#1
	tay
	txa
	eor	#$ff
	adc	#0
	tax
	tya
	rts
.Lsmod_end:
	.size	lisp65_hw_modhi3, .Lsmod_end-lisp65_hw_modhi3

; Adjust a tagged truncating remainder to Common-Lisp MOD semantics.  The
; first tagged argument is in A/X, the tagged divisor in __rc2/__rc3.
	.section	.text.mega65_math_mod_adjust,"ax",@progbits
	.globl	lisp65_mod_adjust_tagged
	.type	lisp65_mod_adjust_tagged,@function
lisp65_mod_adjust_tagged:
	cpx	#0
	bne	.Lmod_adjust_sign
	cmp	#1
	beq	.Lmod_adjust_done
.Lmod_adjust_sign:
	pha
	txa
	eor	__rc3
	bpl	.Lmod_adjust_restore
	pla
	sec
	sbc	#1
	clc
	adc	__rc2
	pha
	txa
	adc	__rc3
	tax
	pla
	rts
.Lmod_adjust_restore:
	pla
.Lmod_adjust_done:
	rts
.Lmod_adjust_end:
	.size	lisp65_mod_adjust_tagged, .Lmod_adjust_end-lisp65_mod_adjust_tagged

	.section	.text.mega65_math_mul,"ax",@progbits
	.globl	lisp65_hw_mulhi3
	.type	lisp65_hw_mulhi3,@function
lisp65_hw_mulhi3:
	php
	sei
	sta	$d770
	txa
	sta	$d771
	stz	$d772
	stz	$d773
	lda	__rc2
	sta	$d774
	lda	__rc3
	sta	$d775
	stz	$d776
	stz	$d777
.Lmul_wait:
	bit	$d70f
	bvs	.Lmul_wait
	lda	$d778
	ldx	$d779
	plp
	rts
.Lmul_end:
	.size	lisp65_hw_mulhi3, .Lmul_end-lisp65_hw_mulhi3

	.section	".note.GNU-stack","",@progbits
