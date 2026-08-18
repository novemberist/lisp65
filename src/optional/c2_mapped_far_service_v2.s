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

	.globl c2_mapped_far_enter
	.type c2_mapped_far_enter,@function
c2_mapped_far_enter:
	; Preserve A/X/Y and the C-ABI value Z=0.  Per the primary MAP encoding,
	; A supplies offset bits 8..15 while X[3:0] supplies bits 16..19 and
	; X[7:4] selects low-half CPU blocks.  Thus $40/$82 exposes physical
	; $02A000..$02BFFF in CPU block 3 only; restore that boundary explicitly.
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
	; A is the one-byte C result.  Restore the ordinary low map while keeping
	; the owned E000 block selected, then re-establish the llvm-mos Z=0 ABI.
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
