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
	ldy	#2
.Lcrc_next_nibble:
	lda	__rc7
	lsr
	lsr
	lsr
	lsr
	tax
	.rept 4
	asl	__rc6
	rol	__rc7
	.endr
	lda	__rc6
	eor	rtov_crc_nibbles_low,x
	sta	__rc6
	lda	__rc7
	eor	rtov_crc_nibbles_high,x
	sta	__rc7
	dey
	bne	.Lcrc_next_nibble
	inw	__rc4
	bra	.Lcrc_next_byte

.Lcrc_done:
	lda	__rc6
	ldx	__rc7
	ldz	#0
	rts
.Lcrc_end:
	.size	rtov_crc_mem, .Lcrc_end-rtov_crc_mem

; Exactly 16 polynomial remainders, split into two 16-byte planes.
; These are a separately priced read-only owner, not a 256-entry table.
	.section .rodata.rtov_crc_nibbles,"a",@progbits
	.type rtov_crc_nibbles_low,@object
rtov_crc_nibbles_low:
	.byte 0x00,0x21,0x42,0x63,0x84,0xa5,0xc6,0xe7,0x08,0x29,0x4a,0x6b,0x8c,0xad,0xce,0xef
	.size rtov_crc_nibbles_low,16
	.type rtov_crc_nibbles_high,@object
rtov_crc_nibbles_high:
	.byte 0x00,0x10,0x20,0x30,0x40,0x50,0x60,0x70,0x81,0x91,0xa1,0xb1,0xc1,0xd1,0xe1,0xf1
	.size rtov_crc_nibbles_high,16
