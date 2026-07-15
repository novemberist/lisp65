/* lisp65 MEGA65 soft-stack reserve gate.
 *
 * The llvm-mos soft stack grows down from __stack ($d000 in the MEGA65
 * profile).  If .bss/heap reaches too high, recursive VM/compiler paths
 * silently overwrite heap[] before the linker notices.  This add-on linker
 * script turns that into a loud build failure for profiles that opt in.
 *
 * Override the cap with:
 *   -Wl,--defsym=__lisp65_bss_cap=0xcd40
 */
__lisp65_bss_cap = DEFINED(__lisp65_bss_cap) ? __lisp65_bss_cap : 0xcd40;

ASSERT(__heap_start <= __lisp65_bss_cap,
       "lisp65 .bss/heap exceeds soft-stack reserve cap");
