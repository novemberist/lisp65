; C2 design-only lower-bound probe for the runtime CRC retry path.
;
; This file is deliberately not part of the product source list.  It gives
; llvm-mos the narrowest contract-complete shape that the approved completion
; contract permits:
;
;   * sample the owned 16-bit frame counter before the first CRC;
;   * on an initial mismatch, retain the expected CRC and start frame;
;   * retry the existing target-stable rtov_crc_mem leaf over the fixed
;     runtime-overlay window and rtov_loaded_len;
;   * accept a match at frame 64, otherwise return the specific timeout.
;
; The probe has no generic consumer context and no Boot branches.  Its section
; sizes are therefore a hard non-LTO floor for the resident runtime mechanism,
; not a proposed product implementation.

	.zeropage	__rc2
	.zeropage	__rc3
	.zeropage	__rc8
	.zeropage	__rc9
	.zeropage	__rc10
	.zeropage	__rc11
	.zeropage	rtov_loaded_len

	.equ	RTOV_TARGET_LO, $56
	.equ	RTOV_TARGET_HI, $c3
	.equ	C2_FRAME_LO, $ff83
	.equ	C2_FRAME_HI, $ff84
	.equ	COMPLETION_TIMEOUT_FRAMES, 64
	.equ	COMPLETION_TIMEOUT_STATUS, 22

; uint16_t rtov_crc_retry_start_probe(void)
; Return a tear-free product frame sample in A/X (low/high).  This must run
; before the first CRC; starting the clock only after a miss would weaken the
; approved 64-frame boundary.
	.section	.text.rtov_crc_retry_start_probe,"ax",@progbits
	.globl	rtov_crc_retry_start_probe
.type	rtov_crc_retry_start_probe,@function
rtov_crc_retry_start_probe:
.Lstart_sample:
	ldx	C2_FRAME_HI
	lda	C2_FRAME_LO
	cpx	C2_FRAME_HI
	bne	.Lstart_sample
	rts
.Lstart_end:
	.size	rtov_crc_retry_start_probe, .Lstart_end-rtov_crc_retry_start_probe

; uint8_t rtov_crc_retry_after_miss_probe(uint16_t expected,
;                                         uint16_t start_frame)
; expected is in A/X, start_frame in __rc2/__rc3.  The result is the public
; overlay status: zero on convergence, 22 on the exact timeout boundary.
	.section	.text.rtov_crc_retry_after_miss_probe,"ax",@progbits
	.globl	rtov_crc_retry_after_miss_probe
	.type	rtov_crc_retry_after_miss_probe,@function
rtov_crc_retry_after_miss_probe:
	sta	__rc8
	stx	__rc9
	lda	__rc2
	sta	__rc10
	lda	__rc3
	sta	__rc11

.Lretry:
	lda	rtov_loaded_len
	sta	__rc2
	lda	rtov_loaded_len+1
	sta	__rc3
	lda	#RTOV_TARGET_LO
	ldx	#RTOV_TARGET_HI
	jsr	rtov_crc_mem
	cmp	__rc8
	bne	.Lmismatch
	cpx	__rc9
	bne	.Lmismatch
	lda	#0
	rts

.Lmismatch:
	; Resample before the subtraction; the local loop keeps the dataflow
	; explicit for objdump gates.
.Lmismatch_sample:
	ldy	C2_FRAME_HI
	lda	C2_FRAME_LO
	cpy	C2_FRAME_HI
	bne	.Lmismatch_sample
	sec
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
	.size	rtov_crc_retry_after_miss_probe, .Lretry_end-rtov_crc_retry_after_miss_probe
