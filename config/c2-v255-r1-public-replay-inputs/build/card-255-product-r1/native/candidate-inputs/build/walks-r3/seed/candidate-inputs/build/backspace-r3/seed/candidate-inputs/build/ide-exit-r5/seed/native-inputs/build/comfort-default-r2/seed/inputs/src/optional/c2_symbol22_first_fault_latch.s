	.section .lisp65_symbol22_first_fault_state,"aw",@progbits
	.globl lisp65_symbol22_latch_state
	.type lisp65_symbol22_latch_state,@object
lisp65_symbol22_latch_state:
	.byte 0, 0, 0, 0, 0
	.size lisp65_symbol22_latch_state, .-lisp65_symbol22_latch_state

	.section .lisp65_symbol22_first_fault_latch,"ax",@progbits
	.globl lisp65_symbol22_latch_capture
	.globl c2_symbol22_repl_buf
	.type lisp65_symbol22_latch_capture,@function
lisp65_symbol22_latch_capture:
	lda lisp65_symbol22_latch_state
	bne .Llatch_return
	tsx
	lda $0107,x
	sta lisp65_symbol22_latch_state+1
	lda $0108,x
	sta lisp65_symbol22_latch_state+2
	lda $16
	sta lisp65_symbol22_latch_state+3
	lda $17
	sta lisp65_symbol22_latch_state+4
	ldy #0
.Llatch_copy:
	lda ($16),y
	sta c2_symbol22_repl_buf,y
	beq .Llatch_commit
	iny
	cpy #$22
	bne .Llatch_copy
.Llatch_commit:
	lda #$a5
	sta lisp65_symbol22_latch_state
.Llatch_return:
	rts
	.size lisp65_symbol22_latch_capture, .-lisp65_symbol22_latch_capture
