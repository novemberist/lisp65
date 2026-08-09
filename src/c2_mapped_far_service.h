#ifndef LISP65_C2_MAPPED_FAR_SERVICE_H
#define LISP65_C2_MAPPED_FAR_SERVICE_H

/* Link-91 ownership boundary.
 *
 * These attributes name owners only.  They deliberately do not request
 * inlining, outlining or a particular LTO partition: the final linker/ELF
 * gate owns placement and rejects any optimizer result that escapes it. */
#if defined(__mos__) && defined(LISP65_CODE_WINDOW_CONVERGENCE)
#define LISP65_C2_MAPPED_FAR_FN \
    __attribute__((section(".lisp65_c2_mapped_far_service")))
#define LISP65_C2_MAPPED_FACADE_FN \
    __attribute__((section(".lisp65_c2_mapped_far_facade.abort")))
#define LISP65_C2_CONVERGENCE_STATE(name) \
    __attribute__((used, section(".lisp65_c2_convergence_state." name)))
#define LISP65_C2_CONVERGENCE_ZP(name) \
    __attribute__((used, section(".lisp65_c2_convergence_zp." name)))
#else
#define LISP65_C2_MAPPED_FAR_FN
#define LISP65_C2_MAPPED_FACADE_FN
#define LISP65_C2_CONVERGENCE_STATE(name)
#define LISP65_C2_CONVERGENCE_ZP(name)
#endif

#endif
