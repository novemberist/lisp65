; Private C2D byte-reader leaf for Prim-ID 67.
;
; llvm-mos C ABI:
;   argument 0, obj *args: __rc2/__rc3
;   obj result: A/X
;
; The C caller first consumes the one canonical vm_byte_args(a,n,2) proof.
; This non-LTO leaf owns only address construction, published-C2D bound
; 0..33839, one read through the canonical c2_stream_c2d_read seam, and a
; tagged Fixnum result.  The read destination is args[0], whose CALLPRIM-local
; lifetime ends at return; no resident state or second scratch authority is
; introduced.

	.zeropage	__rc2
	.zeropage	__rc3
	.zeropage	__rc4
	.zeropage	__rc5
	.zeropage	__rc6
	.zeropage	__rc7

	.section	.lisp65_c2_kernal_window.reopen_gap1,"ax",@progbits
	.globl	vm_c2d_byte
	.type	vm_c2d_byte,@function
vm_c2d_byte:
	; vm_byte_args already proved both operands are byte Fixnums.
	ldz	#0
	lda	(__rc2),z
	sta	__rc6
	inz
	lda	(__rc2),z
	lsr
	lda	__rc6
	ror
	sta	__rc6

	; args[1]: same domain -> offset high byte.
	inz
	lda	(__rc2),z
	sta	__rc7
	inz
	lda	(__rc2),z
	lsr
	lda	__rc7
	ror
	tax

	; Published C2D is [0,$8430), narrower than the backing C2D region.
	cpx	#$84
	bcc	.Lread
	bne	.Lnil
	lda	__rc6
	cmp	#$30
	bcs	.Lnil

.Lread:
	; Preserve the CALLPRIM-local destination across the C reader.  llvm-mos
	; passes offset in A/X, destination in __rc2/__rc3, and length in
	; __rc4/__rc5.  The C call may clobber every pseudo-register.
	lda	__rc2
	pha
	lda	__rc3
	pha
	lda	#1
	sta	__rc4
	; 45GS02 STZ stores Z, so establish the zero authority immediately at
	; the store.  The independent LDA/STA form measured two bytes too large
	; for the immutable 54-byte E000 floor in the robust-form First Red.
	ldz	#0
	stz	__rc5
	lda	__rc6
	jsr	c2_stream_c2d_read
	sta	__rc7
	pla
	sta	__rc3
	pla
	sta	__rc2
	lda	__rc7
	beq	.Lnil

	; Tag the byte deposited in args[0] without a second buffer.
	lda	(__rc2),z
	asl
	ldx	#0
	bcc	.Ltagged
	inx
.Ltagged:
	ora	#1
	rts

.Lnil:
	lda	#0
	ldx	#0
	ldz	#0
	rts
.Lvm_c2d_byte_end:
	.size	vm_c2d_byte, .Lvm_c2d_byte_end-vm_c2d_byte
