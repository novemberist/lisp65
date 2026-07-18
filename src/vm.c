/* lisp65 — Bytecode-VM (Streaming-Modell). Vertrag: docs/bytecode-abi.md (P0). */
#include "vm.h"
#include "interrupt.h"   /* lisp_poll (RUN/STOP in VM-Schleifen) */
#include "mem.h"
#include "symbol.h"
#include "v2_native_function_dispatch.h"
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
/* Die VM-Screen-Primitive sind bewusst separat vom nativen Screen-Ausgabetreiber
 * gegatet: Core braucht scr_init/scr_putc fuer eine HW-sichere REPL, aber nicht
 * die rendernden Bytecode-Primitive. */
#ifdef LISP65_VM_SCREEN_PRIMS
#include "screen.h"
#endif

#if defined(LISP65_VM_SCREEN_PRIMS) && (defined(__MEGA65__) || defined(__C64__) || defined(__CBM__))
#define LISP65_VM_REAL_KEYBOARD 1
#include <cbm.h>
#endif

#ifdef LISP65_HEARTBEAT   /* Diagnose: Schleifen-Ticker auf Bildschirm-RAM (Zeichen flackern) */
#define HB(i) (++*(volatile unsigned char *)(0x0800 + (i)))
#define LA(c) (*(volatile unsigned char *)(0x0800 + 50) = (unsigned char)(c))
#else
#define HB(i) ((void)0)
#define LA(c) ((void)0)
#endif


uint8_t vm_status = VM_OK;
static obj vm_t = NIL;
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
#endif
#ifdef LISP65_VM_DIAGNOSTICS
static obj vm_pending_fn = NIL;
static char vm_diag_msg[128] = "vm: ok";
static uint8_t vm_diag_valid = 0;
#endif

#ifndef VM_CODEBUF
#define VM_CODEBUF 128   /* hot-Puffer fuer das aktuell ausgefuehrte Code-Objekt; groesstes
                          * Stdlib-Objekt = 114 B -> Fast-Path ohne Windowing; groessere
                          * Objekte laufen korrekt ueber das Fenster (getestet ab 16 B). */
#endif
/* EIN hot-Puffer. Geschachtelte vm_run-Laeufe (CALL/CALLPRIM-Bruecke) ueberschreiben ihn;
 * der Aufrufer laedt Header+littab nach der Rueckkehr per Bulk-DMA neu (Reload-on-return).
 * (Ein frueherer Tiefen-Paritaets-Doppelpuffer sparte diese Reloads, war aber fuer eine auf
 * HW widerlegte DMA-Hypothese motiviert; im engen Bank-0-Budget sind die 128 B mehr wert als
 * die eingesparten seichten Header-Reloads. Reload-DMA ist HW-bewiesen unkritisch.) */
static uint8_t vm_codebuf[VM_CODEBUF];
/* BESITZER-TAG (2026-07-03): welches Codeobjekt liegt im Puffer? Nach einem Call laedt
 * der Aufrufer NUR neu, wenn ein anderes Objekt den Puffer benutzt hat. Leaf-Calls zu
 * C-Prims (screen-*, car, ...) beruehren ihn nie -> Reload entfaellt komplett. Gemessen
 * am Geraet: 2405 Code-DMAs je Editor-Taste (~1 s) — der Grossteil davon unnoetig. */
static uint8_t  vm_buf_bank = 0xFF;
static uint16_t vm_buf_off  = 0xFFFF;

#if defined(VM_STEP_LIMIT) || defined(LISP65_DMA_PROF)
/* Minimal-Capture beim Watchdog/Fehler (Diagnose ohne das schwere LISP65_VM_DIAGNOSTICS-
 * Modul): pc/op = klemmende Stelle, bank/off = Code-Objekt (Funktion via Manifest). */
volatile uint16_t vm_dbg_pc = 0, vm_dbg_off = 0;   /* volatile: LTO strippt Nur-Schreiber */
volatile uint8_t  vm_dbg_op = 0, vm_dbg_bank = 0;
#endif

/* Code-Directory: Symbol -> Code-Ort (bank/offset/len im erw. RAM). */
#ifndef VM_DIR_MAX
#define VM_DIR_MAX 128
#endif
#ifdef LISP65_VM_DIAGNOSTICS
static obj      dir_sym[VM_DIR_MAX];   /* nur Diagnose (vm_pending_fn); Aufloesung: s. dir_find */
#endif
/* Bank-0-Footprint komprimiert (2026-07-04, Hebel-C-Spike): das Code-Blob liegt komplett in
 * EINER EXT-Bank (~20 KB < 64 KB) -> Bank als Einzelwert statt Array (-238 B). Und jedes
 * Code-Objekt ist <= 255 B (real max 234) -> dir_len als uint8_t (-238 B). Netto ~476 B .bss
 * gespart OHNE Hot-Path-DMA/Cache (die riskante EXT-Verlagerung entfaellt). Guards in
 * vm_dir_add fangen einen mehrbankigen ODER >255-B-Blob laut ab (statt stiller Trunkierung). */
static uint8_t  dir_bank0 = 0;
/* dir_off SPARSE (2026-07-04, LOAD-Budget): das Blob ist kontinuierlich (off[i] = sum(len[0..i-1]),
 * manifest-verifiziert), also nur JEDES 8. Offset speichern + <=7 dir_len-Summen/Call
 * rekonstruieren (Bank-0-Arithmetik, KEIN DMA/Cache) -> ~-430 B .bss. Guard in vm_dir_add
 * faengt einen nicht-kontinuierlichen Blob laut ab (statt stiller Fehl-Adressierung). */
static uint16_t dir_off_base[(VM_DIR_MAX + 7) / 8];
static uint8_t  dir_len[VM_DIR_MAX];
static uint16_t dir_n = 0;   /* uint16: VM_DIR_MAX darf ueber 255 (229 Objekte seit IDE-Dirty-Lines) */

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
        /* Basis-Versatz (neue Code-Quelle: Disk-Lib hinter Trailer, Compiled-Fn-Region, ...): statt
         * hart zu scheitern auf die naechste 8er-Grenze padden -> der Eintrag wird Block-Start, seine
         * Basis wird GESPEICHERT, die sparse dir_off-Rekonstruktion bleibt exakt. Padded nur beim
         * tatsaechlichen Quellen-Wechsel (nicht pro Eintrag); ersetzt das manuelle vm_dir_align8 der
         * Aufrufer als Wurzel-Fix (docs/bank0-full-suite-strategy.md §5-K1). Innerhalb einer Quelle
         * bleibt Kontinuitaet Pflicht (append-only-Writes garantieren sie). Gegatet: im Default-Profil
         * (nur Stdlib-Blob, keine zweite Quelle) bleibt der harte Guard budgetneutral. */
        vm_dir_align8();
        if (dir_n >= VM_DIR_MAX) return -1;
        dir_off_base[dir_n >> 3] = off;
#else
        return -1;           /* Kontinuitaets-Guard: Blob muss contig sein (keine zweite Code-Quelle) */
#endif
    }
    dir_len[dir_n] = (uint8_t)len;
    return (int)dir_n++;
}
/* Fuer Disk-Bytecode-Libs (docs/disk-bytecode-libs-design.md): dir_n auf die naechste 8er-Block-
 * Grenze padden (Dummy-len-0-Eintraege, nie ueber ein Symbol erreichbar) -> eine geladene Lib
 * beginnt als EIGENER Block, damit die sparse dir_off-Rekonstruktion stimmt (die Lib-Basis ist
 * NICHT das Stdlib-Kontinuum; ihre Block-Basis wird vom ersten Lib-Eintrag gesetzt). */
void
#ifdef LISP65_LCC_INSTALL
__attribute__((noinline))
#endif
vm_dir_align8(void) {
    while ((dir_n & 7u) && dir_n < VM_DIR_MAX) dir_len[dir_n++] = 0;
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

/* Bridge VM -> Tree-Walker (K3): setzt eval.c für CALL-Fehltreffer (Symbol nicht kompiliert).
 * NULL = keine Bridge (Fehltreffer -> VM_DIRMISS). */
#ifndef LISP65_V2_CARRIER_CUT
obj (*vm_treewalk_call)(obj sym, const obj *args, uint8_t n) = 0;

/* Bridge fuer apply/funcall (Prim 7/8): ruft den Tree-Walker-apply mit fn + fertiger Arg-Liste. */
obj (*vm_treewalk_apply)(obj fn, obj arglist) = 0;
#endif

/* Lauf per Directory-Index (Bridge Tree-Walker -> VM, aus apply). */
obj vm_run_dir(int di, const obj *args, uint8_t n) {
    if (di < 0 || di >= (int)dir_n || dir_len[di] == 0) {
        vm_status = VM_DIRMISS;
#ifdef LISP65_VM_DIAGNOSTICS
        vm_diag_capture(vm_status, 0, 0, 0, NIL);
#endif
        return NIL;
    }
#ifdef LISP65_VM_DIAGNOSTICS
    vm_pending_fn = dir_sym[di] != NIL ? dir_sym[di] : MK_BCODE(di);
#endif
    return vm_run(dir_bank0, dir_off_get(di), dir_len[di], args, n);
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
 * 0 = Fehler (Aufrufer -> goto done). GC-Semantik identisch zum alten Inline-Case. */
static uint8_t vm_op_closure(obj sym, uint8_t nuv, uint16_t stack_base) {
    obj lst = NIL, clo; uint8_t k;
    int di = IS_BCODE(sym) ? (int)BCODE_IDX(sym) : dir_find(sym);
    if (di < 0) { vm_status = VM_DIRMISS; return 0; }
    for (k = 0; k < nuv; k++) {                       /* letzter zuerst poppen -> Liste (uv0..) */
        if (gc_rootsp <= stack_base) { vm_status = VM_BADOPCODE; return 0; }
        obj v = gc_rootstack[--gc_rootsp];
        lst = cons(v, lst);
        if (lst == NIL) { vm_status = VM_HEAPOOM; return 0; }
    }
    GC_PUSH(lst); clo = alloc(T_CLOSURE); GC_POPN(1);
    if (clo == NIL) { vm_status = VM_HEAPOOM; return 0; }
    cell_set_a(clo, MK_BCODE(di)); cell_set_b(clo, lst);
    if (gc_rootsp >= GC_ROOTS) { vm_status = VM_STACKOVER; return 0; }
    gc_rootstack[gc_rootsp++] = clo;
    return 1;
}
#endif

/* VM-natives apply (M7): fn (Symbol oder BCODE-Immediate) -> Directory-Index -> vm_run_dir. In der
 * compile-repl-Welt sind ALLE Funktionen Bytecode (keine Closures), also braucht es keinen Treewalk.
 * arglist (cons-Liste) -> argv[] OHNE Allokation, damit die Liste bis vm_run gueltig bleibt (gleiche
 * Invariante wie der alte funcall-Pfad: kein alloc zwischen Listenaufbau und Lauf).
 * Fallback auf den Treewalk-Hook, SOLANGE er existiert (M6: Closures/Primitive-per-Symbol); ohne ihn
 * (M7) sauberer VM_TYPEERROR fuer nicht-aufrufbare fn -- NIE VM_BADOPCODE (Codex-Minimalvertrag).
 * Unter LISP65_COMPILE_REPL oder der neutralen Runtime-Capability
 * LISP65_VM_NATIVE_APPLY kompiliert; das Workbench-Default bleibt unveraendert. */
#if defined(LISP65_COMPILE_REPL) || defined(LISP65_VM_NATIVE_APPLY)
static obj vm_fixbinop(uint8_t op, obj a, obj b);        /* Definitionen weiter unten */
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

/* Gemeinsamer array-basierter Native-Call-Pfad. vm_native_apply ist nur der
 * Listenadapter; CALLPRIM apply/funcall koennen bereits flache Argumente ohne
 * temporaere Cons-Liste direkt uebergeben. */
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
#endif
}

#ifdef LISP65_VM_SCREEN_PRIMS
/* Gleiches Eventformat wie eval.c:key_event: (key code mods). */
static obj vm_key_event(int c) {
    obj mods = NIL, e;
    if (c >= 0xC1 && c <= 0xDA) { c -= 0x80; mods = cons(intern("shift"), NIL); }
    else if (c >= 'A' && c <= 'Z') c += 0x20;
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

static __attribute__((noinline)) obj vm_fixbinop(uint8_t op, obj a, obj b) {
    int16_t x = FIXVAL(a), y = FIXVAL(b);
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
static __attribute__((noinline)) uint8_t vm_byte_args(obj *a, uint8_t n, uint8_t expected) {
    uint8_t i;
    if (n != expected) { vm_status = VM_ARITY; return 0; }
    for (i = 0; i < n; i++) {
        if (!IS_FIX(a[i]) || (uint16_t)FIXVAL(a[i]) > 255u) {
            vm_status = VM_TYPEERROR; return 0;
        }
    }
    return 1;
}
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
    case 0: return (n >= 1 && IS_PTR(a[0]) && cell_type(a[0]) == T_STR) ? vm_t : NIL;  /* stringp */
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
        if (!IS_PTR(a[0]) || cell_type(a[0]) != T_STR) {
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
        { int c; do { lisp_poll(); c = cbm_k_getin(); } while (c == 0); return vm_key_event(c); }
#else
        return vm_key_event(0);
#endif
    case 14:  /* poll-key */
        if (n != 0) { vm_status = VM_TYPEERROR; return NIL; }
#ifdef LISP65_VM_REAL_KEYBOARD
        { int c = cbm_k_getin(); return c == 0 ? NIL : vm_key_event(c); }
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
#ifdef LISP65_DISK_LIBS
    case 18:  /* %disk-load-lib — Bytecode-Lib nach Bank 5 stagen + registrieren (Stufe 2) */
#ifdef LISP65_ATTIC_LIBRARY_SHELF
        if (n == 1) {
            return io_attic_load_lib(a[0]) ? vm_t : NIL;
        }
#endif
        if (n != 2 || !IS_FIX(a[0]) || !IS_FIX(a[1])) { vm_status = VM_TYPEERROR; return NIL; }
        return io_disk_load_lib((uint8_t)FIXVAL(a[0]), (uint8_t)FIXVAL(a[1])) ? vm_t : NIL;
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
            int c;
            do { lisp_poll(); c = cbm_k_getin(); } while (c == 0);
            return vm_key_event(c);
        } else {
            int c = cbm_k_getin();
            return c == 0 ? NIL : vm_key_event(c);
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
#endif
#if defined(LISP65_FIRST_CLASS_BUFFER) && !defined(LISP65_BUFFER_NO_PRIMS)
    /* Numeric labels are intentionally visible to the registry parity gate. */
    case 63: /* %buffer-read */
    case 64: /* %buffer-write */
    case 65: /* %buffer-alloc */
#ifdef LISP65_C1_COMPILER_TIER
    case 66: /* %c1-control */
#endif
        return vm_buffer_call(pid, a, n);
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
static uint8_t vm_arity_accepts(uint8_t actual, uint8_t nargs, uint8_t flags) {
    uint8_t optional = CO_OPTIONAL_COUNT(flags);
    uint8_t minimum;
    if (!(flags & CO_FLAG_STRICT_ARITY)) return 0;
    if (optional > nargs) return 0;
    minimum = (uint8_t)(nargs - optional);
    if (actual < minimum) return 0;
    return (flags & CO_FLAG_REST) || actual <= nargs;
}
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
    HB(1); LA(4);   /* D: vm_run-Entry */

    /* Objekt laden + Header/Fenster einrichten (auch fuer TAILCALL).
     * Layout im Puffer: [Header+littab | Payload-Fenster]. Der Payload streamt inkrementell:
     * nur min(len, VM_CODEBUF) Bytes werden initial geladen; groessere Objekte laden ihr Payload
     * fensterweise per Bulk-DMA nach (WIN_ENSURE), waehrend Header+littab resident bleiben. */
#define OBJ_SETUP() do { \
        uint16_t l0_ = (len < VM_CODEBUF) ? len : VM_CODEBUF; \
        vm_code_load(bank, off, l0_, cbuf); \
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
        payload_off = (uint16_t)(off + hdrlen); \
        payload_len = (uint16_t)(len - hdrlen); \
        pwin_max    = (uint16_t)(VM_CODEBUF - hdrlen); \
        win = 0; \
        winlen = (payload_len < pwin_max) ? payload_len : pwin_max; \
        streaming = (winlen < payload_len); \
        LA(3); /* C: OBJ_SETUP fertig */ \
    } while (0)

    /* Nach einem geschachtelten Aufruf (CALL/CALLPRIM ueberschrieb Puffer UND die
     * vmr_*-Globals!): Header+littab nachladen, ALLE Header-Ableitungen reparsen und das
     * Payload-Fenster am Resume-pc erzwingen. pcur_ MUSS der Aufrufer VOR dem Nested-Call
     * gesichert haben (die Fenster-Globals gehoeren nach der Rueckkehr dem Callee).
     * Trigger unveraendert Owner-Tag; Match = Callee war dieselbe Fn im selben Fenster,
     * dann stimmen auch die Globals (deterministische Header-Ableitung). */
#define BUF_ENSURE_MINE(pcur_) do { \
        if (vm_buf_bank != bank || vm_buf_off != off) { \
            /* fremde Fn resident: Header laden + ALLE Ableitungen reparsen */ \
            vm_code_load(bank, off, (uint16_t)CO_OFF_LITTAB, cbuf); \
            nargs   = cbuf[CO_OFF_NARGS]; \
            nlocals = cbuf[CO_OFF_NLOCS]; \
            flags   = cbuf[CO_OFF_FLAGS]; \
            nlits   = cbuf[CO_OFF_NLITS]; \
            hdrlen  = (uint16_t)(CO_OFF_LITTAB + 2 * (uint16_t)nlits); \
            vm_code_load(bank, off, hdrlen, cbuf); \
            littab      = cbuf + CO_OFF_LITTAB; \
            code        = cbuf + hdrlen; \
            payload_off = (uint16_t)(off + hdrlen); \
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
                vm_code_load(bank, (uint16_t)(payload_off + pc_), winlen, cbuf + hdrlen); \
                ip = code; \
            } \
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

        case OP_ADD: case OP_SUB: case OP_MUL: case OP_DIV: case OP_REMAINDER: case OP_MOD:
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

        case OP_JMPREL:    { int8_t d = (int8_t)RD8(); ip += d; break; }
        case OP_JFALSEREL: { int8_t d = (int8_t)RD8(); if (POP() == NIL) ip += d; break; }

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
            if (di >= 0 && di < (int)dir_n && dir_len[di]) {
#ifdef LISP65_VM_DIAGNOSTICS
                vm_pending_fn = sym;
#endif
                res = vm_run(dir_bank0, dir_off_get(di), dir_len[di], cargs, n);  /* -> VM (anderer Puffer, Paritaet) */
#ifndef LISP65_V2_CARRIER_CUT
            } else if (vm_treewalk_call) {
                res = vm_treewalk_call(sym, cargs, n);          /* -> Tree-Walker (kann re-entrant VM clobbern) */
#endif
            } else { vm_status = VM_DIRMISS; goto done; }
            if (vm_status != VM_OK) goto done;
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
            if (di < 0 || di >= (int)dir_n || !dir_len[di]) {   /* Tail-Aufruf an nicht-kompilierte Fn -> Tree-Walker, Ergebnis = Rueckgabe */
#ifndef LISP65_V2_CARRIER_CUT
                if (vm_treewalk_call) { r = vm_treewalk_call(sym, cargs, n); goto done; }
#endif
                vm_status = VM_DIRMISS; goto done;
            }
#ifdef LISP65_VM_DIAGNOSTICS
            run_fn = sym;
#endif
            bank = dir_bank0; off = dir_off_get(di); len = dir_len[di];
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
            if (vm_status != VM_OK) goto done;
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
        case OP_CLOSURE: {   /* Closure bauen (schwere Schleife+alloc -> vm_op_closure, spart Switch-Bloat).
                              * littab[li] = Helfer (Symbol ODER BCODE-Immediate: lcc-Self-Hosting, kein __L-Leck). */
            uint8_t li = RD8(), nuv = RD8();
            if (!vm_op_closure(LIT(li), nuv, vb)) goto done;
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
    /* Diagnose-Naht: Fehlerort auch OHNE das schwere Diagnostics-Modul festhalten
     * (Bank/Offset + Fenster-PC + Opcode -> Funktion via Manifest/Disasm). */
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
