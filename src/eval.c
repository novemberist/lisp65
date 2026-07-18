/* lisp65 — Evaluator (Lane K), Lisp-2, GC-sicher
 * Phase 1: lexikalisches Environment + Closures, Spezialformen
 * quote/quasiquote/if/lambda/setq/progn/defmacro/function, Makro-Hook, Primitive.
 *
 * GC-Disziplin: GC laeuft nur in alloc(). Jede Funktion, die einen lebenden obj ueber
 * eine Allokation haelt, pusht ihn auf den Shadow-Root-Stack. Muster: base merken,
 * frei pushen, vor jedem return gc_rootsp=base zuruecksetzen. cons() schuetzt seine
 * eigenen Argumente bereits.
 */
#include "eval.h"
#include "mem.h"
#include "symbol.h"
#include "reader.h"
#include "printer.h"
#include "interrupt.h"
#include "io.h"
#include <string.h>

#ifdef LISP65_V2_CARRIER_CUT
#if !defined(LISP65_VM) || !defined(LISP65_DIALECT_V2) || \
    !defined(LISP65_TREEWALK_STRIP) || !defined(LISP65_VM_NATIVE_APPLY) || \
    !defined(LISP65_V2_NATIVE_CAPABILITIES) || \
    !defined(LISP65_V2_NATIVE_STRING_CODECS) || \
    !defined(LISP65_V2_SERVICE_REGISTRY_CLOSED)
#error "LISP65_V2_CARRIER_CUT requires the complete staged v2 VM capability profile"
#endif
#endif
#ifdef LISP65_STAGED_BOOT_OVERLAY
#define WORKBENCH_BOOTFN __attribute__((section(".lisp65_boot"), noinline, used))
#define WORKBENCH_BOOTDATA __attribute__((section(".lisp65_boot.names"), used))
#define WORKBENCH_BOOTLINK
#else
#define WORKBENCH_BOOTFN
#define WORKBENCH_BOOTDATA
#define WORKBENCH_BOOTLINK static
#endif
#ifdef LISP65_HEARTBEAT   /* Diagnose: Schleifen-Ticker auf Bildschirm-RAM (Zeichen flackern) */
#define HB(i) (++*(volatile unsigned char *)(0x0800 + (i)))
#define LA(c) (*(volatile unsigned char *)(0x0800 + 50) = (unsigned char)(c))
#else
#define HB(i) ((void)0)
#define LA(c) ((void)0)
#endif

#ifdef LISP65_VM
#include "vm.h"   /* K3: Bytecode-VM-Integration (gegatet; Default-Build ohne VM unveraendert) */
#ifdef LISP65_DIALECT_V2
#include "v2_native_function_dispatch.h"
#endif

/* VM-Fehlerstatus in einen Lisp-Abbruch uebersetzen (REPL faengt via Toplevel; ohne aktives
 * Toplevel ist lisp_abort ein No-op und der Aufrufer sieht den Fehlerwert). */
static __attribute__((noinline)) void vm_check_status(void) {   /* mehrfach gerufen: Inline-Kopien kosten .text */
    switch (vm_status) {
    case VM_OK:
    case VM_HALT:      return;
    default: {
        /* Status VOR dem Abort loeschen: vm_run startet nicht mehr auf klebrigem
         * Fehler (s. vm.c-Eintritt) -- ohne das Aufraeumen hier waere die REPL nach
         * dem ersten Fehler tot. Die Message zeigt auf statische Puffer (safe). */
#ifndef LISP65_NUMERIC_ERRORS
        const char *m = vm_status_message();
#else
        lisp65_error_code code = vm_status_error_code(vm_status);
#endif
        vm_status = VM_OK;
#ifdef LISP65_NUMERIC_ERRORS
        lisp_abort_code(code);
#else
        lisp_abort(m);
#endif
        break;
    }
    }
}

#ifdef LISP65_V2_CARRIER_CUT
/* The carrier-cut has one checked path from resident services into VM-native
 * application. Keep the sticky-status cleanup and Lisp abort conversion at
 * the same boundary previously owned by apply(). */
static obj eval_vm_native_apply_checked(obj fn, obj arglist) {
    obj result = vm_native_apply(fn, arglist);
    vm_check_status();
    return result;
}
#endif
#endif

/* Materialized once: the runtime LCC slices reuse these resident list accessors. */
obj car(obj o)  { return IS_PTR(o) ? cell_a(o) : NIL; }
obj cdr(obj o)  { return IS_PTR(o) ? cell_b(o) : NIL; }
static obj cadr(obj o) { return car(cdr(o)); }
static __attribute__((unused)) obj caddr(obj o){ return car(cdr(cdr(o))); }

/* Symbol = SYMI-Immediate (interniert) ODER T_SYM-Zelle (gensym). Der Immediate-Test ist
 * ein reiner Registervergleich -> Variablen-Lookup im heissen Pfad wird BILLIGER. */
static uint8_t is_sym(obj o) { return IS_SYMI(o) || (IS_PTR(o) && cell_type(o) == T_SYM); }

/* "undefined function" MIT Namen (Diagnose 2026-07-02: stumme UNDEFs kosteten heute drei
 * HW-Zyklen). Statischer Puffer: lisp_abort longjmpt — die Message muss ueberleben. */
#ifndef LISP65_NUMERIC_ERRORS
static const char *undef_msg(obj sym) {
    static char buf[48];
    const char *n = symname(sym);
    char *p = buf; const char *q = "undefined function: ";
    while (*q) *p++ = *q++;
    while (*n && p < buf + 46) *p++ = *n++;
    *p = 0;
    return buf;
}
#endif

/* Gecachte Ergebnis-Symbole der IDE-Primitive (in eval_init interniert): intern() ist
 * gross — inline an mehreren apply_prim-Stellen blaehte LTO den Code um ~1,8 KB
 * (gap 1388->94, 2026-07-02). */
static obj k_bytecode, k_primitive, k_closure, k_macro, k_other;
#ifdef LISP65_DIALECT_V2
static obj k_lcc_invalid_parameter_list;
#endif
#ifdef LISP65_EVAL_KEYBOARD_PRIMS
static obj k_key, k_shift;
#endif

#ifdef LISP65_EVAL_KEYBOARD_PRIMS
/* Tastatur-Event normalisieren (Codex-Vertrag: `(key code mods)`). PETSCII-Buchstaben ->
 * ASCII klein; geshiftete ($C1-$DA) -> ASCII GROSS + (shift). Steuercodes (RETURN $0D,
 * DEL $14, CRSR $11/$91/$1D/$9D, CLR $93, Ctrl+Buchstabe $01-$1A, ...) bleiben ROH —
 * Keymaps matchen die Codes direkt. Ctrl+M ist auf GETIN-Ebene von RETURN nicht
 * unterscheidbar (beide $0D) — Editor behandelt $0D als RETURN. */
static obj key_event(int c) {
    obj mods = NIL, e;
    if (c >= 0xC1 && c <= 0xDA) { c -= 0x80; mods = cons(k_shift, NIL); }
    else if (c >= 'A' && c <= 'Z') c += 0x20;
    GC_PUSH(mods);
    e = cons(gc_rootstack[GC_TOP], NIL);            /* (mods) */
    GC_SET(GC_TOP, e);
    e = cons(MKFIX((int16_t)c), gc_rootstack[GC_TOP]);   /* (code mods) */
    GC_SET(GC_TOP, e);
    e = cons(k_key, gc_rootstack[GC_TOP]);               /* (key code mods) */
    GC_POPN(1);
    return e;
}
#endif

/* Gecachte Special-Form-Symbole (in eval_init interniert): der Dispatch vergleicht per eq
 * (op == sf_x) statt strcmp(symname(op), "x"). Das haelt symname() KALT — kein Namens-Lookup
 * im heissen eval-/Binding-Pfad -> Voraussetzung fuer die namepool-Auslagerung ins erw. RAM
 * (sonst 10+ EXT-DMAs pro Auswertung). Symbole sind interniert -> eq ist exakt. */
#ifndef LISP65_TREEWALK_STRIP
static obj sf_quote, sf_quasiquote, sf_if, sf_progn, sf_lambda, sf_function,
           sf_setq, sf_defmacro, sf_unquote, sf_unquote_splicing, sf_rest;
/* C-Special-Forms statt Prelude-Makros: die Makro-Definitionen (T_MACRO-Strukturen) haetten
 * ~200 Heap-Zellen + ~1 KB Quelltext gekostet (Bank-0-Gate); als Special-Forms kosten sie nur
 * .text und laufen mit echtem TCO. `cond`/`and`/`or` gibt es seit 2026-07-05 unter
 * LISP65_EVAL_CONTROL_SF (Aequivalenz-Suite-Befund: Compiler kann sie, Treewalk nicht =
 * Werkbank-REPL-Loch; Zuschalten braucht Diaet — historische Messung ~600 B). `case` fehlt
 * weiter bewusst (Drift-Arbeitsliste). */
static obj sf_defun, sf_when, sf_unless, sf_let, sf_letstar, sf_dotimes, sf_dolist;
#ifdef LISP65_DIALECT_V2
static obj sf_defvar, sf_optional;
#ifdef LISP65_DIALECT_FAMILY_HARNESS
static obj sf_v2_string_codes, sf_v2_string_from_codes;
#endif
static uint8_t tree_arity_require(obj params, obj args);
static uint8_t tree_macro_arity_require(obj name, obj params, obj args);
#endif
#ifdef LISP65_EVAL_CONTROL_SF
static obj sf_cond, sf_and, sf_or;   /* Aequivalenz-Naht: Compiler-gelowerte Formen auch im Treewalk */
#endif
#endif
#ifdef LISP65_EVAL_CONTROL_SF
#ifndef LISP65_EVAL_DIV_PRIM
#define LISP65_EVAL_DIV_PRIM 1       /* CONTROL_SF schliesst "/" ein; "/" ist auch solo pinbar (~60 B) */
#endif
#endif
static obj lisp_t;   /* gecachtes t (heisses Praedikat-Ergebnis; sonst intern("t")-Lookup je Aufruf) */

enum { P_ADD, P_SUB, P_MUL, P_MOD, P_CONS, P_CAR, P_CDR, P_CONSP, P_EQ, P_EQL,
       P_LT, P_GT, P_NUMEQ, P_LE, P_GE,
       P_LIST, P_FUNCALL, P_APPLY, P_SETFN, P_GENSYM, P_BOUNDP, P_SYMVAL,
       P_PEEK, P_POKE, P_LOAD,
       P_STRINGP, P_STR2LIST, P_LIST2STR, P_STRLEN, P_STRREF,
       P_NUMBERP, P_SYMBOLP, P_WRITECHAR, P_PRIN1,
#ifndef LISP65_OUTPUT_WRAPPERS_IN_STDLIB
       P_WRITESTR, P_TERPRI, P_PRINC, P_PRINT, P_WRITE, P_WRITELINE,
#endif
#ifndef LISP65_SCREEN_BULK_P_IN_STDLIB
       P_SCRBULKP,
#endif
       /* IDE-Kernel-Naht (Codex-Vertrag docs/editor-architecture.md, Lane K 2026-07-02):
        * Screen-/Keyboard-Primitive (gegated) + Symbol-Introspektion fuer apropos/describe. */
       P_SCRSIZE, P_SCRCLEAR, P_SCRPUT, P_READKEY, P_POLLKEY,
       P_SYMCOUNT, P_SYMMAX,
#ifdef LISP65_NTH_SYMBOL_PRIM
       P_NTHSYM,
#endif
       P_SYMNAME, P_FNKIND, P_NUM2STR,
       P_NREVERSE, P_RPLACA, P_RPLACD, P_SCRWRITE, P_NCALL,
       /* SAVE-Kern-Naht (nur unter MEGA65_F011_WRITE registriert; Namen = kuenftige
        * CALLPRIM-Kandidaten fuer den Maschinenraum — Anti-Drift: EIN Name, EINE Semantik). */
       P_DSKRD, P_DSKBYTE, P_DSKPOKE, P_DSKWR,
       /* eval-Naht (nur unter LISP65_EVAL_PRIMS registriert; im Maschinenraum kuenftig
        * dieselben Namen auf compile_run_top_form — Anti-Drift). */
       P_EVAL, P_EVALSTR, P_SAVE, P_DIV, P_MEXP1, P_LCCINST, P_SETMACRO,
       /* FASL-B2 (docs/device-fasl-design.md; nur unter LISP65_FASL registriert) */
       P_FSTAGE, P_FSTGET, P_FREADF, P_FSRC, P_FSAVE, P_FLIBST,
       /* Workbench-Slow-Path: compile-string (Buffer-String -> FASL), OHNE Disk-Source
        * (kein disk_dir_find). P_CSOPEN: String-Reader (COMPILE_STRING, arena-only).
        * P_SVSTG (%save-staged dst len): base=0-Ausgabe via io_disk_save_named speichern
        * (mit `save` GETEILT) -> die out-of-line Base-Variante io_disk_save_range faellt
        * aus dem Workbench-Produkt (nur FASL-Diagnoseprofil). */
       P_CSOPEN, P_SVSTG, P_LCCBADPARAM, P_REMAINDER, P_LISTMALFORMED,
       P_SET, P_KEYEVENT };

#if defined(LISP65_VM) && defined(LISP65_DIALECT_V2) && defined(LISP65_V2_TREE_PRIMITIVE_VIEW)
/* The installed T_PRIM cell is the resident identity.  The registry generates
 * the only translation from that identity to a VM route, so Apply and
 * function-kind cannot acquire independent primitive name inventories. */
int8_t eval_v2_native_function_view(obj sym, uint8_t *kind, uint8_t *value) {
    obj fn = sym_function(sym);
    int16_t tree_id;
    if (!(IS_PTR(fn) && cell_type(fn) == T_PRIM)) return 0;
    tree_id = FIXVAL(cell_a(fn));
    switch (tree_id) {
#define V2_TREE_ROW(tree, route_kind, route_value) \
    case tree: *kind = (uint8_t)(route_kind); *value = (uint8_t)(route_value); return 1;
        LISP65_V2_NATIVE_FUNCTION_TREE_ROWS(V2_TREE_ROW)
#undef V2_TREE_ROW
    default:
        return -1;
    }
}
#endif

#if defined(__MEGA65__) || defined(__C64__) || defined(__CBM__)
#define LISP_REAL_MEM 1   /* echter Speicherzugriff nur auf dem Geraet */
#include <cbm.h>          /* GETIN fuer read-key/poll-key */
#endif
#if defined(LISP65_SCREEN_DRIVER) || defined(LISP65_EVAL_SCREEN_PRIMS)
#include "screen.h"
#endif
#if defined(LISP65_SCREEN_DRIVER) && !defined(LISP65_VM_STDLIB_IO_WRAPPERS)
#define LISP65_EVAL_SCREEN_PRIMS 1
#endif
#if defined(LISP65_EVAL_SCREEN_PRIMS) && defined(LISP_REAL_MEM)
#define LISP65_EVAL_KEYBOARD_PRIMS 1
#endif

#if defined(LISP65_MACROEXPAND_PRIM) && !defined(LISP65_TREEWALK_STRIP)
/* Forwards fuer P_MEXP1 (beide static, weiter unten definiert). */
static obj env_extend(obj params, obj vals, obj env);
static obj eval_body(obj body, obj env);
#endif

#ifdef LISP_REAL_MEM
/* 16-Bit-Adresse aus Hi/Lo-Fixnums (Fixnums sind 15-Bit, daher byteweise). */
static unsigned hilo(obj hi, obj lo) {
    return (unsigned)(((unsigned)(FIXVAL(hi) & 0xFF) << 8) | (unsigned)(FIXVAL(lo) & 0xFF));
}
#endif

#ifdef LISP65_EVAL_PRIMS
/* eval-Naht (Prio 2, docs/two-product-workflow.md): (eval-string str) streamt die Zeichen
 * DIREKT aus der T_STR-Zeichenliste in den Pull-Reader (kein Puffer, kein .bss) und wertet
 * Form fuer Form aus — Werkzeug fuer Defun-at-point-Eval der IDE. GC-Sicherheit: der Rest-
 * Cursor liegt waehrend der evals in einem gepushten Root-Slot (GC_SET nach jedem Zeichen).
 * NICHT reentrant mit Disk-Load-Streaming (ein Reader-Fetch-Zustand — wie load selbst). */
#ifdef LISP65_STRING_ARENA
/* Arena: String-Objekt + Index-Cursor (Bytes liegen in der Arena, keine cdr-Kette). */
static obj      es_str;
static uint16_t es_idx;
static char es_fetch(void) {
    if (!(IS_PTR(es_str) && cell_type(es_str) == T_STR) || es_idx >= str_len(es_str)) return '\0';
    return (char)str_byte(es_str, es_idx++);
}
#else
static obj      es_cursor;
static uint16_t es_slot;
static char es_fetch(void) {
    obj c = es_cursor;
    if (!(IS_PTR(c) && cell_type(c) == T_CONS)) return '\0';
    es_cursor = cell_b(c);
    GC_SET(es_slot, es_cursor);
    return (char)FIXVAL(cell_a(c));
}
#endif
#endif

/* String-Namen (fasl/save/load) in einen C-Puffer kopieren + nul-terminieren. Arena: str_copy_out;
 * sonst char-listen-Walk. Setzt `i` auf die kopierte Byte-Zahl. */
#ifdef LISP65_STRING_ARENA
#define STR_NAME_COPY(S, NAME, MAX, I) do { (I) = (uint8_t)str_copy_out((S), (NAME), (MAX)); (NAME)[(I)] = '\0'; } while (0)
#else
#define STR_NAME_COPY(S, NAME, MAX, I) do { obj cs_; for (cs_ = cell_a(S); IS_PTR(cs_) && cell_type(cs_) == T_CONS && (I) < (MAX); cs_ = cell_b(cs_)) (NAME)[(I)++] = (char)FIXVAL(cell_a(cs_)); (NAME)[(I)] = '\0'; } while (0)
#endif

#ifdef LISP65_COMPILE_STRING
/* Reader-Fetch ueber einen Quelltext-STRING (compile-string: "Buffer ist Quelle"). Muster wie
 * es_fetch (eval-string), aber der String wird NICHT ausgewertet: read_expr_stream liest Form fuer
 * Form, der Aufrufer gibt sie an den FASL-Emitter. Kein Disk, kein NUL-terminierter C-Puffer.
 * GC-Sicherheit: cs_str IST der Quell-String selbst (Objekt-ID) und bleibt via den lebendigen
 * `source`-Parameter der Lisp-Funktion gerootet; Arena-Compaction aktualisiert cell_b, cs_idx ist
 * ein reiner Byte-Index. Deshalb NUR unter LISP65_STRING_ARENA (der char-list-Cursor-Fallback waere
 * nicht GC-sicher: er wandert durch ungerootete CDRs). */
#ifndef LISP65_STRING_ARENA
#error "LISP65_COMPILE_STRING requires LISP65_STRING_ARENA (GC-safe string reader; char-list cursor is not)"
#endif
static obj      cs_str;
static uint16_t cs_idx;
static char cs_fetch(void) {
    if (!(IS_PTR(cs_str) && cell_type(cs_str) == T_STR) || cs_idx >= str_len(cs_str)) return '\0';
    return (char)str_byte(cs_str, cs_idx++);
}
#endif

#ifdef LISP65_LCC_INSTALL
#ifndef LISP65_VM
#error "LISP65_LCC_INSTALL requires LISP65_VM"
#endif
#include "lcc_install_overlay.h"

/* The transport is idle before transient bytecode runs. This is essential because
 * vm_run may allocate or abort through a tree-walker bridge. */
static obj lcc_install_obj(obj fnlist, obj defname) {
    obj hs = intern("%lcc-lit-keep"), hm = intern("%lcc-helper");
    lcc_install_result installed;
    lcc_install_status status;
    uint16_t root_base = gc_rootsp;
    obj result;
    if (hs == NIL || hm == NIL) return NIL;
    if (!GC_CAN_RESERVE(2)) {
        lisp_abort_static(LISP65_ERR_LCC_INSTALL,
                          lcc_install_status_message(LCC_INSTALL_ERR_ROOTS));
        return NIL;
    }
    GC_PUSH(fnlist);
    GC_PUSH(defname);
    status = lcc_install_overlay(fnlist, defname, lisp_t, hs, hm, &installed);
    if (status != LCC_INSTALL_OK) {
        gc_rootsp = root_base;
        lisp_abort_static(LISP65_ERR_LCC_INSTALL,
                          lcc_install_status_message(status));
        return NIL;
    }
    if (!installed.transient) {
        gc_rootsp = root_base;
        return installed.result;
    }
    result = vm_run(installed.bank, installed.off, installed.length, NULL, 0);
    lcc_install_transient_pop(&installed);
    gc_rootsp = root_base;
    vm_check_status();
    return result;
}
#endif

#if !defined(LISP65_TREEWALK_STDLIB_BRIDGES) && \
    !defined(LISP65_V2_CARRIER_CUT)
/* variadisch-monotoner Zahlenvergleich (CL-treu): (< a b c) ⇔ a<b<c.
 * op: 0:< 1:> 2:= 3:<= 4:>= */
static obj cmp_chain(obj args, uint8_t op) {
    while (args != NIL && cdr(args) != NIL) {
        int16_t x = FIXVAL(car(args)), y = FIXVAL(cadr(args));
        uint8_t ok = (op == 0) ? (x <  y) : (op == 1) ? (x >  y) :
                     (op == 2) ? (x == y) : (op == 3) ? (x <= y) : (x >= y);
        if (!ok) return NIL;
        args = cdr(args);
    }
    return lisp_t;
}
#endif

#ifndef LISP65_TREEWALK_STRIP
static obj eval_env(obj e, obj env);

/* Schleifen-Body sequenziell auswerten (dotimes/dolist; Ergebnis verworfen). noinline:
 * der Handler in eval_env hatte die Schleife 2x inline — ~250 B vermeidbares .text. */
static __attribute__((noinline)) void loop_body(obj body, obj env) {
    while (IS_PTR(body) && cell_type(body) == T_CONS) { eval_env(cell_a(body), env); body = cell_b(body); }
}
#endif
#ifndef LISP65_V2_CARRIER_CUT
static obj apply(obj fn, obj args);
#endif
#ifndef LISP65_TREEWALK_STRIP
static obj qq(obj x, obj env, uint8_t d);
#endif

#if !defined(LISP65_OUTPUT_WRAPPERS_IN_STDLIB) && \
    !defined(LISP65_V2_CARRIER_CUT)
static obj write_string_obj(obj s) {
    if (!(IS_PTR(s) && cell_type(s) == T_STR)) {
        lisp_abort_static(LISP65_ERR_WRITE_STRING_TYPE, "write-string: not a string"); return NIL;
    }
    print_string_raw(s);
    return s;
}
#endif

static void write_readable_obj(obj x) {
    screen_scroll_guard();
    print_obj(x);
}

#if defined(LISP65_DIALECT_V2) && !defined(LISP65_V2_CARRIER_CUT)
static uint8_t primitive_exact_arity(obj args, uint8_t expected) {
    uint8_t actual = 0;
    while (IS_PTR(args) && cell_type(args) == T_CONS) {
        if (actual == expected) goto wrong;
        actual++;
        args = cell_b(args);
    }
    if (args == NIL && actual == expected) return 1;
wrong:
    lisp_abort_static(LISP65_ERR_WRONG_ARGUMENT_COUNT, "wrong argument count");
    return 0;
}

static uint8_t primitive_byte_arg(obj value) {
    if (!IS_FIX(value) || FIXVAL(value) < 0 || FIXVAL(value) > 255) {
        lisp_abort_static(LISP65_ERR_VM_TYPE, "vm: type error");
        return 0;
    }
    return 1;
}
#endif

/* args ist bereits ausgewertet; von apply mit gepushtem args/fn aufgerufen. */
#ifndef LISP65_V2_CARRIER_CUT
#if defined(LISP65_DIALECT_FAMILY_HARNESS) && defined(LISP65_DIALECT_V2)
static obj tree_apply_splice(obj args) {
    uint16_t base;
    obj tail, result;
    if (!(IS_PTR(args) && cell_type(args) == T_CONS)) {
        lisp_abort_static(LISP65_ERR_WRONG_ARGUMENT_COUNT, "wrong argument count");
        return NIL;
    }
    if (cdr(args) == NIL) {
        tail = car(args);
        while (IS_PTR(tail) && cell_type(tail) == T_CONS) tail = cdr(tail);
        if (tail != NIL) {
            lisp_abort_static(LISP65_ERR_VM_TYPE, "apply: final argument is not a list");
            return NIL;
        }
        return car(args);
    }
    base = gc_rootsp;
    GC_PUSH(args);
    tail = tree_apply_splice(cdr(args));
    GC_PUSH(tail);
    result = cons(car(gc_rootstack[base]), tail);
    gc_rootsp = base;
    return result;
}
#endif

static obj apply_prim(int16_t id, obj args) {
    switch (id) {
#ifdef LISP65_DIALECT_V2
    case P_LCCBADPARAM:
        if (!primitive_exact_arity(args, 0)) return NIL;
        lisp_abort_static_symbol(LISP65_ERR_LCC_INVALID_PARAMETER_LIST,
                                 k_lcc_invalid_parameter_list,
                                 "compile failed");
        return NIL;
    case P_LISTMALFORMED:
        if (!primitive_exact_arity(args, 0)) return NIL;
        lisp_abort_static(LISP65_ERR_VM_TYPE, "vm: type error");
        return NIL;
    case P_SET: {
        obj symbol;
        if (!primitive_exact_arity(args, 2)) return NIL;
        symbol = car(args);
        if (!is_sym(symbol)) {
            lisp_abort_static(LISP65_ERR_VM_TYPE, "vm: type error");
            return NIL;
        }
        set_sym_value(symbol, cadr(args));
        return cadr(args);
    }
    case P_KEYEVENT: {
        int16_t mode = 0;
        if (args != NIL) {
            if (!primitive_exact_arity(args, 1) || !IS_FIX(car(args))) {
                lisp_abort_static(LISP65_ERR_VM_TYPE, "vm: type error");
                return NIL;
            }
            mode = FIXVAL(car(args));
        }
        if (mode != 0 && mode != 1) {
            lisp_abort_static(LISP65_ERR_VM_TYPE, "vm: type error");
            return NIL;
        }
#ifdef LISP65_EVAL_KEYBOARD_PRIMS
        {
            int c;
            if (mode) {
                do { lisp_poll(); c = cbm_k_getin(); } while (c == 0);
            } else {
                c = cbm_k_getin();
                if (c == 0) return NIL;
            }
            return key_event(c);
        }
#else
        return NIL;
#endif
    }
#endif
#ifndef LISP65_TREEWALK_STDLIB_BRIDGES
    case P_ADD: { int16_t a = 0; while (args != NIL) { a = (int16_t)(a + FIXVAL(car(args))); args = cdr(args); } return MKFIX(a); }
    case P_MUL: { int16_t a = 1; while (args != NIL) { a = (int16_t)(a * FIXVAL(car(args))); args = cdr(args); } return MKFIX(a); }
    case P_SUB: {
        int16_t a;
        if (args == NIL) return MKFIX(0);
        a = FIXVAL(car(args)); args = cdr(args);
        if (args == NIL) return MKFIX(-a);
        while (args != NIL) { a = (int16_t)(a - FIXVAL(car(args))); args = cdr(args); }
        return MKFIX(a);
    }
#endif
#ifndef LISP65_TREEWALK_STRIP
    case P_MOD: {
        int16_t a = FIXVAL(car(args)), b = FIXVAL(cadr(args)), m;
        if (b == 0) { lisp_abort_static(LISP65_ERR_DIVISION_BY_ZERO, "division by zero"); return NIL; }
        m = (int16_t)(a % b);
        if (m != 0 && ((m < 0) != (b < 0))) m = (int16_t)(m + b);   /* CL-mod: Vorzeichen des Divisors */
        return MKFIX(m);
    }
    case P_REMAINDER: {
        int16_t a = FIXVAL(car(args)), b = FIXVAL(cadr(args));
        if (b == 0) { lisp_abort_static(LISP65_ERR_DIVISION_BY_ZERO, "division by zero"); return NIL; }
        return MKFIX((int16_t)(a % b));
    }
#endif
#ifndef LISP65_TREEWALK_STDLIB_BRIDGES
    case P_LT:    return cmp_chain(args, 0);
    case P_GT:    return cmp_chain(args, 1);
    case P_NUMEQ: return cmp_chain(args, 2);
    case P_LE:    return cmp_chain(args, 3);
    case P_GE:    return cmp_chain(args, 4);
#endif
#ifndef LISP65_TREEWALK_STDLIB_BRIDGES
    case P_CONS: return cons(car(args), cadr(args));
    case P_CAR:  return car(car(args));
    case P_CDR:  return cdr(car(args));
    case P_CONSP:return (IS_PTR(car(args)) && cell_type(car(args)) == T_CONS) ? lisp_t : NIL;
    case P_EQ:   return (car(args) == cadr(args)) ? lisp_t : NIL;
    /* eql: wie eq + Zahl/Char-Wertgleichheit. Fixnums sind immediate (Bitmuster
     * identisch => eq genuegt); Symbole interniert. Divergiert erst mit weiteren
     * Zahlentypen (Floats/Bignums). Vorerst identisch zu eq. */
    case P_EQL:  return (car(args) == cadr(args)) ? lisp_t : NIL;
    case P_LIST: return args;
#endif
    case P_FUNCALL: return apply(car(args), cdr(args));
    case P_APPLY:
#if defined(LISP65_DIALECT_FAMILY_HARNESS) && defined(LISP65_DIALECT_V2)
        {
            uint16_t base = gc_rootsp;
            obj fn, combined, result;
            if (!(IS_PTR(args) && cell_type(args) == T_CONS)) {
                lisp_abort_static(LISP65_ERR_WRONG_ARGUMENT_COUNT, "wrong argument count");
                return NIL;
            }
            fn = car(args); GC_PUSH(fn);
            combined = tree_apply_splice(cdr(args)); GC_PUSH(combined);
            result = apply(fn, combined);
            gc_rootsp = base;
            return result;
        }
#else
        return apply(car(args), cadr(args));
#endif
    case P_SETFN:   set_sym_function(car(args), cadr(args)); return cadr(args);
    case P_GENSYM:  return gensym();
    case P_BOUNDP: {
        obj s = car(args);
        return (is_sym(s) && sym_boundp(s)) ? lisp_t : NIL;
    }
#ifdef LISP65_DIALECT_V2
    case P_SYMVAL: {
        obj s;
        if (!primitive_exact_arity(args, 1)) return NIL;
        s = car(args);
        if (!is_sym(s)) {
            lisp_abort_static(LISP65_ERR_VM_TYPE, "vm: type error");
            return NIL;
        }
        return sym_value(s);
    }
#endif
    case P_PEEK: {                                  /* (peek hi lo) -> Byte */
#ifdef LISP65_DIALECT_V2
        if (!primitive_exact_arity(args, 2) ||
            !primitive_byte_arg(car(args)) ||
            !primitive_byte_arg(cadr(args))) return NIL;
#endif
#ifdef LISP_REAL_MEM
        return MKFIX(*(volatile unsigned char *)hilo(car(args), cadr(args)));
#else
        (void)args; return MKFIX(0);
#endif
    }
    case P_POKE: {                                  /* (poke hi lo wert) */
#ifdef LISP65_DIALECT_V2
        if (!primitive_exact_arity(args, 3) ||
            !primitive_byte_arg(car(args)) ||
            !primitive_byte_arg(cadr(args)) ||
            !primitive_byte_arg(car(cdr(cdr(args))))) return NIL;
#endif
#ifdef LISP_REAL_MEM
        *(volatile unsigned char *)hilo(car(args), cadr(args)) =
            (unsigned char)(FIXVAL(car(cdr(cdr(args)))) & 0xFF);
#endif
        return car(cdr(cdr(args)));
    }
#ifdef LISP65_LCC_INSTALL
    case P_LCCINST: {   /* (lcc-install fnlist name|nil) -> name | BCODE-Wert des Main */
        return lcc_install_obj(car(args), cadr(args));
    }
    case P_SETMACRO: {   /* (%set-macro name bcode-fn) -> name. Konvergenz-M2: Makro mit
                          * BYTECODE-Expander (T_MACRO, cell_a=BCODE) — defmacro-Install ohne
                          * eval_env (docs/einsuite-convergence-design.md). */
        obj nm = car(args), m = alloc(T_MACRO);
        if (m == NIL) return NIL;
        cell_set_a(m, cadr(args)); cell_set_b(m, NIL);
        set_sym_function(nm, m);
        return nm;
    }
#endif
#if defined(LISP65_FASL) || defined(LISP65_COMPILE_STRING)
    /* FASL-Byte-Naht (Workbench: LISP65_COMPILE_STRING = FASL OHNE Disk-Source): Datei-Fenster-
     * Zugriff (Bank-4-Scratch ab 256; host-testbar via Sim), Reader ohne Eval, String-Reader-Open.
     * Layout gehoert lib/lcc-fasl.lisp: [0..0x3F00) Quelle, [0x4000..) Ausgabe+Staging. */
    case P_FSTAGE: {   /* (%fasl-stage i b) -> t | nil (Deckel) */
        uint16_t i = (uint16_t)FIXVAL(car(args));
        if (i >= DISK_EXT_FILE_MAX) return NIL;
        ext_disk_put((uint16_t)(256u + i), (uint8_t)FIXVAL(cadr(args)));
        return lisp_t;
    }
    case P_FSTGET:     /* (%fasl-stage-get i) -> Byte */
        return MKFIX((int16_t)ext_disk_get((uint16_t)(256u + (uint16_t)FIXVAL(car(args)))));
    case P_FREADF: {   /* (%fasl-read-form) -> Form | %fasl-eof (Stream via %fasl-src/%cs-read-open) */
        obj form;
        if (reader_skip_peek() == '\0') return intern("%fasl-eof");
        form = read_expr_stream();
        return reader_status == READER_OK ? form : intern("%fasl-eof");
    }
#ifdef LISP65_COMPILE_STRING
    case P_CSOPEN: {   /* (%cs-read-open source-string) -> t: Reader ueber den Quelltext-STRING
                        * setzen (Buffer ist Quelle; kein Disk, kein disk_dir_find). Arena-only. */
        obj s = car(args);
        if (!(IS_PTR(s) && cell_type(s) == T_STR)) {
            lisp_abort_static(LISP65_ERR_COMPILE_STRING_TYPE, "compile-string: not a string"); return NIL;
        }
        cs_str = s; cs_idx = 0;
        reader_from_fetch(cs_fetch);
        return lisp_t;
    }
#endif
#ifdef MEGA65_F011_WRITE
    case P_SVSTG: {    /* (%save-staged "name" len) -> t | nil: die bereits bei base=0 gestagete
                        * Ausgabe [0..len) als BESTEHENDE Datei schreiben — via io_disk_save_named
                        * (mit `save` GETEILT, kein base-Arg -> keine io_disk_save_range-Variante). */
        obj s = car(args); char name[48]; uint8_t i = 0;
        if (!(IS_PTR(s) && cell_type(s) == T_STR)) {
            lisp_abort_static(LISP65_ERR_SAVE_STAGED_TYPE, "save-staged: not a string"); return NIL;
        }
        STR_NAME_COPY(s, name, 47, i);
        return io_disk_save_named(name, (unsigned int)FIXVAL(cadr(args))) ? lisp_t : NIL;
    }
#endif
#endif  /* FASL || COMPILE_STRING */
#ifdef LISP65_FASL
#ifdef MEGA65_F011_WRITE
    case P_FSRC: {     /* (%fasl-src "name") -> Quell-Bytes | 0 — DISK-SOURCE (zieht disk_dir_find);
                        * NUR unter LISP65_FASL (Diagnose/Historie), NICHT im Workbench-Produkt. */
        obj s = car(args); char name[48]; uint8_t i = 0;
        if (!(IS_PTR(s) && cell_type(s) == T_STR)) {
            lisp_abort_static(LISP65_ERR_FASL_TYPE, "fasl: not a string"); return NIL;
        }
        STR_NAME_COPY(s, name, 47, i);
        return MKFIX((int16_t)io_fasl_open_source(name));
    }
    case P_FSAVE: {    /* (%fasl-save "name" base len) -> t | nil — Base-Variante (io_disk_save_range),
                        * NUR FASL-Diagnoseprofil (Disk-Source @ base 8192); Workbench nutzt %save-staged. */
        obj s = car(args); char name[48]; uint8_t i = 0;
        if (!(IS_PTR(s) && cell_type(s) == T_STR)) {
            lisp_abort_static(LISP65_ERR_FASL_TYPE, "fasl: not a string"); return NIL;
        }
        STR_NAME_COPY(s, name, 47, i);
        return io_disk_save_range(name, (unsigned int)FIXVAL(cadr(args)),
                                  (unsigned int)FIXVAL(car(cdr(cdr(args))))) ? lisp_t : NIL;
    }
#ifdef LISP65_DISK_LIBS
    case P_FLIBST:     /* (%lib-staged n) -> t|nil: xemu-Diagnose (Monitor stagt, kein F011) */
        return io_disk_lib_staged((unsigned int)FIXVAL(car(args))) ? lisp_t : NIL;
#endif
#endif
#endif  /* FASL */
#ifdef LISP65_MACROEXPAND_PRIM
    case P_MEXP1: {
        {                                 /* (macroexpand-1 form) -> Form, 1 Stufe
        (Traeger-Naht des Self-Hosting-Compilers: lcc fragt den TRAEGER nach der Expansion;
        am Geraet (P6) ersetzt funcall-auf-BCODE-Expander diese Naht). */
        obj form = car(args), op, fn, pb;
#ifndef LISP65_TREEWALK_STRIP
        obj menv, r;
#endif
        if (!(IS_PTR(form) && cell_type(form) == T_CONS)) return form;
        op = cell_a(form);
        if (!is_sym(op)) return form;
        fn = sym_function(op);
        if (!(IS_PTR(fn) && cell_type(fn) == T_MACRO)) return form;
        pb = cell_a(fn);
#ifdef LISP65_LCC_INSTALL
        if (IS_BCODE(pb)) return apply(pb, cell_b(form));   /* M2: BCODE-Expander, rohe Args */
#endif
#ifdef LISP65_TREEWALK_STRIP
        return form;   /* M3: (params . body)-Makros existieren ohne Treewalk nicht */
#else
#ifdef LISP65_DIALECT_V2
        if (!tree_macro_arity_require(op, car(pb), cell_b(form))) return NIL;
#endif
        menv = env_extend(car(pb), cell_b(form), cell_b(fn));   /* ROHE Args (wie eval_env) */
        GC_PUSH(menv);
        r = eval_body(cdr(pb), menv);
        GC_POPN(1);
        return r;
#endif
    } }
#endif
#ifdef LISP65_EVAL_PRIMS
    case P_EVAL:                                    /* (eval form) -> Wert (globales env) */
        return eval(car(args));
    case P_EVALSTR: {                               /* (eval-string str) -> Wert der LETZTEN Form */
        obj s = car(args), r = NIL;
        if (!(IS_PTR(s) && cell_type(s) == T_STR)) {
            lisp_abort_static(LISP65_ERR_EVAL_STRING_TYPE, "eval-string: not a string"); return NIL;
        }
#ifdef LISP65_STRING_ARENA
        {   /* Arena: String-Objekt rooten (Compaction aktualisiert seinen Offset), Index-Cursor */
            obj sv_str = es_str; uint16_t sv_idx = es_idx;
            es_str = s; es_idx = 0;
            GC_PUSH(s);                             /* String ueber die evals lebend halten */
            GC_PUSH(NIL);                           /* Ergebnis-Slot */
            reader_from_fetch(es_fetch);
            for (;;) {
                obj form;
                if (reader_skip_peek() == '\0') break;
                form = read_expr_stream();
                if (reader_status != READER_OK) { r = NIL; break; }
                r = eval(form);
                GC_SET(GC_TOP, r);
            }
            GC_POPN(2);
            es_str = sv_str; es_idx = sv_idx;
            return r;
        }
#else
        {
        obj      sv_cursor = es_cursor;             /* Verschachtelung: aeusseren Stream-Zustand retten
        (zuverlaessig, wenn das innere eval-string die LETZTE Form der aeusseren Quelle ist —
        der Reader-Peek-Zustand selbst ist EINER, wie bei load; s. reader.h) */
        uint16_t sv_slot   = es_slot;
        es_cursor = cell_a(s);
        GC_PUSH(es_cursor); es_slot = (uint16_t)GC_TOP;
        GC_PUSH(NIL);                               /* Ergebnis-Slot: r ueber die naechste Form retten */
        reader_from_fetch(es_fetch);
        for (;;) {
            obj form;
            if (reader_skip_peek() == '\0') break;
            form = read_expr_stream();
            if (reader_status != READER_OK) { r = NIL; break; }
            r = eval(form);
            GC_SET(GC_TOP, r);
        }
        GC_POPN(2);
        es_cursor = sv_cursor; es_slot = sv_slot;
        return r;
        }
#endif
    }
#endif
#ifdef MEGA65_F011_WRITE
    /* ---- SAVE-Kern-Naht (Werkbank, Kalibrierung: docs/f011-write-calibration.md) ---- */
    case P_DSKRD:                                   /* (%disk-read-sector t s) -> t/nil */
        return io_disk_read_sector((unsigned char)FIXVAL(car(args)),
                                   (unsigned char)FIXVAL(cadr(args))) ? lisp_t : NIL;
    case P_DSKBYTE:                                 /* (%disk-byte i) -> Byte aus dem Scratch */
        return MKFIX(io_disk_byte((unsigned char)FIXVAL(car(args))));
    case P_DSKPOKE:                                 /* (%disk-poke i b) -> b (Scratch fuellen) */
        io_disk_scratch_poke((unsigned char)FIXVAL(car(args)),
                             (unsigned char)(FIXVAL(cadr(args)) & 0xFF));
        return cadr(args);
    case P_DSKWR:                                   /* (%disk-write-sector t s) -> t/nil (Verify!) */
        return io_disk_write_sector((unsigned char)FIXVAL(car(args)),
                                    (unsigned char)FIXVAL(cadr(args))) ? lisp_t : NIL;
    case P_SAVE: {                                  /* (save "name" quelltext) -> t/nil */
        obj nm = car(args), ct = cadr(args);
        char name[20]; uint8_t ni = 0; unsigned int n = 0;
        if (!(IS_PTR(nm) && cell_type(nm) == T_STR) || !(IS_PTR(ct) && cell_type(ct) == T_STR)) {
            lisp_abort_static(LISP65_ERR_SAVE_ARGS_TYPE, "save: args must be strings"); return NIL; }
        STR_NAME_COPY(nm, name, 19, ni);
        /* Quelle in den EXT-Datei-Puffer stagen (kein alloc -> kein GC waehrenddessen). */
#ifdef LISP65_STRING_ARENA
        { uint16_t L = str_len(ct); for (n = 0; n < L; n++)
            if (!io_disk_stage_put(n, str_byte(ct, n))) {
                lisp_abort_static(LISP65_ERR_SAVE_TOO_LONG, "save: too long"); return NIL;
            } }
#else
        { obj cs; for (cs = cell_a(ct); IS_PTR(cs) && cell_type(cs) == T_CONS; cs = cell_b(cs), n++)
            if (!io_disk_stage_put(n, (unsigned char)FIXVAL(cell_a(cs)))) {
                lisp_abort_static(LISP65_ERR_SAVE_TOO_LONG, "save: too long"); return NIL; } }
#endif
        return io_disk_save_named(name, n) ? lisp_t : NIL;
    }
#endif
#ifdef LISP65_EVAL_DIV_PRIM
    case P_DIV: {                                   /* (/ a b) 2-stellig, trunc — EXAKT OP_DIV (vm.c) */
        int16_t d = (int16_t)FIXVAL(cadr(args));
        if (d == 0) { lisp_abort_static(LISP65_ERR_DIVISION_BY_ZERO, "division by zero"); return NIL; }
        return MKFIX((int16_t)((int16_t)FIXVAL(car(args)) / d));
    }
#endif
    case P_LOAD: {                                  /* (load "name") -> t */
        obj s = car(args);
        char name[48];
        uint8_t i = 0;
        const char *src;
        if (!(IS_PTR(s) && cell_type(s) == T_STR)) {
            lisp_abort_static(LISP65_ERR_LOAD_TYPE, "load: not a string"); return NIL;
        }
        STR_NAME_COPY(s, name, 47, i);
        src = io_load_file(name);
        if (!src) { lisp_abort_static(LISP65_ERR_LOAD_OPEN, "load: cannot open"); return NIL; }
        load_source(src);
        return intern("t");
    }
    /* ---- String-Primitive (Lane-K-ABI; siehe docs/kernel-abi.md) ----
     * Modell: ein String ist eine T_STR-Zelle mit a = Liste von Zeichen-Codes (Fixnums).
     * Zeichen = Fixnum (Code). Minimaler Kern; substring/append/string=/upcase baut die
     * Lib (Lane L) aus diesen + Listen-Ops. */
#ifndef LISP65_TREEWALK_STDLIB_BRIDGES
    case P_STRINGP:                                 /* (stringp x) -> t|nil */
        { obj s = car(args); return (IS_PTR(s) && cell_type(s) == T_STR) ? lisp_t : NIL; }
    case P_NUMBERP:                                 /* (numberp x) -> t|nil  (Fixnum) */
        return IS_FIX(car(args)) ? lisp_t : NIL;
    case P_SYMBOLP:                                 /* (symbolp x) -> t|nil */
        { obj s = car(args); return is_sym(s) ? lisp_t : NIL; }
    case P_STR2LIST:                                /* (string->list s) -> Zeichen-Code-Liste */
        { obj s = car(args);
          if (!(IS_PTR(s) && cell_type(s) == T_STR)) {
              lisp_abort_static(LISP65_ERR_STRING_TO_LIST_TYPE, "string->list: not a string"); return NIL;
          }
#ifdef LISP65_STRING_ARENA
          { uint16_t l = str_len(s), j; obj lst = NIL;
            GC_PUSH(s); GC_PUSH(NIL);                 /* frische Liste aus Arena-Bytes */
            for (j = l; j > 0; j--) { lst = cons(MKFIX((int16_t)str_byte(s, (uint16_t)(j - 1))), gc_rootstack[GC_TOP]); GC_SET(GC_TOP, lst); }
            GC_POPN(2); return lst; }
#else
          return cell_a(s);
#endif
        }
    case P_LIST2STR:                                /* (list->string l) -> String aus Code-Liste */
#ifdef LISP65_STRING_ARENA
        return str_from_charlist(car(args));
#else
        { obj l = car(args), str;
          GC_PUSH(l); str = alloc(T_STR); GC_POPN(1);
          cell_set_a(str, l); cell_set_b(str, NIL); return str; }
#endif
#endif
    case P_SYMCOUNT: return MKFIX((int16_t)sym_count());     /* (symbol-count) */
    case P_SYMMAX:   return MKFIX((int16_t)sym_max());       /* (symbol-max) -> Cap fuer Budget */
    case P_NUM2STR: {                              /* (number->string n) -> Dezimalstring */
        int16_t n = FIXVAL(car(args));
#ifdef LISP65_STRING_ARENA
        { char nb[8]; uint16_t u = (n < 0) ? (uint16_t)(-(int32_t)n) : (uint16_t)n; int k = 8;
          do { nb[--k] = (char)('0' + (u % 10)); u /= 10; } while (u);
          if (n < 0) nb[--k] = '-';
          return str_from_bytes((const uint8_t *)(nb + k), (uint16_t)(8 - k)); }
#else
        obj lst = NIL; uint16_t u = (n < 0) ? (uint16_t)(-(int32_t)n) : (uint16_t)n;
        GC_PUSH(lst);
        do { lst = cons(MKFIX((int16_t)('0' + (u % 10))), gc_rootstack[GC_TOP]);
             GC_SET(GC_TOP, lst); u /= 10; } while (u);
        if (n < 0) { lst = cons(MKFIX('-'), gc_rootstack[GC_TOP]); GC_SET(GC_TOP, lst); }
        { obj str = alloc(T_STR); cell_set_a(str, gc_rootstack[GC_TOP]); cell_set_b(str, NIL); GC_POPN(1); return str; }
#endif
    }
#ifdef LISP65_NTH_SYMBOL_PRIM
    case P_NTHSYM: {                                /* (nth-symbol i) -> Symbol|nil */
        int16_t i = FIXVAL(car(args));
        if (i < 0 || (uint16_t)i >= sym_count()) return NIL;
        return sym_nth((uint16_t)i); }
#endif
    case P_SYMNAME: {                               /* (symbol-name s) -> String */
        obj s = car(args);
        char nb[34]; int16_t len = 0;
        const char *nm;
        if (!is_sym(s)) { lisp_abort_static(LISP65_ERR_SYMBOL_NAME_TYPE, "symbol-name: not a symbol"); return NIL; }
        nm = symname(s);                            /* statischer Puffer -> sofort kopieren */
        while (nm[len] && len < 33) { nb[len] = nm[len]; len++; }
#ifdef LISP65_STRING_ARENA
        return str_from_bytes((const uint8_t *)nb, (uint16_t)len);
#else
        { obj lst = NIL; int16_t k;
          GC_PUSH(lst);
          for (k = len; k > 0; k--) { lst = cons(MKFIX((unsigned char)nb[k-1]), gc_rootstack[GC_TOP]); GC_SET(GC_TOP, lst); }
          { obj str = alloc(T_STR); cell_set_a(str, gc_rootstack[GC_TOP]); cell_set_b(str, NIL); GC_POPN(1); return str; } }
#endif
    }
    case P_FNKIND: {                                /* (function-kind s) -> primitive|closure|macro|bytecode|nil */
        obj s = car(args), f;
        if (!is_sym(s)) return NIL;
        f = sym_function(s);
        if (f == NIL) return NIL;
        if (IS_BCODE(f)) return k_bytecode;
        if (IS_PTR(f)) {
            switch (cell_type(f)) {
            case T_PRIM:    return k_primitive;
            case T_CLOSURE: return k_closure;
            case T_MACRO:   return k_macro;
            default: break;
            }
        }
        return k_other; }
    case P_NREVERSE: {                              /* (nreverse l): Zeiger in place umdrehen */
#ifdef LISP65_DIALECT_V2
        if (!primitive_exact_arity(args, 1)) return NIL;
#endif
        return list_nreverse(car(args));
    }
    case P_RPLACA: {                                /* (rplaca c v) -> c */
        obj c = car(args);
#ifdef LISP65_DIALECT_V2
        if (!primitive_exact_arity(args, 2)) return NIL;
#endif
        if (!(IS_PTR(c) && cell_type(c) == T_CONS)) { lisp_abort_static(LISP65_ERR_RPLACA_TYPE, "rplaca: not a cons"); return NIL; }
        return list_rplaca(c, cadr(args)); }
    case P_RPLACD: {                                /* (rplacd c v) -> c */
        obj c = car(args);
#ifdef LISP65_DIALECT_V2
        if (!primitive_exact_arity(args, 2)) return NIL;
#endif
        if (!(IS_PTR(c) && cell_type(c) == T_CONS)) { lisp_abort_static(LISP65_ERR_RPLACD_TYPE, "rplacd: not a cons"); return NIL; }
        return list_rplacd(c, cadr(args)); }
#ifdef LISP65_EVAL_SCREEN_PRIMS
    case P_SCRSIZE: {                               /* (screen-size) -> (cols rows) */
        obj r = cons(MKFIX((int16_t)scr_rows()), NIL);
        GC_PUSH(r);
        r = cons(MKFIX((int16_t)scr_cols()), gc_rootstack[GC_TOP]);
        GC_POPN(1); return r; }
    case P_SCRCLEAR: scr_clear(); return NIL;       /* (screen-clear) */
    case P_SCRPUT: {                                /* (screen-put-char x y code [attr]) */
        obj a4 = car(cdr(cdr(cdr(args))));
        scr_put_at((uint8_t)FIXVAL(car(args)), (uint8_t)FIXVAL(cadr(args)),
                   (char)FIXVAL(caddr(args)), IS_FIX(a4) ? FIXVAL(a4) : (int16_t)-1);
        return NIL; }
#ifdef LISP65_SCREEN_WRITE_STRING
    case P_SCRWRITE: {                              /* (screen-write-string x y str [attr]) */
        /* BULK: EIN Prim-Call je Zeile statt ein put-char-Roundtrip je Zeichen (Redisplay-
         * Hebel (a), collaboration.md). C-Schleife direkt ueber die Zeichenliste, kein
         * statischer Bank-0-Puffer; attr wie put-char (Bit 7 = Reverse-Video). */
        obj str = caddr(args), a4 = car(cdr(cdr(cdr(args))));
        char wbuf[80];
        int16_t attr = IS_FIX(a4) ? FIXVAL(a4) : (int16_t)-1;
        uint8_t x = (uint8_t)FIXVAL(car(args)), y = (uint8_t)FIXVAL(cadr(args)), n = 0;
        if (!(IS_PTR(str) && cell_type(str) == T_STR)) {
            lisp_abort_static(LISP65_ERR_SCREEN_WRITE_STRING_TYPE, "screen-write-string: not a string"); return NIL;
        }
#ifdef LISP65_STRING_ARENA
        n = (uint8_t)str_copy_out(str, wbuf, 80);
#else
        { obj cs; for (cs = cell_a(str); IS_PTR(cs) && cell_type(cs) == T_CONS && n < 80; cs = cell_b(cs))
            wbuf[n++] = (char)FIXVAL(cell_a(cs)); }
#endif
        /* attr Bit 6 (0x40) = bis Zeilenende auffuellen. Span-Schreiber: Basiszeiger einmal,
         * lineare Stores — vorher ~1500 Zyklen JE ZEICHEN via scr_put_at (xemu-Messung). */
        scr_write_span(x, y, wbuf, n,
                       (attr >= 0 && (attr & 0x40)) ? scr_cols() : 0,
                       (attr >= 0) ? (attr & ~0x40) : attr);
        return NIL; }
#endif /* LISP65_SCREEN_WRITE_STRING */
#ifdef LISP65_EVAL_KEYBOARD_PRIMS
    case P_READKEY: case P_POLLKEY: {               /* (read-key)|(poll-key) -> (key code mods)|nil */
        int c;
        /* lisp_poll IM Warte-Loop: RUN/STOP wird fast immer beim Warten gedrueckt — dort
         * laufen keine VM-Schritte, der VM-Poll feuert nie (HW-Befund 2026-07-02). */
        /* lisp_poll IM Warte-Loop (RUN/STOP; Achtung: lisp_polls STKEY-Adresse stimmt fuer
         * den MEGA65-KERNAL noch NICHT — offener K-Punkt, s. collaboration.md). */
        if (id == P_READKEY) {
#ifdef LISP65_READKEY_DIAG
            *(volatile unsigned char *)0xD020 = 6;   /* BLAU: warte */
#endif
            do { lisp_poll(); c = cbm_k_getin(); } while (c == 0);
#ifdef LISP65_READKEY_DIAG
            *(volatile unsigned char *)0xD020 = 2;   /* ROT: verarbeite */
#endif
        }
        else { c = cbm_k_getin(); if (c == 0) return NIL; }
        return key_event(c); }
#endif
#endif
#ifndef LISP65_TREEWALK_STDLIB_BRIDGES
    case P_STRLEN:                                  /* (string-length s) -> Fixnum */
        { obj s = car(args);
          if (!(IS_PTR(s) && cell_type(s) == T_STR)) {
              lisp_abort_static(LISP65_ERR_STRING_LENGTH_TYPE, "string-length: not a string"); return NIL;
          }
#ifdef LISP65_STRING_ARENA
          return MKFIX((int16_t)str_len(s));
#else
          { obj cs; int16_t n = 0;
            for (cs = cell_a(s); IS_PTR(cs) && cell_type(cs) == T_CONS; cs = cell_b(cs)) n++;
            return MKFIX(n); }
#endif
        }
    case P_STRREF:                                  /* (string-ref s i) -> Zeichen-Code (0-basiert) */
        { obj s = car(args); int16_t i = FIXVAL(cadr(args));
          if (!(IS_PTR(s) && cell_type(s) == T_STR)) {
              lisp_abort_static(LISP65_ERR_STRING_REF_TYPE, "string-ref: not a string"); return NIL;
          }
#ifdef LISP65_STRING_ARENA
          if (i < 0 || i >= (int16_t)str_len(s)) {
              lisp_abort_static(LISP65_ERR_STRING_REF_RANGE, "string-ref: index out of range"); return NIL;
          }
          return MKFIX((int16_t)str_byte(s, (uint16_t)i));
#else
          { obj cs;
            for (cs = cell_a(s); IS_PTR(cs) && cell_type(cs) == T_CONS && i > 0; cs = cell_b(cs)) i--;
            if (!(IS_PTR(cs) && cell_type(cs) == T_CONS)) {
                lisp_abort_static(LISP65_ERR_STRING_REF_RANGE, "string-ref: index out of range"); return NIL;
            }
            return cell_a(cs); }
#endif
        }
#endif
    case P_WRITECHAR:                               /* (write-char code) -> code */
        { obj ch = car(args);
          if (!IS_FIX(ch)) { lisp_abort_static(LISP65_ERR_WRITE_CHAR_TYPE, "write-char: not a fixnum"); return NIL; }
          screen_scroll_guard();
          emit((char)(FIXVAL(ch) & 0xFF));
          return ch; }
#ifndef LISP65_OUTPUT_WRAPPERS_IN_STDLIB
    case P_WRITESTR:                                /* (write-string s) -> s */
        return write_string_obj(car(args));
    case P_TERPRI:                                  /* (terpri) -> nil */
        screen_scroll_guard(); emit('\n'); return NIL;
#endif
    case P_PRIN1:                                   /* readable */
        { obj x = car(args);
          write_readable_obj(x);
          return x; }
#ifndef LISP65_SCREEN_BULK_P_IN_STDLIB
    case P_SCRBULKP:                                /* (screen-bulk-p) -> t iff screen-write-string exists */
#ifdef LISP65_SCREEN_WRITE_STRING
        return lisp_t;
#else
        return NIL;
#endif
#endif
#ifndef LISP65_OUTPUT_WRAPPERS_IN_STDLIB
    case P_PRINC:                                   /* display: Strings roh, sonst readable */
        { obj x = car(args);
          if (IS_PTR(x) && cell_type(x) == T_STR) return write_string_obj(x);
          write_readable_obj(x); return x; }
    case P_WRITE:
        { obj x = car(args); write_readable_obj(x); return x; }
    case P_PRINT:
        { obj x = car(args);
          screen_scroll_guard(); emit('\n');
          write_readable_obj(x);
          screen_scroll_guard(); emit(' ');
          return x; }
    case P_WRITELINE:
        { obj s = write_string_obj(car(args));
          screen_scroll_guard(); emit('\n');
          return s; }
#endif
    }
    return NIL;
}
#endif

#ifdef LISP65_V2_WORKBENCH_SERVICES
/* Array-ABI counterparts of the remaining resident Workbench P_* services.
 * vm_callprim owns exact arity; this switch owns only service semantics. A
 * missing product feature returns zero so the VM fails closed with BADOPCODE. */
uint8_t eval_v2_workbench_service(uint8_t id, const obj *args, obj *result) {
    switch (id) {
#ifdef LISP65_COMPILE_STRING
    case 30: { /* %cs-read-open */
        obj source = args[0];
        if (!(IS_PTR(source) && cell_type(source) == T_STR)) {
            lisp_abort_static(LISP65_ERR_COMPILE_STRING_TYPE,
                              "compile-string: not a string");
            *result = NIL; return 1;
        }
        cs_str = source; cs_idx = 0;
        reader_from_fetch(cs_fetch);
        *result = lisp_t; return 1;
    }
#endif
#if defined(LISP65_FASL) || defined(LISP65_COMPILE_STRING)
    case 31: { /* %fasl-read-form */
        obj form;
        if (reader_skip_peek() == '\0') { *result = intern("%fasl-eof"); return 1; }
        form = read_expr_stream();
        *result = reader_status == READER_OK ? form : intern("%fasl-eof");
        return 1;
    }
    case 32: { /* %fasl-stage */
        uint16_t index = (uint16_t)FIXVAL(args[0]);
        if (index >= DISK_EXT_FILE_MAX) { *result = NIL; return 1; }
        ext_disk_put((uint16_t)(256u + index), (uint8_t)FIXVAL(args[1]));
        *result = lisp_t; return 1;
    }
    case 33: /* %fasl-stage-get */
        *result = MKFIX((int16_t)ext_disk_get(
            (uint16_t)(256u + (uint16_t)FIXVAL(args[0]))));
        return 1;
#endif
#ifdef LISP65_LCC_INSTALL
    case 35: { /* %set-macro */
        obj macro = alloc(T_MACRO);
        if (macro == NIL) { *result = NIL; return 1; }
        cell_set_a(macro, args[1]); cell_set_b(macro, NIL);
        set_sym_function(args[0], macro);
        *result = args[0]; return 1;
    }
#endif
    case 36: { /* function-kind */
        obj function;
        if (!is_sym(args[0])) { *result = NIL; return 1; }
        function = sym_function(args[0]);
        if (function == NIL) { *result = NIL; return 1; }
        if (IS_BCODE(function)) { *result = k_bytecode; return 1; }
        if (IS_PTR(function)) {
            switch (cell_type(function)) {
            case T_PRIM:    *result = k_primitive; return 1;
            case T_CLOSURE: *result = k_closure; return 1;
            case T_MACRO:   *result = k_macro; return 1;
            default: break;
            }
        }
        *result = k_other; return 1;
    }
    case 37: /* gensym */
        *result = gensym(); return 1;
#ifdef LISP65_LCC_INSTALL
    case 38: /* lcc-install */
        *result = lcc_install_obj(args[0], args[1]); return 1;
#endif
#ifdef LISP65_MACROEXPAND_PRIM
    case 39: { /* macroexpand-1 */
        obj form = args[0], op, function, expansion;
        if (!(IS_PTR(form) && cell_type(form) == T_CONS)) { *result = form; return 1; }
        op = cell_a(form);
        if (!is_sym(op)) { *result = form; return 1; }
        function = sym_function(op);
        if (!(IS_PTR(function) && cell_type(function) == T_MACRO)) {
            *result = form; return 1;
        }
        expansion = cell_a(function);
#ifdef LISP65_LCC_INSTALL
        if (IS_BCODE(expansion)) {
#ifdef LISP65_V2_CARRIER_CUT
            *result = eval_vm_native_apply_checked(expansion, cell_b(form));
#else
            *result = apply(expansion, cell_b(form)); return 1;
#endif
            return 1;
        }
#endif
#ifdef LISP65_TREEWALK_STRIP
        *result = form; return 1;
#else
        if (!tree_macro_arity_require(op, car(expansion), cell_b(form))) {
            *result = NIL; return 1;
        }
        {
            obj environment = env_extend(car(expansion), cell_b(form), cell_b(function));
            GC_PUSH(environment);
            *result = eval_body(cdr(expansion), environment);
            GC_POPN(1);
            return 1;
        }
#endif
    }
#endif
    case 41: /* prin1 */
        write_readable_obj(args[0]); *result = args[0]; return 1;
    case 42: /* symbol-count */
        *result = MKFIX((int16_t)sym_count()); return 1;
    case 43: /* symbol-max */
        *result = MKFIX((int16_t)sym_max()); return 1;
    case 44: { /* symbol-name */
        char buffer[34]; int16_t length = 0; const char *name;
        if (!is_sym(args[0])) {
            lisp_abort_static(LISP65_ERR_SYMBOL_NAME_TYPE,
                              "symbol-name: not a symbol");
            *result = NIL; return 1;
        }
        name = symname(args[0]);
        while (name[length] && length < 33) {
            buffer[length] = name[length]; length++;
        }
#ifdef LISP65_STRING_ARENA
        *result = str_from_bytes((const uint8_t *)buffer, (uint16_t)length);
#else
        {
            obj list = NIL; int16_t index;
            GC_PUSH(list);
            for (index = length; index > 0; index--) {
                list = cons(MKFIX((unsigned char)buffer[index - 1]),
                            gc_rootstack[GC_TOP]);
                GC_SET(GC_TOP, list);
            }
            *result = alloc(T_STR);
            if (*result != NIL) {
                cell_set_a(*result, gc_rootstack[GC_TOP]); cell_set_b(*result, NIL);
            }
            GC_POPN(1);
        }
#endif
        return 1;
    }
    case 45: /* write-char */
        if (!IS_FIX(args[0])) {
            lisp_abort_static(LISP65_ERR_WRITE_CHAR_TYPE,
                              "write-char: not a fixnum");
            *result = NIL; return 1;
        }
        screen_scroll_guard(); emit((char)(FIXVAL(args[0]) & 0xff));
        *result = args[0]; return 1;
    default:
        return 0;
    }
}
#endif

/* ---------- Environment ---------- */
#ifndef LISP65_TREEWALK_STRIP   /* Konvergenz-M3: der ganze Treewalk faellt (docs/einsuite-convergence-design.md) */
static obj env_lookup(obj sym, obj env) {        /* keine Allokation */
    while (env != NIL) {
        obj binding = car(env);
        if (car(binding) == sym) return binding;
        env = cdr(env);
    }
    return NIL;
}

static obj env_extend(obj params, obj args, obj env) {
    uint16_t base = gc_rootsp;
    GC_PUSH(params); GC_PUSH(args); GC_PUSH(env);   /* base, base+1, base+2 */
    while (IS_PTR(params) && cell_type(params) == T_CONS) {
        obj p = car(params);
#ifdef LISP65_DIALECT_V2
        if (p == sf_optional) {
            params = cdr(params); GC_SET(base, params);
            continue;
        }
#endif
        if (p == sf_rest) {
            env = cons(cons(cadr(params), args), env);
            GC_SET(base + 2, env);
            gc_rootsp = base;
            return env;
        }
        env = cons(cons(p, car(args)), env);
        GC_SET(base + 2, env);
        params = cdr(params); GC_SET(base, params);
        args = cdr(args);     GC_SET(base + 1, args);
    }
    if (params != NIL) {                            /* dotted / voll-variadisch */
        env = cons(cons(params, args), env);
        GC_SET(base + 2, env);
    }
    gc_rootsp = base;
    return env;
}

#ifdef LISP65_DIALECT_V2
/* Treewalk oracle for the v2 source profile. Shipped VM behavior remains
 * artifact-bound through CO_FLAG_STRICT_ARITY; this mirrors that contract for
 * closures which have no CodeObject header. */
static uint8_t tree_arity_accepts(obj params, obj args) {
    uint16_t required = 0, optional = 0, actual = 0;
    uint8_t state = 0, has_rest = 0;
    while (IS_PTR(params) && cell_type(params) == T_CONS) {
        obj p = car(params);
        params = cdr(params);
        if (p == sf_optional) {
            if (state != 0) return 0;
            state = 1;
            continue;
        }
        if (p == sf_rest) {
            if (state == 2 || !(IS_PTR(params) && cell_type(params) == T_CONS) ||
                cdr(params) != NIL || !is_sym(car(params)) ||
                car(params) == sf_optional || car(params) == sf_rest)
                return 0;
            has_rest = 1;
            params = NIL;
            state = 2;
            break;
        }
        if (!is_sym(p) || state == 2) return 0;
        if (state == 0) required++; else optional++;
    }
    if (params != NIL || optional > 63u) return 0;
    while (IS_PTR(args) && cell_type(args) == T_CONS) {
        actual++;
        args = cdr(args);
    }
    if (args != NIL || actual < required) return 0;
    return has_rest || actual <= (uint16_t)(required + optional);
}

static uint8_t tree_arity_require(obj params, obj args) {
    if (tree_arity_accepts(params, args)) return 1;
    lisp_abort_static(LISP65_ERR_WRONG_ARGUMENT_COUNT, "wrong argument count");
    return 0;
}

static uint8_t tree_macro_arity_require(obj name, obj params, obj args) {
    /* `&rest` models defvar's optional initializer in source, but must not
     * turn the public macro into an unbounded-arity form. */
    if (name == sf_defvar &&
        IS_PTR(cdr(args)) && cell_type(cdr(args)) == T_CONS &&
        cdr(cdr(args)) != NIL) {
        lisp_abort_static(LISP65_ERR_WRONG_ARGUMENT_COUNT, "wrong argument count");
        return 0;
    }
    return tree_arity_require(params, args);
}
#endif

/* ---------- apply ---------- */
static obj eval_body(obj body, obj env) {
    obj r = NIL;
    uint16_t base = gc_rootsp;
    GC_PUSH(body); GC_PUSH(env);
    while (body != NIL) {
        r = eval_env(car(body), env);
        body = cdr(body); GC_SET(base, body);
    }
    gc_rootsp = base;
    return r;
}
#endif /* !LISP65_TREEWALK_STRIP (Environment + eval_body) */

#ifndef LISP65_V2_CARRIER_CUT
static obj apply(obj fn, obj args) {
    uint16_t base = gc_rootsp;
    HB(5); LA(9);   /* I: apply */
    obj r;
    if (is_sym(fn)) {                                    /* Funktions-Designator: Symbol -> Fn */
        obj d = fn;
        fn = sym_function(fn);
        if (fn == NIL) {
            lisp_abort_static_symbol(LISP65_ERR_UNDEFINED_FUNCTION, d, undef_msg(d)); return NIL;
        }
    }
#ifdef LISP65_VM
    if (IS_BCODE(fn)) {   /* kompilierte Fn (Immediate) -> Bytecode-VM (Args-Liste -> Array) */
        obj arr[VM_MAXARGS]; uint8_t n = 0; obj p = args;
        GC_PUSH(args);
        while (IS_PTR(p) && cell_type(p) == T_CONS && n < VM_MAXARGS) { arr[n++] = cell_a(p); p = cell_b(p); }
        /* Mehr als VM_MAXARGS Argumente: LAUT scheitern. Stilles Abschneiden lieferte
         * falsche Ergebnisse ((append a ...x10) verlor die Listen 9+10 kommentarlos). */
        if (p != NIL) { lisp_abort_static(LISP65_ERR_TOO_MANY_ARGS, "too many args"); gc_rootsp = base; return NIL; }
        r = vm_run_dir((int)BCODE_IDX(fn), arr, n);
        gc_rootsp = base;
        vm_check_status();   /* VM-Fehler (Typ/Overflow/Dir-Miss) -> lisp_abort statt stillem NIL */
        return r;
    }
#endif
    if (!IS_PTR(fn)) { lisp_abort_static(LISP65_ERR_NOT_A_FUNCTION, "not a function"); return NIL; }
    GC_PUSH(fn); GC_PUSH(args);
    if (cell_type(fn) == T_PRIM) { r = apply_prim(FIXVAL(cell_a(fn)), args); gc_rootsp = base; return r; }
    if (cell_type(fn) == T_CLOSURE) {
#if defined(LISP65_VM) && (defined(LISP65_COMPILE_REPL) || defined(LISP65_LCC_INSTALL_CLOSURES))
        if (IS_BCODE(cell_a(fn))) {
            r = vm_apply_bcode_closure(fn, args);
            gc_rootsp = base;
            vm_check_status();
            return r;
        }
#endif
#ifndef LISP65_TREEWALK_STRIP
        {   /* Treewalk-(params . body)-Closure — existiert im M3-Strip nicht mehr */
        obj pb = cell_a(fn);
#ifdef LISP65_DIALECT_V2
        if (!tree_arity_require(car(pb), args)) { gc_rootsp = base; return NIL; }
#endif
        obj env = env_extend(car(pb), args, cell_b(fn));
        GC_PUSH(env);
        r = eval_body(cdr(pb), env);
        gc_rootsp = base;
        return r;
        }
#endif
    }
    gc_rootsp = base;
    return NIL;
}
#endif

#ifndef LISP65_TREEWALK_STRIP   /* Konvergenz-M3: quasiquote/make_callable/eval_list/eval_env fallen */
/* ---------- quasiquote ---------- */
static obj append2(obj a, obj b) {
    uint16_t base;
    obj r;
    if (a == NIL) return b;
    if (!IS_PTR(a) || cell_type(a) != T_CONS) return a;
    base = gc_rootsp;
    GC_PUSH(a); GC_PUSH(b);
    r = append2(cdr(a), b);
    GC_PUSH(r);
    { obj res = cons(car(a), r); gc_rootsp = base; return res; }
}

/* (s v)-Zweierliste GC-sicher bauen (nested-qq-Rebuild: (unquote …)/(quasiquote …)). */
static obj qq2(obj s, obj v) {
    uint16_t base = gc_rootsp;
    obj t;
    GC_PUSH(v);
    t = cons(v, NIL); GC_PUSH(t);
    t = cons(s, t);
    gc_rootsp = base;
    return t;
}

/* NESTED quasiquote (CL-Semantik, d = Tiefe): inneres ` erhoeht, , senkt; NUR bei d==1 wird
 * ausgewertet, sonst wird die Syntax mit d-1-verarbeitetem Inhalt REBUILT. Host-Referenz —
 * im Strip-Produkt ist der Block tot (lcc spiegelt die Semantik in %lcc-lower-qq). */
static obj qq_list(obj x, obj env, uint8_t d) {
    uint16_t base;
    obj head, r1, r2, res;
    if (!IS_PTR(x) || cell_type(x) != T_CONS) return qq(x, env, d);
    if (car(x) == sf_unquote) {                        /* dotted-Tail `(a . ,b) */
        if (d == 1) return eval_env(cadr(x), env);
        return qq2(sf_unquote, qq(cadr(x), env, (uint8_t)(d - 1)));
    }
    base = gc_rootsp;
    GC_PUSH(x); GC_PUSH(env);
    head = car(x);
    if (IS_PTR(head) && cell_type(head) == T_CONS && car(head) == sf_unquote_splicing) {
        if (d == 1) {
            r1 = eval_env(cadr(head), env); GC_PUSH(r1);
            r2 = qq_list(cdr(x), env, d);   GC_PUSH(r2);
            res = append2(r1, r2);
            gc_rootsp = base; return res;
        }
        r1 = qq2(sf_unquote_splicing, qq(cadr(head), env, (uint8_t)(d - 1))); GC_PUSH(r1);
        r2 = qq_list(cdr(x), env, d);                                         GC_PUSH(r2);
        res = cons(r1, r2);
        gc_rootsp = base; return res;
    }
    r1 = qq(head, env, d);        GC_PUSH(r1);
    r2 = qq_list(cdr(x), env, d); GC_PUSH(r2);
    res = cons(r1, r2);
    gc_rootsp = base; return res;
}

static obj qq(obj x, obj env, uint8_t d) {
    if (!IS_PTR(x) || cell_type(x) != T_CONS) return x;
    if (car(x) == sf_unquote) {
        if (d == 1) return eval_env(cadr(x), env);
        return qq2(sf_unquote, qq(cadr(x), env, (uint8_t)(d - 1)));
    }
    if (car(x) == sf_quasiquote)
        return qq2(sf_quasiquote, qq(cadr(x), env, (uint8_t)(d + 1)));
    return qq_list(x, env, d);
}

/* ---------- eval ---------- */
static obj make_callable(uint8_t type, obj params, obj body, obj env) {
    uint16_t base = gc_rootsp;
    obj o, pb;
    GC_PUSH(params); GC_PUSH(body); GC_PUSH(env);
    pb = cons(params, body);
    GC_PUSH(pb);
    o = alloc(type);
    gc_rootsp = base;
    cell_set_a(o, pb);
    cell_set_b(o, env);
    return o;
}

/* Wertet jedes Element der Argumentliste aus. Aufrufer rootet args/env (via e). */
static obj eval_list(obj args, obj env) {
    uint16_t base;
    obj a, rest, r;
    if (args == NIL) return NIL;
    base = gc_rootsp;
    GC_PUSH(args); GC_PUSH(env);
    a = eval_env(car(args), env); GC_PUSH(a);
    rest = eval_list(cdr(args), env); GC_PUSH(rest);
    r = cons(a, rest);
    gc_rootsp = base;
    return r;
}

/* Wertet alle Body-Formen außer der letzten aus (nicht-Tail) und gibt die letzte
 * Form zur Tail-Auswertung durch den Aufrufer zurück. Self-rooting. */
static obj tail_prep(obj body, obj env) {
    uint16_t base = gc_rootsp;
    if (body == NIL) return NIL;
    GC_PUSH(body); GC_PUSH(env);
    while (cdr(body) != NIL) { eval_env(car(body), env); body = cdr(body); GC_SET(base, body); }
    gc_rootsp = base;
    return car(body);
}

/* eval mit TCO: Tail-Positionen (if-Zweig, letzter progn-/Body-Ausdruck,
 * Closure-Tail-Calls, Makro-Expansion) ersetzen e/env und loopen, statt in C zu
 * rekurrieren -> Tail-Rekursion laeuft in konstanter C-Stack-Tiefe. */
static obj eval_env(obj e, obj env) {
    uint16_t base = gc_rootsp;
    /* Rekursions-Guard: jede eval-Ebene haelt Root-Slots; GC_PUSH ist (aus Kostengruenden)
     * ungeprueft -> ohne Guard trampelte tiefe NICHT-Tail-Rekursion ((fact 10)) hinter den
     * Rootstack (HW 2026-07-02: Screen-Muell, kaputte Ergebnisse, Haenger). 16er-Marge
     * deckt die Slots einer Ebene inkl. apply/env_extend. */
    if (base >= GC_ROOTS - 16) { lisp_abort_static(LISP65_ERR_RECURSION_TOO_DEEP, "recursion too deep"); return NIL; }
    GC_PUSH(e); GC_PUSH(env);                      /* base=e, base+1=env, ueber den Loop aktuell */
    for (;;) {
        HB(0); LA(8);   /* H: eval-Loop */
        { static unsigned char pc; if (((unsigned char)(++pc) & 0x3F) == 0) lisp_poll(); }  /* RUN/STOP */
        GC_SET(base, e); GC_SET(base + 1, env);
        if (e == NIL || IS_FIX(e)) { gc_rootsp = base; return e; }
        if (is_sym(e)) {
            obj b = env_lookup(e, env);
            gc_rootsp = base; return (b != NIL) ? cdr(b) : sym_value(e);
        }
        if (!IS_PTR(e) || cell_type(e) != T_CONS) { gc_rootsp = base; return e; }
        {
            obj op = car(e), args = cdr(e);
            if (is_sym(op)) {
#if defined(LISP65_DIALECT_FAMILY_HARNESS) && defined(LISP65_DIALECT_V2)
                if (op == sf_v2_string_codes || op == sf_v2_string_from_codes) {
                    obj evaluated, argv[1], result;
                    uint8_t pid = (op == sf_v2_string_codes) ? 28 : 29;
                    if (!primitive_exact_arity(args, 1)) {
                        gc_rootsp = base;
                        return NIL;
                    }
                    evaluated = eval_list(args, env);
                    GC_PUSH(evaluated);
                    argv[0] = car(evaluated);
                    vm_status = VM_OK;
                    result = vm_family_internal_primitive(pid, argv, 1);
                    vm_check_status();
                    gc_rootsp = base;
                    return result;
                }
#endif
                if (op == sf_quote)      { gc_rootsp = base; return car(args); }
                if (op == sf_quasiquote) { obj r = qq(car(args), env, 1); gc_rootsp = base; return r; }
                if (op == sf_if) {                       /* TCO: Zweig in Tail-Position */
                    obj t = eval_env(car(args), env);
                    e = (t != NIL) ? cadr(args) : caddr(args);
                    continue;
                }
                if (op == sf_progn) { e = tail_prep(args, env); continue; }   /* TCO */
                if (op == sf_lambda)  { obj r = make_callable(T_CLOSURE, car(args), cdr(args), env); gc_rootsp = base; return r; }
                if (op == sf_function){   /* (function sym)->sym_function ; #'(lambda ..)->Closure */
                    obj x = car(args);
                    obj r = is_sym(x) ? sym_function(x) : eval_env(x, env);
                    gc_rootsp = base; return r;
                }
                if (op == sf_setq) {
                    obj s = car(args), v = eval_env(cadr(args), env), b = env_lookup(s, env);
                    if (b != NIL) cell_set_b(b, v); else set_sym_value(s, v);
                    gc_rootsp = base; return v;
                }
                if (op == sf_defmacro) {
                    obj nm = car(args);
                    obj m = make_callable(T_MACRO, cadr(args), cdr(cdr(args)), env);
                    set_sym_function(nm, m);
                    gc_rootsp = base; return nm;
                }
                if (op == sf_defun) {    /* (defun name (params) body...) -> Closure auf Fn-Zelle */
                    obj nm = car(args);
                    obj f = make_callable(T_CLOSURE, cadr(args), cdr(cdr(args)), env);
                    set_sym_function(nm, f);
                    gc_rootsp = base; return nm;
                }
                if (op == sf_when || op == sf_unless) {   /* Koerper als progn in Tail-Position */
                    obj t = eval_env(car(args), env);
                    if ((t != NIL) != (op == sf_when)) { gc_rootsp = base; return NIL; }
                    e = tail_prep(cdr(args), env); continue;
                }
#ifdef LISP65_EVAL_CONTROL_SF
                /* cond/and/or als Special Forms (Aequivalenz-Befund 2026-07-05: der Compiler
                 * lowert sie nativ, der Treewalk hatte sie GAR NICHT — Werkbank-REPL-Loch).
                 * Semantik = Compiler-Lowering: cond-Klausel-Body / letztes and/or-Glied in
                 * Tail-Position; (cond (x)) liefert x; (and)->t, (or)->nil. */
                if (op == sf_cond) {
                    obj cl = args, hit = NIL, t = NIL;
                    while (IS_PTR(cl) && cell_type(cl) == T_CONS && hit == NIL) {
                        t = eval_env(car(car(cl)), env);
                        if (t != NIL) hit = car(cl); else cl = cdr(cl);
                    }
                    if (hit == NIL)      { gc_rootsp = base; return NIL; }
                    if (cdr(hit) == NIL) { gc_rootsp = base; return t; }
                    e = tail_prep(cdr(hit), env); continue;
                }
                if (op == sf_and || op == sf_or) {        /* Dual wie when/unless (ein Block = weniger .text) */
                    uint8_t isand = (op == sf_and);
                    obj a = args, t;
                    if (a == NIL) { gc_rootsp = base; return isand ? lisp_t : NIL; }
                    while (IS_PTR(cdr(a)) && cell_type(cdr(a)) == T_CONS) {
                        t = eval_env(car(a), env);
                        if ((t == NIL) == (isand != 0)) { gc_rootsp = base; return isand ? NIL : t; }
                        a = cdr(a);
                    }
                    e = tail_prep(a, env); continue;
                }
#endif
                if (op == sf_let || op == sf_letstar) {   /* ((v init)|v ...) body...; Tail-Pos. */
                    obj bs = car(args), newenv = env;
                    uint16_t b2 = gc_rootsp;
                    GC_PUSH(newenv);
                    while (IS_PTR(bs) && cell_type(bs) == T_CONS) {
                        obj bd = car(bs), var, init, val;
                        if (is_sym(bd)) { var = bd; init = NIL; } else { var = car(bd); init = cadr(bd); }
                        /* let: inits im AEUSSEREN env (parallel); let*: im wachsenden env */
                        val = eval_env(init, (op == sf_letstar) ? newenv : env);
                        newenv = cons(cons(var, val), newenv);   /* cons schuetzt seine Args */
                        GC_SET(b2, newenv);
                        bs = cdr(bs);
                    }
                    env = newenv;
                    gc_rootsp = b2;      /* tail_prep pusht body+env selbst vor jeder Auswertung */
                    e = tail_prep(cdr(args), env); continue;
                }
                if (op == sf_dotimes || op == sf_dolist) {
                    /* (dotimes (var count [result]) body...) | (dolist (var listform [result]) body...)
                     * FLACHE C-Schleife: EINE Binding-Zelle, je Runde nur cell_set_b — kein Alloc,
                     * kein Rootstack-/VM-Frame-Wachstum (Motiv: 3x Nicht-Tail-Bug am 2026-07-02).
                     * Gepinnt (collaboration.md): Result in Tail-Position mit var=count bzw. nil;
                     * Closures aus dem Body teilen die EINE Binding-Zelle (CL-dotimes-Verhalten). */
                    obj spec = car(args), body = cdr(args);
                    obj var = car(spec), newenv, binding, seq;
                    uint16_t b2 = gc_rootsp;
                    uint8_t pollc = 0;
                    seq = eval_env(cadr(spec), env);
                    GC_PUSH(seq);
                    binding = cons(var, NIL);
                    GC_PUSH(binding);
                    newenv = cons(binding, env);
                    GC_PUSH(newenv);
                    if (op == sf_dotimes) {
                        int16_t n, i;
                        if (!IS_FIX(seq)) {
                            lisp_abort_static(LISP65_ERR_DOTIMES_COUNT_TYPE, "dotimes: count must be a fixnum");
                            gc_rootsp = base; return NIL;
                        }
                        n = FIXVAL(seq);
                        for (i = 0; i < n; i++) {
                            cell_set_b(binding, MKFIX(i));
                            loop_body(body, newenv);
                            if (((uint8_t)++pollc & 0x3F) == 0) lisp_poll();   /* RUN/STOP auch bei leerem Body */
                        }
                        cell_set_b(binding, MKFIX(n));
                    } else {
                        obj p = seq;
                        while (IS_PTR(p) && cell_type(p) == T_CONS) {
                            cell_set_b(binding, cell_a(p));
                            loop_body(body, newenv);
                            p = cell_b(p);
                            GC_SET(b2, p);           /* Rest-Liste gerootet halten (Body darf GC ausloesen) */
                            if (((uint8_t)++pollc & 0x3F) == 0) lisp_poll();
                        }
                        cell_set_b(binding, NIL);
                    }
                    env = newenv;
                    gc_rootsp = b2;
                    e = caddr(spec);                 /* Result-Form (fehlend -> NIL -> nil), Tail-Position */
                    continue;
                }
                {
                    obj fn = sym_function(op);          /* via op (Symbol-Root) erreichbar */
                    if (!IS_PTR(fn) && !IS_BCODE(fn)) {
                        lisp_abort_static_symbol(LISP65_ERR_UNDEFINED_FUNCTION, op, undef_msg(op));
                        gc_rootsp = base; return NIL;
                    }
                    if (IS_PTR(fn) && cell_type(fn) == T_MACRO) {     /* TCO: Expansion in Tail-Pos. */
                        obj pb = cell_a(fn);
#ifdef LISP65_LCC_INSTALL
                        if (IS_BCODE(pb)) { e = apply(pb, args); continue; }   /* M2: BCODE-Expander */
#endif
                        {
#ifdef LISP65_DIALECT_V2
                        if (!tree_macro_arity_require(op, car(pb), args)) { gc_rootsp = base; return NIL; }
#endif
                        obj menv = env_extend(car(pb), args, cell_b(fn));
                        GC_PUSH(menv);
                        e = eval_body(cdr(pb), menv);   /* Expansion (Code) */
                        GC_POPN(1);
                        continue;
                        }
                    }
                    {
                        obj ev = eval_list(args, env);
                        if (IS_PTR(fn) && cell_type(fn) == T_CLOSURE) {   /* TCO: Tail-Call */
                            obj pb = cell_a(fn);
                            GC_PUSH(ev);
#ifdef LISP65_DIALECT_V2
                            if (!tree_arity_require(car(pb), ev)) { gc_rootsp = base; return NIL; }
#endif
                            env = env_extend(car(pb), ev, cell_b(fn));
                            GC_POPN(1);
                            e = tail_prep(cdr(pb), env);
                            continue;
                        }
                        { obj r = apply(fn, ev); gc_rootsp = base; return r; }   /* Primitive */
                    }
                }
            }
            {   /* Operator ist eine Form: ((lambda ...) ...) */
                obj f = eval_env(op, env);
                obj ev;
                GC_PUSH(f);
                ev = eval_list(args, env);
                if (IS_PTR(f) && cell_type(f) == T_CLOSURE) {     /* TCO */
                    obj pb = cell_a(f);
                    GC_PUSH(ev);
#ifdef LISP65_DIALECT_V2
                    if (!tree_arity_require(car(pb), ev)) { gc_rootsp = base; return NIL; }
#endif
                    env = env_extend(car(pb), ev, cell_b(f));
                    GC_POPN(2);                                   /* ev, f */
                    e = tail_prep(cdr(pb), env);
                    continue;
                }
                { obj r = apply(f, ev); gc_rootsp = base; return r; }
            }
        }
    }
}

#endif /* !LISP65_TREEWALK_STRIP (quasiquote..eval_env) */

#ifdef LISP65_TREEWALK_STRIP
/* Konvergenz-M3: KEIN Treewalk — eval routet jede Form durch den Blob-Compiler:
 * der Cut nutzt vm_native_apply direkt, das Legacy-Profil weiter apply.
 * Beide fuehren die BCODE-Fn lcc-run auf vm_run aus.
 * eval-string/load_source/P_EVAL erben das Routing automatisch (rufen eval). */
obj eval(obj e) {
    static obj k_lccrun = NIL;
    obj fn, l;
    /* A3-Atom-Fastpath: Kompilieren lohnt nur fuer FORMEN. Gebundene Symbole lesen dieselbe
     * globale Wertzelle wie der kompilierte Pfad (setq schreibt sie); ungebundene Symbole
     * laufen weiter durch lcc (identische Fehlersemantik). Fixnums/Strings selbstauswertend. */
    if (is_sym(e)) { if (sym_boundp(e)) return sym_value(e); }
    else if (!IS_PTR(e)) return e;
    else if (cell_type(e) == T_STR) return e;
    if (k_lccrun == NIL) k_lccrun = intern("lcc-run");
    fn = sym_function(k_lccrun);
    if (fn == NIL) { lisp_abort_static(LISP65_ERR_NO_LCC_RUN, "no lcc-run"); return NIL; }
    GC_PUSH(e);
    l = cons(e, NIL);
    GC_POPN(1);
#ifdef LISP65_V2_CARRIER_CUT
    return eval_vm_native_apply_checked(fn, l);
#else
    return apply(fn, l);
#endif
}
#else
obj eval(obj e) { return eval_env(e, NIL); }
#endif

/* Loader-Hook: alle Top-Level-Formen aus src lesen und im globalen env auswerten.
 * Bootstrap-tauglich: die erste Form darf z. B. defun definieren, spaetere es nutzen. */
#ifndef LISP65_COMPILE_REPL   /* M7: im compile-repl-Profil kommen die Loader aus compile_repl.c (Compiler statt eval) */
void load_source(const char *src) {
    const char *p = src;
    for (;;) {
        while (*p == ' ' || *p == '\t' || *p == '\n' || *p == '\r') p++;
        if (*p == ';') { while (*p && *p != '\n') p++; continue; }
        if (*p == '\0') return;
        {
            obj form = read_expr(&p);
            if (reader_status != READER_OK) return;
            eval(form);
        }
    }
}
/* Wie load_source, aber aus einem Fetch-Stream (Disk-Load: Datei im EXT-RAM). Die 1581-Logik
 * (Bytecode-Lisp) setzt via io.c die Quelle; hier nur die Form-fuer-Form-Auswertung. */
void load_source_stream(char (*fetch)(void)) {
    reader_from_fetch(fetch);
    for (;;) {
        if (reader_skip_peek() == '\0') return;
        {
            obj form = read_expr_stream();
            if (reader_status != READER_OK) return;
            eval(form);
        }
    }
}
#endif /* !LISP65_COMPILE_REPL */

/* ---------- Init ---------- */
WORKBENCH_BOOTLINK WORKBENCH_BOOTFN void defprim(const char *name, int16_t id) {
    obj s = intern(name);
    obj p;
    if (s == NIL || mem_oom) return;
    GC_PUSH(s);
    p = alloc(T_PRIM);
    GC_POPN(1);
    if (p == NIL || mem_oom) return;
    cell_set_a(p, MKFIX(id));
    cell_set_b(p, NIL);
    set_sym_function(s, p);
}

#ifdef LISP65_VM
/* Bridge VM -> Tree-Walker (K3): CALL-Fehltreffer der VM ruft die tree-walker-definierte Fn.
 * Args (Array) -> Liste, dann apply(sym_function(sym), liste). */
#ifndef LISP65_V2_CARRIER_CUT
static obj eval_vm_bridge(obj sym, const obj *args, uint8_t n) {
    obj fn = sym_function(sym), lst = NIL;
    HB(6); LA(10);  /* J: bridge */
    uint16_t abase = gc_rootsp;
    uint8_t i;
    if (fn == NIL) {
        lisp_abort_static_symbol(LISP65_ERR_UNDEFINED_FUNCTION, sym, undef_msg(sym)); return NIL;
    }
    for (i = 0; i < n; i++) GC_PUSH(args[i]);           /* Args rooten */
    GC_PUSH(NIL);                                        /* Slot fuer lst */
    for (i = n; i > 0; i--) { lst = cons(gc_rootstack[abase + i - 1], lst); GC_SET(gc_rootsp - 1, lst); }
    { obj r = apply(fn, lst); gc_rootsp = abase; return r; }
}

/* Bridge fuer VM-CALLPRIM apply/funcall (Prim 7/8): direkt an den Tree-Walker-apply. */
static obj eval_vm_apply(obj fn, obj arglist) { return apply(fn, arglist); }
#endif

#include "vm_registry_impl.inc"
#endif

/* eval_init is the sole consumer of these names. intern() copies every name into the
 * symbol pool, so no pointer into the reclaimed boot window survives eval_init. Keep
 * the declarations under the same feature guards as their registrations: disabled
 * surfaces must not consume boot-payload bytes. */
#define WORKBENCH_BOOTNAME(id, value) \
    static const char workbench_boot_name_##id[] WORKBENCH_BOOTDATA = value
#define BOOTNAME(id) workbench_boot_name_##id

#ifndef LISP65_TREEWALK_STDLIB_BRIDGES
WORKBENCH_BOOTNAME(add, "+");
WORKBENCH_BOOTNAME(sub, "-");
WORKBENCH_BOOTNAME(mul, "*");
WORKBENCH_BOOTNAME(lt, "<");
WORKBENCH_BOOTNAME(gt, ">");
WORKBENCH_BOOTNAME(numeq, "=");
WORKBENCH_BOOTNAME(le, "<=");
WORKBENCH_BOOTNAME(ge, ">=");
WORKBENCH_BOOTNAME(cons, "cons");
WORKBENCH_BOOTNAME(car, "car");
WORKBENCH_BOOTNAME(cdr, "cdr");
WORKBENCH_BOOTNAME(consp, "consp");
WORKBENCH_BOOTNAME(eq, "eq");
WORKBENCH_BOOTNAME(eql, "eql");
WORKBENCH_BOOTNAME(list, "list");
WORKBENCH_BOOTNAME(stringp, "stringp");
WORKBENCH_BOOTNAME(numberp, "numberp");
WORKBENCH_BOOTNAME(symbolp, "symbolp");
#if !defined(LISP65_DIALECT_V2) || !defined(LISP65_DIALECT_FAMILY_HARNESS)
WORKBENCH_BOOTNAME(str2list, "string->list");
WORKBENCH_BOOTNAME(list2str, "list->string");
#endif
WORKBENCH_BOOTNAME(strlen, "string-length");
WORKBENCH_BOOTNAME(strref, "string-ref");
#endif
#ifndef LISP65_TREEWALK_STRIP
WORKBENCH_BOOTNAME(mod, "mod");
#ifndef LISP65_DIALECT_V2
WORKBENCH_BOOTNAME(remainder, "remainder");
#endif
#endif
WORKBENCH_BOOTNAME(funcall, "funcall");
WORKBENCH_BOOTNAME(apply, "apply");
WORKBENCH_BOOTNAME(setfn, "set-symbol-function");
WORKBENCH_BOOTNAME(gensym, "gensym");
WORKBENCH_BOOTNAME(boundp, "boundp");
#if defined(LISP65_DIALECT_V2) && !defined(LISP65_TREEWALK_STDLIB_BRIDGES)
WORKBENCH_BOOTNAME(symbol_value, "symbol-value");
#endif
WORKBENCH_BOOTNAME(peek, "peek");
WORKBENCH_BOOTNAME(poke, "poke");
#ifdef LISP65_EVAL_DIV_PRIM
WORKBENCH_BOOTNAME(div, "/");
#endif
WORKBENCH_BOOTNAME(load, "load");
#ifdef MEGA65_F011_WRITE
WORKBENCH_BOOTNAME(disk_read_sector, "%disk-read-sector");
WORKBENCH_BOOTNAME(disk_byte, "%disk-byte");
WORKBENCH_BOOTNAME(disk_poke, "%disk-poke");
WORKBENCH_BOOTNAME(disk_write_sector, "%disk-write-sector");
WORKBENCH_BOOTNAME(save, "save");
#endif
#ifdef LISP65_EVAL_PRIMS
WORKBENCH_BOOTNAME(eval, "eval");
WORKBENCH_BOOTNAME(eval_string, "eval-string");
#endif
#ifdef LISP65_MACROEXPAND_PRIM
WORKBENCH_BOOTNAME(macroexpand_1, "macroexpand-1");
#endif
#ifdef LISP65_LCC_INSTALL
WORKBENCH_BOOTNAME(lcc_install, "lcc-install");
WORKBENCH_BOOTNAME(set_macro, "%set-macro");
#endif
#ifdef LISP65_DIALECT_V2
WORKBENCH_BOOTNAME(lcc_invalid_parameter_list,
                   "%lcc-error-invalid-parameter-list");
WORKBENCH_BOOTNAME(list_malformed, "%list-malformed-error");
WORKBENCH_BOOTNAME(set, "set");
WORKBENCH_BOOTNAME(key_event, "key-event");
#endif
#if defined(LISP65_FASL) || defined(LISP65_COMPILE_STRING)
WORKBENCH_BOOTNAME(fasl_stage, "%fasl-stage");
WORKBENCH_BOOTNAME(fasl_stage_get, "%fasl-stage-get");
WORKBENCH_BOOTNAME(fasl_read_form, "%fasl-read-form");
#ifdef LISP65_COMPILE_STRING
WORKBENCH_BOOTNAME(cs_read_open, "%cs-read-open");
#endif
#ifdef MEGA65_F011_WRITE
#ifndef LISP65_DIALECT_V2
WORKBENCH_BOOTNAME(save_staged, "%save-staged");
#endif
#endif
#endif
#if defined(LISP65_FASL) && defined(MEGA65_F011_WRITE)
WORKBENCH_BOOTNAME(fasl_src, "%fasl-src");
WORKBENCH_BOOTNAME(fasl_save, "%fasl-save");
#ifdef LISP65_DISK_LIBS
WORKBENCH_BOOTNAME(lib_staged, "lib-staged");
#endif
#endif
WORKBENCH_BOOTNAME(write_char, "write-char");
#ifndef LISP65_OUTPUT_WRAPPERS_IN_STDLIB
WORKBENCH_BOOTNAME(write_string, "write-string");
#endif
WORKBENCH_BOOTNAME(prin1, "prin1");
#ifndef LISP65_SCREEN_BULK_P_IN_STDLIB
WORKBENCH_BOOTNAME(screen_bulk_p, "screen-bulk-p");
#endif
#ifndef LISP65_OUTPUT_WRAPPERS_IN_STDLIB
WORKBENCH_BOOTNAME(terpri, "terpri");
WORKBENCH_BOOTNAME(princ, "princ");
WORKBENCH_BOOTNAME(print, "print");
WORKBENCH_BOOTNAME(write, "write");
WORKBENCH_BOOTNAME(write_line, "write-line");
#endif
WORKBENCH_BOOTNAME(bytecode, "bytecode");
WORKBENCH_BOOTNAME(primitive, "primitive");
WORKBENCH_BOOTNAME(closure, "closure");
WORKBENCH_BOOTNAME(macro, "macro");
WORKBENCH_BOOTNAME(other, "other");
#ifdef LISP65_EVAL_KEYBOARD_PRIMS
WORKBENCH_BOOTNAME(key, "key");
WORKBENCH_BOOTNAME(shift, "shift");
#endif
WORKBENCH_BOOTNAME(nreverse, "nreverse");
WORKBENCH_BOOTNAME(rplaca, "rplaca");
WORKBENCH_BOOTNAME(rplacd, "rplacd");
WORKBENCH_BOOTNAME(symbol_count, "symbol-count");
WORKBENCH_BOOTNAME(symbol_max, "symbol-max");
#ifdef LISP65_NTH_SYMBOL_PRIM
WORKBENCH_BOOTNAME(nth_symbol, "nth-symbol");
#endif
WORKBENCH_BOOTNAME(number_to_string, "number->string");
WORKBENCH_BOOTNAME(symbol_name, "symbol-name");
WORKBENCH_BOOTNAME(function_kind, "function-kind");
#ifdef LISP65_EVAL_SCREEN_PRIMS
WORKBENCH_BOOTNAME(screen_size, "screen-size");
WORKBENCH_BOOTNAME(screen_clear, "screen-clear");
WORKBENCH_BOOTNAME(screen_put_char, "screen-put-char");
#ifdef LISP65_SCREEN_WRITE_STRING
WORKBENCH_BOOTNAME(screen_write_string, "screen-write-string");
#endif
#ifdef LISP65_EVAL_KEYBOARD_PRIMS
WORKBENCH_BOOTNAME(read_key, "read-key");
WORKBENCH_BOOTNAME(poll_key, "poll-key");
#endif
#endif
#ifndef LISP65_TREEWALK_STRIP
WORKBENCH_BOOTNAME(quote, "quote");
WORKBENCH_BOOTNAME(quasiquote, "quasiquote");
WORKBENCH_BOOTNAME(if, "if");
WORKBENCH_BOOTNAME(progn, "progn");
WORKBENCH_BOOTNAME(lambda, "lambda");
WORKBENCH_BOOTNAME(function, "function");
WORKBENCH_BOOTNAME(setq, "setq");
WORKBENCH_BOOTNAME(defmacro, "defmacro");
WORKBENCH_BOOTNAME(unquote, "unquote");
WORKBENCH_BOOTNAME(unquote_splicing, "unquote-splicing");
WORKBENCH_BOOTNAME(rest, "&rest");
WORKBENCH_BOOTNAME(defun, "defun");
WORKBENCH_BOOTNAME(when, "when");
WORKBENCH_BOOTNAME(unless, "unless");
#ifdef LISP65_EVAL_CONTROL_SF
WORKBENCH_BOOTNAME(cond, "cond");
WORKBENCH_BOOTNAME(and, "and");
WORKBENCH_BOOTNAME(or, "or");
#endif
WORKBENCH_BOOTNAME(let, "let");
WORKBENCH_BOOTNAME(letstar, "let*");
WORKBENCH_BOOTNAME(dotimes, "dotimes");
WORKBENCH_BOOTNAME(dolist, "dolist");
#endif
WORKBENCH_BOOTNAME(t, "t");

WORKBENCH_BOOTFN void eval_init(void) {
    obj t;
    mem_init();
#ifdef LISP65_VM
    vm_init();
#ifndef LISP65_V2_CARRIER_CUT
    vm_treewalk_call = eval_vm_bridge;
    vm_treewalk_apply = eval_vm_apply;
#endif
#endif
#ifndef LISP65_TREEWALK_STDLIB_BRIDGES
    defprim(BOOTNAME(add), P_ADD);   defprim(BOOTNAME(sub), P_SUB);   defprim(BOOTNAME(mul), P_MUL);
#endif
#ifndef LISP65_TREEWALK_STRIP
    defprim(BOOTNAME(mod), P_MOD);
#ifndef LISP65_DIALECT_V2
    defprim(BOOTNAME(remainder), P_REMAINDER);
#endif
#endif
#ifndef LISP65_TREEWALK_STDLIB_BRIDGES
    defprim(BOOTNAME(lt), P_LT);    defprim(BOOTNAME(gt), P_GT);    defprim(BOOTNAME(numeq), P_NUMEQ);
    defprim(BOOTNAME(le), P_LE);   defprim(BOOTNAME(ge), P_GE);
#endif
#ifndef LISP65_TREEWALK_STDLIB_BRIDGES
    defprim(BOOTNAME(cons), P_CONS); defprim(BOOTNAME(car), P_CAR); defprim(BOOTNAME(cdr), P_CDR);
    defprim(BOOTNAME(consp), P_CONSP);
    defprim(BOOTNAME(eq), P_EQ);   defprim(BOOTNAME(eql), P_EQL);   defprim(BOOTNAME(list), P_LIST);
#endif
    defprim(BOOTNAME(funcall), P_FUNCALL); defprim(BOOTNAME(apply), P_APPLY);
    defprim(BOOTNAME(setfn), P_SETFN);
    defprim(BOOTNAME(gensym), P_GENSYM);
    defprim(BOOTNAME(boundp), P_BOUNDP);
#if defined(LISP65_DIALECT_V2) && !defined(LISP65_TREEWALK_STDLIB_BRIDGES)
    defprim(BOOTNAME(symbol_value), P_SYMVAL);
#endif
    defprim(BOOTNAME(peek), P_PEEK);   defprim(BOOTNAME(poke), P_POKE);
#ifdef LISP65_EVAL_DIV_PRIM
    defprim(BOOTNAME(div), P_DIV);
#endif
    defprim(BOOTNAME(load), P_LOAD);
#ifdef MEGA65_F011_WRITE
    defprim(BOOTNAME(disk_read_sector), P_DSKRD);  defprim(BOOTNAME(disk_byte), P_DSKBYTE);
    defprim(BOOTNAME(disk_poke), P_DSKPOKE);       defprim(BOOTNAME(disk_write_sector), P_DSKWR);
    defprim(BOOTNAME(save), P_SAVE);
#endif
#ifdef LISP65_EVAL_PRIMS
    defprim(BOOTNAME(eval), P_EVAL);   defprim(BOOTNAME(eval_string), P_EVALSTR);
#endif
#ifdef LISP65_MACROEXPAND_PRIM
    defprim(BOOTNAME(macroexpand_1), P_MEXP1);
#endif
#ifdef LISP65_LCC_INSTALL
    defprim(BOOTNAME(lcc_install), P_LCCINST);
    defprim(BOOTNAME(set_macro), P_SETMACRO);   /* Konvergenz-M2: BCODE-Makro-Install (lcc-run defmacro) */
#endif
#ifdef LISP65_DIALECT_V2
    k_lcc_invalid_parameter_list = intern(BOOTNAME(lcc_invalid_parameter_list));
    defprim(BOOTNAME(lcc_invalid_parameter_list), P_LCCBADPARAM);
    defprim(BOOTNAME(list_malformed), P_LISTMALFORMED);
    defprim(BOOTNAME(set), P_SET);
    defprim(BOOTNAME(key_event), P_KEYEVENT);
#endif
#if defined(LISP65_FASL) || defined(LISP65_COMPILE_STRING)
    defprim(BOOTNAME(fasl_stage), P_FSTAGE);     defprim(BOOTNAME(fasl_stage_get), P_FSTGET);
    defprim(BOOTNAME(fasl_read_form), P_FREADF);
#ifdef LISP65_COMPILE_STRING
    defprim(BOOTNAME(cs_read_open), P_CSOPEN);   /* interne Naht (keine User-API), arena-only */
#endif
#ifdef MEGA65_F011_WRITE
#ifndef LISP65_DIALECT_V2
    defprim(BOOTNAME(save_staged), P_SVSTG);     /* base=0-Ausgabe speichern (io_disk_save_named) */
#endif
#endif
#endif
#ifdef LISP65_FASL
#ifdef MEGA65_F011_WRITE
    defprim(BOOTNAME(fasl_src), P_FSRC);         /* Disk-Source (Diagnose/Historie, nicht Workbench) */
    defprim(BOOTNAME(fasl_save), P_FSAVE);       /* Base-Variante (io_disk_save_range) — FASL-only */
#ifdef LISP65_DISK_LIBS
    defprim(BOOTNAME(lib_staged), P_FLIBST);     /* xemu-Diagnose-Naht (Lib ohne F011) */
#endif
#endif
#endif
#ifndef LISP65_TREEWALK_STDLIB_BRIDGES
    defprim(BOOTNAME(stringp), P_STRINGP);
    defprim(BOOTNAME(numberp), P_NUMBERP); defprim(BOOTNAME(symbolp), P_SYMBOLP);
#if !defined(LISP65_DIALECT_V2) || !defined(LISP65_DIALECT_FAMILY_HARNESS)
    defprim(BOOTNAME(str2list), P_STR2LIST);
    defprim(BOOTNAME(list2str), P_LIST2STR);
#endif
    defprim(BOOTNAME(strlen), P_STRLEN);
    defprim(BOOTNAME(strref), P_STRREF);
#endif
    defprim(BOOTNAME(write_char), P_WRITECHAR);
#ifndef LISP65_OUTPUT_WRAPPERS_IN_STDLIB
    defprim(BOOTNAME(write_string), P_WRITESTR);
#endif
    defprim(BOOTNAME(prin1), P_PRIN1);
#ifndef LISP65_SCREEN_BULK_P_IN_STDLIB
    defprim(BOOTNAME(screen_bulk_p), P_SCRBULKP);
#endif
#ifndef LISP65_OUTPUT_WRAPPERS_IN_STDLIB
    defprim(BOOTNAME(terpri), P_TERPRI);
    defprim(BOOTNAME(princ), P_PRINC);
    defprim(BOOTNAME(print), P_PRINT); defprim(BOOTNAME(write), P_WRITE);
    defprim(BOOTNAME(write_line), P_WRITELINE);
#endif
    /* IDE-Kernel-Naht (docs/editor-architecture.md): Symbol-Introspektion immer... */
    k_bytecode = intern(BOOTNAME(bytecode)); k_primitive = intern(BOOTNAME(primitive));
    k_closure = intern(BOOTNAME(closure)); k_macro = intern(BOOTNAME(macro)); k_other = intern(BOOTNAME(other));
#ifdef LISP65_EVAL_KEYBOARD_PRIMS
    k_key = intern(BOOTNAME(key)); k_shift = intern(BOOTNAME(shift));
#endif
    defprim(BOOTNAME(nreverse), P_NREVERSE);
    defprim(BOOTNAME(rplaca), P_RPLACA); defprim(BOOTNAME(rplacd), P_RPLACD);
    defprim(BOOTNAME(symbol_count), P_SYMCOUNT); defprim(BOOTNAME(symbol_max), P_SYMMAX);
#ifdef LISP65_NTH_SYMBOL_PRIM
    defprim(BOOTNAME(nth_symbol), P_NTHSYM);
#endif
    defprim(BOOTNAME(number_to_string), P_NUM2STR);
    defprim(BOOTNAME(symbol_name), P_SYMNAME);   defprim(BOOTNAME(function_kind), P_FNKIND);
#ifdef LISP65_EVAL_SCREEN_PRIMS
    /* ...Screen nur mit eigenem Treiber, Keyboard nur auf dem Geraet. */
    defprim(BOOTNAME(screen_size), P_SCRSIZE); defprim(BOOTNAME(screen_clear), P_SCRCLEAR);
    defprim(BOOTNAME(screen_put_char), P_SCRPUT);
#ifdef LISP65_SCREEN_WRITE_STRING
    /* Bulk-Zeile (Redisplay-Hebel a): implementiert+host-gruen, aber GEPARKT — kostet
     * ~450 B .text, die erst die .text-Diaet (vm_run!) freischaufelt. Aktivierung:
     * -DLISP65_SCREEN_WRITE_STRING, zusammen mit Codex' Render-Umstellung. */
    defprim(BOOTNAME(screen_write_string), P_SCRWRITE);
#endif
#ifdef LISP65_EVAL_KEYBOARD_PRIMS
    defprim(BOOTNAME(read_key), P_READKEY); defprim(BOOTNAME(poll_key), P_POLLKEY);
#endif
#endif
#ifndef LISP65_TREEWALK_STRIP
    sf_quote = intern(BOOTNAME(quote));   sf_quasiquote = intern(BOOTNAME(quasiquote)); sf_if = intern(BOOTNAME(if));
    sf_progn = intern(BOOTNAME(progn));   sf_lambda = intern(BOOTNAME(lambda));         sf_function = intern(BOOTNAME(function));
    sf_setq = intern(BOOTNAME(setq));     sf_defmacro = intern(BOOTNAME(defmacro));     sf_unquote = intern(BOOTNAME(unquote));
    sf_unquote_splicing = intern(BOOTNAME(unquote_splicing));                           sf_rest = intern(BOOTNAME(rest));
    sf_defun = intern(BOOTNAME(defun));   sf_when = intern(BOOTNAME(when));   sf_unless = intern(BOOTNAME(unless));
#ifdef LISP65_EVAL_CONTROL_SF
    sf_cond = intern(BOOTNAME(cond));     sf_and = intern(BOOTNAME(and));     sf_or = intern(BOOTNAME(or));
#endif
    sf_let = intern(BOOTNAME(let));       sf_letstar = intern(BOOTNAME(letstar));
    sf_dotimes = intern(BOOTNAME(dotimes)); sf_dolist = intern(BOOTNAME(dolist));
#ifdef LISP65_DIALECT_V2
    sf_defvar = intern("defvar"); sf_optional = intern("&optional");
#ifdef LISP65_DIALECT_FAMILY_HARNESS
    sf_v2_string_codes = intern("%string-codes");
    sf_v2_string_from_codes = intern("%string-from-codes");
#endif
#endif
#endif
    t = intern(BOOTNAME(t));   lisp_t = t;
    set_sym_value(t, t);
}
