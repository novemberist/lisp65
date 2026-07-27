; Isolated $e000-$ffff replacement window for the bounded C2 KERNAL-unmap
; proof.  This is not linked into any product profile.

	.include "c2-kernal-unmap-proof-shared.inc"

	.section .lisp65_c2_kernal_window.00_dispatch,"ax",@progbits
	.globl c2ku_window_dispatch
	.type c2ku_window_dispatch,@function
c2ku_window_dispatch:
	lda C2KU_COMMAND
	cmp #C2KU_CMD_VALIDATE
	beq .Lvalidate
	cmp #C2KU_CMD_POLL_EVENT
	; Do not emit a conditional branch relocation across linker sections.
	; The llvm-mos long-branch relocation resolved one byte before the queue
	; entry on the hardware proof, returning through .Lvalidate's RTS instead
	; of calling the consumer.  Keep the conditional edge local and cross the
	; section boundary only with an absolute JMP whose target is link-verifiable.
	bne .Lunknown
	jmp c2ku_queue_poll
.Lunknown:
	lda #$00
	sta C2KU_RESPONSE
	rts
.Lvalidate:
	lda #C2KU_RESPONSE_MAGIC
	sta C2KU_RESPONSE
	rts
.Lc2ku_window_dispatch_end:
	.size c2ku_window_dispatch,.Lc2ku_window_dispatch_end-c2ku_window_dispatch

	.section .lisp65_c2_kernal_window.typed_queue_driver,"ax",@progbits
	.globl c2ku_queue_poll
	.type c2ku_queue_poll,@function
c2ku_queue_poll:
	lda $d60a
	bpl .Lqueue_empty
	and #$7f
	sta C2KU_EVENT_MODIFIERS
	lda $d619
	sta C2KU_EVENT_CODE
	; One write to PETSCIIKEY is the one and only dequeue operation.
	sta $d619
	inc C2KU_DEQUEUE_COUNT
	lda #$01
	sta C2KU_RESPONSE
	rts
.Lqueue_empty:
	lda #$00
	sta C2KU_RESPONSE
	rts
.Lc2ku_queue_poll_end:
	.size c2ku_queue_poll,.Lc2ku_queue_poll_end-c2ku_queue_poll

	.section .lisp65_c2_kernal_window.frame_source,"ax",@progbits
	.globl c2ku_frame_tick
	.type c2ku_frame_tick,@function
c2ku_frame_tick:
	inc C2KU_FRAME_LO
	bne .Lframe_done
	inc C2KU_FRAME_HI
.Lframe_done:
	rts
.Lc2ku_frame_tick_end:
	.size c2ku_frame_tick,.Lc2ku_frame_tick_end-c2ku_frame_tick

	.section .lisp65_c2_kernal_window.irq_handler,"ax",@progbits
	.globl c2ku_irq_handler
	.type c2ku_irq_handler,@function
c2ku_irq_handler:
	pha
	lda $d019
	and #$01
	beq .Lunexpected_irq
	lda #$01
	sta $d019
	jsr c2ku_frame_tick
	pla
	rti
.Lunexpected_irq:
	; A Freezer return can resume a CPU-latched IRQ after its external source
	; has vanished.  Record, but do not acknowledge, any non-owned source: the
	; contract permits this handler to acknowledge only its VIC raster source.
	lda $d019
	; VIC-IV defines IRQ flags only in bits 4..0.  Bits 6..5 are reserved in
	; the pinned register table and read as $60 on the hardware after Freezer
	; return; they are not evidence of an interrupt source.
	and #$1f
	sta C2KU_UNOWNED_VIC_FLAGS
	inc C2KU_UNEXPECTED_IRQ
	lda C2KU_UNEXPECTED_IRQ
	cmp #$02
	bcc .Lsource_less_return
	; A second source-less entry is a storm, not bounded resume jitter.
	; Stop in the owned window without calling C, Lisp or firmware.
	lda #$02
	sta $d020
	lda #$00
	sta $d01a
	lda #'U'
	sta $09e0
.Lsource_less_storm:
	jmp .Lsource_less_storm
.Lsource_less_return:
	pla
	rti
.Lc2ku_irq_handler_end:
	.size c2ku_irq_handler,.Lc2ku_irq_handler_end-c2ku_irq_handler

	.section .lisp65_c2_kernal_window.nmi_and_freezer_return,"ax",@progbits
	.globl c2ku_nmi_handler
	.type c2ku_nmi_handler,@function
c2ku_nmi_handler:
	pha
	lda $dd0d
	inc C2KU_NMI_COUNT
	pla
	rti
.Lc2ku_nmi_handler_end:
	.size c2ku_nmi_handler,.Lc2ku_nmi_handler_end-c2ku_nmi_handler

	.section .lisp65_c2_kernal_window.map_switch_and_guards,"ax",@progbits
	.globl c2ku_fail_closed
	.type c2ku_fail_closed,@function
c2ku_fail_closed:
	sei
	lda #$02
	sta $d020
	lda #$00
	sta $d01a
	lda #'R'
	sta $09e0
.Lfail_closed_loop:
	jmp .Lfail_closed_loop
.Lc2ku_fail_closed_end:
	.size c2ku_fail_closed,.Lc2ku_fail_closed_end-c2ku_fail_closed

	.section .lisp65_c2_kernal_window.post_startup_output_seam,"ax",@progbits
	.globl c2ku_output_cell
	.type c2ku_output_cell,@function
c2ku_output_cell:
	; A deliberately tiny native seam: caller supplies screen code in A and
	; X as an offset in the first row.  No KERNAL edge exists.
	sta $0800,x
	rts
.Lc2ku_output_cell_end:
	.size c2ku_output_cell,.Lc2ku_output_cell_end-c2ku_output_cell

	.section .lisp65_c2_vectors,"a",@progbits
	.word c2ku_nmi_handler
	.word c2ku_fail_closed
	.word c2ku_irq_handler
