/* lisp65 MEGA65 MVP overlay add-on.
 *
 * This script is passed in addition to llvm-mos' default MEGA65 link.ld. It
 * catches generated boot-only stdlib data in .lisp65_boot and places it
 * strictly after llvm-mos' .noinit section. The explicit address matters:
 * lld's INSERT AFTER changes section order, but does not by itself advance the
 * VMA past a zero-sized .noinit section. During boot the soft stack is still
 * shallow; after vm_load_embedded_stdlib() has patched/registered the bytecode,
 * this area is dead and belongs to the downward-growing soft stack.
 */
__lisp65_noinit_start = ADDR(.noinit);
__lisp65_noinit_end = ADDR(.noinit) + SIZEOF(.noinit);
__lisp65_boot_overlay_min_start = ALIGN(__lisp65_noinit_end + 1, 2);

SECTIONS {
    .lisp65_boot_overlay __lisp65_boot_overlay_min_start : {
        __lisp65_boot_overlay_start = .;
        KEEP(*(.lisp65_boot .lisp65_boot.*))
        __lisp65_boot_overlay_end = .;
    } >ram
} INSERT AFTER .noinit;

ASSERT(__heap_start <= __lisp65_boot_overlay_start,
       "lisp65 boot overlay moved before __heap_start");
ASSERT(__lisp65_noinit_end < __lisp65_boot_overlay_start,
       "lisp65 boot overlay overlaps .noinit");
ASSERT(__lisp65_boot_overlay_end <= (__stack - 0x0200),
       "lisp65 boot overlay leaves less than 512 bytes for boot stack");
