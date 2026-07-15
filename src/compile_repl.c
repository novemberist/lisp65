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

/* Arbeits-Puffer fuer EINE Form (Main + Helfer). Bewusst schlank fuer das Bank-0-Budget des
 * compile-repl-Profils; Ueberlauf meldet der Compiler sauber (err=1 -> "cannot compile"), nie stiller
 * Fehlcode. Grosse Funktionen ggf. in kleinere zerlegen. */
#ifndef CREPL_NF
#define CREPL_NF       8                       /* max Funktionen je Form (Main + bis N-1 lambda-Helfer) */
#endif
#ifndef CREPL_CODESZ
#define CREPL_CODESZ   160                     /* max Bytecode je Funktion (Prelude-Fns << 160) */
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

    /* (defmacro X ...) : lowert der Compiler X selbst (when/and/let/...) -> die Prelude-Makro-Definition
     * ist redundant, ignorieren (no-op). Ein ECHTES User-Makro braucht die M5-Expansion (compile->run->
     * expand); bis dahin sauberer Fehler statt still falschem Code. So laesst sich load_source (Boot-Prelude:
     * 11 defmacros, alle bekannte Formen) auf compile_run_top_form umstellen, ohne M5 (Design §4a). */
    if (IS_PTR(form) && cell_type(form) == T_CONS && cell_a(form) == intern("defmacro")) {
        obj rest = cell_b(form);
        obj mname = (IS_PTR(rest) && cell_type(rest) == T_CONS) ? cell_a(rest) : NIL;
        /* Ignorieren, wenn (a) der Compiler die Form selbst lowert (when/and/let/...) ODER (b) sie
         * compile_run_top_form selbst behandelt (defun/defparameter/defvar). Beides macht die
         * Prelude-Makro-Definition redundant. Nur ein ECHTES User-Makro faellt durch -> M5. */
        if (mname != NIL && (bc_is_special_form(mname) ||
                             mname == intern("defun") ||
                             mname == intern("defparameter") ||
                             mname == intern("defvar"))) return mname;
        vm_status = VM_TYPEERROR; return NIL;                          /* echtes Makro -> M5 (noch nicht) */
    }

    /* v1 behaelt die historische Approximation (beide Formen wie setq). v2 bindet
     * die Formen korrekt: defparameter setzt immer; defvar wertet init nur fuer
     * ein ungebundenes Symbol aus und laesst (defvar name) ungebunden. */
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

    /* (defun name params . body): Rumpf DIREKT als benannte Fn kompilieren (bc_compile_defun), NICHT mehr
     * ueber (lambda ..) liften -> spart je defun ein CodeObject/Dir-Eintrag/"__L"-Symbol (Objekt-Effizienz;
     * S5). Kein Form-Rebuild noetig (kein Lowering) -> params/body bleiben als Teil der gerooteten FORM gueltig
     * (bc_compile_defun alloziert nicht -> kein GC dazwischen). */
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
        if (di < 0) { vm_status = VM_DIRMISS; return NIL; }
        set_sym_function(u.fn[i].name, MK_BCODE(di));
    }
    if (is_defun) {                                                  /* fn[0] IST die Funktion -> unter defname */
        uint16_t len = bc_assemble(&u.fn[0], asmbuf, sizeof asmbuf);
        int di;
        at = region_put(asmbuf, len, 1);
        if (at == 0xFFFF) { vm_status = VM_HEAPOOM; return NIL; }
        di = vm_dir_add(defname, CREPL_BANK, at, len);
        if (di < 0) { vm_status = VM_DIRMISS; return NIL; }
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
/* M7 (Load-Vereinheitlichung, Design §4a): load_source/load_source_stream GERAETE-NATIV -- jede Top-Level-Form
 * geht durch compile_run_top_form (derselbe compile-and-run wie der REPL-Swap). Ersetzen die Treewalk-Versionen
 * aus eval.c (die unter LISP65_COMPILE_REPL dort raus sind -> kein Doppelsymbol). Prelude-Boot host-bewiesen
 * (prelude-load-run: alle 54 Prelude-Formen laden sauber, danach laufen die Funktionen). So verliert der Boot-
 * Pfad seine letzte eval()-Referenz -> mit Funktions-Stripping (--gc-sections) faellt der Treewalk (M7). */
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
/* Boot-Ladeanzeige (S5, Source-on-Disk): wird nach JEDER kompilierten Top-Level-Form gerufen.
 * Default 0 (kein Overhead). Der Boot setzt ihn auf eine Render-Funktion, die den Disk-Fortschritt
 * (io_disk_load_permille) als Balken/Prozent zeigt -- Stdlib-Kompilieren beim Boot dauert, der Nutzer
 * braucht Feedback (Nutzer-Anforderung 2026-07-05). */
void (*crepl_progress)(void) = 0;
void load_source_stream(char (*fetch)(void)) {
    reader_from_fetch(fetch);
    for (;;) {
        if (reader_skip_peek() == '\0') return;
        {
            obj form = read_expr_stream();
            if (reader_status != READER_OK) return;
            compile_run_top_form(form);
        }
        if (crepl_progress) crepl_progress();
    }
}

/* Minimal-Boot ohne Treewalk (eval.c weggelassen): mem_init + vm_init. Kein defprim (Primitive =
 * CALLPRIM in der VM), kein Treewalk-Hook (vm_native_apply uebernimmt). Ersetzt eval_init() im Profil. */
void crepl_boot_init(void) {
    mem_init();
    vm_init();
}
#endif
