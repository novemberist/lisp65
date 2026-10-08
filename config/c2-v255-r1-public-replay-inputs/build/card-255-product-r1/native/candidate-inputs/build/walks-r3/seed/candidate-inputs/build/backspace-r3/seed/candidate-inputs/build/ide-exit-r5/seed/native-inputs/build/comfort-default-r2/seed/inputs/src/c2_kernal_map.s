	.section .lisp65_c2_kernal_io_reveal,"ax",@progbits
	.globl c2_kernal_reveal_io
	.type c2_kernal_reveal_io,@function
c2_kernal_reveal_io:
	; Firmware and boot-time code may leave a non-MEGA65 I/O personality
	; selected. $d700 is not DMAgic until the complete knock is repeated.
	lda #$47
	sta $d02f
	lda #$53
	sta $d02f
	rts

	.section .lisp65_c2_kernal_map_switch,"ax",@progbits
	.globl c2_kernal_map_window
	.type c2_kernal_map_window,@function
c2_kernal_map_window:
	; Own only block 7 ($e000-$ffff), mapped to physical bank-0 RAM.  Block 6
	; spans both $c000 RAM and $d000 I/O; selecting it would make MAP precedence
	; hide VIC/CIA/DMA registers behind Bank-0 RAM.  Link-23 hardware diagnosis
	; caught the resulting permanently unacknowledged raster IRQ storm.
	; C2's fixed state at $c080 remains ordinary Bank-0 RAM; the strengthened
	; ownership-order gate prevents its use before this handoff completes.
	; The firmware boundary and its permanent disassembly gate establish
	; Z=$00 before any C or MAP helper runs.  Reuse that normalized zero
	; for A/X/Y, then select block 7 through Z.  This preserves the exact
	; MAP operand tuple (0,0,0,$80) without an unsupported immediate LDQ.
	tza
	tax
	tay
	ldz #$80
	map
	eom
	; llvm-mos reserves Z as the zero index for indirect-Z accesses.
	ldz #$00
	rts
