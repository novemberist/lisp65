/* lisp65 — geraeteseitiger Bytecode-Compiler (Lane K). Siehe compile.c. */
#ifndef LISP65_COMPILE_H
#define LISP65_COMPILE_H
#include <stdint.h>
#include "obj.h"

/* Max Upvalues (eingefangene freie Variablen) je Closure -- M-closures, Phase 1. */
#define BC_MAXUPVAL 8

/* Eine kompilierte Funktion: Bytecode + Literal-Tabelle + Signatur. */
typedef struct {
    obj      name;                                  /* NIL = Toplevel-Main; sonst Helper-Symbol (lambda) */
    uint8_t *code; uint16_t codecap; uint16_t codelen;
    obj     *lit;  uint8_t  litcap;  uint8_t  nlit;
    uint8_t  nargs; uint8_t  nlocals; uint8_t  flags;   /* CO_FLAG_* aus vm.h */
    /* M-closures: eingefangene freie Variablen. nupvals>0 => diese Fn ist eine Closure; upval_slot[i]
     * = Slot der i-ten Upvalue im ERZEUGENDEN (aeusseren) Scope (fuer den Creation-Site-Push). */
    uint8_t  nupvals; uint8_t upval_slot[BC_MAXUPVAL];
} bc_func;

/* Eine Uebersetzungseinheit: fn[0] = Main-Toplevel-Form, fn[1..] = lambda-Helper.
 * Der Aufrufer stellt fn[] samt code/lit-Puffern je Funktion; bc_compile_top fuellt sie + setzt nfn.
 * err=1 => Form (noch) nicht unterstuetzt ODER Puffer/Funktions-Slot voll. */
typedef struct {
    bc_func *fn; uint8_t fncap; uint8_t nfn;
    uint16_t gensym;                                /* Helper-Namenszaehler */
    uint8_t  err;
} bc_unit;

/* Kompiliert EINE Toplevel-Form (Ausdruck + OP_RET in fn[0]) + evtl. Lambda-Helper in fn[1..]. */
void bc_compile_top(bc_unit *u, obj form);

/* Kompiliert einen defun-Rumpf DIREKT als benannte Funktion in fn[0] (Params ab Slot 0), ohne den
 * Lambda-Lift-Umweg -> spart je defun ein CodeObject/Dir-Eintrag/"__L"-Symbol. Innere lambdas -> fn[1..].
 * Der Aufrufer registriert fn[0] unter dem defun-Namen; fn[1..] als Helfer. */
void bc_compile_defun(bc_unit *u, obj params, obj body);

/* 1, wenn der Compiler das Symbol als Kontroll-Special-Form selbst lowert (if/when/and/let/...).
 * Genutzt vom REPL-Swap: eine Prelude-(defmacro X ...) fuer so ein X ist redundant (Compiler macht
 * die Form selbst) -> ignorieren; nur ECHTE User-Makros brauchen die M5-Expansion. */
int bc_is_special_form(obj sym);

/* Assembliert eine kompilierte Funktion zu einem CodeObject-Blob (Header + littab + Bytecode),
 * wie vm_run/vm_code_load es erwartet. Rueckgabe: Blob-Laenge (0 = passt nicht in cap). */
uint16_t bc_assemble(const bc_func *f, uint8_t *out, uint16_t cap);

#endif
