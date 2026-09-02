/* lisp65 phase-0 spike, iteration 2: compute benchmark and code-generation probe.
 * Lisp-like micro-kernel: cons-cell pool, pointer-chasing list traversal,
 * tree-shaped recursive fib, and 16/32-bit arithmetic.
 * Identical source across cc65, llvm-mos, and later m65compiler.
 *
 * Build:
 *   cc65:           cl65 -t c64 -O bench.c -o bench-cc65.prg
 *   llvm-mos MEGA65: ../../tools/llvm-mos/bin/mos-mega65-clang -Os bench.c -o bench-llvmmos-mega65.prg
 *   llvm-mos C64:    ../../tools/llvm-mos/bin/mos-c64-clang    -Os bench.c -o bench-llvmmos-c64.prg
 */
#include <stdio.h>
#include <stdint.h>

typedef struct node { int16_t val; struct node *next; } node;

static node pool[500];
static uint16_t poolidx;

static node *cons(int16_t v, node *n) {
    node *p = &pool[poolidx++];
    p->val = v;
    p->next = n;
    return p;
}

static int32_t sum_list(node *n) {
    int32_t s = 0;
    while (n) { s += n->val; n = n->next; }
    return s;
}

static uint32_t fib(uint8_t n) {
    if (n < 2) return n;
    return fib(n - 1) + fib(n - 2);
}

int main(void) {
    node *lst = 0;
    int16_t i;
    int32_t s;
    uint32_t f;

    for (i = 0; i < 500; i++) lst = cons(i, lst);
    s = sum_list(lst);     /* expected: 124750 */
    f = fib(24);           /* expected: 46368 */

    printf("sum=%ld fib=%lu\n", (long)s, (unsigned long)f);
    return 0;
}
