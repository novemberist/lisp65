/* lisp65 — Abbruch/Fehler (Lane K) */
#include "interrupt.h"

#ifdef LISP65_RUNTIME_OVERLAY
#include "l65m_commit_overlay.h"
#include "vm_runtime_overlay.h"
#endif

#if defined(__MEGA65__) || defined(__C64__) || defined(__CBM__)
#define DEVICE 1
#endif

jmp_buf     lisp_toplevel;
int         lisp_toplevel_active = 0;
const char *lisp_error_msg = 0;
static lisp65_error_code pending_code = LISP65_ERR_NONE;
static obj pending_symbol = NIL;
static const char numeric_error_sentinel[] = "";

/* Optional resident dispatcher. A strong product definition may use the runtime
 * transport; the transient renderer itself must never override this symbol. */
#ifdef LISP65_NUMERIC_ERRORS
extern uint8_t lisp65_error_render_code(lisp65_error_code, obj);
extern void emit(char);
#else
extern uint8_t lisp65_error_render_code(lisp65_error_code, obj)
    __attribute__((weak));
extern void emit(char) __attribute__((weak));
extern void emit_str(const char *) __attribute__((weak));
#endif

#ifdef LISP65_NUMERIC_ERRORS
static char error_hex_digit(uint8_t digit) {
    digit &= 15u;
    return (char)(digit + (digit < 10u ? '0' : (uint8_t)('a' - 10)));
}

static uint8_t error_render_resident(lisp65_error_code code) {
    const char *text;
    if (code == LISP65_ERR_RUNTIME_CATALOG)
        text = "E2e catalog missing; redeploy";
    else if (code == LISP65_ERR_RUNTIME_ISLAND)
        text = "E2f runtime island invalid; redeploy";
    else return 0;
    while (*text) emit(*text++);
    return 1;
}
#endif

static void lisp_abort_jump(void) {
    if (!lisp_toplevel_active) return;
#ifdef LISP65_RUNTIME_OVERLAY
    l65m_commit_abort_cleanup();
    (void)vm_runtime_overlay_abort_cleanup();
#endif
    longjmp(lisp_toplevel, 1);
}

void lisp_abort(const char *msg) {
    pending_code = LISP65_ERR_NONE;
    pending_symbol = NIL;
    lisp_error_msg = msg;
    lisp_abort_jump();
    /* kein Toplevel aktiv (z. B. Smoke/Oracle): nur Meldung merken, normal zurueck */
}

void lisp_abort_symbol(lisp65_error_code code, obj symbol) {
    pending_code = code;
    pending_symbol = symbol;
    lisp_error_msg = numeric_error_sentinel;
    lisp_abort_jump();
}

void lisp_abort_code(lisp65_error_code code) {
    lisp_abort_symbol(code, NIL);
}

lisp65_error_code lisp65_error_pending_code(void) { return pending_code; }
obj lisp65_error_pending_symbol(void) { return pending_symbol; }

void lisp65_error_clear(void) {
    pending_code = LISP65_ERR_NONE;
    pending_symbol = NIL;
    lisp_error_msg = 0;
}

uint8_t lisp65_error_render_pending(void) {
#ifndef LISP65_NUMERIC_ERRORS
    if (pending_code == LISP65_ERR_NONE) {
        if (!emit_str) return 0;
        emit_str(lisp_error_msg ? lisp_error_msg : "abort");
        return 1;
    }
#else
    uint8_t code = pending_code;

    /* The Workbench owns only numeric errors; dynamic text remains a host API. */
    if (code == LISP65_ERR_NONE) return 0;
    if (error_render_resident(code)) return 1;
#endif
#ifdef LISP65_NUMERIC_ERRORS
    if (lisp65_error_render_code(code, pending_symbol)) return 1;
#else
    if (lisp65_error_render_code
        && lisp65_error_render_code(pending_code, pending_symbol)) return 1;
    if (!emit) return 0;
#endif
    emit('E');
#ifdef LISP65_NUMERIC_ERRORS
    emit(error_hex_digit((uint8_t)(code >> 4)));
    emit(error_hex_digit(code));
#else
    {
        static const char hex[] = "0123456789abcdef";
        emit(hex[(pending_code >> 4) & 15u]);
        emit(hex[pending_code & 15u]);
    }
#endif
    return 1;
}

void lisp_poll(void) {
#ifdef DEVICE
    /* STKEY $91 == $7F, wenn RUN/STOP gedrueckt (KERNAL-IRQ aktualisiert es). */
    if (*(volatile unsigned char *)0x91 == 0x7F)
        lisp_abort_static(LISP65_ERR_STOPPED, "stopped (run/stop)");
#endif
}
