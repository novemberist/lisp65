; C2-lite chained-bootstrap resident commit leaf.
;
; Record 1 has already authenticated Record 2 into unpublished Bank 2 and
; tail-jumps here.  The leaf copies those bytes into the self-overwriting
; Workbench VMA, rechecks destination identity, executes the entry, then wipes
; the dead window.  Instruction selection and size are outside WPLTO.

	.zeropage	__rc2
	.zeropage	__rc3
	.zeropage	__rc4
	.zeropage	__rc5
	.zeropage	__rc6
	.zeropage	__rc7
	.zeropage	mem_oom
	.zeropage	vm_boot_overlay_status

; The only cross-overlay geometry is owned by resident immutable data.  Cold
; Record 1 reads this table; it does not own a relocation to its sibling.
	.section .rodata.vm_boot_overlay_chain_expected,"a",@progbits
	.globl vm_boot_overlay_chain_expected
	.type vm_boot_overlay_chain_expected,@object
vm_boot_overlay_chain_expected:
	.word __lisp65_workbench_overlay_start
	.word vm_workbench_boot_overlay_entry
	.word __lisp65_workbench_overlay_len
.Lchain_expected_end:
	.size vm_boot_overlay_chain_expected, .Lchain_expected_end-vm_boot_overlay_chain_expected

	.section .text.vm_boot_overlay_chain_commit,"ax",@progbits
	.globl vm_boot_overlay_chain_commit
	.type vm_boot_overlay_chain_commit,@function
vm_boot_overlay_chain_commit:
	; Preserve Record 2's expected CRC before the Bank-0 copy overwrites the
	; descriptor prefix that currently holds it.
	lda __lisp65_boot_bank3_stage_start+16
	pha
	lda __lisp65_boot_bank3_stage_start+17
	pha

	; c2_facade_c2_dma(0, 2, Workbench VMA, 0, Workbench length).
	lda #2
	sta __rc2
	lda #mos16lo(__lisp65_workbench_overlay_start)
	sta __rc3
	lda #mos16hi(__lisp65_workbench_overlay_start)
	sta __rc4
	stz __rc5
	lda #mos16lo(__lisp65_workbench_overlay_len)
	sta __rc6
	lda #mos16hi(__lisp65_workbench_overlay_len)
	sta __rc7
	ldx #0
	txa
	jsr c2_facade_c2_dma

	lda #8                         ; VM_BOOT_OVERLAY_ERR_CRC
	sta vm_boot_overlay_status
	; ov_crc16 is a WPLTO-internal C helper.  Its linked llvm-mos ABI places
	; argument 0 (the pointer) in __rc2/__rc3 and argument 1 (the length) in
	; A/X.  Keep this seam under the shared assembler-leaf ABI gate: unlike a
	; C caller, handwritten assembly receives no type-checked register setup.
	lda #mos16lo(__lisp65_workbench_overlay_start)
	sta __rc2
	lda #mos16hi(__lisp65_workbench_overlay_start)
	sta __rc3
	lda #mos16lo(__lisp65_workbench_overlay_len)
	ldx #mos16hi(__lisp65_workbench_overlay_len)
	jsr ov_crc16
	sta __rc4
	stx __rc5
	pla                             ; expected high
	eor __rc5
	sta __rc5
	pla                             ; expected low
	eor __rc4
	ora __rc5
	bne .Lchain_return

	lda #9                         ; VM_BOOT_OVERLAY_ERR_ENTRY_RUN
	sta vm_boot_overlay_status
	jsr .Lchain_error_present
	bne .Lchain_return
	jsr vm_workbench_boot_overlay_entry
	jsr .Lchain_error_present
	bne .Lchain_return

	lda #10                        ; VM_BOOT_OVERLAY_ERR_WIPE
	sta vm_boot_overlay_status
	lda #mos16lo(__lisp65_workbench_overlay_start)
	sta __rc2
	lda #mos16hi(__lisp65_workbench_overlay_start)
	sta __rc3
	ldz #0
.Lwipe_more:
	lda #0
	sta (__rc2),z
	lda (__rc2),z
	bne .Lchain_return
	inw __rc2
	lda __rc2
	cmp #mos16lo(__lisp65_workbench_overlay_end)
	bne .Lwipe_more
	lda __rc3
	cmp #mos16hi(__lisp65_workbench_overlay_end)
	bne .Lwipe_more
.Lwipe_done:
	stz vm_boot_overlay_status
.Lchain_return:
	ldz #0
	rts

.Lchain_error_present:
	lda lisp_error_msg
	ora lisp_error_msg+1
	ora mem_oom
	rts
.Lchain_commit_end:
	.size vm_boot_overlay_chain_commit, .Lchain_commit_end-vm_boot_overlay_chain_commit
