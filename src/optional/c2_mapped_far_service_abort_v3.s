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

	.globl c2_mapped_far_enter
	.type c2_mapped_far_enter,@function
c2_mapped_far_enter:
	; Preserve A/X/Y and the C-ABI value Z=0.  $40/$82 exposes physical
	; $02A000..$02BFFF in CPU block 3 only.
	pha
	phx
	phy
	lda #0x40
	ldx #0x82
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
