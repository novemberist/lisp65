/* Direct calls used only to pin llvm-mos' public compiler-runtime ABI. */
#include <stdint.h>
#include "mega65_math.h"

volatile uint16_t math_caller_a;
volatile uint16_t math_caller_b;
volatile uint16_t math_caller_r;
volatile uint16_t math_caller_out;

void math_abi_exercise(void) {
    math_caller_out = __udivhi3(math_caller_a, math_caller_b);
    math_caller_out ^= __umodhi3(math_caller_a, math_caller_b);
    math_caller_out ^= __mulhi3(math_caller_a, math_caller_b);
    math_caller_out ^= lisp65_mod_adjust_tagged(math_caller_a, math_caller_b);
    math_caller_out ^= __udivmodhi4(math_caller_a, math_caller_b,
                                   (uint16_t *)&math_caller_r);
}

uint16_t math_abi_call_udiv(uint16_t a, uint16_t b) {
    return __udivhi3(a, b);
}

uint16_t math_abi_call_umod(uint16_t a, uint16_t b) {
    return __umodhi3(a, b);
}

uint16_t math_abi_call_mul(uint16_t a, uint16_t b) {
    return __mulhi3(a, b);
}

uint16_t math_abi_call_divmod(uint16_t a, uint16_t b, uint16_t *r) {
    return __udivmodhi4(a, b, r);
}

uint16_t math_abi_call_mod_adjust(uint16_t remainder, uint16_t divisor) {
    return lisp65_mod_adjust_tagged(remainder, divisor);
}
