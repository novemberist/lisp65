; Publish-last runtime-family verifier bindings.
;
; This table is assembled outside whole-program LTO.  The product link sees a
; fixed 32-byte layout containing four eight-byte tuples; the packer replaces
; only these sentinel words after it has derived the boot and session records
; from that same link.  Order is part of the binary contract.

	.section .lisp65_runtime_overlay_verifier_bindings,"a",@progbits
	.globl __lisp65_rtov_verifier_bindings_start
__lisp65_rtov_verifier_bindings_start:

	.globl rtov_boot_verifiers
rtov_boot_verifiers:
	.word $a100, $a101, $a102, $a103
	.word $a110, $a111, $a112, $a113

	.globl rtov_verifiers
rtov_verifiers:
	.word $b100, $b101, $b102, $b103
	.word $b110, $b111, $b112, $b113

	.globl __lisp65_rtov_verifier_bindings_end
__lisp65_rtov_verifier_bindings_end:

#ifdef LISP65_C2_LITE_BANK3_STAGING
	; Manifest-derived size/whole-image-CRC tuples.  They extend the
	; publish-last domain without changing any verifier tuple address.
	.globl __lisp65_rtov_family_stage_bindings_start
__lisp65_rtov_family_stage_bindings_start:
	.globl rtov_family_stage_bindings
rtov_family_stage_bindings:
	.word $c100, $c101
	.word $c110, $c111
	.globl __lisp65_rtov_family_stage_bindings_end
__lisp65_rtov_family_stage_bindings_end:
#endif
