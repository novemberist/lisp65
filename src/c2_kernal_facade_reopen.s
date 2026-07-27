; One-time Link-33 E000 reopening extension.  Append to the one facade output
; instead of creating a second fixed-LMA island: one facade is one ABI.

	.section .lisp65_c2_host_facade,"ax",@progbits

	.globl c2_facade_runtime_overlay_exec
c2_facade_runtime_overlay_exec:
	jmp vm_runtime_overlay_exec

	; Link-33 BSS-triage contract extension.  The owned window may reach the
	; fixed Island handle normalizer only through this fifteenth public vector.
	.globl c2_facade_handle_normalize
c2_facade_handle_normalize:
	jmp c2_product_handle_normalize

#ifdef LISP65_C2_APPEND_PLAN_FACADE
	; C2-lite append-plan contract extension.  The owned window reaches the
	; fixed resident-Island walker only through this sixteenth public vector.
	.globl c2_facade_append_plan_walk
c2_facade_append_plan_walk:
	jmp c2_append_plan_walk
#endif
