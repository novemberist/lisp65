/* Focused host gate for the retained private code-list string codec. */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "mem.h"
#include "symbol.h"

uint16_t sym_count(void) { return 0; }
obj sym_nth(uint16_t i) { (void)i; return NIL; }
obj sym_value(obj s) { (void)s; return NIL; }
obj sym_function(obj s) { (void)s; return NIL; }

static int failures;

#define CHECK(name, condition) do { \
    if (!(condition)) { fprintf(stderr, "FAIL %s\n", (name)); failures++; } \
} while (0)

static int bytes_equal(obj s, const char *want) {
    uint16_t i, n = (uint16_t)strlen(want);
    if (!IS_PTR(s) || cell_type(s) != T_STR || str_len(s) != n) return 0;
    for (i = 0; i < n; i++) if (str_byte(s, i) != (uint8_t)want[i]) return 0;
    return 1;
}

static obj make_string(const char *text) {
    return str_from_bytes((const uint8_t *)text, (uint16_t)strlen(text));
}

static obj make_codes(const uint8_t *bytes, uint16_t length) {
    obj list = NIL;
    uint16_t i;
    GC_PUSH(list);
    for (i = length; i > 0; i--) {
        list = cons(MKFIX(bytes[i - 1]), gc_rootstack[GC_TOP]);
        GC_SET(GC_TOP, list);
    }
    GC_POPN(1);
    return list;
}

static void fresh(void) {
    mem_init();
    mem_oom = 0;
}

static void test_materialization(void) {
    static const uint8_t abc[] = {'a', 'b', 'c'};
    obj codes, out;
    fresh();
    codes = make_codes(abc, sizeof(abc));
    out = str_from_charlist(codes);
    CHECK("materialize-result", bytes_equal(out, "abc") && mem_oom == 0);
    out = str_from_charlist(NIL);
    CHECK("materialize-empty", out != NIL && str_len(out) == 0);
}

static void test_gc_during_construction(void) {
    static const uint8_t payload[24] = {
        's','u','r','v','i','v','e','-','a','f','t','e',
        'r','-','c','o','m','p','a','c','t','i','o','n'
    };
    obj dead, codes, out;
    fresh();
    dead = make_string("012345678901234567890123456789012345678901234567");
    (void)dead;
    codes = make_codes(payload, sizeof(payload));
    out = str_from_charlist(codes);
    CHECK("construction-gc-ran", gc_runs != 0);
    CHECK("construction-gc-rooted-source",
          bytes_equal(out, "survive-after-compaction") && mem_oom == 0);
}

static void test_arena_full_recovery(void) {
    static const uint8_t payload[24] = {
        'x','x','x','x','x','x','x','x','x','x','x','x',
        'x','x','x','x','x','x','x','x','x','x','x','x'
    };
    obj resident, codes, partial, recovery;
    fresh();
    resident = make_string("012345678901234567890123456789012345678901234567");
    codes = make_codes(payload, sizeof(payload));
    GC_PUSH(resident);
    GC_PUSH(codes);
    partial = str_from_charlist(codes);
    CHECK("arena-full-signalled", partial != NIL && mem_oom == 1);
    CHECK("arena-full-preserves-live-source",
          bytes_equal(resident, "012345678901234567890123456789012345678901234567"));
    GC_POPN(2);

    mem_oom = 0;
    gc_collect();
    codes = make_codes(payload, 1);
    recovery = str_from_charlist(codes);
    CHECK("arena-full-recovery", bytes_equal(recovery, "x") && mem_oom == 0);
}

static void test_cell_oom_recovery(void) {
    static const uint8_t z[] = {'z'};
    obj codes, chain = NIL, out;
    fresh();
    codes = make_codes(z, sizeof(z));
    GC_PUSH(codes);
    GC_PUSH(chain);
    while (mem_free_cells() != 0) {
        chain = cons(MKFIX(1), chain);
        GC_SET(GC_TOP, chain);
    }
    mem_oom = 0;
    out = str_from_charlist(codes);
    CHECK("cell-oom", out == NIL && mem_oom == 1);
    GC_POPN(2);
    mem_oom = 0;
    out = str_from_charlist(codes);
    CHECK("cell-oom-recovery", bytes_equal(out, "z") && mem_oom == 0);
}

int main(void) {
    test_materialization();
    test_gc_during_construction();
    test_arena_full_recovery();
    test_cell_oom_recovery();
    if (failures) {
        fprintf(stderr, "v2-string-codecs: %d failure(s)\n", failures);
        return 1;
    }
    puts("v2-string-codecs: OK (retained code-list/root/GC/OOM gates)");
    return 0;
}
