/* lisp65 — interaktive REPL (Lane K) */
#ifndef LISP65_REPL_H
#define LISP65_REPL_H

/* Read-Eval-Print-Loop: liest zeilenweise von stdin (Gerät: KERNAL-Tastatur),
 * wertet je eine Form aus und druckt das Ergebnis. Endet bei EOF. */
void repl(void);

#endif /* LISP65_REPL_H */
