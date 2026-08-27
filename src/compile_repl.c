/* lisp65 — REPL-Compile-Integration (Lane K, M6)
 *
 * Die geteilte "eine Top-Level-Form kompilieren + ausfuehren"-Operation, die den Treewalk in der REPL
 * ersetzt und die `load_source` mitbenutzt (Design docs/repl-compile-integration-design.md §4/§4a).
 * Host-validiert via scripts/repl-session-main.c (`make repl-session`); die Geraete-Verdrahtung
 * (repl.c-Swap, EXT-Region-Offset) folgt flag-gegatet + HW-verifiziert.
 *
 * Runtime-Speicher (Compiled-Fn-Region): laufzeit-kompilierte Funktionen (defun/lambda) wohnen
 * append-only; `vm_dir_add` registriert `name -> (bank, off, len)`, `vm_code_load` liest von dort
 * (identische Naht wie Stdlib/Disk-Libs). Host: ein Puffer. Geraet: Bank 5.
 */
#include "compile_repl.h"
#include "compile.h"     /* bc_unit, bc_compile_top, bc_assemble */
#include "vm.h"          /* vm_run, vm_dir_add, vm_status, VM_* */
#include "symbol.h"      /* intern, set_sym_function */
#include "mem.h"         /* cons */
#include "reader.h"      /* read_expr(_stream), reader_from_fetch, reader_skip_peek (M7-Loader) */
#include <string.h>
#ifdef __mos__
#include "vm_embed.h"    /* vm_ext_write (Bank-5-Schreiben) */
#endif

#ifdef __mos__
/* Geraet (S0-Fix, docs/bank0-full-suite-strategy.md): Region = Bank 5, Platz kommt aus dem
 * GEMEINSAMEN Allokator vm_ext_code_alloc (hinter Blob-DATEI inkl. L65M-Trailer + hinter geladenen
 * Disk-Libs; Deckel @0x8000/Namepool). persist=0 = transientes Ausdrucks-Main (Zeiger bleibt).
 * 0xFFFF = Region voll -> Aufrufer meldet Fehler (nie stilles Ueberschreiben). Offen (Design §3):
 * littab-Objekte der Region-Fns permanent GC-rooten. */
#define CREPL_BANK 5u
static uint16_t region_put(const uint8_t *blob, uint16_t len, uint8_t persist) {
    uint16_t at = vm_ext_code_alloc(len, persist);
    if (at == 0xFFFF) return 0xFFFF;
    vm_ext_write((unsigned char *)blob, len, CREPL_BANK, at);
    return at;
}
void crepl_reset(void) { }   /* Geraet: der Allokator seeded sich beim Boot (vm_load_ext_metadata) */
#else
#define CREPL_BANK 0u
uint8_t crepl_store[CREPL_STORE_SIZE];
static uint16_t crepl_off = 0;                 /* Host: einfacher Puffer-Append-Zeiger */
static uint16_t region_put(const uint8_t *blob, uint16_t len, uint8_t persist) {
    uint16_t at = crepl_off;
    if ((uint32_t)at + len <= CREPL_STORE_SIZE) memcpy(crepl_store + at, blob, len);
    if (persist) crepl_off = (uint16_t)(at + len);
    return at;
}
void crepl_reset(void) { crepl_off = 0; }
#endif

/* Working buffers for ONE form (main plus helpers). Deliberately lean for the bank-0 budget of the
 * compile-repl profile; on overflow the compiler reports cleanly (err=1 -> "cannot compile"), never
 * silently wrong code. Split large functions into smaller ones if needed. */
#ifndef CREPL_NF
#define CREPL_NF       8                       /* max functions per form (main + up to N-1 lambda helpers) */
#endif
#ifndef CREPL_CODESZ
#define CREPL_CODESZ   160                     /* max bytecode per function (prelude fns are well under 160) */
#endif
#ifndef CREPL_LITSZ
#define CREPL_LITSZ    13                      /* max Literale je Funktion */
#endif
static bc_func  cf[CREPL_NF];
static uint8_t  cf_code[CREPL_NF][CREPL_CODESZ];
static obj      cf_lit[CREPL_NF][CREPL_LITSZ];
static uint8_t  asmbuf[7 + 2 * CREPL_LITSZ + CREPL_CODESZ];   /* CodeObject-Blob (Header+littab+Payload) */
static uint16_t crepl_gensym = 0;              /* monoton -> eindeutige Helfer-Namen ueber Formen */

/* Innere Logik; `form` liegt GC-GEROOTET im Slot `fslot` des Wrappers (Zugriff via gc_rootstack,
 * Rebuilds via GC_SET). Noetig, weil die defun/defparameter-Pfade cons() rufen: auf dem Geraet
 * (60 hot cells, Heap nach Blob-Boot belegt) feuerte der GC beim ersten cons und sammelte die
 * UNGEROOTETE Eingabe-Form halb ein -> defuns kompilierten zu Muell (xemu-Befund 2026-07-05:
 * 9-B-Helfer "PUSHNIL RET" statt adder; davor auf HW (sq 5)->TYPEERROR). Host (2048 Zellen) sah
 * das nie -- reiner Geraete-Klasse-Bug. Rooting haelt die Form auch waehrend vm_run (littab-objs
 * des transienten Main zeigen in die Form, z.B. quote-Literale). */
static obj crtf_run(uint16_t fslot) {
#define FORM gc_rootstack[fslot]
    bc_unit u; int i; uint16_t at, mainlen; obj form, defname = NIL; uint8_t is_defun = 0;

    form = FORM;

    /* (defmacro X ...): if the compiler lowers X itself (when/and/let/...), the prelude macro definition
     * is redundant -> ignore it (no-op). A REAL user macro needs the M5 expansion (compile->run->expand);
     * until then a clean error instead of silently wrong code. This is what lets load_source (the boot
     * prelude: 11 defmacros, all known forms) move to compile_run_top_form without M5 (design §4a). */
    if (IS_PTR(form) && cell_type(form) == T_CONS && cell_a(form) == intern("defmacro")) {
        obj rest = cell_b(form);
        obj mname = (IS_PTR(rest) && cell_type(rest) == T_CONS) ? cell_a(rest) : NIL;
        /* Ignore it if (a) the compiler lowers the form itself (when/and/let/...) OR (b)
         * compile_run_top_form handles it itself (defun/defparameter/defvar). Either way the
         * prelude macro definition is redundant. Only a REAL user macro falls through -> M5. */
        if (mname != NIL && (bc_is_special_form(mname) ||
                             mname == intern("defun") ||
                             mname == intern("defparameter") ||
                             mname == intern("defvar"))) return mname;
        vm_status = VM_TYPEERROR; return NIL;                          /* a real macro -> M5 (not yet) */
    }

    /* v1 keeps the historical approximation (both forms behave like setq). v2 binds the
     * forms correctly: defparameter always assigns; defvar evaluates init only for an
     * unbound symbol and leaves (defvar name) unbound. */
    if (IS_PTR(form) && cell_type(form) == T_CONS &&
        (cell_a(form) == intern("defparameter") || cell_a(form) == intern("defvar"))) {
        obj rest = cell_b(form);
        if (!(IS_PTR(rest) && cell_type(rest) == T_CONS)) {
#ifdef LISP65_DIALECT_V2
            vm_status = VM_ARITY;
#else
            vm_status = VM_TYPEERROR;
#endif
            return NIL;
        }
#ifdef LISP65_DIALECT_V2
        {
            obj name = cell_a(rest), values = cell_b(rest);
            uint8_t is_defvar = cell_a(form) == intern("defvar");
            uint8_t has_init = IS_PTR(values) && cell_type(values) == T_CONS;
            if (!(IS_SYMI(name) || (IS_PTR(name) && cell_type(name) == T_SYM))) {
                vm_status = VM_TYPEERROR; return NIL;
            }
            if ((!is_defvar && !has_init) ||
                (has_init && cell_b(values) != NIL)) {
                vm_status = VM_ARITY; return NIL;
            }
            if (is_defvar && (sym_boundp(name) || !has_init)) return name;
        }
#endif
        {   /* (setq name init) SCHRITTWEISE GC-gerootet aufbauen (jedes cons kann GC ausloesen!). */
            obj name = cell_a(rest);
            obj init = (IS_PTR(cell_b(rest)) && cell_type(cell_b(rest)) == T_CONS) ? cell_a(cell_b(rest)) : NIL;
            obj t = cons(init, NIL);                       /* name/init haengen an FORM (gerootet) */
            GC_PUSH(t);
            t = cons(name, gc_rootstack[GC_TOP]); GC_SET(GC_TOP, t);
            t = cons(intern("setq"), gc_rootstack[GC_TOP]); GC_POPN(1);
            form = t; GC_SET(fslot, form);                 /* neue Form uebernimmt den Root-Slot */
        }
    }

    /* (defun name params . body): compile the body DIRECTLY as a named fn (bc_compile_defun), no longer
     * lifted through (lambda ..) -> saves one CodeObject / directory entry / "__L" symbol per defun
     * (object efficiency; S5). No form rebuild is needed (no lowering) -> params/body stay valid as part
     * of the rooted FORM (bc_compile_defun does not allocate -> no GC in between). */
    if (IS_PTR(form) && cell_type(form) == T_CONS && cell_a(form) == intern("defun")) {
        obj rest = cell_b(form);
        if (!(IS_PTR(rest) && cell_type(rest) == T_CONS) ||
            !(IS_PTR(cell_b(rest)) && cell_type(cell_b(rest)) == T_CONS)) { vm_status = VM_TYPEERROR; return NIL; }
        defname = cell_a(rest);                            /* SYMI-Immediate, GC-frei */
        is_defun = 1;
    }

    u.fn = cf; u.fncap = CREPL_NF; u.nfn = 0; u.gensym = crepl_gensym; u.err = 0;
    for (i = 0; i < CREPL_NF; i++) { cf[i].code = cf_code[i]; cf[i].codecap = CREPL_CODESZ; cf[i].lit = cf_lit[i]; cf[i].litcap = CREPL_LITSZ; }
    if (is_defun) {                                                  /* defun-Rumpf DIREKT in fn[0] (kein Lift) */
        obj rest = cell_b(FORM);                                     /* FORM = gerootete defun-Form */
        bc_compile_defun(&u, cell_a(cell_b(rest)), cell_b(cell_b(rest)));
    } else bc_compile_top(&u, form);
    crepl_gensym = u.gensym;
    if (u.err) { vm_status = VM_TYPEERROR; return NIL; }             /* "cannot compile" */

    for (i = 1; i < u.nfn; i++) {                                    /* innere Lambda-Helfer -> Region (persistent) */
        uint16_t len = bc_assemble(&u.fn[i], asmbuf, sizeof asmbuf);
        int di;
        at = region_put(asmbuf, len, 1);
        if (at == 0xFFFF) { vm_status = VM_HEAPOOM; return NIL; }    /* Bank-5-Code-Region voll */
        di = vm_dir_add(u.fn[i].name, CREPL_BANK, at, len);
        if (di < 0) return vm_dirmiss_detail(u.fn[i].name);
        set_sym_function(u.fn[i].name, MK_BCODE(di));
    }
    if (is_defun) {                                                  /* fn[0] IST die Funktion -> unter defname */
        uint16_t len = bc_assemble(&u.fn[0], asmbuf, sizeof asmbuf);
        int di;
        at = region_put(asmbuf, len, 1);
        if (at == 0xFFFF) { vm_status = VM_HEAPOOM; return NIL; }
        di = vm_dir_add(defname, CREPL_BANK, at, len);
        if (di < 0) return vm_dirmiss_detail(defname);
        set_sym_function(defname, MK_BCODE(di));
        return defname;                                             /* defun: kein Main-Lauf */
    }

    mainlen = bc_assemble(&u.fn[0], asmbuf, sizeof asmbuf);          /* Ausdruck: Main transient laufen */
    at = region_put(asmbuf, mainlen, 0);
    if (at == 0xFFFF) { vm_status = VM_HEAPOOM; return NIL; }        /* Bank-5-Code-Region voll */
    return vm_run(CREPL_BANK, at, mainlen, NULL, 0);
#undef FORM
}

obj compile_run_top_form(obj form) {
    obj r;
    vm_status = VM_OK;   /* frisch starten: defun/defmacro-Pfade laufen OHNE vm_run -- ohne Reset
                          * klebte der Status der VORIGEN Eingabe und meldete falsches
                          * "cannot compile" fuer korrekte defuns (xemu-Befund 2026-07-05). */
    GC_PUSH(form);                                        /* Form fuer die GANZE Compile+Run-Dauer rooten */
    r = crtf_run((uint16_t)GC_TOP);
    GC_POPN(1);
    return r;
}

#ifdef LISP65_COMPILE_REPL
/* M7 (load unification, design §4a): load_source/load_source_stream go DEVICE-NATIVE -- every toplevel
 * form passes through compile_run_top_form (the same compile-and-run as the REPL swap). These replace the
 * tree-walker versions from eval.c (which are compiled out there under LISP65_COMPILE_REPL -> no duplicate
 * symbol). The prelude boot is host-proven (prelude-load-run: all 54 prelude forms load cleanly and the
 * functions then run). This is how the boot path loses its last eval() reference -> with function
 * stripping (--gc-sections) the tree walker drops out (M7). */
void load_source(const char *src) {
    const char *p = src;
    for (;;) {
        while (*p == ' ' || *p == '\t' || *p == '\n' || *p == '\r') p++;
        if (*p == ';') { while (*p && *p != '\n') p++; continue; }
        if (*p == '\0') return;
        {
            obj form = read_expr(&p);
            if (reader_status != READER_OK) return;
            compile_run_top_form(form);
        }
    }
}
/* Boot progress display (S5, source-on-disk): called after EVERY compiled toplevel form.
 * Default 0 (no overhead). The boot sets it to a render function that shows the disk progress
 * (io_disk_load_permille) as a bar or percentage -- compiling the stdlib at boot takes time and the
 * user needs feedback (user requirement 2026-07-05). */
void (*crepl_progress)(void) = 0;
void load_source_stream(char (*fetch)(void)) {
    reader_from_fetch(fetch);
    for (;;) {
        if (reader_skip_peek() == '\0') return;
        {
            obj form = read_expr_stream();
            if (reader_status != READER_OK) return;
            compile_run_top_form(form);
            /* The next top-level form resets vm_status.  Stop here so it
             * cannot mask the first failing INIT/library form. */
            if (vm_status != VM_OK && vm_status != VM_HALT) return;
        }
        if (crepl_progress) crepl_progress();
    }
}

/* Minimal boot without the tree walker (eval.c omitted): mem_init + vm_init. No defprim (the
 * primitives are CALLPRIM inside the VM), no tree-walk hook (vm_native_apply takes over).
 * Replaces eval_init() in this profile. */
void crepl_boot_init(void) {
    mem_init();
    vm_init();
}
#endif
