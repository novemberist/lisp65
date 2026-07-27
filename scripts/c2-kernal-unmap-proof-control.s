; Low-resident handoff and pre-handoff continuity helpers for the isolated
; KERNAL-unmap target.  None of these sections enters a product link.

	.include "c2-kernal-unmap-proof-shared.inc"

	.section .lisp65_c2_map_switch_and_guards,"ax",@progbits
	.globl c2ku_capture_firmware_map
	.type c2ku_capture_firmware_map,@function
c2ku_capture_firmware_map:
	ldy #$1f
	ldx #$00
	lda #$74
	sta $d640
	clv
	rts

	.globl c2ku_map_window
	.type c2ku_map_window,@function
c2ku_map_window:
	; X[7:4] selects low blocks 0..3; Z[7:4] selects high blocks 4..7.
	; Map only block 7 ($e000-$ffff), with a zero offset into bank-0 RAM.
	lda #$00
	ldx #$00
	ldy #$00
	ldz #$80
	map
	eom
	; llvm-mos treats Z as the zero index for indirect-Z pointer accesses.
	; MAP consumes Z as an operand but must not leak that value back into C.
	ldz #$00
	rts

	.globl c2ku_window_dispatch_call
	.type c2ku_window_dispatch_call,@function
c2ku_window_dispatch_call:
	jsr $e000
	rts

	.section .lisp65_c2_frame_handoff,"ax",@progbits
	.globl c2ku_prehandoff_irq
	.type c2ku_prehandoff_irq,@function
c2ku_prehandoff_irq:
	pha
	lda $d019
	and #$01
	beq .Lpre_chain
	lda #$01
	sta $d019
	inc C2KU_FRAME_LO
	bne .Lpre_frame_done
	inc C2KU_FRAME_HI
.Lpre_frame_done:
.Lpre_chain:
	pla
	jmp (C2KU_OLD_IRQ_LO)
.Lc2ku_prehandoff_irq_end:
	.size c2ku_prehandoff_irq,.Lc2ku_prehandoff_irq_end-c2ku_prehandoff_irq
