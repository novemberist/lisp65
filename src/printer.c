/* lisp65 — Printer + Ausgabe-Sink (Lane K)
 * emit() schreibt auf den Bildschirm (CHROUT via putchar). Im automatisierten
 * xemu-Smoke (-DLISP65_XEMU_TEST) wird dieselbe Ausgabe zusaetzlich in ein festes
 * RAM-Fenster ($C000) gespiegelt, das der Checker deterministisch prueft.
 */
#include "printer.h"
#include "symbol.h"
#ifdef LISP65_STRING_ARENA
#include "mem.h"        /* str_len/str_byte (Packed-Byte-String-Arena) */
#endif
#include <stdio.h>
#ifdef LISP65_SCREEN_DRIVER
#include "screen.h"    /* eigener Treiber: emit -> scr_putc, Scroll nativ (kein Guard) */
#endif

#ifdef LISP65_XEMU_TEST
/* Test-Sink als statisches Array: der Linker legt es in eigenes BSS — kollidiert NIE
 * mit heap[]/Stack (anders als eine hartkodierte Adresse, die je nach HEAP_CELLS/
 * Rekursionstiefe ueberschrieben wurde). Der Dump-Checker sucht im ganzen RAM. */
static volatile uint8_t tsink_buf[1200];
#define TSINK tsink_buf
static uint16_t tpos = 0;
#endif

/* Bildschirmzeilen-Zaehler seit dem letzten Loeschen. Grund: der KERNAL-Editor-Scroll
 * CRASHT mit llvm-mos-mega65-PRGs (HW-bewiesen: jedes CHROUT-Scrollen -> schwarzer Schirm;
 * unmap-basic + Editor-Interna). Statt zu scrollen loescht die REPL bei fast-vollem Schirm
 * (screen_scroll_guard). Zaehlt Newlines; Wraps langer Zeilen werden grob unterschaetzt,
 * daher konservative Schwelle. */
uint8_t screen_row = 0;

void emit(char c) {
#ifdef LISP65_SCREEN_DRIVER
    scr_putc(c);
#else
    putchar(c);
#endif
    if (c == '\n' || c == '\r') screen_row++;
#ifdef LISP65_XEMU_TEST
    TSINK[tpos++] = (uint8_t)c;
#endif
}

/* Vor einer neuen Eingabezeile: wenn der Schirm fast voll ist, loeschen statt den KERNAL
 * scrollen zu lassen (der crasht). Nur auf dem Geraet; Host scrollt normal. */
void screen_scroll_guard(void) {
#ifdef LISP65_SCREEN_DRIVER
    /* eigener Treiber scrollt crashfrei selbst — Guard obsolet (Loeschen entfaellt) */
#elif defined(__MEGA65__) || defined(__C64__) || defined(__CBM__)
    if (screen_row >= 22) { putchar(0x93); screen_row = 0; }   /* 0x93 = CLR/HOME */
#endif
}

void emit_str(const char *s) { while (*s) emit(*s++); }

static void emit_int(int16_t n) {
    char buf[7];
    uint8_t i = 0;
    uint16_t u;
    if (n < 0) { emit('-'); u = (uint16_t)(-n); } else u = (uint16_t)n;
    do { buf[i++] = (char)('0' + (u % 10)); u /= 10; } while (u);
    while (i) emit(buf[--i]);
}

static void print_list(obj o) {
    emit('(');
    while (IS_PTR(o) && cell_type(o) == T_CONS) {
        print_obj(cell_a(o));
        o = cell_b(o);
        if (IS_PTR(o) && cell_type(o) == T_CONS) emit(' ');
    }
    if (o != NIL) { emit_str(" . "); print_obj(o); }
    emit(')');
}

void print_string_raw(obj s) {
#ifdef LISP65_STRING_ARENA
    uint16_t i, l = str_len(s);
    for (i = 0; i < l; i++) { screen_scroll_guard(); emit((char)str_byte(s, i)); }
#else
    obj cs = cell_a(s);
    while (IS_PTR(cs) && cell_type(cs) == T_CONS) {
        screen_scroll_guard();
        emit((char)FIXVAL(cell_a(cs)));
        cs = cell_b(cs);
    }
#endif
}

static void print_string_escaped(obj s) {
#ifdef LISP65_STRING_ARENA
    uint16_t i, l = str_len(s);
    for (i = 0; i < l; i++) {
        uint8_t c = str_byte(s, i);
        screen_scroll_guard();
        if (c == '"' || c == '\\') emit('\\');
        emit((char)c);
    }
#else
    obj cs = cell_a(s);
    while (IS_PTR(cs) && cell_type(cs) == T_CONS) {
        uint8_t c = (uint8_t)FIXVAL(cell_a(cs));
        screen_scroll_guard();
        if (c == '"' || c == '\\') emit('\\');
        emit((char)c);
        cs = cell_b(cs);
    }
#endif
}

void print_obj(obj o) {
    if (o == NIL)  { emit_str("nil"); return; }
    if (IS_FIX(o)) { emit_int(FIXVAL(o)); return; }
    if (IS_SYMI(o))  { emit_str(symname(o)); return; } /* interniertes Symbol (Immediate) */
    if (IS_BCODE(o)) { emit_str("#<fn>"); return; }   /* kompilierte Fn (Immediate) */
    if (!IS_PTR(o))  { emit_str("#<?>"); return; }    /* unbekanntes Immediate: nie Heap lesen */
    switch (cell_type(o)) {
    case T_SYM:     emit_str(symname(o)); return;
    case T_PRIM:    emit_str("#<prim>"); return;
    case T_CLOSURE: emit_str("#<closure>"); return;
    case T_MACRO:   emit_str("#<macro>"); return;
    case T_STR: {                                  /* "…": Zeichenliste ausgeben */
        emit('"');
        print_string_escaped(o);
        emit('"');
        return;
    }
    default:        print_list(o); return;        /* T_CONS */
    }
}

#ifdef LISP65_XEMU_TEST
void emit_test_terminate(void) { TSINK[tpos] = 0; }
#endif
