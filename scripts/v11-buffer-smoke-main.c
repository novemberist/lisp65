/* Independent host smoke for the 1.1-E first-class byte-buffer carrier. */
#include <stdint.h>
#include <stdio.h>

#include "mem.h"
#include "obj.h"
#include "printer.h"

static int expect(int condition, const char *label) {
    if (!condition) fprintf(stderr, "FAIL: %s\n", label);
    return condition ? 0 : 1;
}

int main(void) {
    obj garbage, first, second, frozen, copied;
    uint16_t index;
    int failures = 0;

    mem_init();
    first = buf_make(5);
    failures += expect(first != NIL && cell_type(first) == T_BUF,
                       "make produces T_BUF");
    for (index = 0; index < 5; index++) buf_set(first, index, (uint8_t)('a' + index));
    print_obj(first);
    emit('\n');

    /* Force dead bytes ahead of a live buffer, then compact. */
    garbage = buf_make(17);
    (void)garbage;
    second = buf_make(4);
    for (index = 0; index < 4; index++) buf_set(second, index, (uint8_t)(40 + index));
    GC_PUSH(first);
    GC_PUSH(second);
    gc_collect();
    failures += expect(buf_len(first) == 5 && buf_byte(first, 0) == 'a' &&
                       buf_byte(first, 4) == 'e', "first buffer survives compaction");
    failures += expect(buf_len(second) == 4 && buf_byte(second, 0) == 40 &&
                       buf_byte(second, 3) == 43, "second buffer relocates byte-exactly");

    frozen = buf_freeze(first);
    failures += expect(frozen == first && cell_type(frozen) == T_STR &&
                       str_len(frozen) == 5 && str_byte(frozen, 2) == 'c',
                       "freeze is zero-copy and atomic");
    copied = buf_from_string(frozen);
    failures += expect(copied != NIL && cell_type(copied) == T_BUF &&
                       buf_len(copied) == 5 && buf_byte(copied, 4) == 'e',
                       "string copy is byte-exact");
    GC_POPN(2);

    mem_oom = 0;
    failures += expect(buf_make((uint16_t)(str_arena_capacity() + 1u)) == NIL &&
                       mem_oom, "oversize allocation fails closed");

    fprintf(stderr, "v11-buffer-smoke: %s failures=%d\n",
            failures ? "FAIL" : "PASS", failures);
    return failures ? 1 : 0;
}
