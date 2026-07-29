; Product-owned $e000-$ffff window.  This is linked as an independent product
; artifact and staged in Attic RAM; it is not the receipt-less proof carrier.

	.equ C2K_EVENT_CODE,      $ff80
	.equ C2K_EVENT_MODIFIERS, $ff81
	.equ C2K_EVENT_READY,     $ff82
	.equ C2K_FRAME_LO,        $ff83
	.equ C2K_FRAME_HI,        $ff84
	.equ C2K_NMI_COUNT,       $ff85
	.equ C2K_SOURCELESS_IRQS, $ff86
	.equ C2K_MAP_GENERATION,  $ff87
	.equ C2K_STATE,           $ff88
	.equ C2K_UNOWNED_VIC,     $ff89
	.equ C2K_BREAK_PENDING,   $ff8a
	.equ C2K_BREAK_HELD,      $ff8b

	.section .lisp65_c2_kernal_window.typed_queue_driver,"ax",@progbits
	.zeropage __rc2
	.zeropage __rc3
	.globl c2_kernal_event_poll
	.type c2_kernal_event_poll,@function
c2_kernal_event_poll:
	; llvm-mos ABI: lisp65_key_event * in __rc2/__rc3, boolean in A.
	; A pending physical matrix edge has priority over ordinary queue data and
	; is consumed exactly once at this safe evaluator boundary.
	lda __rc2
	ora __rc3
	beq .Lqueue_empty
	lda C2K_BREAK_PENDING
	beq .Lqueue_next
	stz C2K_BREAK_PENDING
	lda #$03
	ldy #$00
	bra .Lstore_event

.Lqueue_next:
	lda $d60a
	bpl .Lqueue_empty
	and #$7f
	tay
	lda $d619
	; The write advances exactly the queue head sampled above.
	sta $d619
	; Queue $03 is not an abort authority.  Drain it once and continue so the
	; corresponding physical matrix edge cannot be delivered twice.
	cmp #$03
	beq .Lqueue_next
.Lstore_event:
	ldz #$00
	sta (__rc2),z
	inz
	tya
	sta (__rc2),z
	lda #$01
	ldz #$00
	rts
.Lqueue_empty:
	lda #$00
	ldz #$00
	rts
.Lc2_kernal_event_poll_end:
	.size c2_kernal_event_poll, .Lc2_kernal_event_poll_end-c2_kernal_event_poll

	.section .lisp65_c2_kernal_window.irq_handler,"ax",@progbits
	.globl c2_kernal_irq_handler
	.type c2_kernal_irq_handler,@function
c2_kernal_irq_handler:
	pha
	phx
	phy
	phz
	; IRQ entry inherits arbitrary interrupted Z.  On the 45GS02 STZ stores
	; that register, so establish the handler-local zero authority once.
	ldz #0
	lda $d019
	and #$01
	beq .Lsource_less
	; A is already exactly one after the owned-source mask.
	sta $d019
	; Rearm one legitimate source-less return for the next raster-delimited
	; Freezer episode.  This is an episode latch, not a session counter.
	stz C2K_SOURCELESS_IRQS
	inc C2K_FRAME_LO
	bne .Lsample_break
	inc C2K_FRAME_HI
.Lsample_break:
	; D614 was fixed to segment 7 before the owned IRQ was enabled.  Bit 7 is
	; active low. Released rearms; the first held sample latches exactly one
	; pending break and disarms until release.
	lda $d613
	bmi .Lbreak_released
	lda C2K_BREAK_HELD
	bne .Lirq_return
	inc C2K_BREAK_HELD
	inc C2K_BREAK_PENDING
	bra .Lirq_return
.Lbreak_released:
	stz C2K_BREAK_HELD
.Lirq_return:
	plz
	ply
	plx
	pla
	rti
.Lsource_less:
	; A real Freezer return can resume one CPU-latched IRQ after the external
	; source has vanished.  Permit exactly one since the last owned raster;
	; a consecutive source-less entry is an interrupt storm.
	lda $d019
	and #$1f
	sta C2K_UNOWNED_VIC
	lda C2K_SOURCELESS_IRQS
	beq .Lfirst_source_less
	; Cross-section control flow is always an absolute jump.  A long
	; conditional relocation is not an identity-safe facade.
	jmp c2_kernal_fail_closed
.Lfirst_source_less:
	inc C2K_SOURCELESS_IRQS
	bra .Lirq_return

	.section .lisp65_c2_kernal_window.nmi_and_freezer_return,"ax",@progbits
	.globl c2_kernal_nmi_handler
	.type c2_kernal_nmi_handler,@function
c2_kernal_nmi_handler:
	pha
	lda $dd0d
	inc C2K_NMI_COUNT
	pla
	rti

	.section .lisp65_c2_kernal_window.map_switch_and_guards,"ax",@progbits
	.globl c2_kernal_fail_closed
	.type c2_kernal_fail_closed,@function
c2_kernal_fail_closed:
	sei
	lda #$00
	sta $d01a
	lda #$02
	sta $d020
.Lfailed:
	jmp .Lfailed

	.section .lisp65_c2_kernal_window.post_startup_output_seam,"ax",@progbits
	.globl c2_kernal_output_cell
	.type c2_kernal_output_cell,@function
c2_kernal_output_cell:
	sta $0800,x
	rts

	.section .lisp65_c2_kernal_window.state,"a",@progbits
	.space 16, 0

	.section .lisp65_c2_vectors,"a",@progbits
	.word c2_kernal_nmi_handler
	.word c2_kernal_fail_closed
	.word c2_kernal_irq_handler
