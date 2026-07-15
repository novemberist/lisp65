/* lisp65 — Symbole (interniert, Lane K) */
#ifndef LISP65_SYMBOL_H
#define LISP65_SYMBOL_H

#include "obj.h"

obj         intern(const char *name);   /* gleicher Name -> gleiches obj */
uint8_t     sym_lookup(const char *name, obj *out); /* read-only, 1 = vorhanden */
obj         gensym(void);               /* frisches, eindeutiges Symbol (Makro-Hygiene) */
const char *symname(obj o);
extern char sym_name_scratch[34];       /* kalter, nicht-reentranter Namens-Scratch */

/* Lisp-2: getrennte Wert- und Funktions-Zelle pro Symbol (global).
 * Default beider Zellen ist NIL. */
obj     sym_value(obj s);
void    set_sym_value(obj s, obj v);
uint8_t sym_boundp(obj s);          /* 1, wenn die Wert-Zelle gesetzt wurde */
obj  sym_function(obj s);
void set_sym_function(obj s, obj v);
uint8_t sym_function_ptrp(obj s);    /* 1, wenn die Funktionszelle ein Heap-Objekt ist */

/* GC-Roots: alle internierten Symbole sind permanent. Gensyms sind GC-bare Heap-Zellen
 * (nicht hier registriert) und werden vom GC normal eingesammelt. */
uint16_t sym_count(void);
uint16_t sym_pool_used(void);
uint16_t sym_max(void);          /* Symbol-Cap (MAX_SYM) fuer Budget-Anzeige */
uint16_t sym_pool_capacity(void);
obj      sym_nth(uint16_t i);

#endif /* LISP65_SYMBOL_H */
