/* Fixed C2 cross-domain storage.  These attributes are product-cut only:
 * other profiles retain the toolchain's normal whole-program placement. */
#ifndef LISP65_C2_KERNAL_LAYOUT_H
#define LISP65_C2_KERNAL_LAYOUT_H

#if defined(LISP65_C2_PRODUCT_CUT) && defined(LISP65_C2_KERNAL_UNMAP)
#define LISP65_C2_ZP __zp
#define LISP65_C2_FIXED_BANK0(name) \
    __attribute__((used, section(".lisp65_c2_fixed_bank0." name)))
#define LISP65_C2_FIXED_BANK0_CODE(name) \
    __attribute__((used, noinline, section(".lisp65_c2_fixed_bank0_code." name)))
#if defined(LISP65_C2_BSS_TRIAGE)
#define LISP65_C2_FIXED_BANK0_HOT_BSS(name) \
    __attribute__((used, section(".lisp65_c2_fixed_bank0_hot_bss." name)))
#else
#define LISP65_C2_FIXED_BANK0_HOT_BSS(name)
#endif
#define LISP65_C2_FIXED_ZP(name) \
    LISP65_C2_ZP __attribute__((used, section(".lisp65_c2_fixed_zp." name)))
#else
#define LISP65_C2_ZP
#define LISP65_C2_FIXED_BANK0(name)
#define LISP65_C2_FIXED_BANK0_CODE(name)
#define LISP65_C2_FIXED_BANK0_HOT_BSS(name)
#define LISP65_C2_FIXED_ZP(name)
#endif

#endif
