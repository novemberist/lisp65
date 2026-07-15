; Compact product-only scratch transfer for the transaction-bound F011 path.
; llvm-mos ABI: off=A/X, write=__rc2, u8 result=A. ext_disk_get takes its
; u16 scratch index in A/X and may clobber __rc2..__rc8, hence the three-byte
; private state below. f011_read_at returns only $0000 or $0100, so the low
; pointer byte is constructively zero and is not stored. The pointer is rebuilt
; after every call.

	.zeropage	__rc2
	.zeropage	__rc3

	.section	.bss.f011_guard,"aw",@nobits
.Lf011_off_hi:
	.zero	1
.Lf011_mode:
	.zero	1
.Lf011_value:
	.zero	1
.Lf011_mount_token:
	.zero	5
.Lf011_mount_token_valid:
	.zero	1

	.section	.text.lisp65_f011_mount_token_op,"ax",@progbits
	.globl	lisp65_f011_mount_token_op
	.type	lisp65_f011_mount_token_op,@function
; A=1 captures D68B..D68F. A=0 compares. A=2 compares and, on success,
; issues the write trigger before returning. All modes return A=1/0.
lisp65_f011_mount_token_op:
	pha
	cmp	#1
	beq	.Ltoken_capture
	lda	.Lf011_mount_token_valid
	beq	.Ltoken_fail
	ldx	#0
.Ltoken_compare_loop:
	lda	$d68b,x
	cmp	.Lf011_mount_token,x
	bne	.Ltoken_fail
	inx
	cpx	#5
	bne	.Ltoken_compare_loop
	pla
	cmp	#2
	bne	.Ltoken_ok
	lda	#$84
	sta	$d081
.Ltoken_ok:
	lda	#1
	rts
.Ltoken_capture:
	ldx	#0
.Ltoken_capture_loop:
	lda	$d68b,x
	sta	.Lf011_mount_token,x
	inx
	cpx	#5
	bne	.Ltoken_capture_loop
	pla
	lda	#1
	sta	.Lf011_mount_token_valid
	rts
.Ltoken_fail:
	pla
	lda	#0
	rts
.Lf011_mount_token_end:
	.size	lisp65_f011_mount_token_op,.Lf011_mount_token_end-lisp65_f011_mount_token_op

	.section	.text.lisp65_f011_scratch_buffer,"ax",@progbits
	.globl	lisp65_f011_scratch_buffer
	.type	lisp65_f011_scratch_buffer,@function
lisp65_f011_scratch_buffer:
	stx	.Lf011_off_hi
	lda	__rc2
	sta	.Lf011_mode
	ldy	#0
.Lloop:
	phy
	tya
	ldx	#0
	jsr	ext_disk_get
	sta	.Lf011_value
	ply
	stz	__rc2
	lda	.Lf011_off_hi
	clc
	adc	#$de
	sta	__rc3
	lda	.Lf011_value
	ldx	.Lf011_mode
	beq	.Lverify
	sta	(__rc2),y
	bra	.Lnext
.Lverify:
	cmp	(__rc2),y
	bne	.Lfail
.Lnext:
	iny
	bne	.Lloop
	lda	#1
	rts
.Lfail:
	lda	#0
	rts
.Lend:
	.size	lisp65_f011_scratch_buffer,.Lend-lisp65_f011_scratch_buffer
