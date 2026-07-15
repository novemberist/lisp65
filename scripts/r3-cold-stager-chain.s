; R3 cold-start handoff trampoline.
;
; The C stager copies this position-independent fragment to $1800 and writes a
; legacy DMA job at $1840.  The job copies the already verified PRG payload
; from Bank 4 to $2001.  The trampoline is deliberately below the product
; load range, so the DMA may overwrite the complete C stager before control is
; transferred to the manifest-bound llvm-mos entry at $2026.
	.include	"build/generated/asm-c-contract.inc"

	.section	.r3_chain_trampoline,"ax",@progbits
	.globl	r3_chain_begin
	.globl	r3_chain_end
	.type	r3_chain_begin,@function
r3_chain_begin:
	sei
	lda	#1
	sta	$d703
	lda	#0
	sta	$d702
	lda	#ASM_R3_CHAIN_JOB_ADDR_HI
	sta	$d701
	lda	#ASM_R3_CHAIN_JOB_ADDR_LO
	sta	$d700
	jmp	ASM_R3_PRODUCT_ENTRY
r3_chain_end:
	.size	r3_chain_begin, r3_chain_end-r3_chain_begin
