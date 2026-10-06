; Stable Bank-0 ABI for code executing in the owned $e000 window.  Every
; entry is exactly one tail jump: the target may move, the public address may
; not.  JSR facade / JMP target / RTS returns directly to the window caller.

	.section .lisp65_c2_host_facade,"ax",@progbits

	.globl c2_facade_vm_code_load
c2_facade_vm_code_load:
	jmp vm_code_load

	.globl c2_facade_c2_dma
c2_facade_c2_dma:
	jmp c2_facade_target_c2_dma

	.globl c2_facade_overlay_call_family
c2_facade_overlay_call_family:
	jmp c2_facade_target_overlay_call_family

	.globl c2_facade_c2e_cons
c2_facade_c2e_cons:
	jmp c2_facade_target_c2e_cons

	.globl c2_facade_c2e_overlay
c2_facade_c2e_overlay:
	jmp c2_facade_target_c2e_overlay

	.globl c2_facade_car
c2_facade_car:
	jmp car

	.globl c2_facade_cdr
c2_facade_cdr:
	jmp cdr

	.globl c2_facade_gc_collect
c2_facade_gc_collect:
	jmp gc_collect

	.globl c2_facade_str_open
c2_facade_str_open:
	jmp str_open

	.globl c2_facade_str_putc
c2_facade_str_putc:
	jmp str_putc

	.globl c2_facade_intern
c2_facade_intern:
	jmp intern

	.globl c2_facade_select_family
c2_facade_select_family:
	jmp vm_runtime_overlay_select_family

	; Link-27 contract extension.  Append, do not renumber: the original
	; twelve vectors retain their addresses and the C2-owned root walker gets
	; one explicit return edge into the moving Bank-0 collector.
	.globl c2_facade_gc_mark
c2_facade_gc_mark:
	jmp gc_mark
