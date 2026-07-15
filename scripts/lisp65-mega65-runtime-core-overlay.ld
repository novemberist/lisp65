/* Runtime Core boot-code overlay prototype.
 *
 * This add-on is intentionally profile-specific.  It catches functions marked
 * with LISP65_STDLIB_BOOT_OVERLAY_CODE and links them at one fixed Bank-0
 * address.  The build extracts this section as a raw payload and truncates the
 * resident PRG before it, so both artifacts must come from the same ELF.
 *
 * Lifetime contract: load before SYS, execute during shallow boot only, then
 * reclaim the range for the downward-growing soft stack.  No resident path may
 * call an overlay symbol after vm_load_embedded_stdlib() returns.
 */
__lisp65_runtime_core_overlay_vma = 0xb800;
__lisp65_runtime_core_overlay_lma = 0xb800;

SECTIONS {
    .lisp65_runtime_core_overlay __lisp65_runtime_core_overlay_vma :
        AT(__lisp65_runtime_core_overlay_lma) {
        __lisp65_runtime_core_overlay_start = .;
        KEEP(*(.lisp65_boot .lisp65_boot.*))
        __lisp65_runtime_core_overlay_end = .;
    } >ram
} INSERT AFTER .noinit;

/* The regular MEGA65 PRG payload ends after the initialised .data image. */
__lisp65_runtime_core_resident_file_end = __data_load_start + __data_size;
__lisp65_runtime_core_overlay_entry = vm_load_embedded_stdlib;

ASSERT(__lisp65_runtime_core_overlay_start == __lisp65_runtime_core_overlay_vma,
       "runtime-core overlay VMA drifted");
ASSERT(LOADADDR(.lisp65_runtime_core_overlay) == __lisp65_runtime_core_overlay_lma,
       "runtime-core overlay LMA drifted");
ASSERT(__lisp65_runtime_core_overlay_entry >= __lisp65_runtime_core_overlay_start &&
       __lisp65_runtime_core_overlay_entry < __lisp65_runtime_core_overlay_end,
       "runtime-core overlay entry lies outside the raw payload");
ASSERT(__lisp65_runtime_core_resident_file_end <= __bss_start,
       "runtime-core resident file end moved beyond .bss");
ASSERT(__bss_end < __lisp65_runtime_core_overlay_start,
       "runtime-core overlay overlaps resident .bss/heap floor");
ASSERT(__lisp65_runtime_core_overlay_end <= (__stack - 0x0200),
       "runtime-core overlay leaves less than 512 bytes for boot stack");
ASSERT(SIZEOF(.lisp65_runtime_core_overlay) > 0,
       "runtime-core overlay is empty (missing BOOTFN sections)");
