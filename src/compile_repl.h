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
/* Minimal-Boot fuer das compile-repl-Profil OHNE Treewalk (eval.c weggelassen): nur mem_init + vm_init.
 * main.c ruft das statt eval_init(); die Primitive kommen als CALLPRIM aus der VM, nicht via defprim. */
void crepl_boot_init(void);
/* Boot-Ladeanzeige-Hook (S5): nach jeder von load_source_stream kompilierten Form gerufen (0 = aus). */
extern void (*crepl_progress)(void);
#endif

#ifndef __mos__
/* Host: die Compiled-Fn-Region ist dieser Puffer; das Test-vm_code_load liest ihn (Naht-Ersatz fuer
 * Bank 5 auf dem Geraet). */
#define CREPL_STORE_SIZE 8192u
extern uint8_t crepl_store[CREPL_STORE_SIZE];
#endif

#endif
