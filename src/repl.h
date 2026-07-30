/* lisp65 — interaktive REPL (Lane K) */
#ifndef LISP65_REPL_H
#define LISP65_REPL_H

/* Read-eval-print loop: reads line by line from stdin (on the device: the KERNAL keyboard),
 * evaluates one form at a time and prints the result. Ends at EOF. */
void repl(void);

#endif /* LISP65_REPL_H */
