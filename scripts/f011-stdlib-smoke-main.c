/* MEGA65/F011 stdlib smoke: load the chunked full stdlib from the mounted D81. */
#include "obj.h"
#include "printer.h"
#include "eval.h"
#include "io.h"
#include "interrupt.h"
#include "mem.h"
#include "symbol.h"

#ifndef F011_STDLIB_CHUNKS
#define F011_STDLIB_CHUNKS 25
#endif

static void emit_u32(unsigned long n) {
    char buf[11];
    unsigned char i = 0;
    if (!n) {
        emit('0');
        return;
    }
    while (n && i < sizeof(buf)) {
        buf[i++] = (char)('0' + (n % 10));
        n /= 10;
    }
    while (i) emit(buf[--i]);
}

static unsigned long f011_mount_base(void) {
#ifdef __MEGA65__
    __asm__ volatile("lda #$47\n\t sta $d02f\n\t lda #$53\n\t sta $d02f\n\t" ::: "a");
    return (unsigned long)*((volatile unsigned char *)0xD68C)
         | ((unsigned long)*((volatile unsigned char *)0xD68D) << 8)
         | ((unsigned long)*((volatile unsigned char *)0xD68E) << 16)
         | ((unsigned long)*((volatile unsigned char *)0xD68F) << 24);
#else
    return 0;
#endif
}

static uint8_t load_chunk(unsigned char n) {
    char name[4];
    const char *src;

    name[0] = 'l';
    name[1] = (char)('0' + (n / 10));
    name[2] = (char)('0' + (n % 10));
    name[3] = '\0';

    src = io_load_file(name);
    if (!src) {
        emit_str("f011-stdlib FAIL: cannot load ");
        emit_str(name);
        emit('\n');
        return 0;
    }
    lisp_error_msg = 0;
    load_source(src);
    if (lisp_error_msg) {
        emit_str("f011-stdlib FAIL: ");
        emit_str(name);
        emit_str(" ");
        emit_str(lisp_error_msg);
        emit('\n');
        return 0;
    }
    return 1;
}

static uint8_t check_binding(const char *name) {
    uint16_t i, n = sym_count();
    for (i = 0; i < n; i++) {
        obj s = sym_nth(i);
        const char *a = symname(s);
        const char *b = name;
        while (*a && *a == *b) { a++; b++; }
        if (*a == *b) return IS_PTR(sym_function(s)) ? 1 : 0;
    }
    return 0;
}

static uint16_t function_count(void) {
    uint16_t i, n = sym_count(), count = 0;
    for (i = 0; i < n; i++) {
        if (IS_PTR(sym_function(sym_nth(i)))) count++;
    }
    return count;
}

static void update_sentinel_mask(unsigned char chunk, uint8_t *mask) {
    if (chunk == 11 && check_binding("string=")) *mask |= 1;
    if (chunk == 15 && check_binding("reduce"))  *mask |= 2;
    if (chunk == 16 && check_binding("max"))     *mask |= 4;
    if (chunk == 17 && check_binding("getf"))    *mask |= 8;
    if (chunk == 20 && check_binding("format"))  *mask |= 16;
    if (chunk == 23 && check_binding("dotimes")) *mask |= 32;
}

#ifdef F011_STDLIB_LAYER_PROBE
static uint8_t is_layer_checkpoint(unsigned char chunk) {
    return chunk == 11 || chunk == 15 || chunk == 16 ||
           chunk == 17 || chunk == 20 || chunk == 23;
}

static uint16_t string_l11_mask(void) {
    uint16_t mask = 0;
    if (check_binding("%char-list="))   mask |= 1;
    if (check_binding("string="))       mask |= 2;
    if (check_binding("%char-list<"))   mask |= 4;
    return mask;
}

static void emit_layer_probe(unsigned char chunk, uint8_t sentinel_mask) {
    if (!is_layer_checkpoint(chunk)) return;
    emit_str("lisp65 f011-stdlib-layer: ");
    print_obj(MKFIX(chunk));
    emit_str(" fns ");
    print_obj(MKFIX(function_count()));
    emit_str(" syms ");
    print_obj(MKFIX(sym_count()));
    emit_str(" sent ");
    print_obj(MKFIX(sentinel_mask));
    emit_str(" str11 ");
    print_obj(MKFIX(string_l11_mask()));
    emit('\n');
}
#endif

static uint16_t free_cell_sample(void) {
    uint16_t count = 0;
    while (count < 16) {
        if (alloc(T_CONS) == NIL) return count;
        count++;
    }
    return count;
}

int main(void) {
    unsigned char i;
    uint8_t loaded = 0;
    uint8_t bindings = 0;
    uint8_t binding_mask = 0;
    uint8_t sentinel_mask = 0;

    eval_init();

    emit_str("lisp65 f011-stdlib-base: ");
    emit_u32(f011_mount_base());
    emit('\n');

    for (i = 0; i < F011_STDLIB_CHUNKS; i++) {
        loaded += load_chunk(i);
        update_sentinel_mask(i, &sentinel_mask);
#ifdef F011_STDLIB_LAYER_PROBE
        emit_layer_probe(i, sentinel_mask);
#endif
    }

    emit_str("lisp65 f011-stdlib-loaded: ");
    print_obj(MKFIX(loaded));
    emit('\n');

    emit_str("lisp65 f011-stdlib: ");
    print_obj(MKFIX(loaded));
    emit('\n');

    if (loaded == F011_STDLIB_CHUNKS) {
        if (check_binding("string=")) { bindings++; binding_mask |= 1; }
        if (check_binding("reduce"))  { bindings++; binding_mask |= 2; }
        if (check_binding("max"))     { bindings++; binding_mask |= 4; }
        if (check_binding("getf"))    { bindings++; binding_mask |= 8; }
        if (check_binding("format"))  { bindings++; binding_mask |= 16; }
        if (check_binding("dotimes")) { bindings++; binding_mask |= 32; }
    }

    emit_str("lisp65 f011-stdlib-bindings: ");
    print_obj(MKFIX(bindings));
    emit_str(" mask ");
    print_obj(MKFIX(binding_mask));
    emit('\n');
    emit_str("lisp65 f011-stdlib-");
    emit_str("sentinels: ");
    print_obj(MKFIX(sentinel_mask));
    emit('\n');
    emit_str("lisp65 f011-stdlib-");
    emit_str("fns: ");
    print_obj(MKFIX(function_count()));
    emit_str(" syms ");
    print_obj(MKFIX(sym_count()));
    emit('\n');
    emit_str("lisp65 f011-stdlib-free-cell-sample: ");
    print_obj(MKFIX(free_cell_sample()));
    emit('\n');

#ifdef LISP65_XEMU_TEST
    emit_test_terminate();
#ifdef __MEGA65__
    *((volatile unsigned char *)0xD6CF) = 0x42;
#endif
#endif
    return 0;
}
