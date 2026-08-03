; lisp65 -- target-stable destructive-DEL leaf for Workbench and Ship Runtime.
;
; scr_putc/write-char and the public scr_backspace API share this one target
; implementation.  The zero-argument leaf remains outside LLVM bitcode, so
; WPLTO cannot repartition its implementation into compiler-owned static stack.

	.zeropage	__rc2
	.zeropage	__rc3

	.section	.text.scr_backspace,"ax",@progbits
	.globl	scr_backspace
	.type	scr_backspace,@function
scr_backspace:
	lda	lisp65_screen_cursor_on
	beq	.Lmove
	jsr	.Lcell
	ldy	#0
	lda	(__rc2),y
	and	#$7f
	sta	(__rc2),y
	lda	#0
	sta	lisp65_screen_cursor_on

.Lmove:
	lda	lisp65_screen_col
	beq	.Lprevious_row
	dec	lisp65_screen_col
	bra	.Lclear
.Lprevious_row:
	lda	lisp65_screen_row
	beq	.Lclear
	dec	lisp65_screen_row
	lda	lisp65_screen_cols
	dec
	sta	lisp65_screen_col

.Lclear:
	jsr	.Lcell
	ldy	#0
	lda	#$20
	sta	(__rc2),y
	ldz	#0
	rts

; Materialize the current screen-cell pointer in __rc2/__rc3.
.Lcell:
	lda	lisp65_screen_base
	sta	__rc2
	lda	lisp65_screen_base+1
	sta	__rc3
	ldy	lisp65_screen_row
	beq	.Lcolumn
.Lrow:
	clc
	lda	__rc2
	adc	lisp65_screen_cols
	sta	__rc2
	lda	__rc3
	adc	#0
	sta	__rc3
	dey
	bne	.Lrow
.Lcolumn:
	clc
	lda	__rc2
	adc	lisp65_screen_col
	sta	__rc2
	lda	__rc3
	adc	#0
	sta	__rc3
	rts
.Lscr_backspace_end:
	.size	scr_backspace, .Lscr_backspace_end-scr_backspace
