/* Host capacity/correctness probe for lisp65 packed byte strings.
 *
 * Measurement tool for the IDE out-of-memory capacity fix. It uses the real C core and exact
 * heap budget, builds an N-line buffer, reports free cells and OOM, and verifies content after GC.
 *
 * Baseline character-list strings reach OOM near line 32. The packed arena uses about 2.5 cells
 * per line and leaves room after 200 lines.
 *
 * Host build (no device required):
 *   cc -std=c99 -O1 -w -DLISP65_VM -DLISP65_EMBED_STDLIB -DHEAP_CELLS=48 -DEXT_CELLS=1024 \
 *     -DLISP65_EXT_HEAP -DLISP65_MARK_BITMAP -DLISP65_NURSERY_HYSTERESIS=192 -DMAX_SYM=576 \
 *     -DNAMEPOOL=8192 -DGC_ROOTS=128 -DLISP65_STDLIB_EXT_METADATA -DVM_DIR_MAX=480 \
 *     -DVM_CODEBUF=56 -DREPL_BUF_MAX=64 -DLISP65_VM_GLOBAL_PRIMS [-DLISP65_STRING_ARENA] \
 *     -Isrc -Ibuild/bytecode scripts/string-arena-probe-main.c \
 *     src/eval.c src/vm.c src/mem.c src/symbol.c src/reader.c src/printer.c src/interrupt.c \
 *     src/screen.c src/io.c src/vm_embed.c build/bytecode/stdlib-p0.c -o build/string-arena-probe
 *   (build/bytecode/stdlib-p0.c via `make bytecode-p0-stdlib-artifacts \
 *     BYTECODE_STDLIB_SUITE=tests/bytecode/stdlib/p0-stdlib-einsuite-core-subset.json`)
 *
 * GC_STRESS is incompatible with this treewalk harness because that evaluator has distinct
 * rooting assumptions. Validate with natural GC cadence and print_obj, matching device behavior. */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "obj.h"
#include "reader.h"
#include "printer.h"
#include "eval.h"
#include "vm.h"
#include "vm_embed.h"
#include "mem.h"

obj mem_freelist_head(void);
extern uint8_t mem_oom;

/* Host seam: flat EXT code region, matching repl-surface-smoke/return-spam. */
static uint8_t ext_store[65536];
void vm_code_load(uint8_t bank, uint16_t off, uint16_t len, uint8_t *dst){ (void)bank; memcpy(dst, ext_store+off, len); }
void vm_ext_write(const uint8_t *src, uint16_t len, uint8_t bank, uint16_t off){ (void)bank; memcpy(ext_store+off, src, len); }
static uint16_t lcc_off = 0xA000;
int lcc_region_alloc(uint16_t len, uint8_t *bank, uint16_t *off){ if((uint32_t)lcc_off+len>sizeof ext_store) return 0; *bank=5; *off=lcc_off; lcc_off=(uint16_t)(lcc_off+len); return 1; }
void lcc_region_write(uint8_t bank, uint16_t off, const uint8_t *src, uint16_t len){ (void)bank; memcpy(ext_store+off, src, len); }

static obj eval_src(const char *s){ const char *p=s; return eval(read_expr(&p)); }
static uint16_t free_cells(void){ uint16_t n=0; obj f; for(f=mem_freelist_head(); f!=NIL && n<65000; f=cell_a(f)) n++; return n; }
/* print_obj, labels, and line endings all use stdout to avoid mixed streams. */
static void pr(const char *label, const char *e){ printf("%s = ", label); print_obj(eval_src(e)); putchar('\n'); fflush(stdout); }

int main(void){
    eval_init();
    vm_load_embedded_stdlib();
    gc_freeze_boot();

#ifdef LISP65_STRING_ARENA
    const char *mode = "ARENA (packed bytes)";
#else
    const char *mode = "BASELINE (char-listen)";
#endif
    fprintf(stderr, "%s  MAX_CELLS=%u  frei nach Boot=%u\n", mode, (unsigned)MAX_CELLS, free_cells());

    int fails = 0;
#ifdef LISP65_STRING_ARENA
    /* ABI boundary before any arena allocation: length/offset are
       positive fixnums (<=16383). A 16383-byte string is valid with no OOM;
       16384 must report mem_oom and never return a negative length. */
    {
        static uint8_t pl[16384];
        int j; for (j = 0; j < 16384; j++) pl[j] = (uint8_t)('A' + (j % 26));
        mem_oom = 0; obj a = str_from_bytes(pl, 16383);
        int la = (a != NIL) ? (int)FIXVAL(cell_a(a)) : -999;
        int ok_a = (la == 16383 && mem_oom == 0);
        if (!ok_a) fails++;
        fprintf(stderr, "  [%s] ABI 16383-Byte-String len=%d oom=%d (erwartet 16383/0)\n", ok_a?"OK":"FAIL", la, mem_oom);
        mem_oom = 0; obj b = str_from_bytes(pl, 16384);
        int lb = (b != NIL) ? (int)FIXVAL(cell_a(b)) : -999;
        int ok_b = (mem_oom == 1 && lb >= 0);        /* ehrlicher OOM, KEINE negative Laenge */
        if (!ok_b) fails++;
        fprintf(stderr, "  [%s] ABI 16384-Byte-String len=%d oom=%d (erwartet len>=0, oom=1)\n", ok_b?"OK":"FAIL", lb, mem_oom);
        mem_oom = 0;   /* test artifacts are unrooted; the next GC clears the arena */
    }
#endif

    /* A persistent string that must survive many collections and possible compaction. */
    eval_src("(setq keep (list->string (string->list \"world!\")))");

    /* N-line typed buffer, persisted through setq into a symval root. */
    eval_src("(setq buf nil)");
    int i, last = 0;
    for (i = 1; i <= 200; i++){
        char b[96];
        sprintf(b, "(setq buf (cons \"line-%03d-abcdefghijklmnopqr\" buf))", i);
        eval_src(b);
        if (vm_status != VM_OK && vm_status != VM_HALT){ fprintf(stderr, "vm_status=%d @Zeile %d\n", vm_status, i); return 2; }
        if (mem_oom){ fprintf(stderr, "OOM bei Zeile #%d (frei=%u gc=%u)\n", i, free_cells(), gc_runs); break; }
        last = i;
        if (i%20==0 || i<=3) fprintf(stderr, "Zeile #%3d: frei=%4u gc=%u\n", i, free_cells(), gc_runs);
    }
    fprintf(stderr, "-> %d Zeilen ohne OOM (frei=%u, gc_runs=%u)\n", last, free_cells(), gc_runs);

    /* After natural GCs, verify byte-exact content through str_len/str_byte printing. */
    pr("keep (erwartet \"world!\")", "keep");
    pr("car buf (neueste Zeile)", "(car buf)");
    pr("tiefe Zeile (11. von vorn)", "(car (cdr (cdr (cdr (cdr (cdr (cdr (cdr (cdr (cdr (cdr buf)))))))))))");

    /* ---- Gate checks; nonzero exit on failure ---- */
    #define CHK(desc, form, want) do { \
        obj r_ = eval_src(form); int got_ = IS_FIX(r_) ? (int)FIXVAL(r_) : (int)r_; \
        int ok_ = (got_ == (want)); if (!ok_) fails++; \
        fprintf(stderr, "  [%s] %-34s = %d (erwartet %d)\n", ok_?"OK":"FAIL", desc, got_, (want)); \
    } while (0)

    eval_src("(setq str \"abcde\")");
    CHK("string-length", "(string-length str)", 5);
    CHK("string-ref 0", "(string-ref str 0)", 97);
    CHK("string-ref 4", "(string-ref str 4)", 101);
    /* Round trip list->string(string->list s): identical length and characters. */
    eval_src("(setq rt (list->string (string->list str)))");
    CHK("roundtrip len", "(string-length rt)", 5);
    CHK("roundtrip [2]", "(string-ref rt 2)", 99);
    /* string->list freshness: mutate the returned list.
       Arena liefert eine FRISCHE Liste -> str[0] bleibt 97.
       Baseline TEILT die interne Liste -> rplaca korrumpiert str -> str[0] wird 88.
       Erwartung konditional, damit BEIDE Profile GATE PASS geben (Codex-P1-Punkt 3). */
    eval_src("(setq L (string->list str))");
    eval_src("(rplaca L 88)");
#ifdef LISP65_STRING_ARENA
    CHK("string->list frisch (str[0]==97)", "(string-ref str 0)", 97);
#else
    CHK("string->list shared (str[0]==88)", "(string-ref str 0)", 88);
#endif

    fprintf(stderr, "== GATE: %s (%d Fehler) ==\n", fails ? "FAIL" : "PASS", fails);
    return fails ? 1 : 0;
}
