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
    uint8_t  nargs; uint8_t  nlocals; uint8_t  flags;   /* CO_FLAG_* from vm.h */
    /* M closures: captured free variables. nupvals>0 => this fn is a closure; upval_slot[i]
     * = slot of the i-th upvalue in the CREATING (outer) scope (for the creation-site push). */
    uint8_t  nupvals; uint8_t upval_slot[BC_MAXUPVAL];
} bc_func;

/* One translation unit: fn[0] = the main toplevel form, fn[1..] = lambda helpers.
 * The caller provides fn[] plus per-function code/lit buffers; bc_compile_top fills them and sets nfn.
 * err=1 => the form is not (yet) supported OR a buffer / function slot is full. */
typedef struct {
    bc_func *fn; uint8_t fncap; uint8_t nfn;
    uint16_t gensym;                                /* helper name counter */
    uint8_t  err;
} bc_unit;

/* Compiles ONE toplevel form (expression + OP_RET into fn[0]) plus any lambda helpers into fn[1..]. */
void bc_compile_top(bc_unit *u, obj form);

/* Compiles a defun body DIRECTLY as a named function in fn[0] (parameters from slot 0), without the
 * lambda-lift detour -> saves one CodeObject / directory entry / "__L" symbol per defun. Inner lambdas
 * go to fn[1..]. The caller registers fn[0] under the defun name and fn[1..] as helpers. */
void bc_compile_defun(bc_unit *u, obj params, obj body);

/* 1 if the compiler lowers the symbol itself as a control special form (if/when/and/let/...).
 * Used by the REPL swap: a prelude (defmacro X ...) for such an X is redundant (the compiler handles
 * the form) -> ignore it; only REAL user macros need the M5 expansion. */
int bc_is_special_form(obj sym);

/* Assembliert eine kompilierte Funktion zu einem CodeObject-Blob (Header + littab + Bytecode),
 * wie vm_run/vm_code_load es erwartet. Rueckgabe: Blob-Laenge (0 = passt nicht in cap). */
uint16_t bc_assemble(const bc_func *f, uint8_t *out, uint16_t cap);

#endif
