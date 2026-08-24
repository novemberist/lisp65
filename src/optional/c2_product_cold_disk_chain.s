; Product-owned cold disk-chain entry.  This is the non-diagnostic successor
; of the temporary refill witness's placement stub: the product body keeps its
; proven MAP placement while the witness, trace reader and trace origin leave
; the acceptance world completely.

	.section .text.disk_chain_to_scratch,"ax",@progbits
	.globl disk_chain_to_scratch
	.type disk_chain_to_scratch,@function
	.globl c2_mapped_far_enter
	.globl disk_chain_to_scratch_far
	.globl c2_mapped_far_leave
disk_chain_to_scratch:
	jsr c2_mapped_far_enter
	jsr disk_chain_to_scratch_far
	; c2_mapped_far_leave owns X while restoring MAP.  Preserve the high byte
	; of the unsigned-int A/X result across the shared leave routine.
	phx
	jsr c2_mapped_far_leave
	plx
	rts
	.size disk_chain_to_scratch, .-disk_chain_to_scratch
