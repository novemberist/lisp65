; v1.6 input-capture IRQ/state owner.  This file is a build-member only in
; the input-fidelity world; the R1 world links c2_kernal_irq_base.s instead.

	.include "c2_kernal_window_equates.inc"

	.section .lisp65_c2_kernal_window.irq_handler,"ax",@progbits
	.globl c2_kernal_irq_handler
	.type c2_kernal_irq_handler,@function
c2_kernal_irq_handler:
	pha
	phx
	phy
	phz
	ldz #0
	lda $d019
	and #$01
	beq .Lsource_less
	sta $d019
	; Same-size replacement for the base world's STZ.
	jsr c2_kernal_input_capture
	inc C2K_FRAME_LO
	bne .Lsample_break
	inc C2K_FRAME_HI
.Lsample_break:
	lda $d613
	bmi .Lbreak_released
	lda C2K_BREAK_HELD
	bne .Lirq_return
	inc C2K_BREAK_HELD
	inc C2K_BREAK_PENDING
	bra .Lirq_return
.Lbreak_released:
	stz C2K_BREAK_HELD
	.globl c2_kernal_irq_return
.Lirq_return:
c2_kernal_irq_return:
	plz
	ply
	plx
	pla
	rti
.Lsource_less:
	lda $d019
	and #$1f
	sta C2K_UNOWNED_VIC
	lda C2K_SOURCELESS_IRQS
	beq .Lfirst_source_less
	jmp retired_window_brk_classifier
.Lfirst_source_less:
	inc C2K_SOURCELESS_IRQS
	bra .Lirq_return

	; The two fragments occupy the two final-ELF-derived holes.  They are two
	; ordinary assembler functions so every cross-section edge lands on a
	; declared entry.
	.section .lisp65_c2_kernal_window.input_capture_main,"ax",@progbits
	.globl c2_kernal_input_capture
	.type c2_kernal_input_capture,@function
c2_kernal_input_capture:
	stz C2K_SOURCELESS_IRQS
	lda C2K_INPUT_RING_TAIL
	bmi .Lcapture_done
.Lcapture_again:
	lda $d60a
	bpl .Lcapture_done
	; Bound-origin raw witness: queue-present before code read, filtering,
	; normalization or ring admission.
	inc C2K_INPUT_EVENTS_RAW
	lda $d619
	inc C2K_INPUT_EVENTS_SEEN
	jsr c2_kernal_input_capture_commit
	bne .Lcapture_again
.Lcapture_done:
	rts
.Lc2_kernal_input_capture_end:
	.size c2_kernal_input_capture, .Lc2_kernal_input_capture_end-c2_kernal_input_capture

	.section .lisp65_c2_kernal_window.input_capture_helper,"ax",@progbits
	.globl c2_kernal_input_capture_commit
	.type c2_kernal_input_capture_commit,@function
c2_kernal_input_capture_commit:
	; Filtering shares the helper's larger final-image-derived interval.  A
	; discarded RUN/STOP returns nonzero so the main drain continues, just as
	; a successful ring commit does.
	cmp #$03
	beq .Lcapture_discard_stop
	ldx C2K_INPUT_RING_HEAD
	inx
	cpx #C2K_INPUT_RING_SLOTS
	bne .Lcapture_next
	ldx #$00
.Lcapture_next:
	cpx C2K_INPUT_RING_TAIL
	beq .Lcapture_commit_done
	taz
	cmp #$a0
	beq .Lencode_high_normalize
	cmp #$41
	bcc .Lencoded_test
	cmp #$5b
	bcs .Lencode_shifted
	ora #$20
	bra .Lencoded_test
.Lencode_shifted:
	; $5c (`£`, the quasiquote key) enters here, fails the #$c1 bound and
	; commits unchanged.  That pass-through is contractual: the reader wants
	; the byte as ASCII backslash 0x5c, which is the same code.
	cmp #$c1
	bcc .Lencoded_test
	cmp #$db
	bcs .Lencoded_test
.Lencode_high_normalize:
	and #$7f
.Lencoded_test:
	cmp #255
	bne .Lenc_next_0
	lda $d60a
	and #4
	cmp #4
	bne .Lenc_plain_0
	lda #160
	bra .Lenc_store
.Lenc_plain_0:
	lda #255
	bra .Lenc_store
.Lenc_next_0:
	cmp #120
	bne .Lenc_next_1
	lda $d60a
	and #16
	cmp #16
	bne .Lenc_plain_1
	lda #193
	bra .Lenc_store
.Lenc_plain_1:
	lda #120
	bra .Lenc_store
.Lenc_next_1:
.Lenc_store:
	ldy C2K_INPUT_RING_HEAD
	sta C2K_INPUT_RING_BASE,y
	tza
	ldz #0
	sta $d619
	stx C2K_INPUT_RING_HEAD
	inc C2K_INPUT_EVENTS_STORED
.Lcapture_commit_done:
	rts
.Lcapture_discard_stop:
	sta $d619
	tax
	rts
.Lc2_kernal_input_capture_commit_end:
	.size c2_kernal_input_capture_commit, .Lc2_kernal_input_capture_commit_end-c2_kernal_input_capture_commit

	.section .lisp65_c2_kernal_window.state,"a",@progbits
	.space 13, 0
	.byte $ff
	.space 2, 0
