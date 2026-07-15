/* lisp65 -- ABI contract for the optional MEGA65 hardware-math overrides.
 *
 * These are llvm-mos compiler-runtime entry points, not an application API.
 * The declarations live here so the isolated link/ABI gate can exercise the
 * exact symbols.  Product code should continue to use normal C arithmetic.
 * llvm-mos discovers backend libcalls after its initial archive scan.  The
 * link therefore binds these ABI names explicitly to the lisp65_hw_* symbols
 * with --defsym.  This is a strict alias contract, not a multiple-definition
 * escape hatch; the gate proves that the libcrt div/mul bodies stay unlinked.
 */
#ifndef LISP65_MEGA65_MATH_H
#define LISP65_MEGA65_MATH_H

#include <stdint.h>

uint16_t __udivhi3(uint16_t dividend, uint16_t divisor);
uint16_t __umodhi3(uint16_t dividend, uint16_t divisor);
uint16_t __udivmodhi4(uint16_t dividend, uint16_t divisor,
                      uint16_t *remainder);
uint16_t __mulhi3(uint16_t lhs, uint16_t rhs);
uint16_t lisp65_mod_adjust_tagged(uint16_t remainder, uint16_t divisor);

#endif /* LISP65_MEGA65_MATH_H */
