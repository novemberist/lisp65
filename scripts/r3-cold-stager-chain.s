; R3 cold-start handoff trampoline.
;
; The C stager copies this position-independent fragment to $1800 and writes a
; legacy DMA job and CRC state below the product load range.  The job copies
; the already verified PRG payload from Bank 4 to $2001.  DMA submission is
; not content completion: before entering the product, this trampoline checks
; the manifest CRC against the complete CPU-visible destination.  A bounded
; mismatch fails closed with a red border.
	.include	"build/generated/asm-c-contract.inc"
	.zeropage	__rc2

	.equ	R3_STATE, ASM_R3_CHAIN_STATE_ADDR
	.equ	R3_CRC_EXPECT_0, R3_STATE+0
	.equ	R3_CRC_EXPECT_1, R3_STATE+1
	.equ	R3_CRC_EXPECT_2, R3_STATE+2
	.equ	R3_CRC_EXPECT_3, R3_STATE+3
	.equ	R3_CRC_LENGTH_LO, R3_STATE+4
	.equ	R3_CRC_LENGTH_HI, R3_STATE+5
	.equ	R3_CRC_ATTEMPT, R3_STATE+6
	.equ	R3_CRC_0, R3_STATE+7
	.equ	R3_CRC_1, R3_STATE+8
	.equ	R3_CRC_2, R3_STATE+9
	.equ	R3_CRC_3, R3_STATE+10
	.equ	R3_CRC_REMAIN_LO, R3_STATE+11
	.equ	R3_CRC_REMAIN_HI, R3_STATE+12
	.equ	R3_CRC_POLY_0, $20
	.equ	R3_CRC_POLY_1, $83
	.equ	R3_CRC_POLY_2, $b8
	.equ	R3_CRC_POLY_3, $ed
	.equ	R3_CRC_XOR_OUT, $ff
	.equ	R3_CRC_BITS, 8
	.equ	R3_FAIL_BORDER, 2

	.section	.r3_chain_trampoline,"ax",@progbits
	.globl	r3_chain_begin
	.globl	r3_chain_end
	.type	r3_chain_begin,@function
r3_chain_begin:
	sei
	lda	#1
	sta	$d703
	lda	#0
	sta	$d702
	sta	R3_CRC_ATTEMPT
	lda	#ASM_R3_CHAIN_JOB_ADDR_HI
	sta	$d701
	lda	#ASM_R3_CHAIN_JOB_ADDR_LO
	sta	$d700
r3_crc_attempt:
	; Continue the manifest CRC state after its two-byte $2001 load address.
	lda	#ASM_R3_PRODUCT_CRC_INIT_0
	sta	R3_CRC_0
	lda	#ASM_R3_PRODUCT_CRC_INIT_1
	sta	R3_CRC_1
	lda	#ASM_R3_PRODUCT_CRC_INIT_2
	sta	R3_CRC_2
	lda	#ASM_R3_PRODUCT_CRC_INIT_3
	sta	R3_CRC_3
	lda	R3_CRC_LENGTH_LO
	sta	R3_CRC_REMAIN_LO
	lda	R3_CRC_LENGTH_HI
	sta	R3_CRC_REMAIN_HI
	lda	#ASM_R3_PRODUCT_LOAD_LO
	sta	__rc2
	lda	#ASM_R3_PRODUCT_LOAD_HI
	sta	__rc2+1
r3_crc_next:
	ldz	#0
	lda	(__rc2),z
	eor	R3_CRC_0
	sta	R3_CRC_0
	ldx	#R3_CRC_BITS
r3_crc_bit:
	lsr	R3_CRC_3
	ror	R3_CRC_2
	ror	R3_CRC_1
	ror	R3_CRC_0
	bcc	r3_crc_no_xor
	lda	R3_CRC_0
	eor	#R3_CRC_POLY_0
	sta	R3_CRC_0
	lda	R3_CRC_1
	eor	#R3_CRC_POLY_1
	sta	R3_CRC_1
	lda	R3_CRC_2
	eor	#R3_CRC_POLY_2
	sta	R3_CRC_2
	lda	R3_CRC_3
	eor	#R3_CRC_POLY_3
	sta	R3_CRC_3
r3_crc_no_xor:
	dex
	bne	r3_crc_bit
	inc	__rc2
	bne	r3_crc_pointer_done
	inc	__rc2+1
r3_crc_pointer_done:
	lda	R3_CRC_REMAIN_LO
	bne	r3_crc_dec_lo
	dec	R3_CRC_REMAIN_HI
r3_crc_dec_lo:
	dec	R3_CRC_REMAIN_LO
	lda	R3_CRC_REMAIN_LO
	ora	R3_CRC_REMAIN_HI
	bne	r3_crc_next
	lda	R3_CRC_0
	eor	#R3_CRC_XOR_OUT
	cmp	R3_CRC_EXPECT_0
	bne	r3_crc_mismatch
	lda	R3_CRC_1
	eor	#R3_CRC_XOR_OUT
	cmp	R3_CRC_EXPECT_1
	bne	r3_crc_mismatch
	lda	R3_CRC_2
	eor	#R3_CRC_XOR_OUT
	cmp	R3_CRC_EXPECT_2
	bne	r3_crc_mismatch
	lda	R3_CRC_3
	eor	#R3_CRC_XOR_OUT
	cmp	R3_CRC_EXPECT_3
	bne	r3_crc_mismatch
	jmp	ASM_R3_PRODUCT_ENTRY
r3_crc_mismatch:
	inc	R3_CRC_ATTEMPT
	lda	R3_CRC_ATTEMPT
	cmp	#ASM_R3_CHAIN_CRC_ATTEMPTS
	bcc	r3_crc_attempt
	lda	#R3_FAIL_BORDER
	sta	$d020
r3_crc_failed:
	bra	r3_crc_failed
r3_chain_end:
	.size	r3_chain_begin, r3_chain_end-r3_chain_begin
