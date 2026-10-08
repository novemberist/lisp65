; Private v1.6 Comfort scalar dequeue.  A=0 means empty.  Modes arrive in A
; under the llvm-mos byte ABI: 2 consumes any event, 3 only a printable one.

	.include "c2_kernal_window_equates.inc"

	.section .lisp65_c2_kernal_window.input_consumer,"ax",@progbits
	.globl c2_kernal_input_take
	.type c2_kernal_input_take,@function
c2_kernal_input_take:
	tax
	lda C2K_INPUT_RING_TAIL
	bmi .Ltake_none
	cmp C2K_INPUT_RING_HEAD
	beq .Ltake_none
	tay
	lda C2K_INPUT_RING_BASE,y
	cmp #160
	bne .Lscalar_next_0
	lda #255
	bra .Ltake_commit
.Lscalar_next_0:
	cmp #193
	bne .Lscalar_next_1
	lda #120
	bra .Ltake_commit
.Lscalar_next_1:
.Ltake_commit:
	cpx #$03
	bne .Ltake_advance
	cmp #$20
	bcc .Ltake_none
	cmp #$7f
	bcs .Ltake_none
.Ltake_advance:
	iny
	cpy #C2K_INPUT_RING_SLOTS
	bne .Ltake_store
	ldy #$00
.Ltake_store:
	sty C2K_INPUT_RING_TAIL
	inc C2K_INPUT_EVENTS_TAKEN
	rts
.Ltake_none:
	lda #$00
	rts
.Lc2_kernal_input_take_end:
	.size c2_kernal_input_take, .Lc2_kernal_input_take_end-c2_kernal_input_take
