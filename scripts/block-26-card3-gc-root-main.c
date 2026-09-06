/* Block 2.6 Card 3: execute the real collector with a product-only root.
 *
 * The root owns a cdr spine with more than the former 256-entry private
 * worklist could hold.  The flat root handoff plus the collector's existing
 * fixpoint preserves every cell; omitting the product root visibly frees it.
 */
#include <stdint.h>
#include <stdio.h>

#include "mem.h"
#include "symbol.h"

static obj product_root = NIL;
static obj tail_leaf = NIL;

void c2_product_gc_mark_roots(void) {
#ifndef LISP65_CARD3_OMIT_PRODUCT_ROOT
    gc_mark(product_root);
#endif
}

int main(void) {
    uint16_t index;
    uint16_t free_before;
    uint16_t free_after;

    mem_init();
    for (index = 0; index < 300u; ++index) {
        obj leaf = cons(MKFIX((int16_t)index), NIL);
        if (leaf == NIL) return 2;
        if (index == 0u) tail_leaf = leaf;
        product_root = cons(leaf, product_root);
        if (product_root == NIL) return 3;
    }

    free_before = mem_free_cells();
    gc_collect();
    free_after = mem_free_cells();
    if (free_after != free_before || !IS_PTR(tail_leaf) ||
            cell_type(tail_leaf) != T_CONS ||
            cell_a(tail_leaf) != MKFIX(0)) {
        fprintf(stderr,
            "card3-gc-root: FAIL before=%u after=%u tail-type=%u tail-a=%u\n",
            (unsigned)free_before, (unsigned)free_after,
            (unsigned)(IS_PTR(tail_leaf) ? cell_type(tail_leaf) : 0xffu),
            IS_PTR(tail_leaf) ? (unsigned)(uint16_t)cell_a(tail_leaf) : 0xffffu);
        return 1;
    }
    printf("card3-gc-root: PASS spine=300 live=600 free=%u->%u\n",
           (unsigned)free_before, (unsigned)free_after);
    return 0;
}
