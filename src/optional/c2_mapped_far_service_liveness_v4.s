	.section .lisp65_c2_mapped_far_facade.entries,"ax",@progbits
	.globl vm_code_load_converged
	.type vm_code_load_converged,@function
vm_code_load_converged:
	jsr c2_mapped_far_enter
	jsr c2_mapped_far_vm_code_load_converged
	jmp c2_mapped_far_leave
	.size vm_code_load_converged, .-vm_code_load_converged

	.globl c2_physical_read_converged
	.type c2_physical_read_converged,@function
c2_physical_read_converged:
	jsr c2_mapped_far_enter
	jsr c2_mapped_far_physical_read_converged
	jmp c2_mapped_far_leave
	.size c2_physical_read_converged, .-c2_physical_read_converged

	; Cold error/RUN-STOP cleanup.  The linked reachability gate proves that
	; no active far body can reach this entry: nested enter/leave is forbidden.
	.globl c2_abort_driver_facade
	.type c2_abort_driver_facade,@function
c2_abort_driver_facade:
	jsr c2_mapped_far_enter
	jsr c2_abort_driver
	jmp c2_mapped_far_leave
	.size c2_abort_driver_facade, .-c2_abort_driver_facade

	; Retirement-only continuation sanitization.  It runs before the wipe and
	; never taxes __call_indir or any ordinary evaluator call.
	.globl c2_rtov_retire_continuations_facade
	.type c2_rtov_retire_continuations_facade,@function
c2_rtov_retire_continuations_facade:
	jsr c2_mapped_far_enter
	jsr c2_rtov_retire_continuations
	jmp c2_mapped_far_leave
	.size c2_rtov_retire_continuations_facade, .-c2_rtov_retire_continuations_facade

	.globl c2_mapped_far_enter
	.type c2_mapped_far_enter,@function
c2_mapped_far_enter:
	; Preserve A/X/Y and the C-ABI value Z=0.  The linker owns both the
	; page-congruent tenant placement and these two derived MAP bytes.
	pha
	phx
	phy
	lda #mos16lo(__lisp65_c2_mapped_far_maplo_a)
	ldx #mos16lo(__lisp65_c2_mapped_far_maplo_x)
	ldy #0x00
	ldz #0x80
	map
	eom
	ldz #0x00
	ply
	plx
	pla
	rts
	.size c2_mapped_far_enter, .-c2_mapped_far_enter

	.globl c2_mapped_far_leave
	.type c2_mapped_far_leave,@function
c2_mapped_far_leave:
	; Restore the ordinary low map while retaining the owned E000 block.
	pha
	lda #0x00
	ldx #0x00
	ldy #0x00
	ldz #0x80
	map
	eom
	pla
	ldz #0x00
	rts
	.size c2_mapped_far_leave, .-c2_mapped_far_leave

	; Cold runtime-overlay transaction discriminator.  Keep the public C
	; identity in ordinary text while its body shares the mapped Far service.
	.section .text.rtov_transaction_context_if_ready,"ax",@progbits
	.globl rtov_transaction_context_if_ready
	.type rtov_transaction_context_if_ready,@function
rtov_transaction_context_if_ready:
	jsr c2_mapped_far_enter
	jsr rtov_transaction_context_if_ready_far
	jmp c2_mapped_far_leave
	.size rtov_transaction_context_if_ready, .-rtov_transaction_context_if_ready

	; Recovery-side entry for the same saved-CSR sanitation used by normal
	; retirement.  This path deliberately omits the active-frame walker: after
	; the boundary RTI the cleanup stack shape no longer exists.  Mapping is
	; entered only from the permanently visible recovery body at baseline MAP.
	.section .text.c2_rtov_sanitize_recovery,"ax",@progbits
	.globl c2_rtov_sanitize_recovery
	.type c2_rtov_sanitize_recovery,@function
c2_rtov_sanitize_recovery:
	jsr c2_mapped_far_enter
	jsr c2_rtov_sanitize_saved_csrs
	jmp c2_mapped_far_leave
	.size c2_rtov_sanitize_recovery, .-c2_rtov_sanitize_recovery

	.section .lisp65_c2_mapped_far_service.liveness,"ax",@progbits
	.globl c2_rtov_retire_continuations
	.type c2_rtov_retire_continuations,@function
c2_rtov_retire_continuations:
	jsr c2_rtov_sanitize_saved_csrs

	; The final-ELF control-flow population has one live-generation frame on
	; the direct overlay -> lisp_abort_symbol path.  At this entry its stored
	; JSR return word is the fourth hardware-stack frame: walker, facade,
	; cleanup, then the retiring overlay.  Test the actual stored word against
	; [overlay_start-1, overlay_end-2], because RTS adds one, and redirect only
	; an in-generation member.  Resident abort callers remain byte-for-byte
	; untouched.  This is retirement-only; no ordinary indirect call pays for
	; a generation check.
	tsx
	txa
	tay
	lda 0x0107,y
	sec
	sbc #mos16lo(__lisp65_workbench_overlay_start-1)
	tax
	lda 0x0108,y
	sbc #mos16hi(__lisp65_workbench_overlay_start-1)
	bcc .Lretire_done
	cmp #mos16hi(__lisp65_workbench_overlay_len)
	bcc .Lretire_active_frame
	bne .Lretire_done
	cpx #mos16lo(__lisp65_workbench_overlay_len)
	bcs .Lretire_done
.Lretire_active_frame:
	lda #mos16lo(c2_retired_continuation_stub-1)
	sta 0x0107,y
	lda #mos16hi(c2_retired_continuation_stub-1)
	sta 0x0108,y
.Lretire_done:
	rts
	.size c2_rtov_retire_continuations, .-c2_rtov_retire_continuations

	.globl c2_rtov_sanitize_saved_csrs
	.type c2_rtov_sanitize_saved_csrs,@function
c2_rtov_sanitize_saved_csrs:
	; jmp_buf offsets 5..18 are the seven llvm-mos saved-CSR pairs.  Compare
	; each pair against the linked overlay generation and replace only a live
	; member with the always-visible neutral retirement target.  Both normal
	; retirement and boundary recovery consume this single implementation.
	ldy #0
.Lretire_pair:
	lda lisp_toplevel+5,y
	sec
	sbc #mos16lo(__lisp65_workbench_overlay_start)
	tax
	lda lisp_toplevel+6,y
	sbc #mos16hi(__lisp65_workbench_overlay_start)
	bcc .Lretire_next
	cmp #mos16hi(__lisp65_workbench_overlay_len)
	bcc .Lretire_replace
	bne .Lretire_next
	cpx #mos16lo(__lisp65_workbench_overlay_len)
	bcs .Lretire_next
.Lretire_replace:
	lda #mos16lo(c2_retired_continuation_stub)
	sta lisp_toplevel+5,y
	lda #mos16hi(c2_retired_continuation_stub)
	sta lisp_toplevel+6,y
.Lretire_next:
	iny
	iny
	cpy #14
	bne .Lretire_pair
	rts
	.size c2_rtov_sanitize_saved_csrs, .-c2_rtov_sanitize_saved_csrs
