/* lisp65 Phase-0 spike, iteration 2: isolated compute code generation without stdio/printf.
 * The compute kernel matches bench.c, but output goes only to volatile globals.
 * The PRG size therefore measures runtime plus compute code, not printf libc.
 * A real Lisp core supplies its own number output instead of C printf.
 *
 * Build:
 *   cc65:            cl65 -t c64 -O bench-nolib.c -o bench-nolib-cc65.prg
 *   llvm-mos MEGA65: ../../tools/llvm-mos/bin/mos-mega65-clang -Os bench-nolib.c -o bench-nolib-llvmmos-mega65.prg
 *   llvm-mos C64:    ../../tools/llvm-mos/bin/mos-c64-clang    -Os bench-nolib.c -o bench-nolib-llvmmos-c64.prg
 */
#include <stdint.h>

typedef struct node { int16_t val; struct node *next; } node;

static node pool[500];
static uint16_t poolidx;

volatile int32_t g_sum;
volatile uint32_t g_fib;

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
    for (i = 0; i < 500; i++) lst = cons(i, lst);
    g_sum = sum_list(lst);   /* 124750 */
    g_fib = fib(24);         /* 46368  */
    return 0;
}
