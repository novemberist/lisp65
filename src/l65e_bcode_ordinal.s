; L65E allocation-free target renderer.
;
; llvm-mos C ABI:
;   entry argument (context pointer): __rc2/__rc3 (little endian)
;   entry result:                     A (lisp65_error_overlay_status)
;
; error_overlay.c remains the executable host oracle and owns the generated
; table plus compile-time format assertions.  This MOS leaf consumes that same
; table and owns no persistent state.  Its constants are pinned by the BCODE
; ordinal contract/gate against the C headers.

	.zeropage	__rc2
	.zeropage	__rc3
	.zeropage	__rc4
	.zeropage	__rc5
	.zeropage	__rc6
	.zeropage	__rc7

	.section	.lisp65_rt_l65e,"ax",@progbits
	.globl	lisp65_error_overlay_entry
	.type	lisp65_error_overlay_entry,@function
lisp65_error_overlay_entry:
	; Preserve and validate the context pointer, tag ("L65E"), ABI contract,
	; and one-based error code before observing the detail or emitting bytes.
	lda	__rc2
	ora	__rc3
	beq	.Lerr_context
	ldz	#0
	lda	(__rc2),z
	cmp	#$4c
	bne	.Lerr_context
	inz
	lda	(__rc2),z
	cmp	#$36
	bne	.Lerr_context
	inz
	lda	(__rc2),z
	cmp	#$35
	bne	.Lerr_context
	inz
	lda	(__rc2),z
	cmp	#$45
	bne	.Lerr_context
	inz
	lda	(__rc2),z
	cmp	#$e1
	bne	.Lerr_abi
	inz
	lda	(__rc2),z
	cmp	#$65
	bne	.Lerr_abi
	inz
	lda	(__rc2),z
	beq	.Lerr_code
	cmp	#64
	bcs	.Lerr_code
	sta	__rc6
	inz
	lda	(__rc2),z
	sta	__rc4
	inz
	lda	(__rc2),z
	sta	__rc5

	; Closed, code-qualified detail union.  NIL is valid except for code 63,
	; which requires exact Fixnum 5. Code 41 owns BCODE $c000..$dffe. Code 28 and the
	; compile-sentinel range 49..59 own SYMI $e000..$fffe.
	ldx	__rc6
	cpx	#63
	beq	.Ldetail_depth
	lda	__rc4
	ora	__rc5
	beq	.Ldetail_valid
.Ldetail_tagged:
	lda	__rc4
	and	#1
	bne	.Lerr_detail
	lda	__rc5
	cmp	#$c0
	bcc	.Lerr_detail
	cpx	#41
	beq	.Ldetail_bcode
	bra	.Ldetail_symbol
.Ldetail_depth:
	lda	__rc4
	cmp	#$0b			; MKFIX(5)
	bne	.Lerr_detail
	lda	__rc5
	bne	.Lerr_detail
	bra	.Ldetail_valid
.Ldetail_bcode:
	cmp	#$e0
	bcs	.Lerr_detail
	bra	.Ldetail_valid
.Ldetail_symbol:
	cmp	#$e0
	bcc	.Lerr_detail
	cpx	#28
	beq	.Ldetail_valid
	cpx	#49
	bcc	.Lerr_detail
	cpx	#60
	bcs	.Lerr_detail

.Ldetail_valid:
	; Descriptor index = 16 + 2*(code-1) = 14 + 2*code.
	lda	__rc6
	asl
	clc
	adc	#14
	tay
	lda	l65e_table,y
	sta	__rc2
	iny
	lda	l65e_table,y
	pha
	lsr
	lsr
	sta	__rc7                 ; six-bit shared-span length
	beq	.Lerr_code_pop
	pla
	and	#3
	sta	__rc3                 ; descriptor offset bits 8..9
	lda	__rc2
	clc
	adc	#mos16lo(l65e_table + 142)
	sta	__rc2
	lda	__rc3
	adc	#mos16hi(l65e_table + 142)
	sta	__rc3

	; Keep the validated detail and code below the loop's transient save set.
	lda	__rc4
	pha
	lda	__rc5
	pha
	lda	__rc6
	pha
.Ltext_more:
	lda	__rc2
	pha
	lda	__rc3
	pha
	lda	__rc7
	pha
	ldz	#0
	lda	(__rc2),z
	jsr	emit
	pla
	sta	__rc7
	pla
	sta	__rc3
	pla
	sta	__rc2
	inw	__rc2
	dec	__rc7
	bne	.Ltext_more

	pla
	sta	__rc6
	pla
	sta	__rc5
	pla
	sta	__rc4
	lda	__rc4
	ora	__rc5
	beq	.Lok
	lda	__rc6
	cmp	#63
	beq	.Lemit_depth
	cmp	#41
	bne	.Lemit_symbol
.Lemit_bcode:
	lda	__rc4
	ldx	__rc5
	jsr	l65e_emit_bcode_ordinal
	bra	.Lok
.Lemit_depth:
	lda	#$20
	jsr	emit
	lda	#$35
	jmp	emit

.Lemit_symbol:
	lda	__rc4
	ldx	__rc5
	jsr	symname
	; symname returns its stable name pointer in __rc2/__rc3.  A/X are
	; incidental on return and must not be copied over that pointer.
.Lsymbol_more:
	ldz	#0
	lda	(__rc2),z
	beq	.Lok
	lda	__rc2
	pha
	lda	__rc3
	pha
	ldz	#0
	lda	(__rc2),z
	jsr	emit
	pla
	sta	__rc3
	pla
	sta	__rc2
	inw	__rc2
	bra	.Lsymbol_more

.Lerr_code_pop:
	pla
.Lerr_code:
	lda	#5
	bra	.Lreturn_status
.Lerr_detail:
	lda	#7
	bra	.Lreturn_status
.Lerr_abi:
	lda	#2
	bra	.Lreturn_status
.Lerr_context:
	lda	#1
	bra	.Lreturn_status
.Lok:
	lda	#0
.Lreturn_status:
	; llvm-mos C code may immediately use STZ as a zero store.  Error paths
	; have advanced Z through the context header, so restore the C-boundary
	; invariant independently of which status is returned in A.
	ldz	#0
	rts
.Llisp65_error_overlay_entry_end:
	.size	lisp65_error_overlay_entry, .Llisp65_error_overlay_entry_end-lisp65_error_overlay_entry

	; Validated BCODE argument in A/X.  Divide the raw tagged object by two;
	; the low twelve bits are the directory ordinal because the base is $6000.
	.globl	l65e_emit_bcode_ordinal
	.type	l65e_emit_bcode_ordinal,@function
l65e_emit_bcode_ordinal:
	ldy	#$23
.Lemit_tagged_ordinal:
	sty	__rc7
	sta	__rc2
	txa
	lsr
	sta	__rc3
	ror	__rc2

	; Stack the digits low-to-high so they are emitted high-to-low after the
	; two literal prefix characters.  Calls may clobber registers, not these
	; deliberately stacked values.
	lda	__rc2
	jsr	.Lhex
	pha
	lda	__rc2
	lsr
	lsr
	lsr
	lsr
	jsr	.Lhex
	pha
	lda	__rc3
	jsr	.Lhex
	pha

	lda	#$20
	jsr	emit
	lda	__rc7
	jsr	emit
	pla
	jsr	emit
	pla
	jsr	emit
	pla
	jmp	emit

.Lhex:
	and	#$0f
	cmp	#$0a
	bcc	.Ldigit
	adc	#$56	; carry from CMP: value + $57 => 'a'..'f'
	rts
.Ldigit:
	ora	#$30
	rts
.Ll65e_emit_bcode_ordinal_end:
	.size	l65e_emit_bcode_ordinal, .Ll65e_emit_bcode_ordinal_end-l65e_emit_bcode_ordinal
