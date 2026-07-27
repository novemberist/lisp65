	.section .lisp65_c2lt_map_switch,"ax",@progbits
	.globl c2lt_map_window
	.type c2lt_map_window,@function
c2lt_map_window:
	; Own only block 7 ($e000-$ffff), exactly like the product handoff.
	lda #$00
	ldx #$00
	ldy #$00
	ldz #$80
	map
	eom
	ldz #$00
	rts
.Lc2lt_map_window_end:
	.size c2lt_map_window,.Lc2lt_map_window_end-c2lt_map_window

	.globl c2lt_window_dispatch_call
	.type c2lt_window_dispatch_call,@function
c2lt_window_dispatch_call:
	jsr $e000
	rts
.Lc2lt_window_dispatch_call_end:
	.size c2lt_window_dispatch_call,.Lc2lt_window_dispatch_call_end-c2lt_window_dispatch_call

	.globl c2lt_rom_write_enable
	.type c2lt_rom_write_enable,@function
c2lt_rom_write_enable:
	; Idempotent memory-trap service: $D641, A=$02.  The official reference
	; requires the byte following the trap store; NOP is intentional here.
	lda #$02
	sta $d641
	nop
	ldz #$00
	rts
.Lc2lt_rom_write_enable_end:
	.size c2lt_rom_write_enable,.Lc2lt_rom_write_enable_end-c2lt_rom_write_enable
