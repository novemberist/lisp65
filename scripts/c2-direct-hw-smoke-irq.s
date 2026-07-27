; Test-owned CIA1 IRQ shim for the receipt-less C2.1 device pre-smoke.
;
; The KERNAL hardware entry has already saved A/X/Y before dispatching through
; $0314.  Count and acknowledge our Timer-A source, then chain to the vector
; that was active before the smoke so the platform owns the matching exit.

	.section .text.c2_hw_irq_handler,"ax",@progbits
	.globl c2_hw_irq_handler
	.globl c2_hw_irq_count
	.globl c2_hw_old_irq
	.type c2_hw_irq_handler,@function
c2_hw_irq_handler:
	inc c2_hw_irq_count
	lda $dc0d
	jmp (c2_hw_old_irq)
.Lc2_hw_irq_handler_end:
	.size c2_hw_irq_handler, .Lc2_hw_irq_handler_end-c2_hw_irq_handler
