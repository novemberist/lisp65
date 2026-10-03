; C2-lite chained Bootstrap seam.
;
; The resident one-record loader calls this entry after authenticating the
; pre-family stage record.  Both C helpers return while the record is still
; intact.  The final JMP, rather than JSR, preserves the original resident
; return address: the commit seam may overwrite this complete Bank-0 record
; with the verified Workbench payload and return directly to the loader.

	.section .lisp65_boot_bank3_stage_prefix,"a",@progbits
	.space 18,0

	.section .lisp65_boot_bank3_stage,"ax",@progbits
	.globl vm_bank3_boot_stage_entry
	.type vm_bank3_boot_stage_entry,@function
vm_bank3_boot_stage_entry:
	jsr c2_lite_stage_boot_family
	cmp #0
	beq .Lstage_ok
	jsr vm_bank3_boot_stage_fail
	rts
.Lstage_ok:
	jsr vm_boot_overlay_chain_prepare
	cmp #0
	beq .Lchain_fail
	jmp vm_boot_overlay_chain_commit
.Lchain_fail:
	rts
.Lvm_bank3_boot_stage_entry_end:
	.size vm_bank3_boot_stage_entry, .Lvm_bank3_boot_stage_entry_end-vm_bank3_boot_stage_entry
