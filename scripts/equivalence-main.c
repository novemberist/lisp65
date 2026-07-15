/* lisp65 — Äquivalenz-Suite: Treewalk vs. Geräte-Compiler (Anti-Drift-Regel 2, Lane K).
 *
 * Lässt DIESELBEN Top-Level-Formen wahlweise durch den TREEWALK (eval) oder den
 * GERÄTE-COMPILER (compile_run_top_form + vm_run) laufen und druckt je Form genau EINE
 * Zeile "src => wert". Der Treiber (scripts/equivalence-check.sh) ruft beide Modi in
 * GETRENNTEN PROZESSEN auf (saubere Welten: keine symfn-/Heap-Interferenz zwischen den
 * Engines) und diff't die Ausgaben: Übereinstimmung = keine semantische Drift.
 * Es braucht KEIN Orakel — nur Agreement; Fehler beider Engines werden auf "!error"
 * normalisiert (auch Fehler-Übereinstimmung zählt als Äquivalenz).
 *
 * DRITTE ENGINE "lcc" (Self-Hosting P2/2b): der Treewalk fuehrt lib/lcc.lisp aus, das die
 * Form zu Bytecode kompiliert; der Harness assembliert (bc_assemble), registriert defuns im
 * VM-Directory und laesst Ausdruecke auf vm_run laufen -> lcc-kompilierter Code wird END-TO-END
 * semantisch gegen die anderen Engines gedifft. littab-Objekte werden DAUERHAFT gerootet
 * (der Blob referenziert Heap-Zellen; ungerootet fraesse der GC sie -- M6-Lektion).
 *
 * Aufruf: equivalence-check tree|vm|lcc <formen.lisp> [--preload <datei.lisp>]
 * Korpus-Vertrag: EINE Form pro Zeile (einzeilige Ausgabe-Paarung), druckbare Ergebnisse
 * (Zahl/Symbol/Liste), selbsttragend (definiert seine Mini-Lib selbst — der nackte
 * Treewalk hat KEINE Blob-Stdlib). Bekannte, BEWUSSTE Nicht-Schnittmengen (cond/case/
 * and/or ohne Prelude-Makros im Treewalk; "/" fehlt im Treewalk; Vergleichsketten >2 und
 * defmacro fehlen im Compiler; quasiquote nur Treewalk) stehen NICHT im Agreement-Korpus
 * — siehe tests/equivalence/forms.lisp Kopfkommentar. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <setjmp.h>
#include "obj.h"
#include "mem.h"
#include "symbol.h"
#include "reader.h"
#include "printer.h"
#include "eval.h"
#include "vm.h"
#include "compile_repl.h"
#include "interrupt.h"
#include "compile.h"   /* bc_func/bc_assemble fuer den lcc-Modus */
#ifdef LISP65_EVAL_SCREEN_PRIMS
#include "screen.h"
#endif

/* Host-Naht: vm_run liest Code aus der Compiled-Fn-Region; im lcc-Modus aus dem lcc-Store. */
static uint8_t  lcc_store[16384];
static uint16_t lcc_off = 0;
static int      lcc_mode = 0;
static int use_crepl = 0;   /* nur der vm-Modus (C-Compiler) nutzt die crepl-Region */
void vm_code_load(uint8_t bank, uint16_t off, uint16_t len, uint8_t *dst) {
    (void)bank; memcpy(dst, (use_crepl ? crepl_store : lcc_store) + off, len);
}

/* Plattform-Naht fuer das lcc-install-PRIM (eval.c): Host = lcc_store-Append. */
int lcc_region_alloc(uint16_t len, uint8_t *bank, uint16_t *off) {
    if ((uint32_t)lcc_off + len > sizeof lcc_store) return 0;
    *bank = 0; *off = lcc_off; lcc_off = (uint16_t)(lcc_off + len);
    return 1;
}
void lcc_region_write(uint8_t bank, uint16_t off, const uint8_t *src, uint16_t len) {
    (void)bank; memcpy(lcc_store + off, src, len);
}

#ifdef LISP65_DIALECT_FAMILY_HARNESS
uint8_t lisp65_error_render_code(lisp65_error_code code, obj symbol) {
    (void)code; (void)symbol; return 0;
}
#endif

static obj xcar(obj o) { return IS_PTR(o) ? cell_a(o) : NIL; }
static obj xcdr(obj o) { return IS_PTR(o) ? cell_b(o) : NIL; }

/* lcc-Ausgabe: LISTE von fns (nargs nlocals flags lits bytes), innerste Helper zuerst,
 * MAIN ZULETZT. Helper-Referenz-Literale sind Marker (%lcc-helper <idx>) -> beim Laden durch
 * MK_BCODE(di) ersetzt (OP_CLOSURE/funcall nehmen BCODE-Immediates direkt; Marker zeigen
 * stets auf FRUEHER registrierte fns -> Einmal-Durchlauf reicht).
 * defname != NIL: Main als Funktion registrieren (Ergebnis = Name); sonst Toplevel-Lauf. */
static obj lcc_run_obj(obj fnlist, obj defname) {
    static uint8_t codebuf[1024];
    static obj litbuf[128];   /* lcc-eigene defuns haben >32 Symbol-Literale */
    int dimap[32]; int nfn = 0;
    obj helper_sym = intern("%lcc-helper");
    obj fl;
    for (fl = fnlist; IS_PTR(fl); fl = xcdr(fl)) {
        obj res = xcar(fl);
        int is_main = (xcdr(fl) == NIL);
        bc_func f;
        obj l; uint16_t n; uint16_t blen; int di;
        f.name = is_main ? defname : NIL;
        f.code = codebuf; f.codecap = sizeof codebuf; f.codelen = 0;
        f.lit = litbuf; f.litcap = 128; f.nlit = 0; f.nupvals = 0;
        f.nargs   = (uint8_t)FIXVAL(xcar(res));
        f.nlocals = (uint8_t)FIXVAL(xcar(xcdr(res)));
        f.flags   = (uint8_t)FIXVAL(xcar(xcdr(xcdr(res))));
        for (l = xcar(xcdr(xcdr(xcdr(res)))); IS_PTR(l); l = xcdr(l)) {
            obj lit = xcar(l), keep;
            if (f.nlit >= f.litcap) { lisp_error_msg = "lcc: littab voll"; return NIL; }
            if (IS_PTR(lit) && cell_type(lit) == T_CONS && xcar(lit) == helper_sym) {
                int idx = (int)FIXVAL(xcar(xcdr(lit)));
                if (idx < 0 || idx >= nfn) { lisp_error_msg = "lcc: marker vorwaerts"; return NIL; }
                lit = MK_BCODE(dimap[idx]);          /* Marker -> BCODE-Immediate */
            } else {
                /* DAUERHAFT rooten: der Blob referenziert Heap-Zellen (Halte-Symbol, symval=Root). */
                keep = cons(lit, sym_value(intern("%lcc-lit-keep")));
                set_sym_value(intern("%lcc-lit-keep"), keep);
            }
            litbuf[f.nlit++] = lit;
        }
        for (l = xcar(xcdr(xcdr(xcdr(xcdr(res))))), n = 0; IS_PTR(l); l = xcdr(l)) {
            if (n >= sizeof codebuf) { lisp_error_msg = "lcc: code voll"; return NIL; }
            codebuf[n++] = (uint8_t)FIXVAL(xcar(l));
        }
        f.codelen = n;
        blen = bc_assemble(&f, lcc_store + lcc_off, (uint16_t)(sizeof lcc_store - lcc_off));
        if (!blen) { lisp_error_msg = "lcc: store voll"; return NIL; }
        di = vm_dir_add(f.name, 0, lcc_off, blen);
        if (di < 0) { lisp_error_msg = "lcc: dir voll"; return NIL; }
        lcc_off = (uint16_t)(lcc_off + blen);
        if (nfn >= (int)(sizeof dimap / sizeof dimap[0])) { lisp_error_msg = "lcc: zu viele fns"; return NIL; }
        dimap[nfn++] = di;
        if (is_main) {
            if (defname != NIL) { set_sym_function(defname, MK_BCODE(di)); return defname; }
            vm_status = VM_OK;
            return vm_run_dir(di, NULL, 0);
        }
    }
    lisp_error_msg = "lcc: leere fn-Liste";
    return NIL;
}

static char srcbuf[512];

#ifdef LISP65_DIALECT_FAMILY_HARNESS
static uint8_t symbol_named(obj value, const char *name) {
    return (IS_SYMI(value) || (IS_PTR(value) && cell_type(value) == T_SYM)) &&
           strcmp(symname(value), name) == 0;
}

/* Inspect the input before execution. After a longjmp the form may no longer be
 * safe to traverse, so only the boolean crosses the error path. */
static uint8_t removed_public_reference(obj form) {
#ifdef LISP65_DIALECT_V2
    obj op, args, designator;
    if (!(IS_PTR(form) && cell_type(form) == T_CONS)) return 0;
    op = cell_a(form);
    if (symbol_named(op, "do") || symbol_named(op, "remainder") ||
        symbol_named(op, "string->list") || symbol_named(op, "list->string")) return 1;
    if (!symbol_named(op, "funcall") && !symbol_named(op, "apply")) return 0;
    args = cell_b(form);
    if (!(IS_PTR(args) && cell_type(args) == T_CONS)) return 0;
    designator = cell_a(args);
    return IS_PTR(designator) && cell_type(designator) == T_CONS &&
           symbol_named(cell_a(designator), "function") &&
           IS_PTR(cell_b(designator)) && cell_type(cell_b(designator)) == T_CONS &&
           symbol_named(cell_a(cell_b(designator)), "remainder");
#else
    (void)form;
    return 0;
#endif
}

static void put_normalized_error(uint8_t removed_public) {
    lisp65_error_code code = lisp65_error_pending_code();
    obj symbol = lisp65_error_pending_symbol();
    if (symbol_named(symbol, "%lcc-error-invalid-parameter-list")) {
        printf("!error:code=%u:symbol=%%lcc-error-invalid-parameter-list\n",
               (unsigned)code);
        lisp65_error_clear();
        vm_status = VM_OK;
        return;
    }
#ifdef LISP65_FROZEN_V1_HARNESS
    if (code == LISP65_ERR_UNDEFINED_FUNCTION ||
        code == LISP65_ERR_VM_UNDEFINED_FUNCTION || vm_status == VM_DIRMISS ||
        removed_public)
        puts("!error:undefined-public-name");
    else
        puts("!error:runtime");
#else
    if (code == LISP65_ERR_WRONG_ARGUMENT_COUNT || vm_status == VM_ARITY)
        puts("!error:arity");
    else if (code == LISP65_ERR_UNDEFINED_FUNCTION ||
             code == LISP65_ERR_VM_UNDEFINED_FUNCTION || vm_status == VM_DIRMISS ||
             removed_public)
        puts("!error:undefined-public-name");
    else
        puts("!error:runtime");
#endif
    lisp65_error_clear();
    vm_status = VM_OK;
}
#define PUT_NORMALIZED_ERROR(removed) do { printf("%s => ", srcbuf); put_normalized_error(removed); } while (0)
#else
#define removed_public_reference(form) ((void)(form), 0u)
#define PUT_NORMALIZED_ERROR(removed) do { (void)(removed); printf("%s => ", srcbuf); puts("!error"); } while (0)
#endif

/* Quelltext-Span der Form einzeilig festhalten (Newlines -> Space, getrimmt). */
static void capture_src(const char *from, const char *to) {
    size_t n = 0;
    while (from < to && (*from == ' ' || *from == '\n' || *from == '\r' || *from == '\t')) from++;
    while (to > from && (to[-1] == ' ' || to[-1] == '\n' || to[-1] == '\r' || to[-1] == '\t')) to--;
    while (from < to && n < sizeof(srcbuf) - 1) {
        char c = *from++;
        srcbuf[n++] = (c == '\n' || c == '\r' || c == '\t') ? ' ' : c;
    }
    srcbuf[n] = '\0';
}

int main(int argc, char **argv) {
    static char text[65536];
    static char pre[65536];   /* lcc.lisp waechst mit den Phasen -- grosszuegig (Trunkierung parste still!) */
    FILE *f; size_t len; const char *p;
    int vm_mode;
    if (argc < 3 || (strcmp(argv[1], "tree") != 0 && strcmp(argv[1], "vm") != 0
                     && strcmp(argv[1], "lcc") != 0)) {
        fprintf(stderr, "usage: %s tree|vm|lcc <formen.lisp> [--preload <datei.lisp>]\n", argv[0]);
        return 2;
    }
    vm_mode = strcmp(argv[1], "vm") == 0;
    lcc_mode = strcmp(argv[1], "lcc") == 0;
    f = fopen(argv[2], "rb");
    if (!f) { fprintf(stderr, "kann %s nicht lesen\n", argv[2]); return 2; }
    len = fread(text, 1, sizeof(text) - 1, f);
    fclose(f); text[len] = '\0';

    if (vm_mode) {
        use_crepl = 1;
#ifdef LISP65_DIALECT_V2
        /* function-kind parity needs the same bootstrap function cells as the product. */
        eval_init();
        /* The compile-REPL lane still models the carrier cut: no Treewalk fallback. */
        vm_treewalk_call = 0;
        vm_treewalk_apply = 0;
#else
        mem_init(); vm_init();
#endif
        vm_dir_reset(); crepl_reset();
    }
    else if (lcc_mode) { eval_init(); vm_init(); vm_dir_reset(); }   /* Treewalk traegt lcc; VM fuehrt aus */
    else              { eval_init(); }
#ifdef LISP65_EVAL_SCREEN_PRIMS
    scr_init();
#endif

    /* --preload: Quelle VOR dem Korpus laden. Tree/LCC evaluieren sie; der VM-Modus
     * kompiliert jede Top-Level-Form. Das erlaubt getrennte, artefaktgebundene
     * Dialektprofile im AP8.4-Familiennachweis, ohne Runtime-Profilumschalter. */
    if (argc == 5 && strcmp(argv[3], "--preload") == 0) {
        f = fopen(argv[4], "rb");
        if (!f) { fprintf(stderr, "kann %s nicht lesen\n", argv[4]); return 2; }
        len = fread(pre, 1, sizeof(pre) - 1, f);
        fclose(f); pre[len] = '\0';
        /* Manuell laden: load_source waere unter LISP65_COMPILE_REPL immer die
         * Compiler-Route und wuerde damit den Treewalk-Orakelpfad entwerten. */
        p = pre;
        for (;;) {
            obj preload_form;
            while (*p == ' ' || *p == '\t' || *p == '\n' || *p == '\r') p++;
            if (*p == ';') { while (*p && *p != '\n') p++; continue; }
            if (*p == '\0') break;
            preload_form = read_expr(&p);
            lisp_error_msg = 0;
            if (vm_mode) (void)compile_run_top_form(preload_form);
            else (void)eval(preload_form);
            if (lisp_error_msg || (vm_mode && vm_status != VM_OK)) {
                fprintf(stderr, "preload failed\n");
                return 3;
            }
        }
    }

    p = text;
    for (;;) {
        const char *start; obj form, r; uint8_t removed_public;
        while (*p == ' ' || *p == '\t' || *p == '\n' || *p == '\r') p++;
        if (*p == ';') { while (*p && *p != '\n') p++; continue; }
        if (*p == '\0') break;
        start = p;
        form = read_expr(&p);
        removed_public = removed_public_reference(form);
        capture_src(start, p);
        lisp_error_msg = 0;
        lisp_toplevel_active = 1;
        if (setjmp(lisp_toplevel)) {
            r = NIL; PUT_NORMALIZED_ERROR(removed_public); /* Engines-Fehler normalisiert */
        } else {
            if (vm_mode) {
                r = compile_run_top_form(form);
                if (vm_status != VM_OK) { PUT_NORMALIZED_ERROR(removed_public); lisp_toplevel_active = 0; continue; }
            } else if (lcc_mode) {
                /* (lcc-compile-obj (quote <wrapped>)) bauen -- jedes Zwischenergebnis rooten. */
                obj head = IS_PTR(form) ? cell_a(form) : NIL;
                if (IS_PTR(form) && head == intern("defmacro")) {
                    /* Makro-DEFINITION lebt im Traeger (T_MACRO; P6: kompilierter Expander).
                     * Nutzungen expandiert lcc via function-kind/macroexpand-1. */
                    r = eval(form);
                    if (lisp_error_msg) { PUT_NORMALIZED_ERROR(removed_public); lisp_toplevel_active = 0; continue; }
                    printf("%s => ", srcbuf); print_obj(r); putchar('\n');
                    lisp_toplevel_active = 0; continue;
                }
                obj defname = NIL, wrapped, call, res;
                uint16_t base = gc_rootsp;
                GC_PUSH(form);
                if (IS_PTR(form) && (head == intern("lambda") || head == intern("defun"))) {
                    if (head == intern("defun")) defname = xcar(xcdr(form));
                    wrapped = form;
                } else {
                    wrapped = cons(form, NIL);          GC_PUSH(wrapped);
                    wrapped = cons(NIL, wrapped);       GC_SET(GC_TOP, wrapped);
                    wrapped = cons(intern("lambda"), wrapped); GC_SET(GC_TOP, wrapped);
                }
                GC_PUSH(wrapped);
                call = cons(wrapped, NIL);              GC_PUSH(call);
                call = cons(intern("quote"), call);     GC_SET(GC_TOP, call);
                call = cons(call, NIL);                 GC_SET(GC_TOP, call);
                call = cons(intern("lcc-compile-obj"), call); GC_SET(GC_TOP, call);
                res = eval(call);
                GC_PUSH(res);
                if (lisp_error_msg) { gc_rootsp = base; PUT_NORMALIZED_ERROR(removed_public); lisp_toplevel_active = 0; continue; }
                r = lcc_run_obj(res, defname);          /* littab-objs haengen am Halte-Symbol */
                gc_rootsp = base;                        /* transiente Roots weg */
                if (lisp_error_msg || (defname == NIL && vm_status != VM_OK)) {
                    PUT_NORMALIZED_ERROR(removed_public); lisp_toplevel_active = 0; continue;
                }
            } else {
                r = eval(form);
                if (lisp_error_msg) { PUT_NORMALIZED_ERROR(removed_public); lisp_toplevel_active = 0; continue; }
            }
            printf("%s => ", srcbuf); print_obj(r);
            putchar('\n');
        }
        lisp_toplevel_active = 0;
    }
    return 0;
}
