/* Compare the pinned local signed-wrapper model with llvm-mos libcrt IR. */
#include <stdint.h>
#include <stdio.h>

extern uint16_t __divhi3(uint16_t, uint16_t);
extern uint16_t __modhi3(uint16_t, uint16_t);

static uint16_t abs_bits(uint16_t value) {
    return (value & 0x8000u) ? (uint16_t)(0u - value) : value;
}

static uint16_t local_div(uint16_t lhs, uint16_t rhs) {
    uint16_t q = rhs ? (uint16_t)(abs_bits(lhs) / abs_bits(rhs)) : 0;
    return ((lhs ^ rhs) & 0x8000u) ? (uint16_t)(0u - q) : q;
}

static uint16_t local_mod(uint16_t lhs, uint16_t rhs) {
    uint16_t r = rhs ? (uint16_t)(abs_bits(lhs) % abs_bits(rhs)) : abs_bits(lhs);
    return (lhs & 0x8000u) ? (uint16_t)(0u - r) : r;
}

static uint32_t next_random(uint32_t *state) {
    *state = *state * 1664525u + 1013904223u;
    return *state;
}

int main(void) {
    static const uint16_t edges[] = {
        0, 1, 2, 3, 0x7f, 0x80, 0xff, 0x100,
        0x7fff, 0x8000, 0x8001, 0xfffe, 0xffff
    };
    uint16_t (*volatile crt_div)(uint16_t, uint16_t) = __divhi3;
    uint16_t (*volatile crt_mod)(uint16_t, uint16_t) = __modhi3;
    uint32_t state = 0x65u;
    uint32_t checked = 0;
    unsigned i, j;

    if (local_div(0x8000u, 0) != 0 || local_mod(0x8000u, 0) != 0x8000u) {
        fputs("local division-by-zero contract mismatch\n", stderr);
        return 1;
    }
    for (i = 0; i < sizeof(edges) / sizeof(edges[0]); ++i) {
        for (j = 0; j < sizeof(edges) / sizeof(edges[0]); ++j) {
            uint16_t a = edges[i], b = edges[j];
            /* Retargeting libcrt IR turns its MOS udiv libcall into native x86
             * udiv; divisor zero is LLVM-undefined and traps there.  The MOS
             * zero case is pinned separately from the original IR and target
             * disassembly by the static gate. */
            if (b == 0) continue;
            if (crt_div(a, b) != local_div(a, b) ||
                crt_mod(a, b) != local_mod(a, b)) {
                fprintf(stderr, "edge mismatch %04x %04x\n", a, b);
                return 1;
            }
            ++checked;
        }
    }
    for (i = 0; i < 1000000u; ++i) {
        uint16_t a = (uint16_t)next_random(&state);
        uint16_t b = (uint16_t)next_random(&state);
        if (b == 0) continue;
        if (crt_div(a, b) != local_div(a, b) ||
            crt_mod(a, b) != local_mod(a, b)) {
            fprintf(stderr, "random mismatch %04x %04x\n", a, b);
            return 1;
        }
        ++checked;
    }
    printf("mega65-math-host-oracle: PASS %u compiler-rt comparisons\n",
           (unsigned)checked);
    return 0;
}
