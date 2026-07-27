; C2-lite cold-start handoff trampoline.
;
; The C2 media stager copies this position-independent fragment to $1800 and
; writes two normal F018B jobs at $1840.  The first copies the independently
; verified PRG payload from Bank 4 to $2001; the second publishes a completion
; byte at job+24.  The CPU may resume as soon as DMAgic accepts the list, so
; the trampoline must observe that ordered second job before entering the
; product.  C2-lite's linked entry is $2023; this source is deliberately
; separate from the historical R3/$2026 trampoline so neither product can
; silently inherit the other's entry or completion geometry.
	.include	"build/generated/c2-lite-asm-c-contract.inc"

	.equ	R3_CHAIN_COMPLETION_MARKER, (ASM_R3_CHAIN_JOB_ADDR_HI << 8) + ASM_R3_CHAIN_JOB_ADDR_LO + 24

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
1:
	lda	R3_CHAIN_COMPLETION_MARKER
	cmp	#$a5
	bne	1b
	jmp	ASM_R3_PRODUCT_ENTRY
r3_chain_end:
	.size	r3_chain_begin, r3_chain_end-r3_chain_begin
