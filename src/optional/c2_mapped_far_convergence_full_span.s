; C2 mapped Bank-2 content-convergence service.
;
; This is the opt-in successor implementation.  The C bodies remain the host/reference
; authority, while this leaf fixes the target identity independently of LTO.
; It uses caller-clobbered __rc2..__rc15 and preserves every touched
; callee-saved llvm-mos imaginary register (__rc16..__rc31) on the hardware
; stack.  The two public bodies each run underneath one save/restore wrapper,
; so all eight body exits restore the identical ABI state.  The named state
; owners from the Halt-1 contract remain unchanged: there is no compiler
; static stack and no private BSS.  Submission return is never content truth.
;
; llvm-mos ABI, vm-code entry:
;   bank=A, offset=X/__rc2, length=__rc3/__rc4, destination=__rc6/__rc7
; llvm-mos ABI, physical entry:
;   source=A/X/__rc2/__rc3, destination=__rc4/__rc5,
;   length=__rc6/__rc7

	.section .lisp65_c2_mapped_far_service,"ax",@progbits

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
	.zeropage __rc16
	.zeropage __rc17
	.zeropage __rc18
	.zeropage __rc19
	.zeropage __rc20
	.zeropage __rc21
	.zeropage __rc22
	.zeropage __rc23
	.zeropage __rc24
	.zeropage __rc25
	.zeropage __rc26
	.zeropage __rc27
	.zeropage __rc28
	.zeropage __rc29
	.zeropage __rc30
	.zeropage __rc31

	.equ C2_FRAME_LO, 0xff83
	.equ C2_FRAME_HI, 0xff84
	.equ C2_TIMEOUT_FRAMES, 64
	.equ C2_MARKER, 0xa5
	.equ C2_MARKER_CLEAR, 0x5a

; llvm-mos treats __rc16..__rc31 as callee-saved.  Keep the save and restore
; sets visibly symmetric; the linked-image ABI gate proves every byte and
; every public-body exit rather than trusting these macros as source claims.
	.macro c2_far_save_callee
	lda __rc16
	pha
	lda __rc17
	pha
	lda __rc18
	pha
	lda __rc19
	pha
	lda __rc20
	pha
	lda __rc21
	pha
	lda __rc22
	pha
	lda __rc23
	pha
	lda __rc24
	pha
	lda __rc25
	pha
	lda __rc26
	pha
	lda __rc27
	pha
	lda __rc28
	pha
	lda __rc29
	pha
	lda __rc30
	pha
	lda __rc31
	pha
	.endm

	.macro c2_far_restore_callee
	pla
	sta __rc31
	pla
	sta __rc30
	pla
	sta __rc29
	pla
	sta __rc28
	pla
	sta __rc27
	pla
	sta __rc26
	pla
	sta __rc25
	pla
	sta __rc24
	pla
	sta __rc23
	pla
	sta __rc22
	pla
	sta __rc21
	pla
	sta __rc20
	pla
	sta __rc19
	pla
	sta __rc18
	pla
	sta __rc17
	pla
	sta __rc16
	.endm

; Shared clock leaf.  Return low in A, high in X, sampled atomically.
.Lc2_far_frame:
	lda C2_FRAME_HI
	sta __rc31
	lda C2_FRAME_LO
	tay
	lda C2_FRAME_HI
	cmp __rc31
	bne .Lc2_far_frame
	tya
	ldx __rc31
	rts

.Lc2_far_mark_start:
	jsr .Lc2_far_frame
	sta __rc4
	stx __rc5
	rts

; Return A=1 once unsigned (now-start) >= 64, otherwise A=0.  The
; post-primary rescan invokes source probes, whose individual timeout owns
; r2:r3 and r28:r29.  Its fall-through entry restores the whole-transfer start
; retained in caller-clobbered r4:r5 after argument capture, before applying
; the same deadline calculation.
.Lc2_far_primary_timed_out:
	lda __rc4
	sta __rc28
	lda __rc5
	sta __rc29
.Lc2_far_timed_out:
	jsr .Lc2_far_frame
	sec
	sbc __rc28
	tay
	txa
	sbc __rc29
	bne .Lc2_far_timeout_yes
	cpy #C2_TIMEOUT_FRAMES
	bcs .Lc2_far_timeout_yes
	lda #0
	rts
.Lc2_far_timeout_yes:
	lda #1
	rts

; -------------------------------------------------------------------------
; Ordinary F018B source probe.  VM inputs are retained in:
;   bank r8, offset r9:r10, length r11:r12, destination r13:r14,
;   index r15:r16.  Return expected byte in r27 and A=1, or A=0 on timeout.
.Lc2_d700_source_byte:
	lda #4
	sta c2_dma_verify_list+0
	lda #1
	sta c2_dma_verify_list+1
	lda #0
	sta c2_dma_verify_list+2
	clc
	lda __rc9
	adc __rc15
	sta c2_dma_verify_list+3
	lda __rc10
	adc __rc16
	sta c2_dma_verify_list+4
	lda __rc8
	sta c2_dma_verify_list+5
	lda #mos16lo(c2_dma_verify)
	sta c2_dma_verify_list+6
	lda #mos16hi(c2_dma_verify)
	sta c2_dma_verify_list+7
	lda #0
	sta c2_dma_verify_list+8
	sta c2_dma_verify_list+9
	sta c2_dma_verify_list+10
	sta c2_dma_verify_list+11

	sta c2_dma_verify_list+12
	lda #1
	sta c2_dma_verify_list+13
	lda #0
	sta c2_dma_verify_list+14
	lda #mos16lo(c2_dma_verify_marker)
	sta c2_dma_verify_list+15
	lda #mos16hi(c2_dma_verify_marker)
	sta c2_dma_verify_list+16
	lda #0
	sta c2_dma_verify_list+17
	lda #mos16lo(c2_dma_verify_done)
	sta c2_dma_verify_list+18
	lda #mos16hi(c2_dma_verify_done)
	sta c2_dma_verify_list+19
	lda #0
	sta c2_dma_verify_list+20
	sta c2_dma_verify_list+21
	sta c2_dma_verify_list+22
	sta c2_dma_verify_list+23

	lda #C2_MARKER_CLEAR
	sta c2_dma_verify_done
	jsr .Lc2_far_frame
	sta __rc2
	stx __rc3
	lda #0
	sta 0xd702
	lda #mos16hi(c2_dma_verify_list)
	sta 0xd701
	lda #mos16lo(c2_dma_verify_list)
	sta 0xd700
.Lc2_d700_probe_wait:
	lda c2_dma_verify_done
	cmp #C2_MARKER
	beq .Lc2_d700_probe_ok
	jsr .Lc2_far_timed_out
	beq .Lc2_d700_probe_wait
	lda #0
	rts
.Lc2_d700_probe_ok:
	lda c2_dma_verify
	sta __rc27
	lda #1
	rts

; Submit the primary ordinary DMA exactly once and wait for the retained
; first-difference byte.  The full comparison remains in the class gates.
.Lc2_d700_primary:
	lda #0
	sta c2_dma_list+0
	lda __rc11
	sta c2_dma_list+1
	lda __rc12
	sta c2_dma_list+2
	lda __rc9
	sta c2_dma_list+3
	lda __rc10
	sta c2_dma_list+4
	lda __rc8
	sta c2_dma_list+5
	lda __rc13
	sta c2_dma_list+6
	lda __rc14
	sta c2_dma_list+7
	lda #0
	sta c2_dma_list+8
	sta c2_dma_list+9
	sta c2_dma_list+10
	sta c2_dma_list+11
	jsr .Lc2_far_mark_start
	lda #0
	sta 0xd702
	lda #mos16hi(c2_dma_list)
	sta 0xd701
	lda #mos16lo(c2_dma_list)
	sta 0xd700
.Lc2_d700_primary_wait:
	ldy #0
	lda (__rc20),y
	cmp __rc27
	bne .Lc2_d700_primary_not_yet
	lda #0
	sta __rc15
	sta __rc16
	jmp .Lc2_d700_post_scan
.Lc2_d700_primary_not_yet:
	jsr .Lc2_far_primary_timed_out
	beq .Lc2_d700_primary_wait
	lda #0
	rts

.Lc2_d700_post_scan:
	jsr .Lc2_d700_source_byte
	bne .Lc2_d700_post_source_ok
	jmp .Lc2_d700_failure
.Lc2_d700_post_source_ok:
	clc
	lda __rc13
	adc __rc15
	sta __rc20
	lda __rc14
	adc __rc16
	sta __rc21
	ldy #0
	lda (__rc20),y
	cmp __rc27
	bne .Lc2_d700_post_not_yet
	inc __rc15
	bne .Lc2_d700_post_compare
	inc __rc16
.Lc2_d700_post_compare:
	lda __rc15
	cmp __rc11
	bne .Lc2_d700_post_scan
	lda __rc16
	cmp __rc12
	bne .Lc2_d700_post_scan
	lda #1
	rts
.Lc2_d700_post_not_yet:
	jsr .Lc2_far_primary_timed_out
	beq .Lc2_d700_post_retry
	jmp .Lc2_d700_failure
.Lc2_d700_post_retry:
	lda #0
	sta __rc15
	sta __rc16
	jmp .Lc2_d700_post_scan

	.globl c2_mapped_far_vm_code_load_converged
	.type c2_mapped_far_vm_code_load_converged,@function
c2_mapped_far_vm_code_load_converged:
	sta __rc8
	c2_far_save_callee
	lda __rc8
	jsr .Lc2_d700_body
	tax
	c2_far_restore_callee
	txa
	rts
.Lc2_d700_body:
	sta __rc8
	stx __rc9
	lda __rc2
	sta __rc10
	lda __rc3
	sta __rc11
	lda __rc4
	sta __rc12
	lda __rc6
	sta __rc13
	lda __rc7
	sta __rc14
	ora __rc13
	beq .Lc2_d700_failure
	lda __rc11
	ora __rc12
	beq .Lc2_d700_failure
	lda #0
	sta __rc15
	sta __rc16
.Lc2_d700_scan:
	jsr .Lc2_d700_source_byte
	beq .Lc2_d700_failure
	clc
	lda __rc13
	adc __rc15
	sta __rc20
	lda __rc14
	adc __rc16
	sta __rc21
	ldy #0
	lda (__rc20),y
	cmp __rc27
	bne .Lc2_d700_need_primary
	inc __rc15
	bne .Lc2_d700_scan_compare
	inc __rc16
.Lc2_d700_scan_compare:
	lda __rc15
	cmp __rc11
	bne .Lc2_d700_scan
	lda __rc16
	cmp __rc12
	bne .Lc2_d700_scan
	lda #1
	rts
.Lc2_d700_need_primary:
	jmp .Lc2_d700_primary
.Lc2_d700_failure:
	lda #0
	rts
.Lc2_mapped_far_vm_code_load_converged_end:
	.size c2_mapped_far_vm_code_load_converged, .Lc2_mapped_far_vm_code_load_converged_end-c2_mapped_far_vm_code_load_converged

; -------------------------------------------------------------------------
; Enhanced-DMA source probe.  Physical inputs are retained in:
;   source r8:r9:r10:r11, destination r12:r13, length r14:r15,
;   index r16:r17.  r23..r26 hold source+index.
.Lc2_d705_address:
	clc
	lda __rc8
	adc __rc16
	sta __rc23
	lda __rc9
	adc __rc17
	sta __rc24
	lda __rc10
	adc #0
	sta __rc25
	lda __rc11
	adc #0
	sta __rc26
	rts

; Write one 20-byte Enhanced-DMA job at the pointer in r20:r21.
; Source is r23..r26, target is r18:r19, command is r22, length r30:r31.
.Lc2_d705_build_job:
	ldy #0
	lda #0x0b
	sta (__rc20),y
	iny
	lda #0x80
	sta (__rc20),y
	iny
	lda __rc25
	lsr
	lsr
	lsr
	lsr
	sta __rc27
	lda __rc26
	asl
	asl
	asl
	asl
	ora __rc27
	sta (__rc20),y
	iny
	lda #0x81
	sta (__rc20),y
	iny
	lda #0
	sta (__rc20),y
	iny
	lda #0x85
	sta (__rc20),y
	iny
	lda #1
	sta (__rc20),y
	iny
	lda #0
	sta (__rc20),y
	iny
	lda __rc22
	sta (__rc20),y
	iny
	lda __rc30
	sta (__rc20),y
	iny
	lda __rc31
	sta (__rc20),y
	iny
	lda __rc23
	sta (__rc20),y
	iny
	lda __rc24
	sta (__rc20),y
	iny
	lda __rc25
	and #0x0f
	sta (__rc20),y
	iny
	lda __rc18
	sta (__rc20),y
	iny
	lda __rc19
	sta (__rc20),y
	iny
	lda #0
	sta (__rc20),y
	iny
	sta (__rc20),y
	iny
	sta (__rc20),y
	iny
	sta (__rc20),y
	rts

.Lc2_d705_trigger_probe:
	lda #1
	sta 0xd703
	lda #0
	sta 0xd702
	sta 0xd704
	lda #mos16hi(c2_edma_probe_jobs)
	sta 0xd701
	lda #mos16lo(c2_edma_probe_jobs)
	sta 0xd705
	rts

.Lc2_d705_source_byte:
	jsr .Lc2_d705_address
	lda #mos16lo(c2_edma_probe_jobs)
	sta __rc20
	lda #mos16hi(c2_edma_probe_jobs)
	sta __rc21
	lda #mos16lo(c2_edma_probe_value)
	sta __rc18
	lda #mos16hi(c2_edma_probe_value)
	sta __rc19
	lda #4
	sta __rc22
	lda #1
	sta __rc30
	lda #0
	sta __rc31
	jsr .Lc2_d705_build_job

	lda #mos16lo(c2_edma_probe_jobs+20)
	sta __rc20
	lda #mos16hi(c2_edma_probe_jobs+20)
	sta __rc21
	lda #mos16lo(c2_edma_probe_marker)
	sta __rc23
	lda #mos16hi(c2_edma_probe_marker)
	sta __rc24
	lda #0
	sta __rc25
	sta __rc26
	lda #mos16lo(c2_edma_probe_done)
	sta __rc18
	lda #mos16hi(c2_edma_probe_done)
	sta __rc19
	lda #0
	sta __rc22
	lda #1
	sta __rc30
	lda #0
	sta __rc31
	jsr .Lc2_d705_build_job

	lda #C2_MARKER_CLEAR
	sta c2_edma_probe_done
	jsr .Lc2_far_frame
	sta __rc2
	stx __rc3
	jsr .Lc2_d705_trigger_probe
.Lc2_d705_probe_wait:
	lda c2_edma_probe_done
	cmp #C2_MARKER
	beq .Lc2_d705_probe_ok
	jsr .Lc2_far_timed_out
	beq .Lc2_d705_probe_wait
	lda #0
	rts
.Lc2_d705_probe_ok:
	lda c2_edma_probe_value
	sta __rc27
	lda #1
	rts

.Lc2_d705_primary:
	; r20:r21 is the retained first-difference destination pointer.
	lda __rc20
	pha
	lda __rc21
	pha
	lda __rc27
	pha
	lda #mos16lo(c2_edma_job)
	sta __rc20
	lda #mos16hi(c2_edma_job)
	sta __rc21
	lda __rc8
	sta __rc23
	lda __rc9
	sta __rc24
	lda __rc10
	sta __rc25
	lda __rc11
	sta __rc26
	lda __rc12
	sta __rc18
	lda __rc13
	sta __rc19
	lda #0
	sta __rc22
	lda __rc14
	sta __rc30
	lda __rc15
	sta __rc31
	jsr .Lc2_d705_build_job
	pla
	sta __rc27
	jsr .Lc2_far_mark_start
	lda #1
	sta 0xd703
	lda #0
	sta 0xd702
	sta 0xd704
	lda #mos16hi(c2_edma_job)
	sta 0xd701
	lda #mos16lo(c2_edma_job)
	sta 0xd705
	pla
	sta __rc21
	pla
	sta __rc20
.Lc2_d705_primary_wait:
	ldy #0
	lda (__rc20),y
	cmp __rc27
	bne .Lc2_d705_primary_not_yet
	lda #0
	sta __rc16
	sta __rc17
	jmp .Lc2_d705_post_scan
.Lc2_d705_primary_not_yet:
	jsr .Lc2_far_primary_timed_out
	beq .Lc2_d705_primary_wait
	lda #0
	rts

.Lc2_d705_post_scan:
	jsr .Lc2_d705_source_byte
	bne .Lc2_d705_post_source_ok
	jmp .Lc2_d705_failure
.Lc2_d705_post_source_ok:
	clc
	lda __rc12
	adc __rc16
	sta __rc20
	lda __rc13
	adc __rc17
	sta __rc21
	ldy #0
	lda (__rc20),y
	cmp __rc27
	bne .Lc2_d705_post_not_yet
	inc __rc16
	bne .Lc2_d705_post_compare
	inc __rc17
.Lc2_d705_post_compare:
	lda __rc16
	cmp __rc14
	bne .Lc2_d705_post_scan
	lda __rc17
	cmp __rc15
	bne .Lc2_d705_post_scan
	lda #1
	rts
.Lc2_d705_post_not_yet:
	jsr .Lc2_far_primary_timed_out
	beq .Lc2_d705_post_retry
	jmp .Lc2_d705_failure
.Lc2_d705_post_retry:
	lda #0
	sta __rc16
	sta __rc17
	jmp .Lc2_d705_post_scan

	.globl c2_mapped_far_physical_read_converged
	.type c2_mapped_far_physical_read_converged,@function
c2_mapped_far_physical_read_converged:
	sta __rc8
	c2_far_save_callee
	lda __rc8
	jsr .Lc2_d705_body
	tax
	c2_far_restore_callee
	txa
	rts
.Lc2_d705_body:
	sta __rc8
	stx __rc9
	lda __rc2
	sta __rc10
	lda __rc3
	sta __rc11
	lda __rc4
	sta __rc12
	lda __rc5
	sta __rc13
	ora __rc12
	beq .Lc2_d705_failure
	lda __rc6
	sta __rc14
	lda __rc7
	sta __rc15
	ora __rc14
	beq .Lc2_d705_success
	lda #0
	sta __rc16
	sta __rc17
.Lc2_d705_scan:
	jsr .Lc2_d705_source_byte
	beq .Lc2_d705_failure
	clc
	lda __rc12
	adc __rc16
	sta __rc20
	lda __rc13
	adc __rc17
	sta __rc21
	ldy #0
	lda (__rc20),y
	cmp __rc27
	bne .Lc2_d705_need_primary
	inc __rc16
	bne .Lc2_d705_scan_compare
	inc __rc17
.Lc2_d705_scan_compare:
	lda __rc16
	cmp __rc14
	bne .Lc2_d705_scan
	lda __rc17
	cmp __rc15
	bne .Lc2_d705_scan
	jmp .Lc2_d705_success
.Lc2_d705_need_primary:
	jmp .Lc2_d705_primary
.Lc2_d705_failure:
	lda #0
	rts
.Lc2_d705_success:
	lda #1
	rts
.Lc2_mapped_far_physical_read_converged_end:
	.size c2_mapped_far_physical_read_converged, .Lc2_mapped_far_physical_read_converged_end-c2_mapped_far_physical_read_converged

.Lc2_mapped_far_convergence_end:
