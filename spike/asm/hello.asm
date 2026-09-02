; lisp65 phase-0 spike: minimal hand-written C64 PRG built with acme.
; The autostarting PRG prints a banner through KERNAL CHROUT ($FFD2).
; Build: acme hello.asm (creates hello-asm.prg through !to)
; Run:   etherload -4 -r hello-asm.prg (C64 mode on a real MEGA65)

!to "hello-asm.prg", cbm
!cpu 6502

*= $0801
        ; BASIC stub: 10 SYS 2061 ($080D)
        !byte $0c,$08,$0a,$00,$9e,$32,$30,$36,$31,$00,$00,$00

        ; --- Code ab $080D (= 2061) ---
        ldx #0
.loop   lda msg,x
        beq .done
        jsr $ffd2          ; KERNAL CHROUT
        inx
        bne .loop
.done   rts

msg     !pet "lisp65 asm spike ok", $0d, $00
