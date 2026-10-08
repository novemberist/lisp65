/* lisp65 — Abbruch/Fehler (Lane K)
 * Gemeinsame Naht fuer RUN/STOP-Abbruch und Fehler-Reporting: eval ruft lisp_poll()
 * periodisch (RUN/STOP) und lisp_abort() bei Fehlern; die REPL setzt das Toplevel-
 * Sprungziel (setjmp) und faengt beides ab.
 */
#ifndef LISP65_INTERRUPT_H
#define LISP65_INTERRUPT_H

#include <setjmp.h>
#include "error_codes.h"
#ifdef LISP65_C2_KERNAL_UNMAP
#include "c2_kernal_runtime.h"
#endif
#ifndef LISP65_KEYMOD_SHIFT
#define LISP65_KEYMOD_SHIFT   0x03u
#define LISP65_KEYMOD_CONTROL 0x04u
#define LISP65_KEYMOD_META    0x10u
#endif

extern jmp_buf     lisp_toplevel;
extern uint8_t     lisp_toplevel_active;   /* 1, sobald die REPL setjmp gesetzt hat */
extern const char *lisp_error_msg;

void lisp_abort(const char *msg);   /* longjmp zum Toplevel, falls aktiv; sonst no-op */
void lisp_abort_code(lisp65_error_code code);
void lisp_abort_symbol(lisp65_error_code code, obj symbol);
/* The persistent cell predates structured VM details and retains its historic
 * name.  This zero-byte source alias makes the widened SYMI/BCODE/NIL contract
 * explicit without creating a second abort seam or storage location. */
#define lisp_abort_detail(code, detail) \
    lisp_abort_symbol((code), (detail))
lisp65_error_code lisp65_error_pending_code(void);
obj lisp65_error_pending_symbol(void);
void lisp65_error_clear(void);

/* The resident hook may transport a build-bound renderer slice, but is never the
 * transient slice entry itself. It must not allocate and returns 1 only after output. */
uint8_t lisp65_error_render_code(lisp65_error_code code, obj symbol);
uint8_t lisp65_error_render_pending(void);
void lisp_poll(void);               /* RUN/STOP pruefen (Geraet); ggf. lisp_abort */
#ifdef LISP65_C2_KERNAL_UNMAP
uint8_t lisp_input_event(uint8_t blocking, uint8_t idle,
                         lisp65_key_event *event);
#endif

#ifdef LISP65_NUMERIC_ERRORS
#define lisp_abort_static(code, text) \
    do { LISP65_ERROR_EMISSION_MARK(code); lisp_abort_code(code); } while (0)
#define lisp_abort_static_symbol(code, symbol, text) \
    do { LISP65_ERROR_EMISSION_MARK(code); \
         lisp_abort_symbol((code), (symbol)); } while (0)
#else
#define lisp_abort_static(code, text) lisp_abort(text)
#define lisp_abort_static_symbol(code, symbol, text) lisp_abort(text)
#endif

#endif /* LISP65_INTERRUPT_H */
