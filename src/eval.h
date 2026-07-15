/* lisp65 — Evaluator (Lane K) */
#ifndef LISP65_EVAL_H
#define LISP65_EVAL_H

#include "obj.h"

#ifdef LISP65_V2_CARRIER_CUT
#if !defined(LISP65_VM) || !defined(LISP65_DIALECT_V2) || \
    !defined(LISP65_TREEWALK_STRIP) || !defined(LISP65_VM_NATIVE_APPLY) || \
    !defined(LISP65_V2_NATIVE_CAPABILITIES) || \
    !defined(LISP65_V2_NATIVE_STRING_CODECS) || \
    !defined(LISP65_V2_SERVICE_REGISTRY_CLOSED)
#error "LISP65_V2_CARRIER_CUT requires the complete staged v2 VM capability profile"
#endif
#endif

/* Installiert Primitive in die Funktions-Zellen ihrer Symbole + Konstanten (t).
 * Muss vor dem ersten eval() aufgerufen werden. */
void eval_init(void);

#if defined(LISP65_VM) && defined(LISP65_DIALECT_V2) && defined(LISP65_V2_TREE_PRIMITIVE_VIEW)
/* Registry-generated classification of an installed Treewalk primitive.
 *  1: public native function (kind/value filled)
 * -1: installed primitive but explicitly not a public designator
 *  0: no installed Treewalk primitive cell */
int8_t eval_v2_native_function_view(obj sym, uint8_t *kind, uint8_t *value);
#endif

/* Wertet eine Form im globalen Environment aus (Lisp-2). */
obj eval(obj e);

/* Loader-Hook: liest alle Top-Level-Formen aus dem NUL-terminierten Quelltext und
 * wertet jede im globalen Environment aus. So wird das Prelude (eingebettet ODER von
 * Datei geladen) in den laufenden Kern eingespeist. */
void load_source(const char *src);
/* Wie load_source, aber Form fuer Form aus einem Fetch-Stream (Disk-Load: Datei im EXT-RAM). */
void load_source_stream(char (*fetch)(void));

#ifdef LISP65_V2_WORKBENCH_SERVICES
/* Statically linked CALLPRIM services for the staged v2 Workbench profile.
 * Returns zero when a service's owning product feature is not compiled in. */
uint8_t eval_v2_workbench_service(uint8_t id, const obj *args, obj *result);
#endif

#ifdef LISP65_VM
#include "vm_registry.h"
#endif

#endif /* LISP65_EVAL_H */
