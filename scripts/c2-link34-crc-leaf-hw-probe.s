; Receipt-less exact-byte hardware probe for Link 34's linked CRC leaf.
;
; The product is loaded first but not entered.  This deliberately tiny BASIC
; programme overwrites only $2001... below the immutable leaf at $222d, calls
; that exact leaf six times, writes a fixed mailbox at $1f00 and stops.

	.equ MAILBOX, $1f00
	.equ CRC_LEAF, $222d
	.equ CRC_LEN_LO, $04
	.equ CRC_LEN_HI, $05

	.section .text.c2_link34_crc_probe,"ax",@progbits
	; 10 SYS8205, with machine entry at $200d.
	.word $200b
	.word 10
	.byte $9e
	.ascii "8205"
	.byte 0
	.word 0

	.globl c2_link34_crc_probe_entry
	.type c2_link34_crc_probe_entry,@function
c2_link34_crc_probe_entry:
	sei
	ldz #0
	lda #'C'
	sta MAILBOX+0
	lda #'2'
	sta MAILBOX+1
	lda #'C'
	sta MAILBOX+2
	lda #'R'
	sta MAILBOX+3
	lda #0
	sta MAILBOX+4
	lda #$ff
	sta MAILBOX+5
	lda #0
	sta MAILBOX+6
	sta MAILBOX+7
	lda #2
	sta $d020

	; Case 0: canonical CRC-16/CCITT-FALSE check vector.
	lda #0
	sta MAILBOX+5
	lda #9
	sta CRC_LEN_LO
	lda #0
	sta CRC_LEN_HI
	lda #$00
	ldx #$80
	jsr CRC_LEAF
	sta MAILBOX+8
	stx MAILBOX+9
	cmp #$b1
	beq .Lcase0_low_ok
	jmp .Lfail
.Lcase0_low_ok:
	cpx #$29
	beq .Lcase0_high_ok
	jmp .Lfail
.Lcase0_high_ok:
	lda #1
	sta MAILBOX+6

	; Case 1: exact zeroed-CRC catalog header.
	lda #1
	sta MAILBOX+5
	lda #32
	sta CRC_LEN_LO
	lda #0
	sta CRC_LEN_HI
	lda #$00
	ldx #$81
	jsr CRC_LEAF
	sta MAILBOX+10
	stx MAILBOX+11
	cmp #$de
	beq .Lcase1_low_ok
	jmp .Lfail
.Lcase1_low_ok:
	cpx #$f0
	beq .Lcase1_high_ok
	jmp .Lfail
.Lcase1_high_ok:
	lda #2
	sta MAILBOX+6

	; Case 2: exact catalog-verifier payload.
	lda #2
	sta MAILBOX+5
	lda #$84
	sta CRC_LEN_LO
	lda #$04
	sta CRC_LEN_HI
	lda #$00
	ldx #$82
	jsr CRC_LEAF
	sta MAILBOX+12
	stx MAILBOX+13
	cmp #$1d
	beq .Lcase2_low_ok
	jmp .Lfail
.Lcase2_low_ok:
	cpx #$29
	beq .Lcase2_high_ok
	jmp .Lfail
.Lcase2_high_ok:
	lda #3
	sta MAILBOX+6

	; Case 3: exact record-verifier payload.
	lda #3
	sta MAILBOX+5
	lda #$83
	sta CRC_LEN_LO
	lda #$05
	sta CRC_LEN_HI
	lda #$00
	ldx #$87
	jsr CRC_LEAF
	sta MAILBOX+14
	stx MAILBOX+15
	cmp #$7c
	beq .Lcase3_low_ok
	jmp .Lfail
.Lcase3_low_ok:
	cpx #$3d
	beq .Lcase3_high_ok
	jmp .Lfail
.Lcase3_high_ok:
	lda #4
	sta MAILBOX+6

	; Case 4: exact resident-Island installer payload.
	lda #4
	sta MAILBOX+5
	lda #$07
	sta CRC_LEN_LO
	lda #$05
	sta CRC_LEN_HI
	lda #$00
	ldx #$8d
	jsr CRC_LEAF
	sta MAILBOX+16
	stx MAILBOX+17
	cmp #$4b
	beq .Lcase4_low_ok
	jmp .Lfail
.Lcase4_low_ok:
	cpx #$bf
	beq .Lcase4_high_ok
	jmp .Lfail
.Lcase4_high_ok:
	lda #5
	sta MAILBOX+6

	; Case 5: exact resident-Island DATA_ONLY carrier.
	lda #5
	sta MAILBOX+5
	lda #$f5
	sta CRC_LEN_LO
	lda #$06
	sta CRC_LEN_HI
	lda #$00
	ldx #$93
	jsr CRC_LEAF
	sta MAILBOX+18
	stx MAILBOX+19
	cmp #$09
	beq .Lcase5_low_ok
	jmp .Lfail
.Lcase5_low_ok:
	cpx #$80
	beq .Lcase5_high_ok
	jmp .Lfail
.Lcase5_high_ok:
	lda #6
	sta MAILBOX+6
	lda #$ff
	sta MAILBOX+5
	lda #'P'
	sta MAILBOX+4
	lda #5
	sta $d020
	bra .Lstop

.Lfail:
	lda #'F'
	sta MAILBOX+4
	lda #2
	sta $d020
.Lstop:
	bra .Lstop
.Lc2_link34_crc_probe_end:
	.size c2_link34_crc_probe_entry,.Lc2_link34_crc_probe_end-c2_link34_crc_probe_entry
