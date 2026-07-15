/* Link/ABI fixture for the MEGA65 hardware-math override gate. */
#include <stdint.h>
#include "mega65_math.h"

volatile uint16_t math_abi_a = 0x9234u;
volatile uint16_t math_abi_b = 0x0111u;
volatile int16_t math_abi_sa = -12345;
volatile int16_t math_abi_sb = 37;
volatile uint16_t math_abi_q;
volatile uint16_t math_abi_r;
volatile uint16_t math_abi_m;
volatile int16_t math_abi_sq;
volatile int16_t math_abi_sr;

typedef uint16_t (*math_abi_binop)(uint16_t, uint16_t);
typedef uint16_t (*math_abi_divmod)(uint16_t, uint16_t, uint16_t *);
volatile math_abi_binop math_abi_udiv_fn = __udivhi3;
volatile math_abi_binop math_abi_umod_fn = __umodhi3;
volatile math_abi_binop math_abi_mul_fn = __mulhi3;
volatile math_abi_divmod math_abi_divmod_fn = __udivmodhi4;

int main(void) {
    math_abi_q = math_abi_udiv_fn(math_abi_a, math_abi_b);
    math_abi_r = math_abi_umod_fn(math_abi_a, math_abi_b);
    math_abi_q ^= math_abi_divmod_fn(math_abi_a, math_abi_b,
                                    (uint16_t *)&math_abi_r);
    math_abi_m = math_abi_mul_fn(math_abi_a, math_abi_b);
#ifdef LISP65_MATH_TEST_SIGNED
    math_abi_sq = math_abi_sa / math_abi_sb;
    math_abi_sr = math_abi_sa % math_abi_sb;
#endif
    return (int)(math_abi_q ^ math_abi_r ^ math_abi_m);
}
