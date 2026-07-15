/* lisp65 - Reader: Text -> Objektgraph (Lane K)
 * Zwei globale, nicht reentrante Backends: NUL-String oder Fetch-Stream mit Lookahead.
 * Fehler sind ueber reader_status eindeutig von NIL und EOF getrennt.
 */
#include "reader.h"
#include "interrupt.h"
#include "mem.h"
#include "symbol.h"
#include <string.h>

#ifndef READER_MAX_DEPTH
#define READER_MAX_DEPTH 32
#endif

static const char *rd_str;
static char rd_sc, rd_sn;
static char (*rd_sf)(void);
static uint8_t rd_depth;

uint8_t reader_status = READER_OK;
uint8_t reader_error_code = READER_ERR_NONE;

static char rd_peek(void) { return rd_str ? *rd_str : rd_sc; }
static char rd_peek2(void) { return rd_str ? (*rd_str ? rd_str[1] : '\0') : rd_sn; }
static void rd_next(void) {
    if (rd_str) {
        if (*rd_str) rd_str++;
    } else {
        rd_sc = rd_sn;
        rd_sn = rd_sf();
    }
}

static __attribute__((noinline)) obj reader_fail(uint8_t code) {
    reader_status = READER_ERROR;
    reader_error_code = code;
    return NIL;
}

const char *reader_error_message(void) {
    switch (reader_error_code) {
    case READER_ERR_UNCLOSED_LIST: return "reader: unclosed list";
    case READER_ERR_UNCLOSED_STRING: return "reader: unclosed string";
    case READER_ERR_UNFINISHED_ESCAPE: return "reader: unfinished escape";
    case READER_ERR_TOKEN_TOO_LONG:
    case READER_ERR_FIXNUM_RANGE: return "reader: invalid token";
    case READER_ERR_ROOT_OVERFLOW:
    case READER_ERR_TOO_DEEP: return "reader: too deep";
    case READER_ERR_NONE: return "";
    default: return "reader: syntax error";
    }
}

lisp65_error_code reader_lisp_error_code(void) {
    uint8_t code = reader_error_code;

    /* Link-only evidence remains explicit even though the runtime map is arithmetic. */
    LISP65_ERROR_EMISSION_MARK(LISP65_ERR_READER_UNCLOSED_LIST);
    LISP65_ERROR_EMISSION_MARK(LISP65_ERR_READER_UNCLOSED_STRING);
    LISP65_ERROR_EMISSION_MARK(LISP65_ERR_READER_UNFINISHED_ESCAPE);
    LISP65_ERROR_EMISSION_MARK(LISP65_ERR_READER_INVALID_TOKEN);
    LISP65_ERROR_EMISSION_MARK(LISP65_ERR_READER_TOO_DEEP);
    LISP65_ERROR_EMISSION_MARK(LISP65_ERR_READER_SYNTAX);

    if (code == READER_ERR_UNCLOSED_LIST)
        return LISP65_ERR_READER_UNCLOSED_LIST;
    code = (uint8_t)(code - READER_ERR_UNCLOSED_STRING);
    if (code <= (READER_ERR_TOO_DEEP - READER_ERR_UNCLOSED_STRING)) {
        code = (uint8_t)(code + LISP65_ERR_READER_UNCLOSED_STRING);
        if (code >= 6u) --code;
        if (code >= 7u) --code;
        return code;
    }
    return LISP65_ERR_READER_SYNTAX;
}

void reader_from_fetch(char (*fetch)(void)) {
    rd_str = 0;
    rd_sf = fetch;
    rd_sc = fetch();
    rd_sn = fetch();
}

static void skip_ws(void) {
    for (;;) {
        char c = rd_peek();
        if (c > '\0' && c <= ' ') rd_next();
        else if (c == ';') {
            while (rd_peek() != '\0' && rd_peek() != '\n') rd_next();
        } else break;
    }
}

char reader_skip_peek(void) {
    skip_ws();
    return rd_peek();
}

static uint8_t is_delim(char c) {
    return c <= ' ' || c == '(' || c == ')' || c == ';' || c == '\'' || c == '"'
        || c == '`' || c == ',';
}

static obj read_expr_1(void);

static obj read_list(void) {
    uint16_t base = gc_rootsp;
    obj head = NIL, tail = NIL;
    if (!GC_CAN_RESERVE(2)) return reader_fail(READER_ERR_ROOT_OVERFLOW);
    GC_PUSH(head);
    GC_PUSH(tail);

    for (;;) {
        obj value, cell;
        skip_ws();
        if (rd_peek() == '\0') {
            reader_fail(READER_ERR_UNCLOSED_LIST);
            break;
        }
        if (rd_peek() == ')') {
            rd_next();
            gc_rootsp = base;
            return head;
        }
        if (rd_peek() == '.' && is_delim(rd_peek2())) {
            if (tail == NIL) {
                reader_fail(READER_ERR_DOT_WITHOUT_HEAD);
                break;
            }
            rd_next();
            value = read_expr_1();
            if (reader_status == READER_ERROR) break;
            cell_set_b(tail, value);
            skip_ws();
            if (rd_peek() != ')') {
                reader_fail(READER_ERR_EXPECTED_RPAREN);
                break;
            }
            rd_next();
            gc_rootsp = base;
            return head;
        }

        value = read_expr_1();
        if (reader_status == READER_ERROR) break;
        cell = cons(value, NIL);
        if (head == NIL) {
            head = tail = cell;
            GC_SET(base, head);
            GC_SET(base + 1, tail);
        } else {
            cell_set_b(tail, cell);
            tail = cell;
            GC_SET(base + 1, tail);
        }
    }

    gc_rootsp = base;
    return NIL;
}

static __attribute__((noinline)) obj read_atom(void) {
    char tok[34];
    uint8_t n = 0, i, isnum, too_long = 0, neg;
    uint16_t v = 0;

    while (!is_delim(rd_peek())) {
        char c = rd_peek();
        if (n < sizeof(tok) - 1) {
            if (c >= 'A' && c <= 'Z') c = (char)(c + ('a' - 'A'));
            tok[n++] = c;
        } else {
            too_long = 1;
        }
        rd_next();
    }
    tok[n] = '\0';
    if (too_long) return reader_fail(READER_ERR_TOKEN_TOO_LONG);
    if (n == 1 && tok[0] == '.') return reader_fail(READER_ERR_DOT_WITHOUT_HEAD);

    i = (tok[0] == '+' || tok[0] == '-') ? 1 : 0;
    isnum = (tok[i] != '\0');
    for (; tok[i] && isnum; i++)
        if (tok[i] < '0' || tok[i] > '9') isnum = 0;

    if (isnum) {
        neg = (tok[0] == '-');
        for (i = (tok[0] == '+' || tok[0] == '-') ? 1 : 0; tok[i]; i++) {
            uint8_t digit = (uint8_t)(tok[i] - '0');
            if (v > 1638u || (v == 1638u && digit > (uint8_t)(neg ? 4 : 3)))
                return reader_fail(READER_ERR_FIXNUM_RANGE);
            v = (uint16_t)(v * 10u + digit);
        }
        return MKFIX(neg ? -(int16_t)v : (int16_t)v);
    }
    if (strcmp(tok, "nil") == 0) return NIL;
    return intern(tok);
}

static obj sugar(const char *sym) {
    uint16_t base = gc_rootsp;
    obj s, inner, r;
    if (!GC_CAN_RESERVE(2)) return reader_fail(READER_ERR_ROOT_OVERFLOW);
    s = intern(sym);
    GC_PUSH(s);
    if (rd_depth >= READER_MAX_DEPTH - 1) {
        gc_rootsp = base;
        return reader_fail(READER_ERR_TOO_DEEP);
    }
    rd_depth++;
    inner = read_expr_1();
    rd_depth--;
    if (reader_status == READER_ERROR) {
        gc_rootsp = base;
        return NIL;
    }
    GC_PUSH(inner);
    r = cons(s, cons(inner, NIL));
    gc_rootsp = base;
    return r;
}

#ifdef LISP65_STRING_ARENA
static __attribute__((noinline)) obj read_string(void) {
    obj s = str_open();
    rd_next();
    while (rd_peek() != '"') {
        char c;
        if (rd_peek() == '\0') {
            if (s != NIL) str_close(s);
            return reader_fail(READER_ERR_UNCLOSED_STRING);
        }
        c = rd_peek();
        rd_next();
        if (c == '\\') {
            if (rd_peek() == '\0') {
                if (s != NIL) str_close(s);
                return reader_fail(READER_ERR_UNFINISHED_ESCAPE);
            }
            c = rd_peek();
            rd_next();
        }
        if (s != NIL && !str_putc(s, (uint8_t)c)) s = NIL;
    }
    rd_next();
    return s == NIL ? NIL : str_close(s);
}
#else
static __attribute__((noinline)) obj read_string(void) {
    uint16_t base = gc_rootsp;
    obj head = NIL, tail = NIL, str;
    if (!GC_CAN_RESERVE(2)) return reader_fail(READER_ERR_ROOT_OVERFLOW);
    rd_next();
    GC_PUSH(head);
    GC_PUSH(tail);
    while (rd_peek() != '"') {
        char c;
        obj cell;
        if (rd_peek() == '\0') {
            reader_fail(READER_ERR_UNCLOSED_STRING);
            gc_rootsp = base;
            return NIL;
        }
        c = rd_peek();
        rd_next();
        if (c == '\\') {
            if (rd_peek() == '\0') {
                reader_fail(READER_ERR_UNFINISHED_ESCAPE);
                gc_rootsp = base;
                return NIL;
            }
            c = rd_peek();
            rd_next();
        }
        cell = cons(MKFIX((unsigned char)c), NIL);
        if (head == NIL) {
            head = tail = cell;
            GC_SET(base, head);
            GC_SET(base + 1, tail);
        } else {
            cell_set_b(tail, cell);
            tail = cell;
            GC_SET(base + 1, tail);
        }
    }
    rd_next();
    str = alloc(T_STR);
    if (str != NIL) cell_set_a(str, head);
    gc_rootsp = base;
    return str;
}
#endif

static obj read_expr_1(void) {
    char c;
    obj r;
    if (rd_depth >= READER_MAX_DEPTH) return reader_fail(READER_ERR_TOO_DEEP);
    rd_depth++;
    skip_ws();
    c = rd_peek();
    if (c == '\0') {
        if (rd_depth == 1) reader_status = READER_EOF;
        else reader_fail(READER_ERR_UNEXPECTED_EOF);
        r = NIL;
        goto done;
    }
    if (c == '"') { r = read_string(); goto done; }
    if (c == '\'') {
        rd_next();
        r = sugar("quote");
        goto done;
    }
    if (c == '#' && rd_peek2() == '\'') {
        rd_next();
        rd_next();
        r = sugar("function");
        goto done;
    }
    if (c == '`') {
        rd_next();
        r = sugar("quasiquote");
        goto done;
    }
    if (c == ',') {
        rd_next();
        if (rd_peek() == '@') {
            rd_next();
            r = sugar("unquote-splicing");
            goto done;
        }
        r = sugar("unquote");
        goto done;
    }
    if (c == '(') {
        rd_next();
        r = read_list();
        goto done;
    }
    if (c == ')') {
        rd_next();
        r = reader_fail(READER_ERR_UNEXPECTED_RPAREN);
        goto done;
    }
    r = read_atom();
done:
    rd_depth--;
    return r;
}

static obj reader_finish(uint16_t base, obj result) {
    gc_rootsp = base;
    if (reader_status == READER_ERROR) {
#ifdef LISP65_NUMERIC_ERRORS
        lisp_abort_code(reader_lisp_error_code());
#else
        lisp_abort_static(reader_lisp_error_code(), reader_error_message());
#endif
        return NIL;
    }
    return result;
}

obj read_expr(const char **p) {
    uint16_t base = gc_rootsp;
    obj r;
    rd_str = *p;
    rd_depth = 0;
    reader_status = READER_OK;
    reader_error_code = READER_ERR_NONE;
    r = read_expr_1();
    *p = rd_str;
    return reader_finish(base, r);
}

obj read_expr_stream(void) {
    uint16_t base = gc_rootsp;
    obj r;
    rd_depth = 0;
    reader_status = READER_OK;
    reader_error_code = READER_ERR_NONE;
    r = read_expr_1();
    return reader_finish(base, r);
}
