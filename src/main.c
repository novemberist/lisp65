/* lisp65 — Einstiegspunkt / Milestone-Treiber (Lane K)
 * Phase 1, M1.3 (Pivot): Reader-Roundtrip + Eval mit lambda/Closures (Lisp-2).
 * Die "lisp65 print: (+ 1 2)"-Zeile bleibt unveraendert, damit der bestehende
 * xemu-Smoke (Lane T) gruen bleibt; die "lisp65 eval:"-Zeile zeigt ein Eval-Ergebnis.
 */
#ifdef LISP65_BOOT_TRACE
#define BT(c) (*(volatile unsigned char*)0xD020=(c))
#else
#define BT(c) ((void)0)
#endif
#include "obj.h"
#include "mem.h"
#include "reader.h"
#include "printer.h"
#include "eval.h"
#ifdef LISP65_COMPILE_REPL
#include "compile_repl.h"   /* crepl_boot_init + load_source: Compiler statt Treewalk (eval.c weggelassen) */
#endif

#ifdef LISP65_STDLIB_FROM_DISK
#include "io.h"             /* io_disk_load_* : Stdlib als QUELLE von Disk, on-device kompiliert (S5) */
/* Boot-Ladeanzeige: Balken @Zeile 12 (80-Spalten-Screen), gefuellt nach Disk-Reader-Fortschritt.
 * Der Boot kompiliert die ganze Stdlib -> dauert; der Nutzer braucht sichtbares Feedback. Direkter
 * Screen-RAM-Poke (0x0800), unabhaengig vom Screen-Treiber; das REPL-CLR loescht ihn danach. */
static void s5_progress(void) {
    volatile unsigned char *row = (volatile unsigned char *)(0x0800 + 12u * 80u);
    unsigned int pm = io_disk_load_permille();          /* 0..1000 */
    unsigned int fill = pm * 40u / 1000u, i, pct = pm / 10u;
    for (i = 0; i < 40u; i++) row[i] = (i < fill) ? 0xa0u : 0x66u;   /* Vollblock / Leerbalken */
    row[42] = (unsigned char)(0x30u + (pct / 100u) % 10u);
    row[43] = (unsigned char)(0x30u + (pct / 10u) % 10u);
    row[44] = (unsigned char)(0x30u + pct % 10u);
    row[45] = 0x25u;                                     /* '%' */
}
/* Quell-Herkunft (Phase 2, echter F011-Disk-Pfad): die S5-Quell-D81 (Codex' `make s5-source-d81`)
 * traegt die Quelle als Chunks `l00`,`l01`,... (jeweils <= DISK_FILE_MAX). Der Boot laedt sie per
 * Dir-Lookup nach Namen der Reihe nach, bis der erste fehlt, und kompiliert jeden on-device
 * (io_disk_load_named -> io_disk_load_chain -> load_source_stream). Namens-Vertrag mit Lane T:
 * docs/collaboration.md (Dir-Lookup, keine festen Sektoren). */
static const char *const s5_chunks[8] = {"l00","l01","l02","l03","l04","l05","l06","l07"};
unsigned char g_s5_chunks = 0;   /* Diagnose: geladene Chunks (Banner zeigt sie -> Mount sichtbar) */
static void boot_stdlib_from_disk(void) {
    crepl_progress = s5_progress;
    for (g_s5_chunks = 0; g_s5_chunks < 8u; )
        if (io_disk_load_named(s5_chunks[g_s5_chunks])) g_s5_chunks++;
        else break;                                    /* bis zum ersten fehlenden Chunk */
    crepl_progress = 0;
}
#endif

#ifdef LISP65_WITH_PRELUDE
#include "prelude_gen.h"   /* von Lane T generiert: const char prelude_src[] (NUL-term.) */
#endif
#ifdef LISP65_EMBED_STDLIB
#include "vm_embed.h"      /* eingebettete Bytecode-Stdlib (setzt LISP65_VM voraus) */
#ifdef LISP65_STAGED_BOOT_OVERLAY
#include "interrupt.h"
#include "vm_boot_fastpath.h"
#include "vm_boot_overlay.h"
#endif
#endif
#ifdef LISP65_REPL
#include "repl.h"
#endif
#ifdef LISP65_SCREEN_DRIVER
#include "screen.h"
#endif

int main(void) {
#ifdef LISP65_STAGED_BOOT_OVERLAY
    uint8_t boot_overlay_result;
#endif
#if defined(__MEGA65__)
    /* CPU auf 40 MHz (2026-07-03): nach etherload-Reset laeuft die CPU sonst im
     * Kompatibilitaetstakt — ALLE Wandzeit-Anomalien des Perf-Abends (Faktor ~20 zwischen
     * Host-Schrittzahl und Geraetegefuehl) passen zu 1-3,5 MHz. VIC-IV-Knock + FAST-Bit. */
    *(volatile unsigned char *)0xD02F = 0x47;   /* VIC-IV freischalten ("G") */
    *(volatile unsigned char *)0xD02F = 0x53;   /* ... ("S") */
    *(volatile unsigned char *)0xD054 |= 0x40;  /* VFAST: 40 MHz */
#endif
#ifdef LISP65_STAGED_BOOT_OVERLAY
    BT(1);                         /* gesamter Init laeuft im verifizierten Overlay-Entry */
#else
#ifdef LISP65_COMPILE_REPL
    BT(1); crepl_boot_init(); BT(3);   /* Minimal-Boot ohne Treewalk (eval.c weggelassen) */
#else
    BT(1); eval_init(); BT(3);
#endif
#endif
#ifdef LISP65_WITH_PRELUDE
#ifdef LISP65_STAGED_BOOT_OVERLAY
#error "staged Workbench boot does not support LISP65_WITH_PRELUDE"
#endif
    load_source(prelude_src);   /* eingebettetes Prelude beim Boot einspeisen */
#endif
#ifdef LISP65_EMBED_STDLIB
#ifdef LISP65_STAGED_BOOT_OVERLAY
    boot_overlay_result = vm_install_staged_boot_overlay();
    if (boot_overlay_result != VM_BOOT_OVERLAY_OK) {
        if (!lisp_error_msg)
            lisp_abort_static(LISP65_ERR_STDLIB_BOOT_OVERLAY,
                              "stdlib: invalid boot overlay");
        return 1;                  /* kein Toplevel aktiv: trotzdem fail-closed */
    }
#ifdef LISP65_BOOT_OVERLAY_WIPE
    if (!lisp65_boot_overlay_wipe_ok) {
        lisp_abort_static(LISP65_ERR_STDLIB_BOOT_WIPE,
                          "stdlib: boot overlay wipe failed");
        return 1;
    }
#endif
    boot_overlay_result = vm_load_profiled_boot_stdlib();
    if (boot_overlay_result != VM_BOOT_FASTPATH_OK) {
        if (boot_overlay_result == VM_BOOT_FASTPATH_ERR_CATALOG) {
            lisp_abort_static(LISP65_ERR_RUNTIME_CATALOG,
                              "catalog missing; redeploy");
#ifdef LISP65_SCREEN_DRIVER
            scr_init();
            (void)lisp65_error_render_pending();
            emit('\n');
#endif
        } else if (!lisp_error_msg)
            lisp_abort_static(LISP65_ERR_STDLIB_PROFILED_PRELOAD,
                              "stdlib: invalid profiled preload");
        return 1;
    }
    boot_overlay_result = (uint8_t)vm_runtime_overlay_install_island();
    if (boot_overlay_result != VM_RUNTIME_OVERLAY_OK) {
        lisp_abort_static(LISP65_ERR_RUNTIME_ISLAND,
                          "runtime island invalid; redeploy");
#ifdef LISP65_SCREEN_DRIVER
        scr_init();
        (void)lisp65_error_render_pending();
        emit('\n');
#endif
        return 1;
    }
    BT(4);
#else
    vm_load_embedded_stdlib(); BT(4);  /* eingebettete Bytecode-Stdlib ins erw. RAM stagen + registrieren */
#ifdef LISP65_EXT_HEAP
    gc_freeze_boot();   /* Boot-Permanents (EXT) einfrieren; Hot-Bereich an die Freelist-Spitze */
#endif
#endif
#endif
#ifdef LISP65_STDLIB_FROM_DISK
    boot_stdlib_from_disk(); BT(4);    /* S5: Stdlib-QUELLE von Disk on-device kompilieren (mit Ladebalken) */
#ifdef LISP65_EXT_HEAP
    gc_freeze_boot();
#endif
#endif

#ifdef LISP65_REPL
    /* Banner druckt repl() selbst (nach ihrem CLR — hier gedruckt waere es unsichtbar). */
    BT(5); repl();
    return 0;
#else
    {
        const char *s1 = "(+ 1 2)";
        obj e1 = read_expr(&s1);
        emit_str("lisp65 print: ");
        print_obj(e1);
        emit('\n');
    }
    {
        const char *s2 = "((lambda (x) (* x x)) 6)";
        obj r = eval(read_expr(&s2));
        emit_str("lisp65 eval: ");
        print_obj(r);                    /* erwartet: 36 */
        emit('\n');
    }

#ifdef LISP65_XEMU_TEST
    emit_test_terminate();
    asm volatile("jmp $a474");           /* C64 BASIC -> READY -> sauberer xemu-Exit */
#endif
    return 0;
#endif /* LISP65_REPL */
}
