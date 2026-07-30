/* lisp65 — Symbole (interniert, Lane K) */
#ifndef LISP65_SYMBOL_H
#define LISP65_SYMBOL_H

#include "obj.h"

/* Canonical interned-symbol name contract.  The reader has its own smaller
 * token limit, but generated L65M libraries and native service names may use
 * all 33 bytes.  Every validator/loader buffer includes the trailing NUL. */
#define LISP65_SYMBOL_NAME_MAX 33u
#define LISP65_SYMBOL_NAME_BUFFER (LISP65_SYMBOL_NAME_MAX + 1u)

obj         intern(const char *name);   /* gleicher Name -> gleiches obj */
uint8_t     sym_lookup(const char *name, obj *out); /* read-only, 1 = vorhanden */
obj         gensym(void);               /* frisches, eindeutiges Symbol (Makro-Hygiene) */
const char *symname(obj o);
extern char sym_name_scratch[LISP65_SYMBOL_NAME_BUFFER];

/* Lisp-2: getrennte Wert- und Funktions-Zelle pro Symbol (global).
 * Default beider Zellen ist NIL. */
obj     sym_value(obj s);
void    set_sym_value(obj s, obj v);
uint8_t sym_boundp(obj s);          /* 1, wenn die Wert-Zelle gesetzt wurde */
obj  sym_function(obj s);
void set_sym_function(obj s, obj v);
uint8_t sym_function_ptrp(obj s);    /* 1 if the function cell holds a heap object */

/* GC roots: every interned symbol is permanent. Gensyms are plain GC-managed heap cells
 * (not registered here) and are collected normally. */
uint16_t sym_count(void);
uint16_t sym_pool_used(void);
uint16_t sym_max(void);          /* symbol cap (MAX_SYM), for the budget display */
uint16_t sym_pool_capacity(void);
obj      sym_nth(uint16_t i);

#endif /* LISP65_SYMBOL_H */
