/* lisp65 — interactive REPL (lane K)
 * Phase 2: read lines, evaluate ALL forms on the (multi-form) line and print them.
 *  - several forms per line
 *  - ; line comments (in the reader)
 *  - RUN/STOP aborts evaluation; CLR/HOME clears the screen and restarts the input
 *  - errors -> a message, and the REPL recovers (setjmp/lisp_abort)
 *
 * Input: device = raw keys (KERNAL GETIN) + echo + block cursor; host = getchar.
 */
#include <stdio.h>
#include <setjmp.h>
#include "obj.h"
#include "mem.h"
#include "symbol.h"
#include "reader.h"
#include "printer.h"
#include "eval.h"
#include "interrupt.h"
#include "repl.h"
#ifdef LISP65_REPL_BANNER_REQUIRED
#include "stdlib-p0.h"
#ifndef LISP65_BYTECODE_STDLIB_REPL_BANNER_ENTRY
#error "Workbench REPL banner is required but absent from the generated stdlib directory"
#endif
#endif
#if defined(LISP65_COMPILE_REPL) || defined(LISP65_BYTECODE_STDLIB_REPL_BANNER_ENTRY) \
    || defined(LISP65_BYTECODE_STDLIB_NATIVE_READ_LINE_ENTRY)
#include "vm.h"
#endif
#ifdef LISP65_COMPILE_REPL
#include "compile_repl.h"   /* compile_run_top_form: REPL wertet via geraeteseitigem Compiler aus (M6, Design §4a) */
#endif
#ifdef LISP65_C2_NESTED_APPEND_V5
#include "c2_product_runtime.h"
#endif

#if defined(__MEGA65__) || defined(__C64__) || defined(__CBM__)
#ifndef LISP65_C2_KERNAL_UNMAP
#include <cbm.h>
#endif
#define DEVICE_KB 1
#ifdef LISP65_SCREEN_DRIVER
#include "screen.h"
#endif
#endif

#ifndef REPL_BUF_MAX
#define REPL_BUF_MAX 250
#endif
#if REPL_BUF_MAX < 2 || REPL_BUF_MAX > 255
#error "REPL_BUF_MAX must fit the byte-sized REPL cursor contract (2..255)"
#endif
#define BUF_MAX REPL_BUF_MAX

#define C2K_INPUT_RING_TAIL (*(volatile unsigned char *)0xff8d)

#ifdef DEVICE_KB
/* Input history (1 entry = the last submitted line). Recall: cursor-up (0x91) or Ctrl+P (0x10).
 * Ctrl+arrow cannot be told apart reliably through KERNAL GETIN; cursor-up is free here (the REPL
 * has no on-screen navigation). ONE entry, capped at HIST_MAX (bank-0 budget: the full BUF_MAX size
 * broke the stack gate); longer lines leave the existing entry in place. More history is IDE
 * territory (lane L, ide-buffer).
 *
 * LISP65_REPL_HISTORY_IN_BUF is the workbench economy path: no separate history buffer — the last
 * submitted line simply stays in the static REPL buffer. It is recallable only at an empty prompt;
 * started or abandoned line edits belong in the IDE. */
#ifndef HIST_MAX
#define HIST_MAX 120
#endif
#if HIST_MAX > 0 && !defined(LISP65_REPL_HISTORY_IN_BUF)
static unsigned char hist_len = 0;
static char hist[HIST_MAX];
#endif

/* Output primitives for the input line. With -DLISP65_SCREEN_DRIVER they go through our own
 * driver (ASCII directly, no quote mode, no PETSCII detour); otherwise through the KERNAL. */
#ifdef LISP65_SCREEN_DRIVER
static void kb_cursor_on(void)  { scr_cursor(1); }
static void LISP65_C2_FIXED_BANK0_CODE("kb_cursor_off")
kb_cursor_off(void) { scr_cursor(0); }
static void kb_clear(void)      { scr_clear(); }
static void kb_del(void)        { scr_backspace(); }
static void echo_char(char ch)  { scr_putc(ch); }
#else
static void kb_cursor_on(void)  {   /* Block-Cursor zeichensatz-unabhaengig: RVS-Space */
    cbm_k_chrout(0x12); cbm_k_chrout(' '); cbm_k_chrout(0x92); cbm_k_chrout(0x9D);
}
static void LISP65_C2_FIXED_BANK0_CODE("kb_cursor_off")
kb_cursor_off(void) { cbm_k_chrout(' '); cbm_k_chrout(0x9D); }
static void kb_clear(void)      { cbm_k_chrout(0x93); }
static void kb_del(void)        { cbm_k_chrout(0x14); }
/* Ein Zeichen aus buf/hist zurueck auf den Schirm echoen (Reader-Kleinbuchstaben -> PETSCII;
 * '"' mit dem Doppel-Quote-Trick, damit der KERNAL-Quote-Modus aus bleibt). */
static void echo_char(char ch) {
    if (ch == '"') { cbm_k_chrout('"'); cbm_k_chrout('"'); cbm_k_chrout(0x14); return; }
    if (ch >= 'a' && ch <= 'z') { cbm_k_chrout((unsigned char)(ch - 0x20)); return; }
    cbm_k_chrout((unsigned char)ch);
}
#endif
#endif

/* Liest eine Zeile, haengt ab buf[*np] an, aktualisiert *np.
 * return: 1 = mit RETURN beendet, 0 = EOF (Host), 2 = CLR/HOME (Screen geloescht). */
#ifdef LISP65_BYTECODE_STDLIB_NATIVE_READ_LINE_ENTRY
static uint8_t read_line(char *buf, uint8_t *np, uint8_t max) {
    obj line;
    uint16_t length;
    lisp65_error_code code;
    vm_status = VM_OK;
    line = vm_run_dir(LISP65_BYTECODE_STDLIB_NATIVE_READ_LINE_ENTRY, NULL, 0);
    if (vm_status != VM_OK && vm_status != VM_HALT) {
        code = vm_status_error_code(vm_status);
        vm_status = VM_OK;
        lisp_abort_code(code);
        return 0;
    }
    vm_status = VM_OK;
    if (!IS_PTR(line) || cell_type(line) != T_STR) {
        lisp_abort_code(LISP65_ERR_VM_TYPE);
        return 0;
    }
    length = str_len(line);
    if (length >= (uint16_t)(max - *np)) {
        lisp_abort_code(LISP65_ERR_READER_INVALID_TOKEN);
        return 0;
    }
    *np = (uint8_t)(*np + str_copy_out(line, buf + *np, length));
    return 1;
}
#else
static uint8_t read_line(char *buf, uint8_t *np, uint8_t max) {
    uint8_t n = *np, floor = *np;
#ifdef DEVICE_KB
    uint8_t c;
#else
    int c;
#endif
    for (;;) {
#ifdef DEVICE_KB
        kb_cursor_on();
#ifdef LISP65_C2_KERNAL_UNMAP
        {
            lisp65_key_event event;
            (void)lisp_input_event(1u, 1u, &event);
            c = event.code;
        }
#else
        do { c = cbm_k_getin(); } while (c == 0);
#endif
        if (c == '\r' || c == '\n') { kb_cursor_off(); *np = n; return 1; }
        if (c == 0x93 || c == 0x13) { kb_clear(); *np = n; return 2; }  /* CLR/HOME */
        if (c == 0x14) {                                  /* DEL/Backspace */
            kb_cursor_off();
            if (n > floor) { n--; kb_del(); }
            continue;
        }
#if HIST_MAX > 0 && defined(LISP65_REPL_HISTORY_IN_BUF)
        if (c == 0x91) {                                  /* Workbench: CRSR-hoch am leeren Prompt */
            if (n == floor) for (; buf[n] && n < max - 1; n++) echo_char(buf[n]);
            continue;
        }
#elif HIST_MAX > 0
        if (c == 0x91 || c == 0x10) {                     /* CRSR-hoch / Ctrl+P: History-Abruf */
            int k;
            kb_cursor_off();
            for (k = n; k > floor; k--) kb_del();         /* aktuelle Eingabe wegloeschen */
            n = floor;
            for (k = 0; k < hist_len && n < max - 1; k++) { echo_char(hist[k]); buf[n++] = hist[k]; }
            continue;
        }
#endif
#ifndef LISP65_SCREEN_DRIVER
        if (c == '"') {                                   /* " ohne haengenden Quote-Modus */
            /* zweimal ausgeben toggelt den KERNAL-Quote-Modus wieder AUS, dann das zweite
             * per DELETE entfernen -> sichtbar bleibt ein ", Steuercodes danach laufen
             * normal (adress-unabhaengig, kein Poken einer geratenen Flag-Adresse). Mit
             * eigenem Treiber gibt es keinen Quote-Modus -> normaler Pfad unten. */
            cbm_k_chrout('"'); cbm_k_chrout('"'); cbm_k_chrout(0x14);
            if (n < max - 1) buf[n++] = '"';
            continue;
        }
#endif
        /* WYSIWYG input boundary: shifted PETSCII Space is visually identical
         * to Space and therefore must also be semantic whitespace.  Every
         * remaining unhandled control is rejected visibly; silently dropping
         * it would make the accepted line differ from the typed one. */
        /* Clearing bit 7 makes both unhandled PETSCII control bands the
         * same $00..$1f interval.  Keep the visible rejection, but let its
         * fall-through share the capacity branch: lisp_abort_code normally
         * longjmps, and its no-toplevel smoke fallback reaches the loop tail. */
        if ((c & 0x7F) < 0x20) {
            lisp_abort_code(LISP65_ERR_READER_INVALID_TOKEN);
        } else if (n < max - 1) {
            if (c == 0xA0) c = ' ';
#ifdef LISP65_SCREEN_DRIVER
            /* PETSCII -> ASCII VOR dem Echo: unshifted Buchstaben ($41-$5A) -> klein,
             * geshiftete ($C1-$DA) -> GROSS; der Treiber mappt ASCII selbst. */
            if (c >= 'A' && c <= 'Z') c += 0x20;
            else if (c >= 0xC1 && c <= 0xDA) c -= 0x80;
            echo_char((char)c);
            buf[n++] = (char)c;
#else
            cbm_k_chrout((unsigned char)c);               /* Echo: ueberschreibt Cursor */
            if (c >= 'A' && c <= 'Z') c += 0x20;          /* fuer den Reader klein */
            buf[n++] = (char)c;
#endif
        }
#else
        c = getchar();
        if (c == EOF) { *np = n; return 0; }
        if (c == '\r' || c == '\n') { *np = n; return 1; }
        if (n < max - 1) buf[n++] = (char)c;
#endif
    }
}

#endif

void repl(void) {
    static char buf[BUF_MAX];
    int aborted = 0;

#ifdef LISP65_COMPILE_REPL
    crepl_reset();   /* Compiled-Fn-Region einmalig (VOR setjmp -> defuns ueberleben Abbrueche) */
#endif
    if (setjmp(lisp_toplevel)) {                          /* Rueckkehr nach Abbruch/Fehler */
        /* A longjmp can cross the Bank-2 Comfort loop.  Disable its raw IRQ
         * capture before rendering or re-entering the native fallback. */
        C2K_INPUT_RING_TAIL = 0xff;
#ifdef LISP65_C2_NESTED_APPEND_V5
        /* Retirement ran before longjmp while its generation was still
         * named.  Transported journal recovery belongs here: setjmp has now
         * restored the shallow top-level soft stack, and no new evaluation
         * or error rendering has begun. */
        (void)c2_product_abort_recover();
#endif
        aborted = 1;
        emit('\n');
        emit_str("*** ");
        (void)lisp65_error_render_pending();
        emit('\n');
        lisp65_error_clear();
        gc_rootsp = 0;                                    /* Roots der abgebrochenen eval verwerfen */
    }
    lisp_toplevel_active = 1;
#ifdef DEVICE_KB
    if (!aborted) {
#ifdef LISP65_SCREEN_DRIVER
        scr_init();            /* Geometrie erkennen, Farb-RAM weiss, loeschen, home */
#else
        cbm_k_chrout(14);      /* Kleinschrift-/Mixed-Case-Modus (unsere Symbole sind klein) */
        cbm_k_chrout(0x93);    /* sauberer Schirm -> Zeilenzaehler (screen_row) synchron */
        screen_row = 0;
#endif
    }
#endif
#ifdef LISP65_STDLIB_FROM_DISK
    /* S5-Diagnose im Banner: cN = geladene Disk-Chunks (Mount sichtbar), sMMM = interne Symbole
     * (Compile sichtbar). c0 -> Mount/F011 liest die D81 nicht; c2 s2xx -> Stdlib+IDE compiliert. */
    if (!aborted) {
        extern unsigned char g_s5_chunks;
        uint16_t sc = sym_count();
        emit_str("lisp65 c"); emit((char)('0' + (g_s5_chunks & 15u)));
        emit_str(" s");
        emit((char)('0' + (sc / 100u) % 10u));
        emit((char)('0' + (sc / 10u) % 10u));
        emit((char)('0' + sc % 10u));
        emit('\n');
    }
#else
#ifdef LISP65_BYTECODE_STDLIB_REPL_BANNER_ENTRY
    if (!aborted) {
        (void)vm_run_dir(LISP65_BYTECODE_STDLIB_REPL_BANNER_ENTRY, NULL, 0);
        /* A prompt is a publication claim: the product banner entry really
         * executed.  Preserve the inner VM status and fail closed instead of
         * turning a missing/invalid Bank-2 plane into a plausible REPL. */
        if (vm_status != VM_OK && vm_status != VM_HALT) {
            /* The numeric error seam is the one resident error truth.  Do not
             * pull vm_status_message() and its private string table into Bank
             * 0 merely to report a boot-time VM failure. */
            lisp_abort_code(vm_status_error_code(vm_status));
        }
    }
#else
    if (!aborted) emit_str("lisp65\n");
#endif
#endif

    for (;;) {
        uint8_t n = 0, st;
#ifndef LISP65_BYTECODE_STDLIB_NATIVE_READ_LINE_ENTRY
        emit_str("lisp65> ");
#endif
        st = read_line(buf, &n, BUF_MAX);
#ifndef LISP65_BYTECODE_STDLIB_NATIVE_READ_LINE_ENTRY
        if (st == 1) emit('\n');
#endif
        if (st == 0) return;                              /* EOF */
        if (st == 2) continue;                            /* CLR -> restart */
#ifdef DEVICE_KB
        /* Fill the history BEFORE evaluating (so even a faulty line can be corrected with
         * cursor-up). Empty or over-long lines do not overwrite the entry. */
#if HIST_MAX > 0 && !defined(LISP65_REPL_HISTORY_IN_BUF)
        if (n > 0 && n <= HIST_MAX) { int k; for (k = 0; k < n; k++) hist[k] = buf[k]; hist_len = (unsigned char)n; }
#endif
        /* Wrap compensation: long input lines (prompt + echo) wrap without emit() seeing it.
         * Compute conservatively with 40 columns (in 80-column mode that counts double ->
         * clearing earlier, never scrolling). */
        screen_row = (uint8_t)(screen_row + (unsigned)(n + 8) / 40);
#endif

        /* Clear only AFTER the input (if the screen is full): this keeps the previous output
         * visible while the user types the next command. The clear happens right before the new
         * output. (A KERNAL scroll crashes -> we clear instead of scrolling.) */
        screen_scroll_guard();

        /* One line = one input (several forms per line are allowed). NO multi-line continuation:
         * that needs a small paren/string/comment scanner in the native REPL path. It comes back
         * as soon as we have PRG-end headroom again; until then the workbench is pinned to longer
         * single-line forms. */
        buf[n] = '\0';
        {
            const char *p = buf;                          /* alle Formen auswerten */
            for (;;) {
                while (*p == ' ' || *p == '\t' || *p == '\n' || *p == '\r') p++;
                if (*p == ';') { while (*p && *p != '\n') p++; continue; }
                if (*p == '\0') break;
#ifdef LISP65_COMPILE_REPL
                {   /* M6: Nutzer-Eingabe wird KOMPILIERT + ausgefuehrt (Treewalk-Ersatz, Design §4a). */
                    obj r = compile_run_top_form(read_expr(&p));
                    if (vm_status != VM_OK) emit_str("*** cannot compile");
                    else print_obj(r);
                }
#elif defined(LISP65_LCC_FIRST_REPL) && !defined(LISP65_TREEWALK_STRIP)
                {   /* Konvergenz-M1 (docs/einsuite-convergence-design.md): Eingabe laeuft lcc-first —
                     * als (lcc-run (quote FORM)) durch den Blob-Compiler auf vm_run (Maschinenraum-
                     * Semantik im Ein-Produkt). Treewalk = Traeger + Fallback (Blob ohne lcc-run). */
                    obj form = read_expr(&p);
                    obj lccrun = intern("lcc-run");
                    if (sym_function(lccrun) != NIL) {
                        obj q;
                        GC_PUSH(form);
                        q = cons(form, NIL);
                        GC_POPN(1); GC_PUSH(q);
                        q = cons(intern("quote"), q);
                        GC_POPN(1); GC_PUSH(q);
                        q = cons(q, NIL);
                        GC_POPN(1); GC_PUSH(q);
                        q = cons(lccrun, q);
                        GC_POPN(1);
                        print_obj(eval(q));
                    } else {
                        print_obj(eval(form));
                    }
                }
#else
                print_obj(eval(read_expr(&p)));
#endif
                emit('\n');
            }
            if (mem_oom) {                       /* OOM ehrlich melden statt Geister-nil */
                mem_oom = 0;
#ifdef LISP65_NUMERIC_ERRORS
                lisp_abort_static(LISP65_ERR_VM_OOM, "vm: out of memory");
#else
                emit_str("*** out of memory\n");
#endif
            }
        }
    }
}
