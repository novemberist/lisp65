; lisp65 -- target-stable runtime-overlay DMA completion leaf.
;
; The C caller patches the two-job Enhanced-DMA chain.  This non-LTO leaf
; owns the complete publication boundary: reset the one-byte marker, preserve
; interrupt state, submit the chain, wait for the ordered $a5 FILL, then
; restore interrupt state.  The external call boundary is the compiler memory
; barrier; the explicit loop is the hardware completion barrier.

	.section	.text.rtov_dma_submit_wait,"ax",@progbits
	.globl	rtov_dma_submit_wait
	.type	rtov_dma_submit_wait,@function
rtov_dma_submit_wait:
	php
	sei
	lda	#0
	sta	rtov_edma_complete
	lda	#1
	sta	$d703
	lda	#0
	sta	$d702
	sta	$d704
	lda	#mos16hi(rtov_edma_job)
	sta	$d701
	lda	#mos16lo(rtov_edma_job)
	sta	$d705
.Lrtov_dma_wait:
	lda	rtov_edma_complete
	cmp	#$a5
	bne	.Lrtov_dma_wait
	plp
	rts
.Lrtov_dma_submit_wait_end:
	.size	rtov_dma_submit_wait, .Lrtov_dma_submit_wait_end-rtov_dma_submit_wait
