; Product KERNAL-window IRQ/state owner without v1.6 input capture.

	.include "c2_kernal_window_equates.inc"

	.section .lisp65_c2_kernal_window.irq_handler,"ax",@progbits
	.globl c2_kernal_irq_handler
	.type c2_kernal_irq_handler,@function
c2_kernal_irq_handler:
	pha
	phx
	phy
	phz
	ldz #0
	lda $d019
	and #$01
	beq .Lsource_less
	sta $d019
	stz C2K_SOURCELESS_IRQS
	inc C2K_FRAME_LO
	bne .Lsample_break
	inc C2K_FRAME_HI
.Lsample_break:
	lda $d613
	bmi .Lbreak_released
	lda C2K_BREAK_HELD
	bne .Lirq_return
	inc C2K_BREAK_HELD
	inc C2K_BREAK_PENDING
	bra .Lirq_return
.Lbreak_released:
	stz C2K_BREAK_HELD
	.globl c2_kernal_irq_return
.Lirq_return:
c2_kernal_irq_return:
	plz
	ply
	plx
	pla
	rti
.Lsource_less:
	lda $d019
	and #$1f
	sta C2K_UNOWNED_VIC
	lda C2K_SOURCELESS_IRQS
	beq .Lfirst_source_less
	jmp retired_window_brk_classifier
.Lfirst_source_less:
	inc C2K_SOURCELESS_IRQS
	bra .Lirq_return

	.section .lisp65_c2_kernal_window.state,"a",@progbits
	.space 16, 0
