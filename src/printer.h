/* lisp65 — Printer + Ausgabe-Sink (Lane K) */
#ifndef LISP65_PRINTER_H
#define LISP65_PRINTER_H

#include "obj.h"

void emit(char c);                  /* ein Zeichen: Screen (+ Test-Sink) */
void emit_str(const char *s);
void print_obj(obj o);              /* S-Expression drucken              */
void print_string_raw(obj s);       /* T_STR ohne umgebende Quotes        */
extern uint8_t screen_row;          /* Bildschirmzeilen seit letztem Loeschen (Scroll-Guard) */
void screen_scroll_guard(void);     /* Schirm loeschen statt KERNAL-Scroll (der crasht) */

#ifdef LISP65_XEMU_TEST
void emit_test_terminate(void);     /* NUL-terminiert den $C000-Sink     */
#endif

#endif /* LISP65_PRINTER_H */
