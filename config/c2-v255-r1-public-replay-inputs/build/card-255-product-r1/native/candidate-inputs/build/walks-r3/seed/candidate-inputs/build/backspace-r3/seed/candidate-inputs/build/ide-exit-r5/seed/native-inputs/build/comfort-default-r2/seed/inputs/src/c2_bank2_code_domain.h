/* Half-open execution-code domain. Product composition supplies the first
 * reserved Bank-2 owner's offset; standalone historical profiles retain
 * their whole-bank domain. No CPU pointer represents the 65536 endpoint. */
#ifndef LISP65_C2_BANK2_CODE_DOMAIN_H
#define LISP65_C2_BANK2_CODE_DOMAIN_H
#include <stdint.h>
#if defined(LISP65_C2_LITE_COLD_EVICTION) && !defined(LISP65_C2_BANK2_CODE_LIMIT)
#error "Cold-eviction product requires its explicit Bank-2 owner boundary"
#endif
#ifndef LISP65_C2_BANK2_CODE_LIMIT
#define LISP65_C2_BANK2_CODE_LIMIT 65536UL
#endif
_Static_assert(LISP65_C2_BANK2_CODE_LIMIT > 0UL
               && LISP65_C2_BANK2_CODE_LIMIT <= 65536UL,
               "Bank-2 code limit outside its physical bank");
static inline uint8_t c2_bank2_code_range(uint32_t at, uint32_t bytes) {
    return at <= LISP65_C2_BANK2_CODE_LIMIT
        && bytes <= LISP65_C2_BANK2_CODE_LIMIT - at;
}
#endif
