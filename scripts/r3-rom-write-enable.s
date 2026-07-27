	.section .r3_rom_write_enable,"ax",@progbits
	.globl r3_rom_write_enable
	.type r3_rom_write_enable,@function
r3_rom_write_enable:
	; Bank 2 and Bank 3 are ROM backing banks.  The idempotent HYPPO memory
	; trap removes their write protection before the cold stager submits any
	; normal-F018B write job.  The byte after the trap store is mandatory.
	lda #$02
	sta $d641
	nop
	ldz #$00
	rts
.Lr3_rom_write_enable_end:
	.size r3_rom_write_enable,.Lr3_rom_write_enable_end-r3_rom_write_enable
