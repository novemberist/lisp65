; Product-owned $e000-$ffff window.  This is linked as an independent product
; artifact and staged in Attic RAM; it is not the receipt-less proof carrier.

	.set C2K_EQUATE_OWNER, 1
	.include "c2_kernal_window_equates.inc"
	.zeropage c2_backstop_rtov_busy
	.zeropage c2_backstop_rtov_loaded_len
	.zeropage lisp_toplevel_active
	.zeropage c2_backstop_pending_code

	.section .lisp65_c2_kernal_window.typed_queue_driver,"ax",@progbits
	.zeropage __rc2
	.zeropage __rc3
	.globl c2_kernal_event_poll
	.type c2_kernal_event_poll,@function
c2_kernal_event_poll:
	; llvm-mos ABI: lisp65_key_event * in __rc2/__rc3, boolean in A.
	; A pending physical matrix edge has priority over ordinary queue data and
	; is consumed exactly once at this safe evaluator boundary.
	lda __rc2
	ora __rc3
	beq .Lqueue_empty
	lda C2K_BREAK_PENDING
	beq .Lqueue_next
	stz C2K_BREAK_PENDING
	lda #$03
	ldy #$00
	bra .Lstore_event

.Lqueue_next:
	lda $d60a
	bpl .Lqueue_empty
	and #$7f
	tay
	lda $d619
	; The write advances exactly the queue head sampled above.
	sta $d619
	; Queue $03 is not an abort authority.  Drain it once and continue so the
	; corresponding physical matrix edge cannot be delivered twice.
	cmp #$03
	beq .Lqueue_next
.Lstore_event:
	ldz #$00
	sta (__rc2),z
	inz
	tya
	sta (__rc2),z
	lda #$01
	ldz #$00
	rts
.Lqueue_empty:
	lda #$00
	ldz #$00
	rts
.Lc2_kernal_event_poll_end:
	.size c2_kernal_event_poll, .Lc2_kernal_event_poll_end-c2_kernal_event_poll

	.section .lisp65_c2_kernal_window.nmi_and_freezer_return,"ax",@progbits
	.globl c2_kernal_nmi_handler
	.type c2_kernal_nmi_handler,@function
c2_kernal_nmi_handler:
	pha
	lda $dd0d
	inc C2K_NMI_COUNT
	pla
	rti

	.section .lisp65_c2_kernal_window.map_switch_and_guards,"ax",@progbits
	.globl c2_kernal_fail_closed
	.type c2_kernal_fail_closed,@function
c2_kernal_fail_closed:
	sei
	lda #$00
	sta $d01a
	lda #$02
	sta $d020
.Lfailed:
	jmp .Lfailed

	; Complete retired-window enforcement lives at the execution boundary.
	; A second source-less interrupt is recoverable only when it is a software
	; BRK whose stacked continuation belongs to the now-retired overlay, no
	; overlay transaction is live, and the top-level recovery target exists.
	; The IRQ handler has already saved A/X/Y/Z, so Y is safe scratch here.
	.section .text.retired_window_brk_classifier,"ax",@progbits
	.globl retired_window_brk_classifier
	.type retired_window_brk_classifier,@function
	; This sized ASM function is an IRQ-owned tail continuation rather than a
	; C-callable entry.  Its explicit ABI policy records that distinction while
	; preserving its ELF function identity for the transitive ownership graph.
	; It inherits the handler's established Z=0 and returns through the saved
	; IRQ frame rather than through the ordinary function ABI.
retired_window_brk_classifier:
	tsx
	lda $0105,x
	and #$10
	beq .Lretired_window_not_ours
	lda c2_backstop_rtov_busy
	ora c2_backstop_rtov_loaded_len
	ora c2_backstop_rtov_loaded_len+1
	bne .Lretired_window_not_ours
	lda lisp_toplevel_active
	beq .Lretired_window_not_ours
	lda $0106,x
	sec
	sbc #mos16lo(__lisp65_workbench_overlay_start+2)
	tay
	lda $0107,x
	sbc #mos16hi(__lisp65_workbench_overlay_start+2)
	bcc .Lretired_window_not_ours
	cmp #mos16hi(__lisp65_workbench_overlay_len)
	bcc .Lretired_window_accept
	bne .Lretired_window_not_ours
	cpy #mos16lo(__lisp65_workbench_overlay_len)
	bcs .Lretired_window_not_ours
.Lretired_window_accept:
	lda #mos16lo(retired_window_resume)
	sta $0106,x
	lda #mos16hi(retired_window_resume)
	sta $0107,x
	jmp c2_kernal_irq_return
.Lretired_window_not_ours:
	jmp c2_kernal_fail_closed
	.size retired_window_brk_classifier, .-retired_window_brk_classifier

	; Cleanup has already retired and wiped the overlay.  Re-entering it here
	; would recurse through the defect, so preserve an existing pending error
	; (or synthesize the stable E3e family-stage identity) and jump directly to
	; the established top-level continuation.
	.section .text.retired_window_resume,"ax",@progbits
	.globl retired_window_resume
	.type retired_window_resume,@function
retired_window_resume:
	; The recovery writer obeys the same liveness contract as retirement.
	; Sanitize the saved register file before longjmp can restore it.
	jsr c2_rtov_sanitize_recovery
	lda c2_backstop_pending_code
	bne .Lretired_window_pending
	lda #62
	sta c2_backstop_pending_code
	stz c2_backstop_pending_symbol
	stz c2_backstop_pending_symbol+1
.Lretired_window_pending:
	lda #mos16lo(lisp_toplevel)
	sta __rc2
	lda #mos16hi(lisp_toplevel)
	sta __rc3
	lda #1
	ldx #0
	jmp longjmp
	.size retired_window_resume, .-retired_window_resume

	.section .lisp65_c2_kernal_window.post_startup_output_seam,"ax",@progbits
	.globl c2_kernal_output_cell
	.type c2_kernal_output_cell,@function
c2_kernal_output_cell:
	sta $0800,x
	rts

	.section .lisp65_c2_vectors,"a",@progbits
	.word c2_kernal_nmi_handler
	.word c2_kernal_fail_closed
	.word c2_kernal_irq_handler
