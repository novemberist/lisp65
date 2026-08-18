; Synchronous 28-bit physical reader for the 2.1 library-load transport.
;
; The routine executes from ordinary high memory while CPU block 2
; ($4000-$5fff) is temporarily mapped over the source window.  It therefore
; has no DMA submission and no completion signal.  The private ABI is the
; llvm-mos ABI for
;
;   uint8_t c2_map_cpu_read(uint32_t source, uint8_t *dst, uint16_t length)
;
; source=A/X/__rc2/__rc3, dst=__rc4/__rc5, length=__rc6/__rc7.  The admitted
; product callers use at most 64 bytes and destination storage outside the
; mapped block; the linked-image gate proves both facts.

	.section .text.c2_map_cpu_read,"ax",@progbits
	.globl c2_map_cpu_read
	.type c2_map_cpu_read,@function
	.globl __lisp65_c2_fixed_bank0_runtime

	.zeropage __rc2
	.zeropage __rc3
	.zeropage __rc4
	.zeropage __rc5
	.zeropage __rc6
	.zeropage __rc7
	.zeropage __rc8
	.zeropage __rc9
	.zeropage __rc10
	.zeropage __rc11
	.zeropage __rc12
	.zeropage __rc13
	.zeropage __rc14
	.zeropage __rc15

c2_map_cpu_read:
	sta __rc8                    ; physical source, little endian
	stx __rc9
	lda __rc2
	sta __rc10
	lda __rc3
	sta __rc11
	; The ordinary product owns its LOADING LIBRARIES progress.  c2_runtime is
	; reached through its linker-owned base and phase is byte 42 of that ABI.
	; Render one hexadecimal phase ordinal in the first free cell after the
	; existing line.  Values outside the public 0..a phase range relinquish the
	; screen cell: $29 follows the existing letter path to screen-code $20.
	; Thus the private $fe handoff clears the ordinal when the banner performs
	; its final read after scr_init(), rather than leaving a stray 0 at the REPL.
	; No counter state, diagnostic identity or asynchronous observer survives.
	lda __lisp65_c2_fixed_bank0_runtime+42
	cmp #$0d
	bcc .Lc2_progress_phase_valid
	lda #$29
.Lc2_progress_phase_valid:
	cmp #10
	bcs .Lc2_progress_phase_letter
	adc #$30                    ; C is clear: screen codes '0'..'9'
	bra .Lc2_progress_phase_store
.Lc2_progress_phase_letter:
	sbc #9                      ; C is set: 10 becomes screen code 1 ('A')
.Lc2_progress_phase_store:
	sta $0b3a                   ; row 10, column 26
	lda __rc7
	bne .Lc2_cpu_fail
	lda __rc6                    ; admitted length is one byte
	beq .Lc2_cpu_ok

	php
	sei
	; Disable the low mapping before changing its megabyte selector.
	lda #0
	tax
	ldz #$80
	map
	eom
	; MB = physical[27:20] = (source[3] << 4) | source[2] >> 4.
	lda __rc10
	lsr
	lsr
	lsr
	lsr
	sta __rc14
	lda __rc11
	asl
	asl
	asl
	asl
	ora __rc14
	ldx #$0f
	ldy #0
	map
	eom

	; Bind the initial physical window to the CPU pointer and retain the MAP
	; tuple itself.  Later 8-KiB crossings advance that tuple directly; the
	; copy loop therefore never needs an asynchronous transport cursor.
	lda __rc8
	sta __rc12
	lda __rc9
	and #$1f
	ora #$40
	sta __rc13
	lda __rc9
	and #$e0
	sec
	sbc #$40
	sta __rc15
	lda __rc10
	sbc #0
	; The subtract can borrow from the low byte.  Mask *after* applying that
	; borrow so it cannot escape into X's high MAP-mask nibble ($FFC0 was the
	; hardware witness); then select CPU block 2 and no other low block.
	and #$0f
	ora #$40
	sta __rc14
	jsr .Lc2_cpu_map_window
.Lc2_cpu_copy:
	; The mapper returns Y=0 and the copy loop never changes Y.  Keeping that
	; invariant saves the redundant two-byte LDY on every iteration without
	; weakening any length, mapping, or restore check.
	lda (__rc12),y
	sta (__rc4),y
	inc __rc12
	bne .Lc2_cpu_pointer_advanced
	inc __rc13
.Lc2_cpu_pointer_advanced:
	inc __rc4
	bne .Lc2_cpu_destination_advanced
	inc __rc5
.Lc2_cpu_destination_advanced:
	dec __rc6
	beq .Lc2_cpu_restore
	lda __rc13
	cmp #$60                     ; crossed the mapped 8-KiB window
	bne .Lc2_cpu_copy
	lda #$40
	sta __rc13
	lda __rc15
	; The equal CMP #$60 immediately above leaves C set.  Adding $1f with
	; that proven carry advances the physical offset by $20 without spending
	; a separate CLC byte.
	adc #$1f
	sta __rc15
	bcc .Lc2_cpu_next_window
	inc __rc14
	; A $4f->$50 offset wrap sets mask bit 0.  Clear that carry bit while
	; retaining block-2 mask bit 6 and the wrapped offset nibble.
	rmb4 __rc14
.Lc2_cpu_next_window:
	jsr .Lc2_cpu_map_window
	bra .Lc2_cpu_copy

.Lc2_cpu_restore:
	; Restore the product's ordinary MAPL=0 / low-MB=0 view.  Block 7 stays
	; mapped throughout, so the E000 KERNAL window and IRQ owner never move.
	lda #0
	tax
	tay
	ldz #$80
	map
	eom
	ldx #$0f
	map
	eom
	ldz #0
	plp
.Lc2_cpu_ok:
	lda #1
	rts
.Lc2_cpu_fail:
	lda #0
	rts

; Map the retained 8-KiB tuple onto CPU block 2.  The megabyte selector is
; already established for this call.
.Lc2_cpu_map_window:
	lda __rc15
	ldx __rc14
	ldy #0
	ldz #$80
	map
	eom
	ldz #0
	rts
	.size c2_map_cpu_read, .-c2_map_cpu_read

; Preserve the historical runtime-overlay vector while admitting the two
; E000 CPU-reader callers through that fixed crossing.  The identities are
; the hardware-pushed return PCs, expressed as offsets from the two genuine
; function entries.  The linked-image gate derives both offsets from the
; actually emitted JSR/tail bytes; no internal return point is exported as a
; false function entry.  Every other identity takes the historical
; vm_runtime_overlay_exec tail.
	.section .text.c2_map_cpu_selector,"ax",@progbits
	.globl c2_map_cpu_selector
	.type c2_map_cpu_selector,@function
	.globl c2_stream_c2d_read
	.globl c2_stream_shelf_read
	.globl vm_runtime_overlay_exec

c2_map_cpu_selector:
	pha
	phx
	tsx
	lda $0104,x
	; The real WPLTO C2D caller starts at its function entry and reaches the
	; hardware-pushed PC at linked offset $4b.
	cmp #>(c2_stream_c2d_read+$4b)
	bne .Lc2_cpu_selector_shelf
	lda $0103,x
	cmp #<(c2_stream_c2d_read+$4b)
	beq .Lc2_cpu_selector_reader
	bra .Lc2_cpu_selector_runtime
.Lc2_cpu_selector_shelf:
	; The real WPLTO Shelf caller reaches its hardware-pushed PC at linked
	; offset $b0.  Its following two-byte store is part of the emitted-output
	; proof, not an exported ownership node.
	cmp #>(c2_stream_shelf_read+$b0)
	bne .Lc2_cpu_selector_runtime
	lda $0103,x
	cmp #<(c2_stream_shelf_read+$b0)
	beq .Lc2_cpu_selector_reader
.Lc2_cpu_selector_runtime:
	plx
	pla
	jmp vm_runtime_overlay_exec
.Lc2_cpu_selector_reader:
	plx
	pla
	jmp c2_map_cpu_read
	.size c2_map_cpu_selector, .-c2_map_cpu_selector
