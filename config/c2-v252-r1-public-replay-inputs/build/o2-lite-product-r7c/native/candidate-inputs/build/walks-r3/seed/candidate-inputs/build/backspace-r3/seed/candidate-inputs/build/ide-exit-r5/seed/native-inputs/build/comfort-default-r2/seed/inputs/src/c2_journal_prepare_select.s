; C2-lite co-resident journal-prepare selector.
;
; llvm-mos C ABI:
;   argument 0 c2_append_state pointer: __rc2/__rc3
;   uint8_t result: A
;
; The two C bodies remain the semantic authorities.  This leaf only reads
; main_ordinal and the existing C2J result byte, then tail-jumps to exactly
; one body.  The offsets are target-ABI facts guarded by matching _Static_assert
; declarations in c2_product_runtime.c.

	.zeropage	__rc2
	.zeropage	__rc3

	.section	.lisp65_rt_c2append_journal_prepare,"ax",@progbits
	.globl	c2_append_journal_prepare_phase
	.type	c2_append_journal_prepare_phase,@function
c2_append_journal_prepare_phase:
	; Preserve the existing first-error-wins install provenance.
	lda	lisp65_c2_phase_scratch+303
	bmi	.Lstamped
	lda	#30
	sta	lisp65_c2_phase_scratch+302
.Lstamped:
	; A null context fails before either logical body mutates state.
	lda	__rc2
	ora	__rc3
	beq	.Lstate_error

	; main_ordinal at target offset 2 selects the normal direct write.
	ldz	#2
	lda	(__rc2),z
	inz
	ora	(__rc2),z
	bne	.Lnormal

	; record[31] at target offset 213 drives rollback NONE -> PREPARED
	; -> ACTIVE.  ACTIVE and every foreign byte are replay errors.
	ldz	#213
	lda	(__rc2),z
	beq	.Lprepare
	cmp	#2
	beq	.Lwrite
	bra	.Lstate_error

.Lnormal:
	ldz	#213
	lda	(__rc2),z
	bne	.Lstate_error
.Lwrite:
	; llvm-mos requires Z=0 at every C function entry.  The selector used
	; Z=$d5 for the journal-result byte, so restore that invariant before
	; either tail edge.  The C bodies legitimately use (ptr),z without
	; reinitializing Z.
	ldz	#0
	jmp	c2_append_journal_write_phase
.Lprepare:
	ldz	#0
	jmp	c2_append_rollback_prepare_phase
.Lstate_error:
	lda	#8			; C2_STREAM_ERR_STATE
	ldz	#0
	rts
.Lc2_append_journal_prepare_phase_end:
	.size	c2_append_journal_prepare_phase, .Lc2_append_journal_prepare_phase_end-c2_append_journal_prepare_phase
