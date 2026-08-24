; Temporary v1.6 refill-boundary witness.  The trace storage aliases repl.buf
; only while Comfort owns input.  Origin is published by %rl-screen-tail:
; BC87/88/89 = next/sequence/wrap, BC8A = active slot, BC8B = $A5 origin.

	.section .text.disk_chain_to_scratch,"ax",@progbits
	.globl disk_chain_to_scratch
	.type disk_chain_to_scratch,@function
	.globl c2_mapped_far_enter
	.globl disk_chain_to_scratch_far
	.globl c2_mapped_far_leave
disk_chain_to_scratch:
	jsr c2_mapped_far_enter
	jsr disk_chain_to_scratch_far
	; c2_mapped_far_leave preserves the one-byte result in A but owns X while
	; restoring MAP.  The disk-chain result is unsigned int in A/X, so retain
	; its high byte explicitly across the shared leave routine.
	phx
	jsr c2_mapped_far_leave
	plx
	rts
	.size disk_chain_to_scratch, .-disk_chain_to_scratch

	.section .text.c2_refill_trace_read,"ax",@progbits
	.globl c2_refill_trace_read
	.type c2_refill_trace_read,@function
	.globl c2_product_entry_read
c2_refill_trace_read:
	pha
	phx
	; The one target is directory ordinal $02FD, logical PC $0045, 21 bytes.
	lda $b9b4
	cmp #$fd
	bne .Lpass
	lda $b9b5
	cmp #$02
	bne .Lpass
	lda $bfe9
	cmp #$45
	bne .Lpass
	lda $bfea
	bne .Lpass
	lda $bfeb
	cmp #$15
	bne .Lpass
	lda $bfec
	bne .Lpass
	ldx $bc87
	stz $bd00,x
	inc $bc88
	lda $bc88
	sta $bd01,x
	lda $b9b4
	sta $bd02,x
	lda $b9b5
	sta $bd03,x
	lda $bfe9
	sta $bd04,x
	lda $bfea
	sta $bd05,x
	lda $bfeb
	sta $bd06,x
	lda $bfec
	sta $bd07,x
	stz $bd08,x
	lda $ff83
	sta $bd09,x
	lda $ff84
	sta $bd0a,x
	stx $bc8a
	cpx #$00
	bne .Lnext_zero
	ldx #$22
	bra .Lnext_store
.Lnext_zero:
	ldx #$00
	inc $bc89
.Lnext_store:
	stx $bc87
	plx
	pla

	jsr c2_product_entry_read
	pha
	ldx $bc8a
	sta $bd08,x
	lda $ff83
	sta $bd0b,x
	lda $ff84
	sta $bd0c,x

	; The payload begins vmr_hdrlen bytes into vm_codebuf ($BFA4).
	clc
	lda #$a4
	adc $bfdd
	sta $04
	lda #$bf
	adc $bfde
	sta $05
	txa
	clc
	adc #$0d
	sta $06
	lda #$bd
	adc #$00
	sta $07
	ldy #$00
.Lcopy:
	lda ($04),y
	sta ($06),y
	iny
	cpy #$15
	bne .Lcopy
	lda #$a5
	sta $bd00,x
	pla
	rts

.Lpass:
	plx
	pla
	jmp c2_product_entry_read
	.size c2_refill_trace_read, .-c2_refill_trace_read
