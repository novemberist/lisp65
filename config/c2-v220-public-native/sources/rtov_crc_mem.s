; lisp65 -- target-stable CRC-16/CCITT-FALSE memory leaf.
;
; llvm-mos C ABI:
;   argument 0 pointer: __rc2/__rc3 (little endian)
;   argument 1 length:  A/X
;   uint16_t result:    A/X
;
; The implementation deliberately owns instruction selection.  In
; particular, the 16-bit length is decremented as two byte objects; no WPLTO
; pass can replace that sequence with a DEW on an unrelated ZP operand.

	.zeropage	__rc2
	.zeropage	__rc3
	.zeropage	__rc4
	.zeropage	__rc5
	.zeropage	__rc6
	.zeropage	__rc7

	.section	.text.rtov_crc_mem,"ax",@progbits
	.globl	rtov_crc_mem
	.type	rtov_crc_mem,@function
rtov_crc_mem:
	ldy	__rc2
	sty	__rc4
	ldy	__rc3
	sty	__rc5
	sta	__rc2
	stx	__rc3
	lda	#$ff
	sta	__rc6
	sta	__rc7

.Lcrc_next_byte:
	lda	__rc2
	ora	__rc3
	beq	.Lcrc_done
	lda	__rc2
	bne	.Lcrc_dec_low
	dec	__rc3
.Lcrc_dec_low:
	dec	__rc2

	ldz	#0
	lda	(__rc4),z
	eor	__rc7
	sta	__rc7
	ldy	#8
.Lcrc_next_bit:
	asl	__rc6
	rol	__rc7
	bcc	.Lcrc_no_poly
	lda	__rc6
	eor	#$21
	sta	__rc6
	lda	__rc7
	eor	#$10
	sta	__rc7
.Lcrc_no_poly:
	dey
	bne	.Lcrc_next_bit
	inw	__rc4
	bra	.Lcrc_next_byte

.Lcrc_done:
	lda	__rc6
	ldx	__rc7
	ldz	#0
	rts
.Lcrc_end:
	.size	rtov_crc_mem, .Lcrc_end-rtov_crc_mem
