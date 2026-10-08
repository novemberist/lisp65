/* lisp65 — REPL-Compile-Integration (Lane K, M6). Siehe compile_repl.c. */
#ifndef LISP65_COMPILE_REPL_H
#define LISP65_COMPILE_REPL_H
#include <stdint.h>
#include "obj.h"

/* DIE geteilte Operation (Design §4a): eine Top-Level-Form kompilieren + ausfuehren.
 * REPL-Swap UND load_source rufen genau das:
 *   - (defun name params body...) -> Rumpf in die Compiled-Fn-Region + registrieren; Rueckgabe = name.
 *   - sonst (Ausdruck)            -> kompilieren + vm_run; Rueckgabe = Ergebnis.
 * Bei Compile-Fehler: vm_status != VM_OK, Rueckgabe NIL (Aufrufer meldet "cannot compile"). */
obj compile_run_top_form(obj form);

/* Compiled-Fn-Region + gensym zuruecksetzen (Boot / Test). */
void crepl_reset(void);

#ifdef LISP65_COMPILE_REPL
/* Minimal boot for the compile-repl profile WITHOUT the tree walker (eval.c omitted): only mem_init
 * plus vm_init. main.c calls this instead of eval_init(); the primitives arrive as CALLPRIM from the
 * VM, not via defprim. */
void crepl_boot_init(void);
/* Boot progress hook (S5): called after every form compiled by load_source_stream (0 = off). */
extern void (*crepl_progress)(void);
#endif

#ifndef __mos__
/* Host: this buffer IS the compiled-fn region; the test vm_code_load reads it (the seam substitute
 * for bank 5 on the device). */
#define CREPL_STORE_SIZE 8192u
extern uint8_t crepl_store[CREPL_STORE_SIZE];
#endif

#endif
