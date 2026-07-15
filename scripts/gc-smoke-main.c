/* lisp65 host GC smoke. Closes the CI gap that hid the MEGA65 GC freeze:
 * The original smoke covered only C64. This test stresses the fixed-point collector: a rooted
 * list and interned symbols must survive many collections under heavy garbage production.
 * It verifies length and checksum after every collection using a minimal mem/symbol/interrupt link.
 * Exit 0 means PASS. Hardware counterpart: tools/host-lisp/gc-stress-test.c. */
#include <stdio.h>
#include "obj.h"
#include "mem.h"
#include "symbol.h"

#ifndef LIVE_N
#define LIVE_N 50
#endif
#ifndef ITERS
#define ITERS 400
#endif
#ifndef GARBAGE
#define GARBAGE 150
#endif
#ifndef PRESYM
#define PRESYM 60          /* internal symbols add marking pressure to every GC */
#endif

int main(void) {
    uint16_t base, iter;
    int i;

    mem_init();   /* match production eval_init by constructing the free list explicitly */

    /* Intern symbols that remain GC roots, exercising the symbol-marking phase. */
    for (i = 0; i < PRESYM; i++) {
        char nm[8];
        nm[0] = 's'; nm[1] = (char)('0' + (i / 10) % 10); nm[2] = (char)('0' + i % 10); nm[3] = 0;
        (void)intern(nm);
    }

    /* Build and permanently root the live list. */
    base = gc_rootsp;
    GC_PUSH(NIL);
    for (i = LIVE_N - 1; i >= 0; i--) { obj c = cons(MKFIX(i), gc_rootstack[base]); GC_SET(base, c); }
    { obj p = gc_rootstack[base]; uint16_t len = 0; while (IS_PTR(p)) { len++; p = cell_b(p); }
      if (len != LIVE_N) { printf("gc-smoke: heap too small for test configuration (%u/%u)\n", len, (unsigned)LIVE_N); return 2; } }

    for (iter = 0; iter < ITERS; iter++) {
        int j;
        for (j = 0; j < GARBAGE; j++) (void)cons(MKFIX(j & 0x3f), NIL);   /* Muell -> GC feuert */
        gc_collect();
        { obj p = gc_rootstack[base]; uint16_t len = 0, sum = 0;
          while (IS_PTR(p)) { len++; sum = (uint16_t)(sum + FIXVAL(cell_a(p))); p = cell_b(p); }
          if (len != LIVE_N || sum != (uint16_t)(LIVE_N * (LIVE_N - 1) / 2)) {
              printf("gc-smoke: FAIL @iter=%u len=%u sum=%u (soll %u/%u) gc_runs=%u badobj=%u\n",
                     iter, len, sum, (unsigned)LIVE_N, (unsigned)(LIVE_N * (LIVE_N - 1) / 2),
                     gc_runs, gc_badobj);
              return 1;
          } }
    }
    printf("gc-smoke: PASS %u Zyklen, gc_runs=%u, badobj=%u (LIVE_N=%u, PRESYM=%u)\n",
           (unsigned)ITERS, gc_runs, gc_badobj, (unsigned)LIVE_N, (unsigned)PRESYM);
    return 0;
}
