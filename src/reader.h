/* lisp65 — Reader: Text -> Objektgraph (Lane K) */
#ifndef LISP65_READER_H
#define LISP65_READER_H

#include "obj.h"
#include "error_codes.h"

enum {
    READER_OK,
    READER_EOF,
    READER_ERROR
};

enum {
    READER_ERR_NONE,
    READER_ERR_UNEXPECTED_EOF,
    READER_ERR_UNEXPECTED_RPAREN,
    READER_ERR_UNCLOSED_LIST,
    READER_ERR_DOT_WITHOUT_HEAD,
    READER_ERR_EXPECTED_RPAREN,
    READER_ERR_UNCLOSED_STRING,
    READER_ERR_UNFINISHED_ESCAPE,
    READER_ERR_TOKEN_TOO_LONG,
    READER_ERR_FIXNUM_RANGE,
    READER_ERR_ROOT_OVERFLOW,
    READER_ERR_TOO_DEEP
};

extern uint8_t reader_status;
extern uint8_t reader_error_code;
const char *reader_error_message(void);
lisp65_error_code reader_lisp_error_code(void);

/* Liest EINE S-Expression aus dem NUL-terminierten Quelltext **p und setzt *p hinter die
 * gelesene Form (String-Backend, praezise Position). reader_status unterscheidet ein
 * gueltiges NIL, EOF und Fehler. */
obj read_expr(const char **p);

/* Disk-Stream-Naht (Regel-B-LOAD): Datei liegt im EXT-RAM, ein Fetch-Callback liefert Rohzeichen
 * (0 = EOF) ueber ein winziges Bank-0-Fenster -> KEIN grosser Parse-Puffer in Bank 0, beliebige
 * Dateigroesse. Der Reader ist KALT (nur Parse-Zeit) => Fn-Call/Zeichen ohne Perf-Belang; globale
 * Quelle => NICHT reentrant (wie das alte load). reader_from_fetch setzt die Quelle,
 * read_expr_stream liest EINE Form daraus, reader_skip_peek ueberspringt WS/Kommentar fuer den
 * EOF-Check der Lade-Schleife (s. load_source_stream). */
void reader_from_fetch(char (*fetch)(void));
obj  read_expr_stream(void);
char reader_skip_peek(void);

#endif /* LISP65_READER_H */
