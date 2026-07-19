/* lisp65 — interaktive REPL (Lane K)
 * Phase 2: Zeilen lesen, ALLE Formen der (Multi-)Zeile auswerten und drucken.
 *  - mehrere Formen pro Zeile
 *  - ; Zeilenkommentare (im Reader)
 *  - RUN/STOP bricht Auswertung ab; CLR/HOME loescht Screen + Neustart der Eingabe
 *  - Fehler -> Meldung, REPL erholt sich (setjmp/lisp_abort)
 *
 * Eingabe: Gerät = rohe Tasten (KERNAL GETIN) + Echo + Block-Cursor; Host = getchar.
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
#if defined(LISP65_COMPILE_REPL) || defined(LISP65_BYTECODE_STDLIB_REPL_BANNER_ENTRY)
#include "vm.h"
#endif
#ifdef LISP65_COMPILE_REPL
#include "compile_repl.h"   /* compile_run_top_form: REPL wertet via geraeteseitigem Compiler aus (M6, Design §4a) */
#endif

#if defined(__MEGA65__) || defined(__C64__) || defined(__CBM__)
#include <cbm.h>
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

#ifdef DEVICE_KB
/* Eingabe-History (1 Eintrag = letzte abgeschickte Zeile). Abruf: CRSR-hoch (0x91) oder
 * Ctrl+P (0x10). Ctrl+Pfeil ist ueber KERNAL-GETIN nicht zuverlaessig unterscheidbar;
 * CRSR-hoch ist bei uns frei (keine Bildschirm-Navigation im REPL). EIN Eintrag, gedeckelt
 * auf HIST_MAX (Bank-0-Budget: volle BUF_MAX-Groesse riss das Stack-Gate); laengere Zeilen
 * lassen den letzten Eintrag stehen. Mehr History ist IDE-Territorium (Lane L, ide-buffer).
 *
 * LISP65_REPL_HISTORY_IN_BUF ist der Workbench-Sparpfad: kein separater History-Puffer,
 * sondern die letzte abgeschickte Zeile bleibt im statischen REPL-Buffer liegen. Das ist nur
 * am leeren Prompt abrufbar; begonnene/abgebrochene Zeilenedits gehoeren in die IDE. */
#ifndef HIST_MAX
#define HIST_MAX 120
#endif
#if HIST_MAX > 0 && !defined(LISP65_REPL_HISTORY_IN_BUF)
static unsigned char hist_len = 0;
static char hist[HIST_MAX];
#endif

/* Ausgabe-Primitive der Eingabezeile. Mit -DLISP65_SCREEN_DRIVER laufen sie ueber den
 * eigenen Treiber (ASCII direkt, kein Quote-Modus, kein PETSCII-Umweg); sonst KERNAL. */
#ifdef LISP65_SCREEN_DRIVER
static void kb_cursor_on(void)  { scr_cursor(1); }
static void kb_cursor_off(void) { scr_cursor(0); }
static void kb_clear(void)      { scr_clear(); }
static void kb_del(void)        { scr_backspace(); }
static void echo_char(char ch)  { scr_putc(ch); }
#else
static void kb_cursor_on(void)  {   /* Block-Cursor zeichensatz-unabhaengig: RVS-Space */
    cbm_k_chrout(0x12); cbm_k_chrout(' '); cbm_k_chrout(0x92); cbm_k_chrout(0x9D);
}
static void kb_cursor_off(void) { cbm_k_chrout(' '); cbm_k_chrout(0x9D); }
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
static uint8_t read_line(char *buf, uint8_t *np, uint8_t max) {
    uint8_t n = *np, floor = *np;
    int c;
    for (;;) {
#ifdef DEVICE_KB
        kb_cursor_on();
        do { c = cbm_k_getin(); } while (c == 0);
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
        /* Unbehandelte Steuercodes IGNORIEREN (Cursor-Tasten, INST, Farben, ...): weder echoen
         * noch speichern. Sonst landen sie im Puffer, waehrend der Schirm etwas anderes zeigt
         * (BASIC-Gewohnheit "Cursor zurueck + uebertippen" desynct Puffer<->Bildschirm und
         * erzeugt Geister-Formen). Editieren geht per DEL; Zeilen-Editor = IDE-Territorium. */
        if (c < 0x20 || (c >= 0x80 && c < 0xA0)) continue;
        if (n < max - 1) {
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

void repl(void) {
    static char buf[BUF_MAX];
    int aborted = 0;

#ifdef LISP65_COMPILE_REPL
    crepl_reset();   /* Compiled-Fn-Region einmalig (VOR setjmp -> defuns ueberleben Abbrueche) */
#endif
    if (setjmp(lisp_toplevel)) {                          /* Rueckkehr nach Abbruch/Fehler */
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
    if (!aborted)
        (void)vm_run_dir(LISP65_BYTECODE_STDLIB_REPL_BANNER_ENTRY, NULL, 0);
#else
    if (!aborted) emit_str("lisp65\n");
#endif
#endif

    for (;;) {
        uint8_t n = 0, st;
        emit_str("lisp65> ");
        st = read_line(buf, &n, BUF_MAX);
        if (st == 1) emit('\n');
        if (st == 0) return;                              /* EOF */
        if (st == 2) continue;                            /* CLR -> Neustart */
#ifdef DEVICE_KB
        /* History fuellen: VOR der Auswertung (auch fehlerhafte Zeilen sind so per CRSR-hoch
         * korrigierbar). Leere/ueberlange Zeilen ueberschreiben den Eintrag nicht. */
#if HIST_MAX > 0 && !defined(LISP65_REPL_HISTORY_IN_BUF)
        if (n > 0 && n <= HIST_MAX) { int k; for (k = 0; k < n; k++) hist[k] = buf[k]; hist_len = (unsigned char)n; }
#endif
        /* Wrap-Kompensation: lange Eingabezeilen (Prompt+Echo) brechen um, ohne dass emit()
         * es sieht. Konservativ mit 40 Spalten rechnen (im 80er-Modus zaehlt das doppelt ->
         * frueheres Loeschen, nie Scroll). */
        screen_row = (uint8_t)(screen_row + (unsigned)(n + 8) / 40);
#endif

        /* Erst NACH der Eingabe loeschen (falls Schirm voll): so bleibt die vorige Ausgabe
         * sichtbar, waehrend der Nutzer den naechsten Befehl tippt. Geloescht wird direkt vor
         * der neuen Ausgabe. (KERNAL-Scroll crasht -> wir loeschen statt zu scrollen.) */
        screen_scroll_guard();

        /* Eine Zeile = eine Eingabe (mehrere Formen pro Zeile erlaubt). KEINE
         * Mehrzeilen-Fortsetzung: sie braucht einen kleinen Paren-/String-/Kommentar-
         * Scanner im nativen REPL-Pfad. Das kommt zurueck, sobald wir wieder PRG-Ende-
         * Luft haben; bis dahin ist Workbench auf laengere Single-Line-Forms gepinnt. */
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
