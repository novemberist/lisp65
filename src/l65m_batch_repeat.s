; Compact MEGA65 predicate for immutable L65M preflight/commit batches.
; llvm-mos indirect-call ABI here: context=__rc2/__rc3, slot=A, result=X.
	.include	"build/generated/asm-c-contract.inc"

	.zeropage	__rc2
	.zeropage	__rc3
	.zeropage	__rc4
	.zeropage	__rc6

	.section	.lisp65_resident_island,"ax",@progbits
	.globl	vm_l65m_batch_repeat
	.type	vm_l65m_batch_repeat,@function
vm_l65m_batch_repeat:
	sta	__rc4                  ; slot
	cpx	#ASM_L65M_OK           ; entry_result == L65M_OK
	bne	.Lfail
	lda	__rc2
	ora	__rc3
	beq	.Lfail

	ldz	#ASM_L65M_ABI_VERSION_OFFSET
	lda	(__rc2),z              ; ABI tag is the first field
	cmp	#ASM_L65M_PREFLIGHT_ABI
	beq	.Lpreflight
	cmp	#ASM_L65M_COMMIT_ABI
	bne	.Lfail
	ldy	#ASM_L65M_COMMIT_SLOT_BASE
	bra	.Lconfigured
.Lpreflight:
	ldy	#ASM_L65M_PREFLIGHT_SLOT_BASE
.Lconfigured:
	sty	__rc6                  ; slot base
	ldy	#ASM_L65M_ABI_VERSION_HIGH_OFFSET
	lda	(__rc2),y              ; ABI high byte must be zero
	bne	.Lfail

	lda	__rc4
	sec
	sbc	__rc6
	sta	__rc6                  ; phase = slot - policy base
	ldy	#ASM_L65M_EXPECTED_PHASE_OFFSET
	cmp	(__rc2),y              ; expected_phase
	bne	.Lfail
	ldy	#ASM_L65M_BUSY_OFFSET
	lda	(__rc2),y              ; busy
	iny
	ora	(__rc2),y              ; transport_status
	bne	.Lfail
	ldy	#ASM_L65M_REPEAT_PHASE_OFFSET
	lda	(__rc2),y              ; repeat_phase
	beq	.Lfail
	lda	#1
	rts
.Lfail:
	lda	#0
	rts
	nop                         ; keep the immutable image/annex boundary even
.Lend:
	.size	vm_l65m_batch_repeat, .Lend-vm_l65m_batch_repeat
