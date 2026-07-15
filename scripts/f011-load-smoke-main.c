/* MEGA65/F011 offline smoke: load a library from the mounted D81. */
#include "obj.h"
#include "reader.h"
#include "printer.h"
#include "eval.h"

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

static obj eval_src(const char *src) {
    const char *p = src;
    return eval(read_expr(&p));
}

int main(void) {
    obj r;

    eval_init();

    emit_str("lisp65 f011-base: ");
    emit_u32(f011_mount_base());
    emit('\n');

    r = eval_src("(load \"testlib\")");
    emit_str("lisp65 f011-load-ret: ");
    print_obj(r);
    emit('\n');

    r = eval_src("(sq 5)");

    emit_str("lisp65 f011-load: ");
    print_obj(r);
    emit('\n');

#ifdef LISP65_F011_HW_HOLD
    for (;;) {
#ifdef __MEGA65__
        __asm__ volatile("nop");
#endif
    }
#endif

#ifdef LISP65_XEMU_TEST
    emit_test_terminate();
#ifdef __MEGA65__
    *((volatile unsigned char *)0xD6CF) = 0x42;
#endif
#endif
    return 0;
}
