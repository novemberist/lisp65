; Standalone Ship Runtime raster-clock owner.
;
; The KERNAL hardware entry has already saved the machine context before it
; dispatches through $0314.  Count and acknowledge only the armed VIC raster
; source, preserve A, and chain to the vector that was active before Ship so
; that its keyboard/GETIN service remains live.  The source belongs to this
; wrapper; acknowledgement must not depend on the inherited handler.

	.section .text.lisp65_ship_timebase_irq,"ax",@progbits
	.globl lisp65_ship_timebase_irq
	.globl lisp65_ship_frame_lo
	.globl lisp65_ship_frame_hi
	.globl lisp65_ship_old_irq
	.type lisp65_ship_timebase_irq,@function
lisp65_ship_timebase_irq:
	pha
	lda $d019
	and #$01
	beq .Lship_irq_chain
	sta $d019
	inc lisp65_ship_frame_lo
	bne .Lship_irq_chain
	inc lisp65_ship_frame_hi
.Lship_irq_chain:
	pla
	jmp (lisp65_ship_old_irq)
.Lship_timebase_irq_end:
	.size lisp65_ship_timebase_irq,.Lship_timebase_irq_end-lisp65_ship_timebase_irq
