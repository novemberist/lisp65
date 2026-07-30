/* lisp65 — Bytecode-VM (Streaming-Modell). Vertrag: docs/bytecode-abi.md (P0). */
#include "vm.h"
#include "interrupt.h"   /* lisp_poll (RUN/STOP in VM-Schleifen) */
#include "mem.h"
#include "symbol.h"
#include "v2_native_function_dispatch.h"
#ifdef LISP65_C2_PRODUCT_CUT
#include "c2_product_runtime.h"
#include "c2_session_emitter.h"
#endif
#ifdef LISP65_INTERN_SESSION_SERVICE
#include "intern_service_overlay.h"
#include "vm_runtime_overlay.h"
#endif
#if defined(LISP65_FIRST_CLASS_BUFFER) && !defined(LISP65_BUFFER_NO_PRIMS)
#include "buffer_overlay.h"
#ifdef LISP65_RUNTIME_OVERLAY
#include "vm_runtime_overlay.h"
#endif
#endif
#if defined(MEGA65_F011_LOAD) || defined(LISP65_V2_WORKBENCH_SERVICES) || defined(LISP65_V2_TREE_PRIMITIVE_VIEW)
#include "eval.h"        /* load_source for %disk-load-file */
#endif
#if defined(MEGA65_F011_LOAD) || defined(LISP65_C1_COMPILER_TIER)
#include "io.h"
#endif
#if defined(__MEGA65__) || defined(__C64__) || defined(__CBM__)
#define LISP_REAL_MEM 1
#endif
/* The VM screen primitives are deliberately gated separately from the native screen
 * output driver: the core needs scr_init/scr_putc for a hardware-safe REPL, but not
 * the rendering bytecode primitives. */
#ifdef LISP65_VM_SCREEN_PRIMS
#include "screen.h"
#endif

#if defined(LISP65_VM_SCREEN_PRIMS) && (defined(__MEGA65__) || defined(__C64__) || defined(__CBM__))
#define LISP65_VM_REAL_KEYBOARD 1
#ifndef LISP65_C2_KERNAL_UNMAP
#include <cbm.h>
#endif
#endif

#ifdef LISP65_HEARTBEAT   /* Diagnose: Schleifen-Ticker auf Bildschirm-RAM (Zeichen flackern) */
#define HB(i) (++*(volatile unsigned char *)(0x0800 + (i)))
#define LA(c) (*(volatile unsigned char *)(0x0800 + 50) = (unsigned char)(c))
#else
#define HB(i) ((void)0)
#define LA(c) ((void)0)
#endif


uint8_t vm_status = VM_OK;
/* C2 already owns the canonical truth object as eval_init:lisp_t.  Keeping a
 * second VM-only cache made vm_init intern the same name again and retained a
 * second identity derivation in resident text.  Non-C2 compiler-only profiles
 * do not link eval.c, so they retain their private bootstrap cache. */
#ifdef LISP65_C2_PRODUCT_CUT
#define vm_t lisp_t
#else
static obj vm_t = NIL;
#endif
#ifdef LISP65_V2_WORKBENCH_SERVICES
static obj vm_workbench_error_symbols[11];
#endif
#if defined(LISP65_COMPILE_REPL) || defined(LISP65_VM_NATIVE_APPLY) || defined(LISP65_LCC_INSTALL_CLOSURES)
static obj vm_upvals = NIL;   /* M-closures: Upvalue-Liste des aktuell laufenden Closure-Frames (OP_UPVAL liest sie);
                               * von vm_native_apply/vm_apply_bcode_closure um den vm_run des Closure-Rumpfs
                               * gesetzt/wiederhergestellt. */
#endif
#ifdef LISP65_VM_SCREEN_PRIMS
static obj vm_k_key = NIL;
static obj vm_k_shift = NIL, vm_k_control = NIL, vm_k_meta = NIL;
#endif
#ifdef LISP65_VM_DIAGNOSTICS
static obj vm_pending_fn = NIL;
static char vm_diag_msg[128] = "vm: ok";
static uint8_t vm_diag_valid = 0;
#endif

#ifndef VM_CODEBUF
#define VM_CODEBUF 128   /* hot buffer for the code object currently executing; the largest
                          * stdlib object is 114 B -> fast path without windowing; larger
                          * objects run correctly through the window (tested from 16 B up). */
#endif
/* ONE hot buffer. Nested vm_run runs (the CALL/CALLPRIM bridge) overwrite it; after the
 * return the caller reloads header+littab by bulk DMA (reload-on-return).
 * (An earlier depth-parity double buffer saved those reloads, but it was motivated by a DMA
 * hypothesis that hardware refuted; in the tight bank-0 budget the 128 B are worth more than
 * the saved shallow header reloads. Reload DMA is proven uncritical on hardware.) */
static uint8_t vm_codebuf[VM_CODEBUF];
/* OWNER TAG (2026-07-03): which code object is in the buffer? After a call the caller
 * reloads ONLY if another object used the buffer. Leaf calls into C prims (screen-*, car,
 * ...) never touch it -> the reload disappears entirely. Measured on the device:
 * 2405 code DMAs per editor keystroke (~1 s) — most of them unnecessary. */
static uint8_t  vm_buf_bank = 0xFF;
static uint16_t vm_buf_off  = 0xFFFF;

#if defined(VM_STEP_LIMIT) || defined(LISP65_DMA_PROF)
/* Minimal capture on watchdog/error (diagnosis without the heavy LISP65_VM_DIAGNOSTICS
 * module): pc/op = the stuck location, bank/off = code object (function via the manifest). */
volatile uint16_t vm_dbg_pc = 0, vm_dbg_off = 0;   /* volatile: LTO strips write-only objects */
volatile uint8_t  vm_dbg_op = 0, vm_dbg_bank = 0;
#endif

/* Code directory: symbol -> code location (bank/offset/len in extended RAM). */
#ifndef VM_DIR_MAX
#define VM_DIR_MAX 128
#endif
#if defined(LISP65_VM_DIAGNOSTICS) && !defined(LISP65_C2_PRODUCT_CUT)
static obj      dir_sym[VM_DIR_MAX];   /* diagnosis only (vm_pending_fn); resolution: see dir_find */
#endif
#ifndef LISP65_C2_PRODUCT_CUT
/* Bank-0 footprint compressed (2026-07-04, lever-C spike): the code blob lives entirely in
 * ONE EXT bank (~20 KB < 64 KB) -> the bank becomes a single value instead of an array (-238 B).
 * And every code object is <= 255 B (real max 234) -> dir_len as uint8_t (-238 B). Net saving
 * ~476 B of .bss WITHOUT hot-path DMA or cache (the risky EXT relocation is unnecessary).
 * Guards in vm_dir_add reject a multi-bank OR >255-byte blob loudly (instead of truncating
 * silently). */
static uint8_t  dir_bank0 = 0;
/* dir_off SPARSE (2026-07-04, LOAD budget): the blob is contiguous (off[i] = sum(len[0..i-1]),
 * manifest-verified), so store only EVERY 8th offset and reconstruct with <=7 dir_len sums per
 * call (bank-0 arithmetic, NO DMA or cache) -> about -430 B of .bss. A guard in vm_dir_add
 * rejects a non-contiguous blob loudly (instead of mis-addressing silently). */
static uint16_t dir_off_base[(VM_DIR_MAX + 7) / 8];
static uint8_t  dir_len[VM_DIR_MAX];
static uint16_t dir_n = 0;   /* uint16: VM_DIR_MAX may exceed 255 (229 objects since IDE dirty lines) */

/* dir_off[di] rekonstruieren: 8er-Block-Basis + Summe der dir_len bis di. */
static uint16_t dir_off_get(uint16_t di) {
    uint16_t o = dir_off_base[di >> 3], k = (uint16_t)(di & ~7u);
    while (k < di) o = (uint16_t)(o + dir_len[k++]);
    return o;
}

void vm_dir_reset(void) { dir_n = 0; }
uint16_t vm_dir_count(void) { return dir_n; }   /* Diagnose: registrierte Objekte (Objekt-Effizienz) */
uint16_t vm_dir_capacity(void) { return VM_DIR_MAX; }
#ifdef LISP65_C1_COMPILER_TIER
#if defined(__mos__) && defined(LISP65_RUNTIME_OVERLAY)
__attribute__((section(".lisp65_rt_c1_compiler"), noinline))
#endif
uint8_t vm_dir_truncate(uint16_t count) {
    if (count > dir_n) return 0;
    dir_n = count;
    return 1;
}
#endif
int  vm_dir_add(obj sym, uint8_t bank, uint16_t off, uint16_t len) {
    if (dir_n >= VM_DIR_MAX || len > 255) return -1;     /* len>255 / Bank-Wechsel: laut scheitern */
    if (dir_n == 0) dir_bank0 = bank;
    else if (bank != dir_bank0) return -1;
#ifdef LISP65_VM_DIAGNOSTICS
    dir_sym[dir_n] = sym;
#else
    (void)sym;
#endif
    if ((dir_n & 7u) == 0) dir_off_base[dir_n >> 3] = off;   /* Block-Start: Offset speichern */
    else if (off != dir_off_get(dir_n)) {
#if defined(LISP65_DISK_LIBS) || defined(LISP65_COMPILE_REPL)
        /* Base offset (a new code source: disk library behind the trailer, compiled-fn region, ...):
         * instead of failing hard, pad to the next multiple of 8 -> the entry becomes a block start,
         * its base is STORED, and the sparse dir_off reconstruction stays exact. Padding happens only
         * on an actual source change (not per entry); it replaces the callers' manual vm_dir_align8 as
         * the root fix (docs/bank0-full-suite-strategy.md §5-K1). Within one source contiguity remains
         * mandatory (append-only writes guarantee it). Gated: in the default profile (stdlib blob only,
         * no second source) the hard guard stays budget-neutral. */
        vm_dir_align8();
        if (dir_n >= VM_DIR_MAX) return -1;
        dir_off_base[dir_n >> 3] = off;
#else
        return -1;           /* contiguity guard: the blob must be contiguous (no second code source) */
#endif
    }
    dir_len[dir_n] = (uint8_t)len;
    return (int)dir_n++;
}
/* For disk bytecode libraries (docs/disk-bytecode-libs-design.md): pad dir_n to the next 8-entry
 * block boundary (dummy len-0 entries, never reachable through a symbol) -> a loaded library starts
 * as its OWN block, so the sparse dir_off reconstruction stays correct (the library base is NOT
 * part of the stdlib continuum; its block base is set by the first library entry). */
void
#ifdef LISP65_LCC_INSTALL
__attribute__((noinline))
#endif
vm_dir_align8(void) {
    while ((dir_n & 7u) && dir_n < VM_DIR_MAX) dir_len[dir_n++] = 0;
}
#else
/* C2D-v3 is the only directory.  These compatibility entry points remain so
 * generic diagnostics can ask for counts, but no second publisher exists. */
void vm_dir_reset(void) { }
uint16_t vm_dir_count(void) { return c2_product_dir_count(); }
uint16_t vm_dir_capacity(void) { return 2048u; }
int vm_dir_add(obj sym, uint8_t bank, uint16_t off, uint16_t len) {
    (void)sym; (void)bank; (void)off; (void)len; return -1;
}
void vm_dir_align8(void) { }
#endif

static uint16_t vm_directory_length(uint16_t ordinal) {
#ifdef LISP65_C2_PRODUCT_CUT
    return c2_product_entry_length(ordinal);
#else
    return ordinal < dir_n ? dir_len[ordinal] : 0u;
#endif
}

static void vm_directory_address(uint16_t ordinal, uint8_t *bank,
                                 uint16_t *offset) {
#ifdef LISP65_C2_PRODUCT_CUT
    *bank = LISP65_C2_CODE_BANK_TAG; *offset = ordinal;
#else
    *bank = dir_bank0; *offset = dir_off_get(ordinal);
#endif
}

static uint8_t vm_object_load(uint8_t bank, uint16_t object,
                              uint16_t relative, uint16_t length,
                              uint8_t *destination) {
#ifdef LISP65_C2_PRODUCT_CUT
    if (bank == LISP65_C2_CODE_BANK_TAG)
        return c2_product_entry_read(object, relative, destination, length);
#endif
    vm_code_load(bank, (uint16_t)(object + relative), length, destination);
    return 1;
}
/* Callee-Aufloesung O(1) statt linearem dir_sym-Scan (2026-07-02): die Funktionszelle des
 * Symbols traegt den Directory-Index als BCODE-Immediate. Nebenwirkung erwuenscht:
 * REDEFINIERT der Nutzer eine Stdlib-Fn (Closure statt BCODE), greift ab sofort seine
 * Definition (Treewalk-Fallback) — der alte Scan haette stur den Directory-Eintrag genommen. */
static int dir_find(obj sym) {
    obj f = sym_function(sym);
    return IS_BCODE(f) ? (int)BCODE_IDX(f) : -1;
}

#ifdef LISP65_VM_DIAGNOSTICS
static const char *vm_status_name(uint8_t status) {
    switch (status) {
    case VM_OK:        return "ok";
    case VM_HALT:      return "halt";
    case VM_TYPEERROR: return "type error";
    case VM_STACKOVER: return "stack overflow";
    case VM_HEAPOOM:   return "out of memory";
    case VM_DIRMISS:   return "undefined function";
    case VM_STEPLIMIT: return "step limit (watchdog)";
    case VM_ARITY:     return "wrong argument count";
    case VM_NOTDESIGNATOR: return "primitive is not a function designator";
    default:           return "bad bytecode";
    }
}

static char *diag_put(char *p, const char *s) {
    char *end = vm_diag_msg + sizeof(vm_diag_msg) - 1;
    while (*s && p < end) *p++ = *s++;
    *p = 0;
    return p;
}

static char *diag_hex2(char *p, uint8_t v) {
    static const char h[] = "0123456789abcdef";
    char *end = vm_diag_msg + sizeof(vm_diag_msg) - 1;
    if (p < end) *p++ = h[(v >> 4) & 15];
    if (p < end) *p++ = h[v & 15];
    *p = 0;
    return p;
}

static char *diag_hex4(char *p, uint16_t v) {
    p = diag_hex2(p, (uint8_t)(v >> 8));
    return diag_hex2(p, (uint8_t)v);
}

static char *diag_dec(char *p, uint16_t v) {
    char digits[5]; uint8_t n = 0;
    do { digits[n++] = (char)('0' + v % 10u); v = (uint16_t)(v / 10u); } while (v);
    while (n) {
        char one[2]; one[0] = digits[--n]; one[1] = 0; p = diag_put(p, one);
    }
    return p;
}

static void vm_diag_capture(uint8_t status, uint8_t op, uint16_t pc, uint16_t sp, obj fn) {
    char *p = vm_diag_msg;
    p = diag_put(p, "vm: ");
    p = diag_put(p, vm_status_name(status));
    p = diag_put(p, " pc=$");
    p = diag_hex4(p, pc);
    p = diag_put(p, " op=$");
    p = diag_hex2(p, op);
    p = diag_put(p, " sp=$");
    p = diag_hex4(p, sp);
    p = diag_put(p, " fn=");
    if (IS_SYMI(fn) || (IS_PTR(fn) && cell_type(fn) == T_SYM)) p = diag_put(p, symname(fn));
    else if (IS_BCODE(fn)) { p = diag_put(p, "entry #"); p = diag_dec(p, BCODE_IDX(fn)); }
    else p = diag_put(p, "?");
    (void)p;
    vm_diag_valid = 1;
}

const char *vm_status_message(void) {
    if (vm_status == VM_OK || vm_status == VM_HALT) return "vm: ok";
    if (vm_diag_valid) return vm_diag_msg;
    vm_diag_capture(vm_status, 0, 0, 0, NIL);
    return vm_diag_msg;
}
#else
const char *vm_status_message(void) {
    switch (vm_status) {
    case VM_OK:
    case VM_HALT:      return "vm: ok";
    case VM_TYPEERROR: return "vm: type error";
    case VM_STACKOVER: return "vm: stack overflow";
    case VM_HEAPOOM:   return "vm: out of memory";
    case VM_DIRMISS:   return "vm: undefined function";
    case VM_STEPLIMIT: return "vm: step limit (watchdog)";
    case VM_ARITY:     return "vm: wrong argument count";
    case VM_NOTDESIGNATOR: return "vm: primitive is not a function designator";
    default:           return "vm: bad bytecode";
    }
}
#endif

lisp65_error_code vm_status_error_code(uint8_t status) {
    uint8_t offset;

    /* Link-only evidence remains explicit even though both enums are contiguous. */
    LISP65_ERROR_EMISSION_MARK(LISP65_ERR_VM_TYPE);
    LISP65_ERROR_EMISSION_MARK(LISP65_ERR_VM_STACK);
    LISP65_ERROR_EMISSION_MARK(LISP65_ERR_VM_OOM);
    LISP65_ERROR_EMISSION_MARK(LISP65_ERR_VM_UNDEFINED_FUNCTION);
    LISP65_ERROR_EMISSION_MARK(LISP65_ERR_VM_STEP_LIMIT);
    LISP65_ERROR_EMISSION_MARK(LISP65_ERR_VM_BAD_BYTECODE);
    LISP65_ERROR_EMISSION_MARK(LISP65_ERR_WRONG_ARGUMENT_COUNT);
    LISP65_ERROR_EMISSION_MARK(LISP65_ERR_VM_PRIMITIVE_NOT_DESIGNATOR);

    if (status == VM_ARITY) return LISP65_ERR_WRONG_ARGUMENT_COUNT;
    if (status == VM_NOTDESIGNATOR) return LISP65_ERR_VM_PRIMITIVE_NOT_DESIGNATOR;

    offset = (uint8_t)(status - VM_TYPEERROR);
    if (offset <= (VM_STEPLIMIT - VM_TYPEERROR))
        return (lisp65_error_code)(LISP65_ERR_VM_TYPE + offset);
    return LISP65_ERR_VM_BAD_BYTECODE;
}

/* Permanent status-plus-detail seam.  Keep this out of line so every producer
 * shares one status write and cannot grow a private diagnostic convention. */
__attribute__((noinline))
obj vm_dirmiss_detail(obj detail) {
    vm_status = VM_DIRMISS;
    return detail;
}

/* Bridge VM -> tree walker (K3): set by eval.c for CALL misses (symbol not compiled).
 * NULL = no bridge (a miss becomes VM_DIRMISS). */
#ifndef LISP65_V2_CARRIER_CUT
obj (*vm_treewalk_call)(obj sym, const obj *args, uint8_t n) = 0;

/* Bridge fuer apply/funcall (Prim 7/8): ruft den Tree-Walker-apply mit fn + fertiger Arg-Liste. */
obj (*vm_treewalk_apply)(obj fn, obj arglist) = 0;
#endif

/* Lauf per Directory-Index (Bridge Tree-Walker -> VM, aus apply). */
obj vm_run_dir(int di, const obj *args, uint8_t n) {
    uint16_t length;
    uint8_t bank; uint16_t offset;
    if (di < 0 || !(length = vm_directory_length((uint16_t)di))) {
#ifdef LISP65_VM_DIAGNOSTICS
        vm_diag_capture(VM_DIRMISS, 0, 0, 0, NIL);
#endif
        return vm_dirmiss_detail(
            (di >= 0 && (uint16_t)di < 4096u) ? MK_BCODE((uint16_t)di) : NIL);
    }
#ifdef LISP65_VM_DIAGNOSTICS
#ifdef LISP65_C2_PRODUCT_CUT
    vm_pending_fn = MK_BCODE(di);
#else
    vm_pending_fn = dir_sym[di] != NIL ? dir_sym[di] : MK_BCODE(di);
#endif
#endif
    vm_directory_address((uint16_t)di, &bank, &offset);
    return vm_run(bank, offset, length, args, n);
}

#if defined(LISP65_COMPILE_REPL) || defined(LISP65_VM_NATIVE_APPLY) || defined(LISP65_LCC_INSTALL_CLOSURES)
obj vm_apply_bcode_closure(obj fn, obj arglist) {
    obj argv[VM_MAXARGS], p, saved, res;
    uint8_t na = 0;
    if (!IS_PTR(fn) || cell_type(fn) != T_CLOSURE || !IS_BCODE(cell_a(fn))) {
        vm_status = VM_TYPEERROR;
        return NIL;
    }
    for (p = arglist; IS_PTR(p) && cell_type(p) == T_CONS; p = cell_b(p)) {
        if (na >= VM_MAXARGS) { vm_status = VM_TYPEERROR; return NIL; }
        argv[na++] = cell_a(p);
    }
    if (p != NIL) { vm_status = VM_TYPEERROR; return NIL; }
    saved = vm_upvals;
    vm_upvals = cell_b(fn);
    GC_PUSH(fn);                         /* fn haelt die Upvalues waehrend vm_run lebendig. */
    res = vm_run_dir((int)BCODE_IDX(cell_a(fn)), argv, na);
    GC_POPN(1);
    vm_upvals = saved;
    return res;
}

/* Closure-Opcode-Helfer, aus dem vm_run-Switch EXTRAHIERT (2026-07-06, Lane K): die drei Cases
 * inline kosteten +929 B (~310 B/Case durch die Switch-Codegen des riesigen vm_run); als eigene
 * Funktionen kosten sie nur sich selbst und machen die lcc-Closures im Ein-Suite-Profil bezahlbar.
 * Operieren auf dem globalen VM-Stack (= gc_rootstack/gc_rootsp) + vm_upvals. */
static obj vm_upval_nth(uint8_t i) {                 /* i-te Upvalue-Listenzelle (nil-sicher) */
    obj u = vm_upvals;
    while (i && IS_PTR(u) && cell_type(u) == T_CONS) { u = cell_b(u); i--; }
    return u;
}
/* OP_CLOSURE: T_CLOSURE{a=MK_BCODE(di), b=(uv0..uvN-1)} aus nuv Stack-Werten bauen + pushen.
 * NIL = Erfolg; ein Fehler liefert sein Detail (nur VM_DIRMISS ist benannt).
 * GC-Semantik identisch zum alten Inline-Case. */
static obj vm_op_closure(obj sym, uint8_t nuv, uint16_t stack_base) {
    obj lst = NIL, clo; uint8_t k;
    int di = IS_BCODE(sym) ? (int)BCODE_IDX(sym) : dir_find(sym);
    if (di < 0) return vm_dirmiss_detail(sym);
    for (k = 0; k < nuv; k++) {                       /* letzter zuerst poppen -> Liste (uv0..) */
        if (gc_rootsp <= stack_base) { vm_status = VM_BADOPCODE; return NIL; }
        obj v = gc_rootstack[--gc_rootsp];
        lst = cons(v, lst);
        if (lst == NIL) { vm_status = VM_HEAPOOM; return NIL; }
    }
    GC_PUSH(lst); clo = alloc(T_CLOSURE); GC_POPN(1);
    if (clo == NIL) { vm_status = VM_HEAPOOM; return NIL; }
    cell_set_a(clo, MK_BCODE(di)); cell_set_b(clo, lst);
    if (gc_rootsp >= GC_ROOTS) { vm_status = VM_STACKOVER; return NIL; }
    gc_rootstack[gc_rootsp++] = clo;
    return NIL;
}
#endif

/* VM-native apply (M7): fn (a symbol or a BCODE immediate) -> directory index -> vm_run_dir. In the
 * compile-repl world ALL functions are bytecode (no closures), so no tree walk is needed.
 * arglist (a cons list) -> argv[] WITHOUT allocating, so the list stays valid until vm_run (same
 * invariant as the old funcall path: no alloc between building the list and running).
 * Falls back to the tree-walk hook AS LONG AS it exists (M6: closures / per-symbol primitives);
 * without it (M7) a clean VM_TYPEERROR for a non-callable fn -- NEVER VM_BADOPCODE (the minimal
 * contract agreed with Codex). Compiled under LISP65_COMPILE_REPL or the neutral runtime capability
 * LISP65_VM_NATIVE_APPLY; the workbench default is unchanged. */
#if defined(LISP65_COMPILE_REPL) || defined(LISP65_VM_NATIVE_APPLY)
static obj vm_fixbinop(uint8_t op, obj a, obj b);        /* definitions further below */
static obj vm_callprim(uint8_t pid, obj *a, uint8_t n);
#ifndef VM_APPLY_MAXARGS
#ifdef LISP65_VM_NATIVE_APPLY
#define VM_APPLY_MAXARGS VM_MAXARGS
#else
#define VM_APPLY_MAXARGS 8
#endif
#endif

#if defined(LISP65_DIALECT_V2) && defined(LISP65_VM_APPLY_OPFN)
static int vm_apply_opfn(uint8_t k, obj *argv, uint8_t na, obj *out) {
    if (k <= 4) {
        obj a0;
        if (na != 1) { vm_status = VM_TYPEERROR; *out = NIL; return 1; }
        a0 = argv[0];
        if (k == 4)      *out = (a0 == NIL) ? vm_t : NIL;
        else if (k == 3) *out = (IS_PTR(a0) && cell_type(a0) == T_CONS) ? vm_t : NIL;
        else if (!IS_PTR(a0)) *out = NIL;
        else             *out = (k == 1) ? cell_a(a0) : cell_b(a0);
        return 1;
    }
    if (na != 2) { vm_status = VM_TYPEERROR; *out = NIL; return 1; }
    if (k == 5) { *out = cons(argv[0], argv[1]); return 1; }
    if (k == 6) { *out = (argv[0] == argv[1]) ? vm_t : NIL; return 1; }
    if (!IS_FIX(argv[0]) || !IS_FIX(argv[1])) {
        vm_status = VM_TYPEERROR; *out = NIL; return 1;
    }
    if (k == 11) { *out = FIXVAL(argv[0]) <= FIXVAL(argv[1]) ? vm_t : NIL; return 1; }
    if (k == 12) { *out = FIXVAL(argv[0]) >= FIXVAL(argv[1]) ? vm_t : NIL; return 1; }
    *out = vm_fixbinop(k == 9 ? OP_REMAINDER :
                       (k == 10 ? OP_MOD : (k == 7 ? OP_LESS : OP_GREATER)),
                       argv[0], argv[1]);
    return 1;
}
#endif

/* Native Funktionsdesignatoren werden aus derselben Registry erzeugt wie das
 * Paritaets- und Drei-Wege-Gate. Neue Eintraege koennen deshalb nicht mehr in
 * der Registry landen, ohne zugleich Teil dieses Dispatches zu werden. */
static int vm_apply_primitive(obj sym, obj *argv, uint8_t na, obj *out) {
#ifdef LISP65_DIALECT_V2
#ifndef LISP65_V2_TREE_PRIMITIVE_VIEW
    static const struct { const char *name; uint8_t value; } generated_callprim[] = {
#define V2_CALLPRIM_NAME(name, value) {name, value},
        LISP65_V2_NATIVE_FUNCTION_CALLPRIM_ROWS(V2_CALLPRIM_NAME)
#undef V2_CALLPRIM_NAME
    };
    static const struct { const char *name; uint8_t value; } generated_opfn[] = {
#define V2_OPFN_NAME(name, value) {name, value},
        LISP65_V2_NATIVE_FUNCTION_OPFN_ROWS(V2_OPFN_NAME)
#undef V2_OPFN_NAME
    };
    static const char *const generated_exclusions[] = {
#define V2_EXCLUDED_NAME(name, value) name,
        LISP65_V2_NATIVE_FUNCTION_EXCLUSION_ROWS(V2_EXCLUDED_NAME)
#undef V2_EXCLUDED_NAME
    };
#endif
    typedef char dispatch_parity[
        (LISP65_V2_NATIVE_FUNCTION_FOLD_IDENTITY_COUNT +
         LISP65_V2_NATIVE_FUNCTION_FOLD_REQUIRED_COUNT +
         LISP65_V2_NATIVE_FUNCTION_CALLPRIM_COUNT +
         LISP65_V2_NATIVE_FUNCTION_OPFN_COUNT +
         LISP65_V2_NATIVE_FUNCTION_BOUNDP_COUNT ==
         LISP65_V2_NATIVE_FUNCTION_COUNT) ? 1 : -1
    ];
#else
    static const struct { const char *name; uint8_t pid; } legacy_primfn[] = {
        {"stringp",0},{"string->list",1},{"list->string",2},
        {"string-length",3},{"string-ref",4},{"symbolp",5},{"numberp",6},
    };
#endif
    uint8_t i;
#ifdef LISP65_DIALECT_V2
    uint8_t native_kind = 0, native_value = 0;
    int8_t native_view;
    (void)sizeof(dispatch_parity);
#ifdef LISP65_V2_TREE_PRIMITIVE_VIEW
    native_view = eval_v2_native_function_view(sym, &native_kind, &native_value);
#else
    native_view = 0;
    if (LISP65_V2_NATIVE_FUNCTION_FOLD_IDENTITY_MATCH(sym)) {
        native_kind = LISP65_V2_NATIVE_KIND_FOLD_IDENTITY;
        native_value = LISP65_V2_NATIVE_FUNCTION_FOLD_IDENTITY_VALUE(sym);
        native_view = 1;
    } else if (LISP65_V2_NATIVE_FUNCTION_FOLD_REQUIRED_MATCH(sym)) {
        native_kind = LISP65_V2_NATIVE_KIND_FOLD_REQUIRED;
        native_value = LISP65_V2_NATIVE_FUNCTION_FOLD_REQUIRED_VALUE(sym);
        native_view = 1;
    } else {
        for (i = 0; i < (uint8_t)(sizeof(generated_callprim) / sizeof(generated_callprim[0])); i++)
            if (sym == intern(generated_callprim[i].name)) {
                native_kind = LISP65_V2_NATIVE_KIND_CALLPRIM;
                native_value = generated_callprim[i].value;
                native_view = 1;
                break;
            }
        if (!native_view) {
            for (i = 0; i < (uint8_t)(sizeof(generated_opfn) / sizeof(generated_opfn[0])); i++)
                if (sym == intern(generated_opfn[i].name)) {
                    native_kind = LISP65_V2_NATIVE_KIND_OPFN;
                    native_value = generated_opfn[i].value;
                    native_view = 1;
                    break;
                }
        }
    }
    if (!native_view) {
        for (i = 0; i < (uint8_t)(sizeof(generated_exclusions) / sizeof(generated_exclusions[0])); i++)
            if (sym == intern(generated_exclusions[i])) {
                vm_status = VM_NOTDESIGNATOR;
                *out = NIL;
                return 1;
            }
    }
#endif
    if (native_view > 0 && native_kind == LISP65_V2_NATIVE_KIND_FOLD_IDENTITY) {
        uint8_t op = native_value;
        obj acc = MKFIX(op == OP_MUL ? 1 : 0);
        for (i = 0; i < na; i++) {
            if (!IS_FIX(argv[i])) { vm_status = VM_TYPEERROR; *out = NIL; return 1; }
            acc = vm_fixbinop(op, acc, argv[i]);
        }
        *out = acc; return 1;
    }
    if (native_view > 0 && native_kind == LISP65_V2_NATIVE_KIND_FOLD_REQUIRED) {
        uint8_t op = native_value;
        obj acc;
        if (na < 1 || !IS_FIX(argv[0])) { vm_status = VM_TYPEERROR; *out = NIL; return 1; }
        acc = argv[0];
        for (i = 1; i < na; i++) {
            if (!IS_FIX(argv[i])) { vm_status = VM_TYPEERROR; *out = NIL; return 1; }
            acc = vm_fixbinop(op, acc, argv[i]);
        }
        *out = acc; return 1;
    }
    if (native_view > 0 && native_kind == LISP65_V2_NATIVE_KIND_CALLPRIM) {
        *out = vm_callprim(native_value, argv, na); return 1;
    }
#ifdef LISP65_VM_APPLY_OPFN
    if (native_view > 0 && native_kind == LISP65_V2_NATIVE_KIND_OPFN)
        return vm_apply_opfn(native_value, argv, na, out);
#define V2_INTRINSIC_ALIAS(name, value) \
    if (sym == intern(name)) return vm_apply_opfn((uint8_t)(value), argv, na, out);
    LISP65_V2_NATIVE_FUNCTION_INTRINSIC_ALIAS_ROWS(V2_INTRINSIC_ALIAS)
#undef V2_INTRINSIC_ALIAS
#endif
    if (native_view < 0) {
        vm_status = VM_NOTDESIGNATOR; *out = NIL; return 1;
    }
#else
    if (sym == intern("+") || sym == intern("*")) {
        uint8_t op = (sym == intern("*")) ? OP_MUL : OP_ADD;
        obj acc = MKFIX((sym == intern("*")) ? 1 : 0);
        for (i = 0; i < na; i++) {
            if (!IS_FIX(argv[i])) { vm_status = VM_TYPEERROR; *out = NIL; return 1; }
            acc = vm_fixbinop(op, acc, argv[i]);
        }
        *out = acc; return 1;
    }
    if (sym == intern("-") || sym == intern("/")) {
        uint8_t op = (sym == intern("/")) ? OP_DIV : OP_SUB;
        obj acc;
        if (na < 1 || !IS_FIX(argv[0])) { vm_status = VM_TYPEERROR; *out = NIL; return 1; }
        acc = argv[0];
        for (i = 1; i < na; i++) {
            if (!IS_FIX(argv[i])) { vm_status = VM_TYPEERROR; *out = NIL; return 1; }
            acc = vm_fixbinop(op, acc, argv[i]);
        }
        *out = acc; return 1;
    }
    for (i = 0; i < (uint8_t)(sizeof(legacy_primfn) / sizeof(legacy_primfn[0])); i++)
        if (sym == intern(legacy_primfn[i].name)) {
            *out = vm_callprim(legacy_primfn[i].pid, argv, na); return 1;
        }
#endif
#if !defined(LISP65_DIALECT_V2) && defined(LISP65_VM_APPLY_OPFN)
    {
        static const struct { const char *name; uint8_t k; } opfn[] = {
            {"car",1},{"cdr",2},{"consp",3},{"not",4},{"null",4},
            {"cons",5},{"eq",6},{"eql",6},{"=",6},{"<",7},{">",8},
            {"remainder",9},{"mod",10},
        };
        for (i = 0; i < (uint8_t)(sizeof(opfn) / sizeof(opfn[0])); i++)
            if (sym == intern(opfn[i].name)) {
                uint8_t k = opfn[i].k;
                if (k <= 4) {
                    obj a0;
                    if (na != 1) { vm_status = VM_TYPEERROR; *out = NIL; return 1; }
                    a0 = argv[0];
                    if (k == 4)      *out = (a0 == NIL) ? vm_t : NIL;
                    else if (k == 3) *out = (IS_PTR(a0) && cell_type(a0) == T_CONS) ? vm_t : NIL;
                    else if (!IS_PTR(a0)) *out = NIL;
                    else             *out = (k == 1) ? cell_a(a0) : cell_b(a0);
                    return 1;
                }
                if (na != 2) { vm_status = VM_TYPEERROR; *out = NIL; return 1; }
                if (k == 5) { *out = cons(argv[0], argv[1]); return 1; }
                if (k == 6) { *out = (argv[0] == argv[1]) ? vm_t : NIL; return 1; }
                if (!IS_FIX(argv[0]) || !IS_FIX(argv[1])) { vm_status = VM_TYPEERROR; *out = NIL; return 1; }
                *out = vm_fixbinop(k == 9 ? OP_REMAINDER : (k == 10 ? OP_MOD : (k == 7 ? OP_LESS : OP_GREATER)),
                                   argv[0], argv[1]);
                return 1;
            }
    }
#endif
    return 0;
}

/* Shared array-based native call path. vm_native_apply is only the list adapter;
 * CALLPRIM apply/funcall can already pass flat arguments directly, without a
 * temporary cons list. */
#ifdef LISP65_V2_CARRIER_CUT
static obj vm_native_call(obj fn, obj *argv, uint8_t na) {
    obj result = NIL;
    int di, is_sym = IS_SYMI(fn) || (IS_PTR(fn) && cell_type(fn) == T_SYM);
    if (na > VM_APPLY_MAXARGS) { vm_status = VM_TYPEERROR; return NIL; }
    if (IS_PTR(fn) && cell_type(fn) == T_CLOSURE) {
        obj saved = vm_upvals;
        if (!IS_BCODE(cell_a(fn))) {
            vm_status = VM_TYPEERROR; return NIL;
        }
        vm_upvals = cell_b(fn);
        GC_PUSH(fn);
        result = vm_run_dir((int)BCODE_IDX(cell_a(fn)), argv, na);
        GC_POPN(1);
        vm_upvals = saved;
        return result;
    }
    di = IS_BCODE(fn) ? (int)BCODE_IDX(fn) : (is_sym ? dir_find(fn) : -1);
    if (di >= 0) return vm_run_dir(di, argv, na);
    if (is_sym && vm_apply_primitive(fn, argv, na, &result)) return result;
    vm_status = VM_TYPEERROR;
    return NIL;
}
#endif

obj vm_native_apply(obj fn, obj arglist) {
    obj argv[VM_APPLY_MAXARGS], p;
    uint8_t na = 0;
#ifndef LISP65_V2_CARRIER_CUT
    obj r;
    int di, is_sym = IS_SYMI(fn) || (IS_PTR(fn) && cell_type(fn) == T_SYM);
#endif
    for (p = arglist; IS_PTR(p) && cell_type(p) == T_CONS; p = cell_b(p)) {  /* arglist -> argv[] */
        if (na >= VM_APPLY_MAXARGS) { vm_status = VM_TYPEERROR; return NIL; } /* zu viele Args */
        argv[na++] = cell_a(p);
    }
    if (p != NIL) { vm_status = VM_TYPEERROR; return NIL; }
#ifdef LISP65_V2_CARRIER_CUT
    return vm_native_call(fn, argv, na);
#else
    if (IS_PTR(fn) && cell_type(fn) == T_CLOSURE) {
        obj saved = vm_upvals, result;
        if (!IS_BCODE(cell_a(fn))) { vm_status = VM_TYPEERROR; return NIL; }
        vm_upvals = cell_b(fn);
        GC_PUSH(fn);
        result = vm_run_dir((int)BCODE_IDX(cell_a(fn)), argv, na);
        GC_POPN(1);
        vm_upvals = saved;
        return result;
    }
    di = IS_BCODE(fn) ? (int)BCODE_IDX(fn) : (is_sym ? dir_find(fn) : -1);
    if (di >= 0) return vm_run_dir(di, argv, na);
    if (is_sym && vm_apply_primitive(fn, argv, na, &r)) return r;
    if (vm_treewalk_apply) return vm_treewalk_apply(fn, arglist);   /* M6-Fallback (Closure) */
    vm_status = VM_TYPEERROR; return NIL;                           /* M7: nicht aufrufbar (kein BADOPCODE) */
#endif
}
#endif /* LISP65_COMPILE_REPL || LISP65_VM_NATIVE_APPLY */

void vm_init(void) {
    vm_t = intern("t");
#ifdef LISP65_V2_WORKBENCH_SERVICES
    vm_workbench_error_symbols[0] = intern("%fasl-error-entries-overflow");
    vm_workbench_error_symbols[1] = intern("%fasl-error-nodes-overflow");
    vm_workbench_error_symbols[2] = intern("%fasl-error-not-a-defun");
    vm_workbench_error_symbols[3] = intern("%fasl-error-output-overflow");
    vm_workbench_error_symbols[4] = intern("%fasl-error-patches-overflow");
    vm_workbench_error_symbols[5] = intern("%fasl-error-strings-overflow");
    vm_workbench_error_symbols[6] = intern("%fasl-error-too-many-helpers");
    vm_workbench_error_symbols[7] = intern("%fasl-error-unsupported-literal");
    vm_workbench_error_symbols[8] = intern("%fasl-error-window-overflow");
    vm_workbench_error_symbols[9] = intern("%lcc-error-do-body-too-big");
    vm_workbench_error_symbols[10] = intern("%lcc-error-invalid-parameter-list");
#endif
#ifdef LISP65_VM_SCREEN_PRIMS
    vm_k_key = intern("key");
    vm_k_shift = intern("shift");
    vm_k_control = intern("control");
    vm_k_meta = intern("meta");
#endif
}

#ifdef LISP65_VM_SCREEN_PRIMS
/* Gleiches Eventformat wie eval.c:key_event: (key code mods). */
static obj vm_key_event(int c, uint8_t event_modifiers) {
    obj mods = NIL, e;
    if (c >= 0xC1 && c <= 0xDA) { c -= 0x80; event_modifiers |= LISP65_KEYMOD_SHIFT; }
    else if (c >= 'A' && c <= 'Z') c += 0x20;
    if (event_modifiers & LISP65_KEYMOD_SHIFT) mods = cons(vm_k_shift, mods);
    if (event_modifiers & LISP65_KEYMOD_CONTROL) mods = cons(vm_k_control, mods);
    if (event_modifiers & LISP65_KEYMOD_META) mods = cons(vm_k_meta, mods);
    GC_PUSH(mods);
    e = cons(gc_rootstack[GC_TOP], NIL);
    GC_SET(GC_TOP, e);
    e = cons(MKFIX((int16_t)c), gc_rootstack[GC_TOP]);
    GC_SET(GC_TOP, e);
    e = cons(vm_k_key, gc_rootstack[GC_TOP]);
    GC_POPN(1);
    return e;
}
#endif

/* Fixnum-Binop-Kern (Diaet 2026-07-02, noinline): die 7 Arith-/Vergleichs-Ops inline in
 * vm_run kosteten ~275 B/Stueck (MUL/DIV ziehen die Soft-Routinen in die Cases!) —
 * gruppiert + ausgelagert einmalig. Typecheck (NEEDFIX2) macht der Aufrufer. */
#if defined(LISP65_MEGA65_MATH_OVERRIDE)
extern obj lisp65_mod_adjust_tagged(obj remainder, obj divisor);
#define vm_mod_adjust lisp65_mod_adjust_tagged
#else
static __attribute__((noinline)) obj vm_mod_adjust(obj remainder, obj divisor) {
    if (remainder != MKFIX(0) && (int16_t)(remainder ^ divisor) < 0)
        return (obj)(remainder + divisor - 1);
    return remainder;
}
#endif

#if defined(LISP65_MEGA65_MATH_OVERRIDE)
extern obj lisp65_ash_tagged(obj value, obj count);
#else
static __attribute__((noinline)) obj lisp65_ash_tagged(obj a, obj b) {
    int16_t x = FIXVAL(a), y = FIXVAL(b);
    uint8_t shift;
    if (y < -14 || y > 14) { vm_status = VM_TYPEERROR; return NIL; }
    if (y < 0) return MKFIX((int16_t)(x >> (uint8_t)(-y)));
    shift = (uint8_t)y;
    while (shift--) {
        if (x < -8192 || x > 8191) {
            vm_status = VM_TYPEERROR;
            return NIL;
        }
        x = (int16_t)(x << 1);
    }
    return MKFIX(x);
}
#endif

static __attribute__((noinline)) obj vm_fixbinop(uint8_t op, obj a, obj b) {
    int16_t x = FIXVAL(a), y = FIXVAL(b);
    if (op == OP_ASH) return lisp65_ash_tagged(a, b);
    if (op == OP_LOGAND) return (obj)(a & b);
    if (op == OP_LOGIOR) return (obj)(a | b);
    if (op == OP_LOGXOR) return (obj)((a ^ b) | 1u);
    switch (op) {
    case OP_ADD: return MKFIX(x + y);
    case OP_SUB: return MKFIX(x - y);
    case OP_MUL: return MKFIX(x * y);
    case OP_DIV: if (y == 0) { vm_status = VM_TYPEERROR; return NIL; } return MKFIX(x / y);
    case OP_REMAINDER: if (y == 0) { vm_status = VM_TYPEERROR; return NIL; } return MKFIX(x % y);
    case OP_MOD: if (y == 0) { vm_status = VM_TYPEERROR; return NIL; }
                 return vm_mod_adjust(MKFIX(x % y), b);
    case OP_LESS: return x < y ? vm_t : NIL;
    default:      return x > y ? vm_t : NIL;   /* OP_GREATER */
    }
}

#ifdef LISP65_V2_WORKBENCH_SERVICES
#ifndef LISP65_DIALECT_V2
#error "LISP65_V2_WORKBENCH_SERVICES requires LISP65_DIALECT_V2"
#endif
/* Direct constant branches keep the error identities visible to the product
 * emission gate. vm_init resolves the diagnostic symbols before execution, so
 * the error path performs neither heap nor symbol/name-pool allocation. */
static obj vm_workbench_compile_error(uint8_t pid) {
    switch (pid) {
    case 46:
        lisp_abort_static_symbol(LISP65_ERR_FASL_ENTRIES_OVERFLOW,
            vm_workbench_error_symbols[0], "compile failed"); break;
    case 47:
        lisp_abort_static_symbol(LISP65_ERR_FASL_NODES_OVERFLOW,
            vm_workbench_error_symbols[1], "compile failed"); break;
    case 48:
        lisp_abort_static_symbol(LISP65_ERR_FASL_NOT_A_DEFUN,
            vm_workbench_error_symbols[2], "compile failed"); break;
    case 49:
        lisp_abort_static_symbol(LISP65_ERR_FASL_OUTPUT_OVERFLOW,
            vm_workbench_error_symbols[3], "compile failed"); break;
    case 50:
        lisp_abort_static_symbol(LISP65_ERR_FASL_PATCHES_OVERFLOW,
            vm_workbench_error_symbols[4], "compile failed"); break;
    case 51:
        lisp_abort_static_symbol(LISP65_ERR_FASL_STRINGS_OVERFLOW,
            vm_workbench_error_symbols[5], "compile failed"); break;
    case 52:
        lisp_abort_static_symbol(LISP65_ERR_FASL_TOO_MANY_HELPERS,
            vm_workbench_error_symbols[6], "compile failed"); break;
    case 53:
        lisp_abort_static_symbol(LISP65_ERR_FASL_UNSUPPORTED_LITERAL,
            vm_workbench_error_symbols[7], "compile failed"); break;
    case 54:
        lisp_abort_static_symbol(LISP65_ERR_FASL_WINDOW_OVERFLOW,
            vm_workbench_error_symbols[8], "compile failed"); break;
    case 55:
        lisp_abort_static_symbol(LISP65_ERR_LCC_DO_BODY_TOO_BIG,
            vm_workbench_error_symbols[9], "compile failed"); break;
    case 56:
        lisp_abort_static_symbol(LISP65_ERR_LCC_INVALID_PARAMETER_LIST,
            vm_workbench_error_symbols[10], "compile failed"); break;
    default:
        vm_status = VM_BADOPCODE; break;
    }
    return NIL;
}
#endif

/* CALLPRIM-Dispatch: gefrorene Prim-ID (§4a) -> VM-native Implementierung. */
/* noinline (Diaet 2026-07-02): inline in vm_run kostete 1752 B, out-of-line 1506 —
 * netto -246 B .text; CALLPRIM ist ohnehin ein Bridge-/Stringpfad, kein Zyklenzaehlen. */
#ifdef LISP65_DIALECT_V2
#if defined(LISP65_C2_KERNAL_UNMAP) && \
    defined(LISP65_C2_LITE_CHIP_RAM)
/* Post-ownership hot leaf.  The complete C2-lite execution path owns the
 * KERNAL window before CALLPRIM can run.  This helper has no outbound
 * control-flow edge; it only reads its arguments and writes vm_status on a
 * rejected byte-domain value.  Keeping it in the existing C2-resident slab
 * restores the contracted Bank-0 LTO-noise reserve without a new facade
 * vector, section, state cell, or pre-ownership dependency. */
#define VM_BYTE_ARGS_FN __attribute__((noinline, \
    section(".lisp65_c2_kernal_window.c2_resident")))
#else
#define VM_BYTE_ARGS_FN __attribute__((noinline))
#endif
static VM_BYTE_ARGS_FN uint8_t
vm_byte_args(obj *a, uint8_t n, uint8_t expected) {
    uint8_t i;
    if (n != expected) { vm_status = VM_ARITY; return 0; }
    for (i = 0; i < n; i++) {
        if (!IS_FIX(a[i]) || (uint16_t)FIXVAL(a[i]) > 255u) {
            vm_status = VM_TYPEERROR; return 0;
        }
    }
    return 1;
}
#undef VM_BYTE_ARGS_FN

#if defined(LISP65_INTERN_SESSION_SERVICE) || \
    defined(LISP65_V2_NATIVE_STRING_CODECS)
/* Prim 0 and Prim 68 share one resident string-domain truth.  Keeping the
 * extended-heap-aware cell_type expansion out of both switch arms is the
 * capacity condition that lets the operation-specific conversion remain a
 * single cold Session-service record. */
static __attribute__((noinline)) uint8_t vm_string_arg_p(obj value) {
    return IS_PTR(value) && cell_type(value) == T_STR;
}
#endif
#endif

#ifdef LISP65_C2_REQUIRE_RESOLVER
extern obj vm_c2d_byte(obj *args);
#endif

#if defined(LISP65_FIRST_CLASS_BUFFER) && !defined(LISP65_BUFFER_NO_PRIMS)
#ifdef LISP65_C1_COMPILER_TIER
#include "c1_compiler_overlay.h"
#endif
#ifdef LISP65_RUNTIME_OVERLAY
static LISP65_RESIDENT_ISLAND_FN obj vm_buffer_call(
#else
static __attribute__((noinline)) obj vm_buffer_call(
#endif
        uint8_t pid, obj *a, uint8_t n) {
    lisp65_buffer_overlay_context *context =
        (lisp65_buffer_overlay_context *)(void *)vm_codebuf;
    uint8_t slot = (uint8_t)(LISP65_BUFFER_OVERLAY_READ_SLOT +
                             pid - LISP65_BUFFER_PRIM_FIRST);
#ifdef LISP65_INTERN_SESSION_SERVICE
    if (pid == 68u) slot = LISP65_INTERN_SERVICE_SLOT;
#endif
    /* The synchronous overlay context deliberately reuses vm_codebuf.  Retire
     * its owner before the first context byte is written: OP_CALLPRIM's
     * BUF_ENSURE_MINE must reload the caller even when no nested VM invocation
     * changed the ordinary bank/object tag. */
    vm_buf_bank = 0xFFu;
    vm_buf_off = 0xFFFFu;
    context->args = a;
    context->argc = n;
#ifdef LISP65_RUNTIME_OVERLAY
    /* The transport writes ENTRY_NOT_RUN before any fallible step. A failed
     * load therefore leaves vm_status nonzero and all VM callers fail closed;
     * the returned object is ignored whenever vm_status is nonzero. */
    (void)vm_runtime_overlay_exec(slot, context, &vm_status);
#else
    if (slot == LISP65_C1_COMPILER_OVERLAY_SLOT)
        vm_status = lisp65_c1_compiler_overlay_entry(context);
    else if (slot == LISP65_BUFFER_OVERLAY_ALLOC_SLOT)
        vm_status = lisp65_buffer_overlay_alloc_entry(context);
    else if (slot == LISP65_BUFFER_OVERLAY_WRITE_SLOT)
        vm_status = lisp65_buffer_overlay_write_entry(context);
    else vm_status = lisp65_buffer_overlay_read_entry(context);
#endif
    return context->result;
}

#endif

static __attribute__((noinline)) obj vm_callprim(uint8_t pid, obj *a, uint8_t n) {
#ifndef LISP65_STRING_ARENA
    obj cs;
#endif
    int16_t k;
    switch (pid) {
    case 0:
#ifdef LISP65_INTERN_SESSION_SERVICE
        return (n >= 1 && vm_string_arg_p(a[0])) ? vm_t : NIL;          /* stringp */
#else
        return (n >= 1 && IS_PTR(a[0]) && cell_type(a[0]) == T_STR) ? vm_t : NIL;
#endif
    case 5: return (n >= 1 && (IS_SYMI(a[0]) || (IS_PTR(a[0]) && cell_type(a[0]) == T_SYM))) ? vm_t : NIL;  /* symbolp */
    case 6: return (n >= 1 && IS_FIX(a[0])) ? vm_t : NIL;                              /* numberp */
#if defined(LISP65_DIALECT_V2) && defined(LISP65_V2_NATIVE_CAPABILITIES)
    case 1: case 2: case 26: case 27: case 40:
        vm_status = VM_BADOPCODE; return NIL;                       /* v2 tombstones */
#else
    case 1:
        if (n < 1 || !IS_PTR(a[0]) || cell_type(a[0]) != T_STR) { vm_status = VM_TYPEERROR; return NIL; }
#ifdef LISP65_STRING_ARENA
        {   /* string->list: frische Fixnum-Liste aus Arena-Bytes (a[0] rooten: Offset kann per GC wandern) */
            uint16_t l = str_len(a[0]), i; obj lst = NIL;
            GC_PUSH(a[0]); GC_PUSH(NIL);
            for (i = l; i > 0; i--) {
                lst = cons(MKFIX((int16_t)str_byte(a[0], (uint16_t)(i - 1))), gc_rootstack[GC_TOP]);
                GC_SET(GC_TOP, lst);
            }
            GC_POPN(2);
            return lst;
        }
#else
        return cell_a(a[0]);                                                            /* string->list */
#endif
    case 2: {                                                                          /* list->string */
#ifdef LISP65_STRING_ARENA
        obj s;
        if (n < 1) { vm_status = VM_TYPEERROR; return NIL; }
        s = str_from_charlist(a[0]);
        if (s == NIL || mem_oom) vm_status = VM_HEAPOOM;
        return s;
#else
        obj s;
        if (n < 1) { vm_status = VM_TYPEERROR; return NIL; }
        GC_PUSH(a[0]); s = alloc(T_STR); GC_POPN(1);
        if (s == NIL) { vm_status = VM_HEAPOOM; return NIL; }
        cell_set_a(s, a[0]); cell_set_b(s, NIL); return s;
#endif
    }
#endif
    case 3:
        if (n < 1 || !IS_PTR(a[0]) || cell_type(a[0]) != T_STR) { vm_status = VM_TYPEERROR; return NIL; }
#ifdef LISP65_STRING_ARENA
        return MKFIX((int16_t)str_len(a[0]));                                          /* string-length */
#else
        for (k = 0, cs = cell_a(a[0]); IS_PTR(cs) && cell_type(cs) == T_CONS; cs = cell_b(cs)) k++;
        return MKFIX(k);                                                               /* string-length */
#endif
    case 4:
        if (n < 2 || !IS_PTR(a[0]) || cell_type(a[0]) != T_STR || !IS_FIX(a[1])) { vm_status = VM_TYPEERROR; return NIL; }
#ifdef LISP65_STRING_ARENA
        k = FIXVAL(a[1]);
        if (k < 0 || k >= (int16_t)str_len(a[0])) { vm_status = VM_TYPEERROR; return NIL; }
        return MKFIX((int16_t)str_byte(a[0], (uint16_t)k));                            /* string-ref */
#else
        k = FIXVAL(a[1]);
        for (cs = cell_a(a[0]); IS_PTR(cs) && cell_type(cs) == T_CONS && k > 0; cs = cell_b(cs)) k--;
        if (!IS_PTR(cs) || cell_type(cs) != T_CONS) { vm_status = VM_TYPEERROR; return NIL; }
        return cell_a(cs);                                                             /* string-ref */
#endif
#if defined(LISP65_DIALECT_V2) && defined(LISP65_V2_NATIVE_CAPABILITIES)
    case 23: {                                                                         /* nreverse */
        if (n != 1) { vm_status = VM_ARITY; return NIL; }
        return list_nreverse(a[0]);
    }
    case 24:                                                                           /* rplaca */
        if (n != 2) { vm_status = VM_ARITY; return NIL; }
        if (!IS_PTR(a[0]) || cell_type(a[0]) != T_CONS) {
            vm_status = VM_TYPEERROR; return NIL;
        }
        return list_rplaca(a[0], a[1]);
    case 25:                                                                           /* rplacd */
        if (n != 2) { vm_status = VM_ARITY; return NIL; }
        if (!IS_PTR(a[0]) || cell_type(a[0]) != T_CONS) {
            vm_status = VM_TYPEERROR; return NIL;
        }
        return list_rplacd(a[0], a[1]);
#ifdef LISP65_V2_NATIVE_STRING_CODECS
    case 28: {                                                                         /* %string-codes */
        uint16_t l, i; obj lst = NIL;
        if (n != 1) { vm_status = VM_ARITY; return NIL; }
        if (!vm_string_arg_p(a[0])) {
            vm_status = VM_TYPEERROR; return NIL;
        }
        l = str_len(a[0]);
        GC_PUSH(a[0]); GC_PUSH(NIL);
        for (i = l; i > 0; i--) {
            lst = cons(MKFIX((int16_t)str_byte(a[0], (uint16_t)(i - 1))),
                       gc_rootstack[GC_TOP]);
            if (lst == NIL || mem_oom) {
                vm_status = VM_HEAPOOM; GC_POPN(2); return NIL;
            }
            GC_SET(GC_TOP, lst);
        }
        GC_POPN(2);
        return lst;
    }
    case 29: {                                                                         /* %string-from-codes */
        obj result;
        if (n != 1) { vm_status = VM_ARITY; return NIL; }
        result = str_from_charlist(a[0]);
        if (result == NIL || mem_oom) { vm_status = VM_HEAPOOM; return NIL; }
        return result;
    }
#endif
#endif
    case 7: {  /* apply: (fn a1..ak lst) -> Argliste (a1..ak . lst). Compile-REPL: VM-nativ; Default: Treewalk. */
        HB(7);
#if defined(LISP65_COMPILE_REPL) || defined(LISP65_VM_NATIVE_APPLY)
#ifdef LISP65_V2_CARRIER_CUT
        obj argv[VM_APPLY_MAXARGS], p;
        uint8_t i, na = 0;
        if (n < 1) { vm_status = VM_TYPEERROR; return NIL; }
        for (i = 1; i + 1 < n; i++) argv[na++] = a[i];
        p = n > 1 ? a[n - 1] : NIL;
        while (IS_PTR(p) && cell_type(p) == T_CONS) {
            if (na >= VM_APPLY_MAXARGS) { vm_status = VM_TYPEERROR; return NIL; }
            argv[na++] = cell_a(p); p = cell_b(p);
        }
        if (p != NIL) { vm_status = VM_TYPEERROR; return NIL; }
        return vm_native_call(a[0], argv, na);
#else
        uint16_t base = gc_rootsp; uint8_t i; obj lst, fn;
        if (n < 1) { vm_status = VM_TYPEERROR; return NIL; }
        if (n == 1) return vm_native_apply(a[0], NIL);
        for (i = 0; i < n; i++) GC_PUSH(a[i]);             /* fn + Prefix-Args + Liste rooten */
        lst = gc_rootstack[base + n - 1];                 /* letztes Arg = die Liste */
        GC_PUSH(lst);                                     /* Slot fuer die wachsende Argliste */
        for (i = n - 1; i > 1; i--) { lst = cons(gc_rootstack[base + i - 1], lst); GC_SET(gc_rootsp - 1, lst); }
        fn = gc_rootstack[base]; gc_rootsp = base;         /* kein alloc mehr bis apply -> fn/lst sicher */
        return vm_native_apply(fn, lst);
#endif
#else
        if (n < 1 || !vm_treewalk_apply) { vm_status = VM_BADOPCODE; return NIL; }
        return vm_treewalk_apply(a[0], (n >= 2) ? a[1] : NIL);
#endif
    }
    case 8: { /* funcall: (fn a b ...) -> apply(fn, (a b ...)) */
        HB(7);
#ifdef LISP65_V2_CARRIER_CUT
        if (n < 1) { vm_status = VM_TYPEERROR; return NIL; }
        return vm_native_call(a[0], a + 1, (uint8_t)(n - 1));
#else
        uint16_t base = gc_rootsp; uint8_t i; obj lst = NIL, fn;
#if defined(LISP65_COMPILE_REPL) || defined(LISP65_VM_NATIVE_APPLY)
        if (n < 1) { vm_status = VM_TYPEERROR; return NIL; }
#else
        if (n < 1 || !vm_treewalk_apply) { vm_status = VM_BADOPCODE; return NIL; }
#endif
        for (i = 0; i < n; i++) GC_PUSH(a[i]);   /* alle Args rooten (inkl. fn) */
        GC_PUSH(NIL);                             /* Slot fuer lst */
        for (i = n; i > 1; i--) { lst = cons(gc_rootstack[base + i - 1], lst); GC_SET(gc_rootsp - 1, lst); }
        fn = gc_rootstack[base]; gc_rootsp = base;   /* kein alloc mehr bis apply -> fn/lst sicher */
#if defined(LISP65_COMPILE_REPL) || defined(LISP65_VM_NATIVE_APPLY)
        return vm_native_apply(fn, lst);   /* delegiert an apply-Semantik */
#else
        return vm_treewalk_apply(fn, lst);
#endif
#endif
    }
#ifdef LISP65_VM_SCREEN_PRIMS
    case 9: {  /* screen-size */
        obj r;
        if (n != 0) { vm_status = VM_TYPEERROR; return NIL; }
        r = cons(MKFIX((int16_t)scr_rows()), NIL);
        GC_PUSH(r);
        r = cons(MKFIX((int16_t)scr_cols()), gc_rootstack[GC_TOP]);
        GC_POPN(1);
        return r;
    }
    case 10:  /* screen-clear */
        if (n != 0) { vm_status = VM_TYPEERROR; return NIL; }
        scr_clear(); return NIL;
    case 11: {  /* screen-put-char */
        int16_t attr;
        if (n < 3 || n > 4 || !IS_FIX(a[0]) || !IS_FIX(a[1]) || !IS_FIX(a[2]) ||
            (n == 4 && !IS_FIX(a[3]))) { vm_status = VM_TYPEERROR; return NIL; }
        attr = (n == 4) ? FIXVAL(a[3]) : (int16_t)-1;
        scr_put_at((uint8_t)FIXVAL(a[0]), (uint8_t)FIXVAL(a[1]), (char)FIXVAL(a[2]), attr);
        return NIL;
    }
#ifdef LISP65_SCREEN_WRITE_STRING
    case 12: {  /* screen-write-string */
        obj str, cs; char wbuf[80];
        int16_t attr; uint8_t x, y, cnt = 0;
        if (n < 3 || n > 4 || !IS_FIX(a[0]) || !IS_FIX(a[1]) ||
            !IS_PTR(a[2]) || cell_type(a[2]) != T_STR ||
            (n == 4 && !IS_FIX(a[3]))) { vm_status = VM_TYPEERROR; return NIL; }
        x = (uint8_t)FIXVAL(a[0]); y = (uint8_t)FIXVAL(a[1]); str = a[2];
        attr = (n == 4) ? FIXVAL(a[3]) : (int16_t)-1;
#ifdef LISP65_STRING_ARENA
        cnt = (uint8_t)str_copy_out(str, wbuf, 80);
        (void)cs;
#else
        for (cs = cell_a(str); IS_PTR(cs) && cell_type(cs) == T_CONS && cnt < 80; cs = cell_b(cs))
            wbuf[cnt++] = (char)FIXVAL(cell_a(cs));
#endif
        scr_write_span(x, y, wbuf, cnt,
                       (attr >= 0 && (attr & 0x40)) ? scr_cols() : 0,
                       (attr >= 0) ? (attr & ~0x40) : attr);
        return NIL;
    }
#endif
    case 13:  /* read-key */
        if (n != 0) { vm_status = VM_TYPEERROR; return NIL; }
#ifdef LISP65_VM_REAL_KEYBOARD
        {
#ifdef LISP65_C2_KERNAL_UNMAP
            lisp65_key_event event;
            (void)lisp_input_event(1u, 0u, &event);
            return vm_key_event(event.code, event.modifiers);
#else
            int c; do { lisp_poll(); c = cbm_k_getin(); } while (c == 0);
            return vm_key_event(c, 0u);
#endif
        }
#else
        return vm_key_event(0, 0u);
#endif
    case 14:  /* poll-key */
        if (n != 0) { vm_status = VM_TYPEERROR; return NIL; }
#ifdef LISP65_VM_REAL_KEYBOARD
        {
#ifdef LISP65_C2_KERNAL_UNMAP
            lisp65_key_event event;
            return lisp_input_event(0u, 0u, &event)
                ? vm_key_event(event.code, event.modifiers) : NIL;
#else
            int c = cbm_k_getin(); return c == 0 ? NIL : vm_key_event(c, 0u);
#endif
        }
#else
        return NIL;
#endif
#endif /* LISP65_VM_SCREEN_PRIMS */
#ifdef MEGA65_F011_LOAD
    case 15:  /* %disk-read-sector */
        if (n != 2 || !IS_FIX(a[0]) || !IS_FIX(a[1])) { vm_status = VM_TYPEERROR; return NIL; }
        return io_disk_read_sector((uint8_t)FIXVAL(a[0]), (uint8_t)FIXVAL(a[1])) ? vm_t : NIL;
    case 16:  /* %disk-byte */
        if (n != 1 || !IS_FIX(a[0])) { vm_status = VM_TYPEERROR; return NIL; }
        return MKFIX(io_disk_byte((uint8_t)FIXVAL(a[0])));
    case 17:  /* %disk-load-file — io.c streamt die Datei aus EXT via load_source_stream */
        if (n != 2 || !IS_FIX(a[0]) || !IS_FIX(a[1])) { vm_status = VM_TYPEERROR; return NIL; }
        return io_disk_load_chain((uint8_t)FIXVAL(a[0]), (uint8_t)FIXVAL(a[1])) ? vm_t : NIL;
#if defined(LISP65_DISK_LIBS) || defined(LISP65_C2_PRODUCT_CUT)
    case 18:  /* %disk-load-lib — Bytecode-Lib nach Bank 5 stagen + registrieren (Stufe 2) */
#ifdef LISP65_C2_PRODUCT_CUT
        if (n == 1)
            return c2_product_static_image_named(a[0]) ? vm_t : NIL;
        if (n != 2 || !IS_FIX(a[0]) || !IS_FIX(a[1])) {
            vm_status = VM_TYPEERROR; return NIL;
        }
        {
            uint16_t staged = io_disk_stage_chain((uint8_t)FIXVAL(a[0]),
                                                  (uint8_t)FIXVAL(a[1]));
            return staged && c2_product_append_staged(staged) ? vm_t : NIL;
        }
#else
#ifdef LISP65_ATTIC_LIBRARY_SHELF
        if (n == 1) {
            return io_attic_load_lib(a[0]) ? vm_t : NIL;
        }
#endif
        if (n != 2 || !IS_FIX(a[0]) || !IS_FIX(a[1])) { vm_status = VM_TYPEERROR; return NIL; }
        return io_disk_load_lib((uint8_t)FIXVAL(a[0]), (uint8_t)FIXVAL(a[1])) ? vm_t : NIL;
#endif
#endif
#ifdef MEGA65_F011_WRITE
    case 21:  /* %disk-poke */
        io_disk_scratch_poke((uint8_t)FIXVAL(a[0]), (uint8_t)(FIXVAL(a[1]) & 0xFF));
        return a[1];
    case 22:  /* %disk-write-sector */
        if (n == 0) {
            io_disk_transaction_capture_mount_token();
            return MKFIX(0);
        }
        if (n == 1 && IS_FIX(a[0]))
            return MKFIX(io_disk_transaction_classify_status((uint8_t)FIXVAL(a[0])));
        if (n == 2 && IS_FIX(a[0]) && IS_FIX(a[1]))
            return io_disk_write_sector((uint8_t)FIXVAL(a[0]), (uint8_t)FIXVAL(a[1])) ? vm_t : NIL;
        if (n == 3 && IS_FIX(a[0]) && IS_FIX(a[1]) && IS_FIX(a[2]))
            return MKFIX(io_disk_write_sector_guarded(
                (uint8_t)FIXVAL(a[0]), (uint8_t)FIXVAL(a[1])));
        vm_status = VM_TYPEERROR; return NIL;
#endif
#endif
#ifdef LISP65_VM_GLOBAL_PRIMS
    case 19:  /* symbol-value */
        if (n != 1 || !(IS_SYMI(a[0]) || (IS_PTR(a[0]) && cell_type(a[0]) == T_SYM))) { vm_status = VM_TYPEERROR; return NIL; }
        return sym_value(a[0]);
    case 20:  /* set-symbol-value */
        if (n != 2 || !(IS_SYMI(a[0]) || (IS_PTR(a[0]) && cell_type(a[0]) == T_SYM))) { vm_status = VM_TYPEERROR; return NIL; }
        set_sym_value(a[0], a[1]); return a[1];
#endif
#ifdef LISP65_V2_WORKBENCH_SERVICES
    case 30: case 33: case 36: case 39: case 41: case 44: case 45:
        if (n != 1) { vm_status = VM_ARITY; return NIL; }
        {
            obj result = NIL;
            if (!eval_v2_workbench_service(pid, a, &result)) {
                vm_status = VM_BADOPCODE; return NIL;
            }
            return result;
        }
    case 31: case 37: case 42: case 43:
        if (n != 0) { vm_status = VM_ARITY; return NIL; }
        {
            obj result = NIL;
            if (!eval_v2_workbench_service(pid, a, &result)) {
                vm_status = VM_BADOPCODE; return NIL;
            }
            return result;
        }
    case 32: case 34: case 35: case 38:
        if (n != 2) { vm_status = VM_ARITY; return NIL; }
        {
            obj result = NIL;
            if (!eval_v2_workbench_service(pid, a, &result)) {
                vm_status = VM_BADOPCODE; return NIL;
            }
            return result;
        }
    case 46: case 47: case 48: case 49: case 50:
    case 51: case 52: case 53: case 54: case 55:
    case 56:
        if (n != 0) { vm_status = VM_ARITY; return NIL; }
        return vm_workbench_compile_error(pid);
#endif
#ifdef LISP65_DIALECT_V2
    case 57: /* boundp -- public native designator closure */
        if (n != 1) { vm_status = VM_ARITY; return NIL; }
        if (!(IS_SYMI(a[0]) || (IS_PTR(a[0]) && cell_type(a[0]) == T_SYM))) {
            vm_status = VM_TYPEERROR; return NIL;
        }
        return sym_boundp(a[0]) ? vm_t : NIL;
    case 58: /* %list-malformed-error -- internal public-error-channel emitter */
        if (n != 0) { vm_status = VM_ARITY; return NIL; }
        vm_status = VM_TYPEERROR; return NIL;
    case 59: /* set */
        if (n != 2) { vm_status = VM_ARITY; return NIL; }
        if (!(IS_SYMI(a[0]) || (IS_PTR(a[0]) && cell_type(a[0]) == T_SYM))) {
            vm_status = VM_TYPEERROR; return NIL;
        }
        set_sym_value(a[0], a[1]); return a[1];
    case 60: { /* key-event: optional mode 0=nonblocking, 1=blocking */
        int16_t mode;
        if (n > 1) { vm_status = VM_ARITY; return NIL; }
        if (n == 1 && !IS_FIX(a[0])) { vm_status = VM_TYPEERROR; return NIL; }
        mode = n == 0 ? 0 : FIXVAL(a[0]);
        if (mode != 0 && mode != 1) { vm_status = VM_TYPEERROR; return NIL; }
#if defined(LISP65_VM_SCREEN_PRIMS) && defined(LISP65_VM_REAL_KEYBOARD)
        if (mode) {
#ifdef LISP65_C2_KERNAL_UNMAP
            lisp65_key_event event;
            (void)lisp_input_event(1u, 0u, &event);
            return vm_key_event(event.code, event.modifiers);
#else
            int c;
            do { lisp_poll(); c = cbm_k_getin(); } while (c == 0);
            return vm_key_event(c, 0u);
#endif
        } else {
#ifdef LISP65_C2_KERNAL_UNMAP
            lisp65_key_event event;
            return lisp_input_event(0u, 0u, &event)
                ? vm_key_event(event.code, event.modifiers) : NIL;
#else
            int c = cbm_k_getin();
            return c == 0 ? NIL : vm_key_event(c, 0u);
#endif
        }
#else
        return NIL;
#endif
    }
    case 61: /* peek */
    case 62: { /* poke -- shared strict byte contract, no implicit masking */
        uint16_t address;
        if (!vm_byte_args(a, n, (uint8_t)(pid - 59u))) return NIL;
        address = ((uint16_t)FIXVAL(a[0]) << 8) | (uint16_t)FIXVAL(a[1]);
#ifdef LISP_REAL_MEM
        if (pid == 61) return MKFIX(*(volatile unsigned char *)(uintptr_t)address);
        *(volatile unsigned char *)(uintptr_t)address = (unsigned char)FIXVAL(a[2]);
#else
        (void)address;
        if (pid == 61) return MKFIX(0);
#endif
        return a[2];
    }
    case 68: { /* intern -- canonical public string-to-symbol operation */
#ifdef LISP65_INTERN_SESSION_SERVICE
        uint16_t length;
        if (n != 1) { vm_status = VM_ARITY; return NIL; }
        if (!vm_string_arg_p(a[0])) {
            vm_status = VM_TYPEERROR; return NIL;
        }
        length = str_len(a[0]);
        if (length > LISP65_SYMBOL_NAME_MAX) {
            vm_status = VM_TYPEERROR; return NIL;
        }
        return vm_buffer_call(pid, a, n);
#else
        uint16_t length;
        if (n != 1) { vm_status = VM_ARITY; return NIL; }
        if (!IS_PTR(a[0]) || cell_type(a[0]) != T_STR) {
            vm_status = VM_TYPEERROR; return NIL;
        }
        length = str_len(a[0]);
        if (length > LISP65_SYMBOL_NAME_MAX) {
            vm_status = VM_TYPEERROR; return NIL;
        }
        str_copy_out(a[0], sym_name_scratch, length);
        sym_name_scratch[length] = '\0';
        return intern(sym_name_scratch);
#endif
    }
#endif
#if defined(LISP65_FIRST_CLASS_BUFFER) && !defined(LISP65_BUFFER_NO_PRIMS)
    /* Numeric labels are intentionally visible to the registry parity gate. */
    case 63: /* %buffer-read */
    case 64: /* %buffer-write */
    case 65: /* %buffer-alloc */
#ifdef LISP65_C2_PRODUCT_CUT
        return vm_buffer_call(pid, a, n);
    case 66: /* %c2-control -- the sole born-code emitter */
        if (n != 2) { vm_status = VM_ARITY; return NIL; }
        return c2_session_emit_control(a[0], a[1]);
    case 67: /* %c2d-byte -- private read-only published-C2D seam */
        if (!vm_byte_args(a, n, 2u)) return NIL;
        return vm_c2d_byte(a);
#else
#ifdef LISP65_C1_COMPILER_TIER
    case 66: /* historical C1 carrier (excluded from the C2 product cut) */
#endif
        return vm_buffer_call(pid, a, n);
#endif
#endif
    default: vm_status = VM_BADOPCODE; return NIL;
    }
}

#if defined(LISP65_DIALECT_FAMILY_HARNESS) && defined(LISP65_DIALECT_V2)
obj vm_family_internal_primitive(uint8_t pid, obj *args, uint8_t nargs) {
    if (pid != 28 && pid != 29) {
        vm_status = VM_BADOPCODE;
        return NIL;
    }
    return vm_callprim(pid, args, nargs);
}
#endif
#ifdef LISP65_DIRECTORY_ONLY_HARNESS
obj vm_directory_only_test_callprim(uint8_t pid, obj *args, uint8_t nargs) {
    if (pid != 7u && pid != 8u) {
        vm_status = VM_BADOPCODE;
        return NIL;
    }
    return vm_callprim(pid, args, nargs);
}
#endif

/* Frame bei base fuellen: fixe Params [0,nargs), dann Locals=NIL. Variadisch (flags&1): der
 * Rest-Slot (erstes Local, Index nargs) bekommt die Liste der Args[nargs..n) — exakt wie die
 * Host-VM (P0VM). Setzt gc_rootsp = vb (Frame-Top) und gibt vb zurueck. Callee prueft GC_ROOTS. */
static uint16_t vm_frame_fill(uint16_t base, const obj *args, uint8_t n,
                              uint8_t nargs, uint8_t nlocals, uint8_t flags) {
    uint16_t i, vb = (uint16_t)(base + nargs + nlocals);
    for (i = 0; i < nargs;   i++) gc_rootstack[base + i]         = (i < n) ? args[i] : NIL;
    for (i = 0; i < nlocals; i++) gc_rootstack[base + nargs + i] = NIL;
    if (flags & CO_FLAG_REST) {      /* Rest-Liste aus Args[nargs..n) bauen (GC-gerootet ueber vb) */
        uint8_t cnt = (n > nargs) ? (uint8_t)(n - nargs) : 0, j;
        obj rest = NIL;
        for (j = 0; j < cnt; j++) gc_rootstack[vb + j] = args[nargs + j];
        gc_rootstack[vb + cnt] = NIL;
        gc_rootsp = (uint16_t)(vb + cnt + 1);
        for (j = cnt; j > 0; j--) { rest = cons(gc_rootstack[vb + j - 1], rest); gc_rootstack[vb + cnt] = rest; }
        gc_rootstack[base + nargs] = rest;   /* Rest-Slot */
    }
    gc_rootsp = vb;
    return vb;
}

#ifdef LISP65_DIALECT_V2
#if defined(LISP65_C2_KERNAL_UNMAP) && \
    defined(LISP65_C2_LITE_VM_ARITY_E000)
/* Post-ownership hot leaf: two VM call sites enter it after the KERNAL
 * handoff; it has no outbound call or data edge.  Keeping it in the already
 * owned C2-resident slab restores a real Bank-0 LTO-noise margin without a
 * new section, vector, state byte, or pre-ownership dependency. */
#define VM_ARITY_FN __attribute__((noinline, \
    section(".lisp65_c2_kernal_window.c2_resident")))
#else
#define VM_ARITY_FN
#endif
static VM_ARITY_FN uint8_t vm_arity_accepts(
        uint8_t actual, uint8_t nargs, uint8_t flags) {
    uint8_t optional = CO_OPTIONAL_COUNT(flags);
    uint8_t minimum;
    if (!(flags & CO_FLAG_STRICT_ARITY)) return 0;
    if (optional > nargs) return 0;
    minimum = (uint8_t)(nargs - optional);
    if (actual < minimum) return 0;
    return (flags & CO_FLAG_REST) || actual <= nargs;
}
#undef VM_ARITY_FN
#endif

/* C-STACK-DIAET (2026-07-03): alles Header-Abgeleitete lebt als file-scope-Static statt
 * im rekursiven vm_run-Frame. Grund (xemu-vermessen): der Editor-Tastenpfad stapelt ~24
 * vm_run-Ebenen; mit fetten Frames brauchte er 1834 B C-Stack bei nur 1232 B Gap -> Stack
 * trampelte in heap/BSS ("vm: stack overflow"/"vm: type error" am Geraet). Diese Werte
 * sind nach jeder Call-Rueckkehr ohnehin reload-pflichtig (Owner-Tag) und aus bank/off/len
 * (C-Parameter, ueberleben die Rekursion natuerlich) + Resume-pc rekonstruierbar.
 * 6502-Bonus: absolute Adressen schlagen Stack-relativ (vgl. Doppelpuffer-Lektion). */
static uint8_t  vmr_nargs, vmr_nlocals, vmr_nlits, vmr_flags;
static uint8_t  vmr_streaming;   /* 1 = Objekt groesser als Fenster -> WIN_ENSURE aktiv */
static uint16_t vmr_hdrlen, vmr_poff, vmr_plen, vmr_pwmax, vmr_win, vmr_winlen;
static const uint8_t *vmr_littab, *vmr_code;

static __attribute__((noinline))
obj vm_run_inner(uint8_t bank, uint16_t off, uint16_t len,
                 const obj *args, uint8_t nargs_actual);

/* Keep the guard outside the large dispatch body. Besides keeping its LTO
 * layout stable, this preserves the check on every recursive OP_CALL: the
 * inner interpreter deliberately calls the public wrapper below. */
__attribute__((noinline))
obj vm_run(uint8_t bank, uint16_t off, uint16_t len,
           const obj *args, uint8_t nargs_actual) {
#ifdef LISP65_STACK_GUARD
    if (lisp_stack_low()) { vm_status = VM_STACKOVER; return NIL; }
#endif
    return vm_run_inner(bank, off, len, args, nargs_actual);
}

/* Relative bytecode edges live in the logical u16 payload-PC domain.  The
 * C pointer is only a cache cursor inside vm_codebuf and must never carry a
 * target across a streamed-window boundary.  In the C2 product this pure,
 * shared calculation lives in the already-owned fixed window; all VM entry
 * paths are structurally after c2_kernal_take_ownership(). */
#ifdef LISP65_C2_KERNAL_UNMAP
#define VM_LOGICAL_PC_HELPER \
    __attribute__((noinline, section(".lisp65_c2_kernal_window.c2_resident")))
#else
#define VM_LOGICAL_PC_HELPER __attribute__((noinline))
#endif
static VM_LOGICAL_PC_HELPER uint8_t
vm_logical_relative_target(uint16_t next, uint16_t payload_length,
                           int8_t delta, uint16_t *target) {
    uint16_t result;
    if (delta < 0) {
        uint8_t back = (uint8_t)(-(int16_t)delta);
        if (next < back) return 0;
        result = (uint16_t)(next - back);
    } else {
        uint8_t forward = (uint8_t)delta;
        if (next >= payload_length
            || forward >= (uint16_t)(payload_length - next)) return 0;
        result = (uint16_t)(next + forward);
    }
    *target = result;
    return 1;
}

static __attribute__((noinline))
obj vm_run_inner(uint8_t bank, uint16_t off, uint16_t len,
                 const obj *args, uint8_t nargs_actual) {
    uint8_t  op = 0;
    uint16_t base, vb;
    const uint8_t *ip;   /* Byte-Cursor im Fenster (ersetzt pc: 16-bit-Buchhaltung je Byte
                          * war ein Dispatch-Hauptposten — 1280 Zyklen/Op gemessen) */
#ifdef LISP65_VM_DIAGNOSTICS
    uint16_t op_pc = 0;
#endif
#define nargs       vmr_nargs
#define nlocals     vmr_nlocals
#define nlits       vmr_nlits
#define flags       vmr_flags
#define streaming   vmr_streaming
#define hdrlen      vmr_hdrlen
#define payload_off vmr_poff
#define payload_len vmr_plen
#define pwin_max    vmr_pwmax
#define win         vmr_win
#define winlen      vmr_winlen
#define littab      vmr_littab
#define code        vmr_code
    uint8_t *cbuf = vm_codebuf;
    obj a, b, r = NIL;
#ifdef VM_STEP_LIMIT
    uint16_t vm_steps = 0;   /* Diagnose-Watchdog (16 bit, Limit <= 65000): Endlosschleife -> Fehler */
#endif
#ifdef LISP65_VM_DIAGNOSTICS
    obj run_fn = vm_pending_fn;
#endif

    /* KEIN Status-Reset am Eintritt (2026-07-06): der bedingungslose Reset
     * verschluckte Fehler verschachtelter Laeufe (STACKOVER eines inneren Calls ->
     * Aufrufer lief mit NIL weiter -> "vm: type error" drei Frames spaeter, am
     * Geraet Muell-bank/off). Fehler sind KLEBRIG bis zur Abort-Stelle
     * (vm_check_status, eval.c) — DORT wird jetzt aufgeraeumt. */
#ifdef LISP65_VM_DIAGNOSTICS
    vm_diag_valid = 0;
    vm_pending_fn = NIL;
#endif
    base = gc_rootsp;
    vb = base;
    HB(1); LA(4);   /* D: vm_run entry */

    /* Load the object and set up header/window (also for TAILCALL).
     * Buffer layout: [header+littab | payload window]. The payload streams incrementally: only
     * min(len, VM_CODEBUF) bytes are loaded initially; larger objects reload their payload window
     * by window via bulk DMA (WIN_ENSURE), while header+littab stay resident. */
#define OBJ_SETUP() do { \
        uint16_t l0_ = (len < VM_CODEBUF) ? len : VM_CODEBUF; \
        if (!vm_object_load(bank, off, 0, l0_, cbuf)) { vm_status = VM_BADOPCODE; goto done; } \
        vm_buf_bank = bank; vm_buf_off = off; \
        if (cbuf[CO_OFF_MAGIC] != CO_MAGIC) { vm_status = VM_BADOPCODE; goto done; } \
        nargs   = cbuf[CO_OFF_NARGS]; \
        nlocals = cbuf[CO_OFF_NLOCS]; \
        flags   = cbuf[CO_OFF_FLAGS]; \
        /* v1 artifacts are format-frozen and reach the VM through build-bound gates. */ \
        /* v2 validates its expanded flag space again at the execution boundary. */ \
        LISP65_V2_CODE_FLAGS_CHECK(nargs, nlocals, flags); \
        nlits   = cbuf[CO_OFF_NLITS]; \
        hdrlen  = (uint16_t)(CO_OFF_LITTAB + 2 * (uint16_t)nlits); \
        if ((uint16_t)(hdrlen + 3) > VM_CODEBUF) { vm_status = VM_BADOPCODE; goto done; } \
        littab      = cbuf + CO_OFF_LITTAB; \
        code        = cbuf + hdrlen;                 /* Fenster-Basis (Payload-Offset win) */ \
        payload_off = hdrlen; \
        payload_len = (uint16_t)(len - hdrlen); \
        pwin_max    = (uint16_t)(VM_CODEBUF - hdrlen); \
        win = 0; \
        winlen = (payload_len < pwin_max) ? payload_len : pwin_max; \
        streaming = (winlen < payload_len); \
        LA(3); /* C: OBJ_SETUP fertig */ \
    } while (0)

    /* After a nested call (CALL/CALLPRIM overwrote the buffer AND the vmr_* globals!):
     * reload header+littab, re-parse ALL header derivations and force the payload window at the
     * resume pc. The caller MUST have saved pcur_ BEFORE the nested call (after the return the
     * window globals belong to the callee).
     * The trigger is still the owner tag; a match means the callee was the same fn in the same
     * window, in which case the globals are correct too (header derivation is deterministic). */
#define BUF_ENSURE_MINE(pcur_) do { \
        if (vm_buf_bank != bank || vm_buf_off != off) { \
            /* a foreign fn is resident: load the header and re-parse ALL derivations */ \
            if (!vm_object_load(bank, off, 0, (uint16_t)CO_OFF_LITTAB, cbuf)) { vm_status = VM_BADOPCODE; goto done; } \
            nargs   = cbuf[CO_OFF_NARGS]; \
            nlocals = cbuf[CO_OFF_NLOCS]; \
            flags   = cbuf[CO_OFF_FLAGS]; \
            nlits   = cbuf[CO_OFF_NLITS]; \
            hdrlen  = (uint16_t)(CO_OFF_LITTAB + 2 * (uint16_t)nlits); \
            if (!vm_object_load(bank, off, 0, hdrlen, cbuf)) { vm_status = VM_BADOPCODE; goto done; } \
            littab      = cbuf + CO_OFF_LITTAB; \
            code        = cbuf + hdrlen; \
            payload_off = hdrlen; \
            payload_len = (uint16_t)(len - hdrlen); \
            pwin_max    = (uint16_t)(VM_CODEBUF - hdrlen); \
            vm_buf_bank = bank; vm_buf_off = off; \
            win = (pcur_); winlen = 0; ip = code; streaming = 1; \
        } else if ((pcur_) >= win && (uint16_t)((pcur_) - win) < winlen) { \
            /* selbe Fn, Fenster deckt Resume-pc: Globals gueltig, nur Cursor setzen \
             * (Selbstrekursions-Fastpath — voll residente Fns zahlen nichts) */ \
            ip = code + (uint16_t)((pcur_) - win); \
        } else { \
            /* selbe Fn, Fenster verschoben: Header-Globals gueltig, Fenster neu holen */ \
            win = (pcur_); winlen = 0; ip = code; streaming = 1; \
        } \
    } while (0)

    /* Sicherstellen, dass das Fenster [pc, min(pc+3, payload_len)) abdeckt (3 = max. Instr.-Laenge);
     * sonst am pc neu laden. Fast-Path (Objekt passt ganz): win=0, winlen=payload_len -> nie neu. */
#define WIN_ENSURE() do { \
        if (streaming) { \
            uint16_t pc_ = (uint16_t)(win + (uint16_t)(ip - code)); \
            uint16_t need_ = (uint16_t)(((uint16_t)(payload_len - pc_) < 3) ? payload_len : (uint16_t)(pc_ + 3)); \
            if (pc_ < win || (uint16_t)(win + winlen) < need_) { \
                win = pc_; \
                winlen = (uint16_t)(((uint16_t)(payload_len - pc_) < pwin_max) ? (uint16_t)(payload_len - pc_) : pwin_max); \
                if (!vm_object_load(bank, off, (uint16_t)(payload_off + pc_), winlen, cbuf + hdrlen)) { vm_status = VM_BADOPCODE; goto done; } \
                ip = code; \
            } \
        } \
    } while (0)
#define JUMP_REL(delta_) do { \
        uint16_t next__ = (uint16_t)(win + (uint16_t)(ip - code)); \
        uint16_t target__; \
        if (!vm_logical_relative_target(next__, payload_len, \
                                        (int8_t)(delta_), &target__)) { \
            vm_status = VM_BADOPCODE; goto done; \
        } \
        if (target__ >= win && (uint16_t)(target__ - win) < winlen) { \
            ip = code + (uint16_t)(target__ - win); \
        } else { \
            /* Never form a C pointer outside vm_codebuf.  The old direct \
             * `ip += delta` relied on out-of-array pointer arithmetic when a \
             * relative edge crossed a streamed window.  That is undefined C \
             * behavior and the MOS/LTO product build did in fact misexecute \
             * the banner separator's PC 72 -> PC 8 backedge. */ \
            win = target__; winlen = 0; ip = code; streaming = 1; \
        } \
    } while (0)
#define RD8()  (*ip++)                              /* Byte am Cursor (nach WIN_ENSURE in-window) */

    OBJ_SETUP();

#ifdef LISP65_DIALECT_V2
    if (!vm_arity_accepts(nargs_actual, nargs, flags)) { vm_status = VM_ARITY; goto done; }
#endif

    /* Frame-Guard NUR fuer Args+Locals (2026-07-06): die alte Pauschal-Reservierung
     * von +VM_MAXARGS+1 Operanden-Slots je Frame (13!) begrenzte die Aufruftiefe auf
     * ~9 Frames — der kalte (ide)-Start (~11 Frames) lief NUR dank verschluckter
     * STACKOVER (s. klebriger Status). Operanden-Pushes sind einzeln PUSH-geprueft
     * und brechen jetzt ehrlich ab -> die Reservierung darf auf das wirklich
     * Geschriebene schrumpfen. Typischer Frame 17->5 Slots, Tiefe ~3x. */
    if ((uint16_t)(base + nargs + nlocals + 1) >= GC_ROOTS) { vm_status = VM_STACKOVER; goto done; }
    vb = vm_frame_fill(base, args, nargs_actual, nargs, nlocals, flags);   /* fix + variadisch */
    ip = code;

#define PUSH(x)  do { if (gc_rootsp >= GC_ROOTS) { vm_status = VM_STACKOVER; goto done; } \
                      gc_rootstack[gc_rootsp++] = (obj)(x); } while (0)
#define POP()    (gc_rootsp > vb ? gc_rootstack[--gc_rootsp] : (vm_status = VM_BADOPCODE, NIL))
#define SLOT(n)  gc_rootstack[base + (n)]
#define LIT(i)   ((obj)(littab[2*(i)] | (littab[2*(i)+1] << 8)))
#define NEEDFIX2 do { if (!IS_FIX(a) || !IS_FIX(b)) { vm_status = VM_TYPEERROR; goto done; } } while (0)

    for (;;) {
        /* RUN/STOP auch in reinen VM-Schleifen: kompilierte Endlos-Loops ((ide), dotimes-
         * Lowering) waren sonst unabbrechbar — der Treewalker pollt in eval_env, die VM
         * tat es bis 2026-07-02 nie. Alle 256 Schritte, Kosten im Rauschen. */
        { static uint8_t poll_; if (++poll_ == 0) lisp_poll(); }
#ifdef LISP65_DMA_PROF
        { extern uint32_t perf_vm_ops; perf_vm_ops++; }   /* Diagnose: Instruktionen zaehlen */
#endif
#ifdef VM_STEP_LIMIT
        if (++vm_steps > (uint16_t)(VM_STEP_LIMIT)) {
            vm_status = VM_STEPLIMIT;
            vm_dbg_pc = (uint16_t)(win + (uint16_t)(ip - code)); vm_dbg_op = op; vm_dbg_bank = bank; vm_dbg_off = off;
            goto done;
        }
#endif
        HB(2);
        WIN_ENSURE();          /* Fenster deckt die naechste Instruktion ([pc, pc+3)) */
#ifdef LISP65_VM_DIAGNOSTICS
        op_pc = (uint16_t)(win + (uint16_t)(ip - code));
#endif
        op = RD8();
        switch (op) {
        case OP_HALT:
        case OP_RET:
            r = (gc_rootsp > vb) ? gc_rootstack[gc_rootsp - 1] : NIL;
            vm_status = VM_OK; goto done;

        case OP_PUSHI8:  PUSH(MKFIX((int8_t)RD8())); break;
        case OP_PUSHNIL: PUSH(NIL); break;
        case OP_PUSHT:   PUSH(vm_t); break;
        case OP_PUSHLIT: { uint8_t i = RD8(); PUSH(LIT(i)); break; }

        case OP_PUSHARG0: PUSH(SLOT(0)); break;
        case OP_PUSHARG1: PUSH(SLOT(1)); break;
        case OP_PUSHARG2: PUSH(SLOT(2)); break;
        case OP_PUSHARGN: { uint8_t n = RD8(); PUSH(SLOT(n)); break; }
        case OP_LOADL:    { uint8_t n = RD8(); PUSH(SLOT(n)); break; }
        case OP_STOREL:   { uint8_t n = RD8(); a = POP(); SLOT(n) = a; break; }
        case OP_DROP:     (void)POP(); break;

        case OP_ADD: case OP_SUB: case OP_MUL: case OP_DIV:
        case OP_REMAINDER: case OP_MOD:
        case OP_LOGAND: case OP_LOGIOR: case OP_LOGXOR: case OP_ASH:
        case OP_LESS: case OP_GREATER: {
            obj r;
            b = POP(); a = POP(); NEEDFIX2;
            r = vm_fixbinop(op, a, b);           /* Rechenkern ausgelagert (Diaet) */
            if (vm_status != VM_OK) goto done;
            PUSH(r);
            break;
        }

        case OP_EQ:  b = POP(); a = POP(); PUSH(a == b ? vm_t : NIL); break;
        case OP_EQL: b = POP(); a = POP(); PUSH(a == b ? vm_t : NIL); break;
        case OP_NOT: a = POP(); PUSH(a == NIL ? vm_t : NIL); break;

        case OP_CONS: b = POP(); a = POP();
                      { obj c; GC_PUSH(a); GC_PUSH(b); c = cons(a, b); GC_POPN(2);
                        if (c == NIL) { vm_status = VM_HEAPOOM; goto done; } PUSH(c); } break;
        case OP_CAR:  a = POP(); PUSH(IS_PTR(a) ? cell_a(a) : NIL); break;
        case OP_CDR:  a = POP(); PUSH(IS_PTR(a) ? cell_b(a) : NIL); break;
        case OP_CONSP:a = POP(); PUSH((IS_PTR(a) && cell_type(a) == T_CONS) ? vm_t : NIL); break;

        /* One shared emission site: the logical-PC seam is deliberately not
         * duplicated into both switch arms. */
        case OP_JMPREL:
            a = NIL;
            goto relative_branch;
        case OP_JFALSEREL:
            a = POP();
relative_branch: {
            int8_t d = (int8_t)RD8();
            if (a == NIL) JUMP_REL(d);
            break;
        }

        case OP_CALL: {   /* Callee = littab[idx] (Symbol) -> Directory (VM) | Tree-Walker-Bridge */
            LA(7);   /* G */
            uint8_t li = RD8(), n = RD8();
            obj sym = LIT(li);               /* JETZT lesen (vor dem Puffer-Ueberschreiben) */
            int di = IS_BCODE(sym) ? (int)BCODE_IDX(sym) : dir_find(sym);
            obj cargs[VM_MAXARGS]; unsigned i; obj res;
            /* Resume-pc VOR dem Nested-Call sichern: der Callee besitzt danach die
             * vmr_*-Fenster-Globals (C-Stack-Diaet) — win/code sind dann seine. */
            uint16_t pcur = (uint16_t)(win + (uint16_t)(ip - code));
            if (n > VM_MAXARGS) { vm_status = VM_BADOPCODE; goto done; }
            for (i = n; i > 0; i--) cargs[i-1] = POP();
            if (di >= 0 && vm_directory_length((uint16_t)di)) {
#ifdef LISP65_VM_DIAGNOSTICS
                vm_pending_fn = sym;
#endif
                res = vm_run_dir(di, cargs, n);  /* -> VM (anderer Puffer, Paritaet) */
#ifndef LISP65_V2_CARRIER_CUT
            } else if (vm_treewalk_call) {
                res = vm_treewalk_call(sym, cargs, n);          /* -> Tree-Walker (kann re-entrant VM clobbern) */
#endif
            } else {
                r = vm_dirmiss_detail(sym); goto done;
            }
            if (vm_status != VM_OK) { r = res; goto done; }
            BUF_ENSURE_MINE(pcur);   /* Callee ueberschrieb Puffer+Globals -> reparsen */
            PUSH(res);
            break;
        }
        case OP_TAILCALL: {   /* Callee laden, Frame wiederverwenden (echtes TCO) */
            LA(5);   /* E */
            uint8_t li = RD8(), n = RD8();
            obj sym = LIT(li);
            int di = IS_BCODE(sym) ? (int)BCODE_IDX(sym) : dir_find(sym);
            obj cargs[VM_MAXARGS]; unsigned i;
            if (n > VM_MAXARGS) { vm_status = VM_BADOPCODE; goto done; }
            for (i = n; i > 0; i--) cargs[i-1] = POP();
            if (di < 0 || !vm_directory_length((uint16_t)di)) {   /* Tail-Aufruf an nicht-kompilierte Fn -> Tree-Walker, Ergebnis = Rueckgabe */
#ifndef LISP65_V2_CARRIER_CUT
                if (vm_treewalk_call) { r = vm_treewalk_call(sym, cargs, n); goto done; }
#endif
                r = vm_dirmiss_detail(sym); goto done;
            }
#ifdef LISP65_VM_DIAGNOSTICS
            run_fn = sym;
#endif
            len = vm_directory_length((uint16_t)di);
            vm_directory_address((uint16_t)di, &bank, &off);
            OBJ_SETUP();   /* neues Objekt: Header + Payload-Fenster (streambar) */
#ifdef LISP65_DIALECT_V2
            if (!vm_arity_accepts(n, nargs, flags)) { vm_status = VM_ARITY; goto done; }
#endif
            /* Frame-Guard NUR fuer Args+Locals (2026-07-06): die alte Pauschal-Reservierung
     * von +VM_MAXARGS+1 Operanden-Slots je Frame (13!) begrenzte die Aufruftiefe auf
     * ~9 Frames — der kalte (ide)-Start (~11 Frames) lief NUR dank verschluckter
     * STACKOVER (s. klebriger Status). Operanden-Pushes sind einzeln PUSH-geprueft
     * und brechen jetzt ehrlich ab -> die Reservierung darf auf das wirklich
     * Geschriebene schrumpfen. Typischer Frame 17->5 Slots, Tiefe ~3x. */
    if ((uint16_t)(base + nargs + nlocals + 1) >= GC_ROOTS) { vm_status = VM_STACKOVER; goto done; }
            vb = vm_frame_fill(base, cargs, n, nargs, nlocals, flags);   /* fix + variadisch */
            ip = code;
            break;
        }
        case OP_CALLPRIM: {
            LA(6);   /* F */
            uint8_t pid = RD8(), n = RD8();
            obj cargs[VM_MAXARGS]; unsigned i; obj res;
            uint16_t pcur = (uint16_t)(win + (uint16_t)(ip - code));   /* vor moegl. Re-Entry */
            if (n > VM_MAXARGS) { vm_status = VM_BADOPCODE; goto done; }
            for (i = n; i > 0; i--) cargs[i-1] = POP();
            res = vm_callprim(pid, cargs, n);   /* funcall/apply (7/8) koennen re-entrant die VM clobbern */
            if (vm_status != VM_OK) { r = res; goto done; }
            BUF_ENSURE_MINE(pcur);   /* funcall/apply (7/8): Puffer+Globals reparsen falls geclobbert */
            PUSH(res);
            break;
        }

#if defined(LISP65_COMPILE_REPL) || defined(LISP65_VM_NATIVE_APPLY) || defined(LISP65_LCC_INSTALL_CLOSURES)
        case OP_UPVAL: {   /* M-closures: i-te Upvalue des aktuellen Closure-Frames pushen (Helfer s.o.) */
            obj u = vm_upval_nth(RD8());
            PUSH((IS_PTR(u) && cell_type(u) == T_CONS) ? cell_a(u) : NIL);
            break;
        }
        case OP_CLOSURE: {   /* Build a closure (heavy loop + alloc -> vm_op_closure, avoids switch bloat).
                              * littab[li] = the helper (a symbol OR a BCODE immediate: lcc self-hosting,
                              * no __L leak). */
            uint8_t li = RD8(), nuv = RD8();
            obj detail = vm_op_closure(LIT(li), nuv, vb);
            if (vm_status != VM_OK) { r = detail; goto done; }
            break;
        }
        case OP_SETUPVAL: {   /* M-closures Phase 2: Wert poppen + i-te Upvalue schreiben (per-Closure persistent) */
            uint8_t i = RD8(); obj v = POP(), u = vm_upval_nth(i);
            if (!IS_PTR(u) || cell_type(u) != T_CONS) { vm_status = VM_TYPEERROR; goto done; }
            cell_set_a(u, v);
            break;
        }
#endif
        default: vm_status = VM_BADOPCODE; goto done;
        }
        if (vm_status != VM_OK) goto done;
    }

done:
#ifdef LISP65_DMA_PROF
    /* Diagnostic seam: record the error location even WITHOUT the heavy diagnostics module
     * (bank/offset + window pc + opcode -> function via the manifest/disassembly). */
    if (vm_status != VM_OK && vm_status != VM_HALT && vm_dbg_pc == 0) {
        vm_dbg_pc = (uint16_t)(win + (uint16_t)(ip - code));
        vm_dbg_op = op; vm_dbg_bank = bank; vm_dbg_off = off;
    }
#endif
#ifdef LISP65_VM_DIAGNOSTICS
    if (vm_status != VM_OK && vm_status != VM_HALT && !vm_diag_valid) {
        uint16_t sp = (gc_rootsp > vb) ? (uint16_t)(gc_rootsp - vb) : 0;
        vm_diag_capture(vm_status, op, op_pc, sp, run_fn);
    }
#endif
    gc_rootsp = base;
    return r;

#undef PUSH
#undef POP
#undef SLOT
#undef LIT
#undef NEEDFIX2
#undef OBJ_SETUP
#undef BUF_ENSURE_MINE
#undef WIN_ENSURE
#undef JUMP_REL
#undef RD8
#undef nargs
#undef nlocals
#undef nlits
#undef flags
#undef streaming
#undef hdrlen
#undef payload_off
#undef payload_len
#undef pwin_max
#undef win
#undef winlen
#undef littab
#undef code
}
