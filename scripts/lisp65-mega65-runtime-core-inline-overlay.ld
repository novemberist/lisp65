/* Runtime Core inline boot-overlay prototype.
 *
 * Unlike the fixed-$b800 split-package experiment, this layout keeps the
 * boot-only code in the flat PRG.  The payload is placed immediately after
 * .noinit (with the two-byte alignment guard required by the current MEGA65
 * layout), so etherload/reset loads it together with the resident image.
 * After vm_load_embedded_stdlib() returns, the range is owned by the
 * downward-growing soft stack.
 */
__lisp65_runtime_core_inline_noinit_start = ADDR(.noinit);
__lisp65_runtime_core_inline_noinit_end = ADDR(.noinit) + SIZEOF(.noinit);
__lisp65_runtime_core_inline_overlay_address =
    ALIGN(__lisp65_runtime_core_inline_noinit_end + 1, 2);

__lisp65_runtime_core_inline_required_boot_stack =
    DEFINED(__lisp65_runtime_core_inline_required_boot_stack_param)
        ? __lisp65_runtime_core_inline_required_boot_stack_param : 0x0200;
__lisp65_runtime_core_inline_required_runtime_stack =
    DEFINED(__lisp65_runtime_core_inline_required_runtime_stack_param)
        ? __lisp65_runtime_core_inline_required_runtime_stack_param : 0x2000;
__lisp65_runtime_core_inline_required_post_boot_reserve =
    DEFINED(__lisp65_runtime_core_inline_required_post_boot_reserve_param)
        ? __lisp65_runtime_core_inline_required_post_boot_reserve_param : 0x2000;
__lisp65_runtime_core_inline_max_file_end =
    DEFINED(__lisp65_runtime_core_inline_max_file_end_param)
        ? __lisp65_runtime_core_inline_max_file_end_param : 0xb000;

SECTIONS {
    .lisp65_boot_overlay __lisp65_runtime_core_inline_overlay_address :
        AT(__lisp65_runtime_core_inline_overlay_address) {
        __lisp65_boot_overlay_start = .;
        __lisp65_runtime_core_inline_overlay_start = .;
        KEEP(*(.lisp65_boot .lisp65_boot.*))
        __lisp65_runtime_core_inline_overlay_end = .;
        __lisp65_boot_overlay_end = .;
    } >ram
} INSERT AFTER .noinit;

__lisp65_noinit_start = __lisp65_runtime_core_inline_noinit_start;
__lisp65_noinit_end = __lisp65_runtime_core_inline_noinit_end;
__lisp65_runtime_core_inline_overlay_entry = vm_load_embedded_stdlib;
__lisp65_runtime_core_inline_file_end =
    LOADADDR(.lisp65_boot_overlay) + SIZEOF(.lisp65_boot_overlay);

ASSERT(__lisp65_runtime_core_inline_overlay_start ==
           __lisp65_runtime_core_inline_overlay_address,
       "runtime-core inline overlay placement drifted");
ASSERT(LOADADDR(.lisp65_boot_overlay) ==
           __lisp65_runtime_core_inline_overlay_start,
       "runtime-core inline overlay is not part of the flat PRG");
ASSERT(__lisp65_runtime_core_inline_noinit_end <
           __lisp65_runtime_core_inline_overlay_start,
       "runtime-core inline overlay overlaps .noinit");
ASSERT(__heap_start <= __lisp65_runtime_core_inline_overlay_start,
       "runtime-core inline overlay moved below the heap floor");
ASSERT(__lisp65_runtime_core_inline_overlay_entry >=
           __lisp65_runtime_core_inline_overlay_start &&
       __lisp65_runtime_core_inline_overlay_entry <
           __lisp65_runtime_core_inline_overlay_end,
       "runtime-core inline overlay entry lies outside the payload");
ASSERT(__lisp65_runtime_core_inline_overlay_end <=
           (__stack - __lisp65_runtime_core_inline_required_boot_stack),
       "runtime-core inline overlay leaves too little boot stack");
ASSERT((__stack - __heap_start) >=
           (__lisp65_runtime_core_inline_required_runtime_stack +
            __lisp65_runtime_core_inline_required_post_boot_reserve),
       "runtime-core inline overlay leaves too little post-boot reserve");
ASSERT(__lisp65_runtime_core_inline_file_end <
           __lisp65_runtime_core_inline_max_file_end,
       "runtime-core inline PRG exceeds the file-end ceiling");
ASSERT(SIZEOF(.lisp65_boot_overlay) > 0,
       "runtime-core inline overlay is empty");
