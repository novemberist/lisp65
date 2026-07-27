; C2 product-shaped probe: one target-specialized CRC convergence driver.
;
; ABI:
;   uint8_t rtov_crc_converge_shared_probe(uint16_t expected)
;   expected: A/X, result: A (0 or completion-timeout status 22)
;
; The target and length are the one resident execution window and the already
; published rtov_loaded_len.  The 20-byte entry head remains low-resident; the
; exact 52-byte retry tail is the sole tenant of the terminal $e000 floor
; debit.  The split is semantic: capture/publish the transaction start, then
; retry the immutable payload until it converges or the frame bound expires.

	.zeropage	__rc2
	.zeropage	__rc3
	.zeropage	__rc8
	.zeropage	__rc9
	.zeropage	__rc10
	.zeropage	__rc11
	.zeropage	rtov_loaded_len
	.zeropage	__rc4
	.zeropage	__rc5

	.equ	RTOV_TARGET_LO, $56
	.equ	RTOV_TARGET_HI, $c3
	.equ	C2_FRAME_LO, $ff83
	.equ	C2_FRAME_HI, $ff84
	.equ	COMPLETION_TIMEOUT_FRAMES, 64
	.equ	COMPLETION_TIMEOUT_STATUS, 22

	.section	.text.rtov_crc_converge_shared_probe,"ax",@progbits
	.globl	rtov_crc_converge_shared_probe
	.type	rtov_crc_converge_shared_probe,@function
rtov_crc_converge_shared_probe:
	sta	__rc8
	stx	__rc9
	jsr	rtov_crc_start_sample_fixed
	jmp	rtov_crc_converge_retry_window
.Lhead_end:
	.size	rtov_crc_converge_shared_probe, .Lhead_end-rtov_crc_converge_shared_probe

; The existing post-hot-BSS pocket owns the cold start sample and the serial
; Island phase call.  Together they are 29 bytes under the 33-byte wall.
	.section	.lisp65_c2_crc_retry_fixed,"ax",@progbits
	.type	rtov_crc_start_sample_fixed,@function
rtov_crc_start_sample_fixed:
	php
	sei
	lda	C2_FRAME_LO
	ldx	C2_FRAME_HI
	plp
	sta	__rc10
	stx	__rc11
	rts
.Lsample_end:
	.size	rtov_crc_start_sample_fixed, .Lsample_end-rtov_crc_start_sample_fixed

	.globl	rtov_install_island_finalize
	.type	rtov_install_island_finalize,@function
rtov_install_island_finalize:
	stz	__rc2
	stz	__rc3
	ldx	#<rtov_batch_slot_id
	stx	__rc4
	ldx	#>rtov_batch_slot_id
	stx	__rc5
	lda	#9
	jmp	vm_runtime_overlay_exec
.Lfinalize_end:
	.size	rtov_install_island_finalize, .Lfinalize_end-rtov_install_island_finalize

; The window half may leave $e000 only through the sixteenth facade vector.
; Its 52-byte size is part of the owner-bound floor contract.
	.section	.lisp65_c2_kernal_window.crc_retry,"ax",@progbits
	.globl	rtov_crc_converge_retry_window
	.type	rtov_crc_converge_retry_window,@function
rtov_crc_converge_retry_window:
.Lretry:
	lda	rtov_loaded_len
	sta	__rc2
	lda	rtov_loaded_len+1
	sta	__rc3
	lda	#RTOV_TARGET_LO
	ldx	#RTOV_TARGET_HI
	jsr	c2_facade_rtov_crc_mem
	cmp	__rc8
	bne	.Lmismatch
	cpx	__rc9
	bne	.Lmismatch
	lda	#0
	rts

.Lmismatch:
.Lframe_sample:
	ldy	C2_FRAME_HI
	lda	C2_FRAME_LO
	cpy	C2_FRAME_HI
	bne	.Lframe_sample
	; CPY equality already supplies the carry needed by the subtraction.
	sbc	__rc10
	tax
	tya
	sbc	__rc11
	bne	.Ltimeout
	cpx	#COMPLETION_TIMEOUT_FRAMES
	bcc	.Lretry
.Ltimeout:
	lda	#COMPLETION_TIMEOUT_STATUS
	rts
.Lretry_end:
	.size	rtov_crc_converge_retry_window, .Lretry_end-rtov_crc_converge_retry_window

; Append, do not fork, the one fixed host-facade ABI.
	.section	.lisp65_c2_host_facade,"ax",@progbits
	.globl	c2_facade_rtov_crc_mem
	.type	c2_facade_rtov_crc_mem,@function
c2_facade_rtov_crc_mem:
	jmp	rtov_crc_mem
.Lfacade_end:
	.size	c2_facade_rtov_crc_mem, .Lfacade_end-c2_facade_rtov_crc_mem
