/* Host-only protocol driver for the native reader conformance gate. */
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "mem.h"
#include "obj.h"
#include "reader.h"
#include "symbol.h"

typedef struct {
    char *data;
    size_t len;
    size_t cap;
    size_t nodes;
    uint8_t failed;
} outbuf;

static void out_reserve(outbuf *out, size_t extra) {
    size_t needed;
    size_t cap;
    char *grown;

    if (out->failed) return;
    if (extra > (size_t)-1 - out->len - 1) {
        out->failed = 1;
        return;
    }
    needed = out->len + extra + 1;
    if (needed <= out->cap) return;
    cap = out->cap ? out->cap : 128;
    while (cap < needed) {
        if (cap > (size_t)-1 / 2) {
            out->failed = 1;
            return;
        }
        cap *= 2;
    }
    grown = (char *)realloc(out->data, cap);
    if (!grown) {
        out->failed = 1;
        return;
    }
    out->data = grown;
    out->cap = cap;
}

static void out_char(outbuf *out, char c) {
    out_reserve(out, 1);
    if (out->failed) return;
    out->data[out->len++] = c;
    out->data[out->len] = '\0';
}

static void out_text(outbuf *out, const char *text) {
    size_t len = strlen(text);
    out_reserve(out, len);
    if (out->failed) return;
    memcpy(out->data + out->len, text, len + 1);
    out->len += len;
}

static void out_fixnum(outbuf *out, int16_t value) {
    char number[8];
    int len = snprintf(number, sizeof number, "%d", (int)value);
    if (len < 0 || (size_t)len >= sizeof number) {
        out->failed = 1;
        return;
    }
    out_text(out, number);
}

static char ascii_upper(char c) {
    return c >= 'a' && c <= 'z' ? (char)(c - ('a' - 'A')) : c;
}

static void out_symbol(outbuf *out, obj value) {
    const char *name = symname(value);
    while (*name) out_char(out, ascii_upper(*name++));
}

static void out_string_byte(outbuf *out, uint8_t c) {
    static const char hex[] = "0123456789ABCDEF";

    switch (c) {
    case '"': out_text(out, "\\\""); return;
    case '\\': out_text(out, "\\\\"); return;
    case '\n': out_text(out, "\\n"); return;
    case '\r': out_text(out, "\\r"); return;
    case '\t': out_text(out, "\\t"); return;
    default:
        if (c >= 0x20 && c <= 0x7e) {
            out_char(out, (char)c);
        } else {
            out_text(out, "\\x");
            out_char(out, hex[c >> 4]);
            out_char(out, hex[c & 0x0f]);
        }
    }
}

static void out_object(outbuf *out, obj value, uint16_t depth);

static void out_string(outbuf *out, obj value) {
    out_char(out, '"');
#ifdef LISP65_STRING_ARENA
    {
        uint16_t i;
        uint16_t len = str_len(value);
        for (i = 0; i < len; i++) out_string_byte(out, str_byte(value, i));
    }
#else
    {
        obj chars = cell_a(value);
        while (IS_PTR(chars) && cell_type(chars) == T_CONS) {
            obj code = cell_a(chars);
            if (!IS_FIX(code) || FIXVAL(code) < 0 || FIXVAL(code) > 255) {
                out->failed = 1;
                return;
            }
            out_string_byte(out, (uint8_t)FIXVAL(code));
            chars = cell_b(chars);
            if (++out->nodes > (size_t)HEAP_CELLS * 8u) {
                out->failed = 1;
                return;
            }
        }
        if (chars != NIL) {
            out->failed = 1;
            return;
        }
    }
#endif
    out_char(out, '"');
}

static void out_list(outbuf *out, obj value, uint16_t depth) {
    uint8_t first = 1;

    out_char(out, '(');
    while (IS_PTR(value) && cell_type(value) == T_CONS) {
        if (!first) out_char(out, ' ');
        out_object(out, cell_a(value), (uint16_t)(depth + 1));
        if (out->failed) return;
        first = 0;
        value = cell_b(value);
        if (++out->nodes > (size_t)HEAP_CELLS * 8u) {
            out->failed = 1;
            return;
        }
    }
    if (value != NIL) {
        out_text(out, " . ");
        out_object(out, value, (uint16_t)(depth + 1));
    }
    out_char(out, ')');
}

static void out_object(outbuf *out, obj value, uint16_t depth) {
    if (out->failed) return;
    if (depth > 4096 || ++out->nodes > (size_t)HEAP_CELLS * 8u) {
        out->failed = 1;
        return;
    }
    if (value == NIL) {
        out_text(out, "NIL");
    } else if (IS_FIX(value)) {
        out_fixnum(out, FIXVAL(value));
    } else if (IS_SYMI(value)) {
        out_symbol(out, value);
    } else if (!IS_PTR(value)) {
        out->failed = 1;
    } else {
        switch (cell_type(value)) {
        case T_CONS: out_list(out, value, depth); break;
        case T_SYM: out_symbol(out, value); break;
        case T_STR: out_string(out, value); break;
        default: out->failed = 1; break;
        }
    }
}

static void json_string(const char *text) {
    const unsigned char *p = (const unsigned char *)text;
    static const char hex[] = "0123456789abcdef";

    putchar('"');
    while (*p) {
        unsigned char c = *p++;
        switch (c) {
        case '"': fputs("\\\"", stdout); break;
        case '\\': fputs("\\\\", stdout); break;
        case '\b': fputs("\\b", stdout); break;
        case '\f': fputs("\\f", stdout); break;
        case '\n': fputs("\\n", stdout); break;
        case '\r': fputs("\\r", stdout); break;
        case '\t': fputs("\\t", stdout); break;
        default:
            if (c >= 0x20 && c <= 0x7e) {
                putchar((char)c);
            } else {
                fputs("\\u00", stdout);
                putchar(hex[c >> 4]);
                putchar(hex[c & 0x0f]);
            }
        }
    }
    putchar('"');
}

static const char *status_name(uint8_t status) {
    switch (status) {
    case READER_OK: return "ok";
    case READER_EOF: return "eof";
    case READER_ERROR: return "error";
    default: return "unknown";
    }
}

static const char *error_name(uint8_t error) {
    switch (error) {
    case READER_ERR_NONE: return "none";
    case READER_ERR_UNEXPECTED_EOF: return "unexpected-eof";
    case READER_ERR_UNEXPECTED_RPAREN: return "unexpected-rparen";
    case READER_ERR_UNCLOSED_LIST: return "unclosed-list";
    case READER_ERR_DOT_WITHOUT_HEAD: return "dot-without-head";
    case READER_ERR_EXPECTED_RPAREN: return "expected-rparen";
    case READER_ERR_UNCLOSED_STRING: return "unclosed-string";
    case READER_ERR_UNFINISHED_ESCAPE: return "unfinished-escape";
    case READER_ERR_TOKEN_TOO_LONG: return "token-too-long";
    case READER_ERR_FIXNUM_RANGE: return "fixnum-range";
    case READER_ERR_ROOT_OVERFLOW: return "root-overflow";
    case READER_ERR_TOO_DEEP: return "too-deep";
    default: return "unknown";
    }
}

static char *read_stdin(void) {
    char *data = NULL;
    size_t len = 0;
    size_t cap = 0;

    for (;;) {
        size_t got;
        if (cap - len < 256) {
            size_t grown_cap = cap ? cap * 2 : 512;
            char *grown;
            if (grown_cap <= cap) {
                free(data);
                return NULL;
            }
            grown = (char *)realloc(data, grown_cap);
            if (!grown) {
                free(data);
                return NULL;
            }
            data = grown;
            cap = grown_cap;
        }
        got = fread(data + len, 1, cap - len - 1, stdin);
        len += got;
        if (got == 0) break;
    }
    if (ferror(stdin)) {
        free(data);
        return NULL;
    }
    if (!data) {
        data = (char *)malloc(1);
        if (!data) return NULL;
    }
    data[len] = '\0';
    return data;
}

int main(int argc, char **argv) {
    const char *source;
    const char *cursor;
    const char *message;
    char *owned = NULL;
    obj value;
    outbuf canonical = {0};

    if (argc > 2) {
        fputs("usage: reader-conformance-main [source]\n", stderr);
        return 2;
    }
    if (argc == 2) {
        source = argv[1];
    } else {
        owned = read_stdin();
        if (!owned) {
            fputs("reader-conformance-main: cannot read stdin\n", stderr);
            return 2;
        }
        source = owned;
    }

    mem_init();
    cursor = source;
    value = read_expr(&cursor);
    if (mem_oom) {
        fputs("reader-conformance-main: heap exhausted\n", stderr);
        free(owned);
        return 3;
    }
    if (reader_status == READER_OK) {
        out_object(&canonical, value, 0);
        if (canonical.failed) {
            fputs("reader-conformance-main: cannot render reader result\n", stderr);
            free(canonical.data);
            free(owned);
            return 3;
        }
    }

    message = reader_error_message();
    fputs("{\"status\":", stdout);
    json_string(status_name(reader_status));
    printf(",\"status_code\":%u,\"error\":", (unsigned)reader_status);
    json_string(error_name(reader_error_code));
    printf(",\"error_code\":%u,\"message\":", (unsigned)reader_error_code);
    json_string(message ? message : "");
    printf(",\"offset\":%lu,\"value\":", (unsigned long)(cursor - source));
    if (reader_status == READER_OK) json_string(canonical.data ? canonical.data : "");
    else fputs("null", stdout);
    fputs("}\n", stdout);

    free(canonical.data);
    free(owned);
    return 0;
}
