/* Pricing fragment: splice after ordinary .bss, before the generic .noinit
 * collector. Not active in the product linker script. Addresses are derived;
 * the three-byte record is the instrument contract, not spare capacity. */
.noinit.lisp65_f011_status (ADDR(.bss) + SIZEOF(.bss)) (NOLOAD) : {
    KEEP(*(.noinit.lisp65_f011_status))
}
ASSERT(SIZEOF(.noinit.lisp65_f011_status) == 3,
       "missing or malformed F011 witness owner");
ASSERT(ADDR(.noinit.lisp65_f011_status) +
       SIZEOF(.noinit.lisp65_f011_status) + 5 <=
       ADDR(.lisp65_c2_input_raw_owner),
       "F011 witness violates raw-input protection floor");
