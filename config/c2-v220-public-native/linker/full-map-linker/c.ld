/* Generated Block-2.6 full-map owner.  Fixed raw-access
 * windows are linker-visible NOLOAD owners; the ordinary and symbol-metadata
 * BSS classes are placed on opposite sides of the input window. */
INCLUDE zp.ld
.text 0x2023 : {
    INCLUDE text-sections.ld
} >c_readonly

.rodata 0xb61d : {
    INCLUDE rodata-sections.ld
} >c_readonly

.lisp65_runtime_overlay_verifier_bindings 0xb98c : {
    __lisp65_rtov_binding_section_start = .;
    KEEP(*(.lisp65_runtime_overlay_verifier_bindings))
    __lisp65_rtov_binding_section_end = .;
} >c_writeable

.data 0xb9b4 : AT(0xb9b4) {
    INCLUDE data-sections.ld
} >c_writeable
INCLUDE data-symbols.ld

.bss 0xb9ca (NOLOAD) : {
    __bss_start = .;
    *(.bss .bss.* BSS COMMON)
} >c_writeable

.noinit.lisp65_f011_status (ADDR(.bss) + SIZEOF(.bss)) (NOLOAD) : {
    KEEP(*(.noinit.lisp65_f011_status))
} >c_writeable
ASSERT(SIZEOF(.noinit.lisp65_f011_status) == 0 ||
       SIZEOF(.noinit.lisp65_f011_status) == 3,
       "malformed F011 status witness owner")
ASSERT(ADDR(.noinit.lisp65_f011_status) +
       SIZEOF(.noinit.lisp65_f011_status) + 5 <=
           ADDR(.lisp65_c2_input_raw_owner),
       "F011 witness breached the raw-input floor")

.lisp65_c2_input_raw_owner 0xbc90 (NOLOAD) : {
    __lisp65_c2_input_raw_owner_start = .;
    . += 0x70;
    __lisp65_c2_input_raw_owner_end = .;
} >c_writeable

.lisp65_c2_symbol_metadata_bss 0xbd00 (NOLOAD) : {
    __lisp65_c2_symbol_metadata_bss_start = .;
    KEEP(*(.lisp65_c2_symbol_metadata_bss))
    __lisp65_c2_symbol_metadata_bss_end = .;
    __bss_end = .;
} >c_writeable
.lisp65_vm_soft_frames_bss (ADDR(.lisp65_c2_symbol_metadata_bss) + SIZEOF(.lisp65_c2_symbol_metadata_bss)) (NOLOAD) : {
    KEEP(*(.lisp65_vm_soft_frames_bss))
    __bss_end = .;
} >c_writeable
ASSERT(SIZEOF(.lisp65_vm_soft_frames_bss) == 146, "R2 frame owner size drift")
ASSERT(ADDR(.lisp65_vm_soft_frames_bss) + SIZEOF(.lisp65_vm_soft_frames_bss) + 5 <= 0xc000, "R2 high BSS floor")
__bss_size = __bss_end - __bss_start;
.noinit.library_symbol_functions 0x2e720 (NOLOAD) : {
    __library_symbol_functions_start = .;
    . += 1590;
    __library_symbol_functions_end = .;
} >library_symbol_functions
__library_bank2_code_limit = __library_symbol_functions_start - 0x20000;
ASSERT(__library_symbol_functions_end == __card2b_carrier_start,
       "Library function cells are not adjacent to their carrier authority")
ASSERT(__library_bank2_code_limit == 59168,
       "Consumed code-limit definition differs from composed owner")
ASSERT(SIZEOF(.noinit.library_symbol_functions) == 795 * 2,
       "Library function-cell population drift")


ASSERT(ADDR(.bss) + SIZEOF(.bss) + 5 <=
           ADDR(.lisp65_c2_input_raw_owner),
       "ordinary low BSS breached the input-owner floor")
ASSERT(ADDR(.lisp65_c2_input_raw_owner) == 0xbc90 &&
       SIZEOF(.lisp65_c2_input_raw_owner) == 112,
       "fixed input raw owner geometry drift")
ASSERT(ADDR(.lisp65_c2_symbol_metadata_bss) == 0xbd00 &&
       SIZEOF(.lisp65_c2_symbol_metadata_bss) == 600,
       "symbol metadata BSS geometry drift")
ASSERT(__lisp65_c2_symbol_metadata_bss_end <= 0xc000,
       "symbol metadata BSS crossed the Bank-0 floor")

/* The sole .noinit-namespace resident is extracted by the named static-stack
 * owner before this empty ordinary owner. */
.noinit 0xc34d (NOLOAD) : {
    INCLUDE noinit-sections.ld
} >c_writeable
__lisp65_c2_ordinary_noinit_end = ADDR(.noinit) + SIZEOF(.noinit);
__heap_start = 0xc354;

ASSERT(LOADADDR(.zp.data) + SIZEOF(.zp.data) <= ADDR(.text), "initialized ZP load image overlaps text")
