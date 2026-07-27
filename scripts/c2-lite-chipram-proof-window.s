; Owned $e000 test window for the C2-lite Bank-2/3 metal proof.  It is linked
; separately and installed by CPU stores, so the proof has no Attic premise.

	.include "c2-lite-chipram-proof-shared.inc"

	.section .lisp65_c2lt_window.dispatch,"ax",@progbits
	.globl c2lt_window_dispatch
	.type c2lt_window_dispatch,@function
c2lt_window_dispatch:
	lda C2LT_COMMAND
	cmp #C2LT_CMD_POLL_EVENT
	bne .Lunknown
	jmp c2lt_queue_poll
.Lunknown:
	lda #$00
	sta C2LT_RESPONSE
	rts
.Lc2lt_window_dispatch_end:
	.size c2lt_window_dispatch,.Lc2lt_window_dispatch_end-c2lt_window_dispatch

	.section .lisp65_c2lt_window.queue,"ax",@progbits
	.globl c2lt_queue_poll
	.type c2lt_queue_poll,@function
c2lt_queue_poll:
	lda $d60a
	bpl .Lempty
	and #$7f
	sta C2LT_EVENT_MODIFIERS
	lda $d619
	sta C2LT_EVENT_CODE
	sta $d619
	inc C2LT_DEQUEUE_COUNT
	lda #$01
	sta C2LT_RESPONSE
	rts
.Lempty:
	lda #$00
	sta C2LT_RESPONSE
	rts
.Lc2lt_queue_poll_end:
	.size c2lt_queue_poll,.Lc2lt_queue_poll_end-c2lt_queue_poll

	.section .lisp65_c2lt_window.irq,"ax",@progbits
	.globl c2lt_irq_handler
	.type c2lt_irq_handler,@function
c2lt_irq_handler:
	pha
	lda $d019
	and #$01
	beq .Lsource_less
	lda #$01
	sta $d019
	inc C2LT_FRAME_LO
	bne .Ldone
	inc C2LT_FRAME_HI
.Ldone:
	pla
	rti
.Lsource_less:
	lda $d019
	and #$1f
	sta C2LT_UNOWNED_VIC_FLAGS
	inc C2LT_UNEXPECTED_IRQ
	lda C2LT_UNEXPECTED_IRQ
	cmp #$02
	bcc .Ldone
	lda #$02
	sta $d020
	lda #$00
	sta $d01a
.Lstorm:
	jmp .Lstorm
.Lc2lt_irq_handler_end:
	.size c2lt_irq_handler,.Lc2lt_irq_handler_end-c2lt_irq_handler

	.section .lisp65_c2lt_window.nmi,"ax",@progbits
	.globl c2lt_nmi_handler
	.type c2lt_nmi_handler,@function
c2lt_nmi_handler:
	pha
	lda $dd0d
	inc C2LT_NMI_COUNT
	pla
	rti
.Lc2lt_nmi_handler_end:
	.size c2lt_nmi_handler,.Lc2lt_nmi_handler_end-c2lt_nmi_handler

	.section .lisp65_c2lt_window.fail,"ax",@progbits
	.globl c2lt_fail_closed
	.type c2lt_fail_closed,@function
c2lt_fail_closed:
	sei
	lda #$02
	sta $d020
	lda #$00
	sta $d01a
.Lfail:
	jmp .Lfail
.Lc2lt_fail_closed_end:
	.size c2lt_fail_closed,.Lc2lt_fail_closed_end-c2lt_fail_closed

	.section .lisp65_c2lt_vectors,"a",@progbits
	.word c2lt_nmi_handler
	.word c2lt_fail_closed
	.word c2lt_irq_handler
