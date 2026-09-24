"""Explicit V6 single-row cache transform for a successor product.

Never edits a historical generated tree. Callers supply the consumed V6
runtime and write the returned source in a new candidate directory. The
cache holds directory bytes only; roots and materialized objects stay live.
"""
import re

DECLARATIONS = '''
/* One validated V6 row; split placement preserves both five-byte BSS floors.
 * Only the synchronous VM path consumes this cache; IRQ never executes Lisp.
 * The high tag bit is valid; clearing its byte invalidates atomically.
 * Physical entry indices are 0..2047, so bit 15 is available as a tag. */
static uint8_t c2_code_cache_key[2]
    __attribute__((section(".lisp65_code_cache_key")));
static uint8_t c2_code_cache_row[10]
    __attribute__((section(".lisp65_code_cache_row")));
'''

RECORD = '''C2_KERNAL_RESIDENT uint8_t c2_product_entry_record(
        uint16_t ordinal, uint8_t directory[10], uint16_t *physical) {
    uint8_t i, transient = (uint8_t)(ordinal >= 2048u);
    uint16_t resolution_limit = transient ? 4096u : c2_runtime.resolution_count;
    if (!c2_ready || !directory || !physical
#ifdef LISP65_C2_NESTED_APPEND_V5
        || (ordinal = C2_HANDLE_NORMALIZE(&c2_runtime, ordinal)) == 0xffffu
#else
        || ordinal >= c2_runtime.entry_count
#endif
        ) return 0;
    if (c2_u16(c2_code_cache_key) == (uint16_t)(ordinal | 0x8000u)) {
        for (i = 0; i < 10u; ++i) directory[i] = c2_code_cache_row[i];
    } else if (!c2_stream_c2d_read((uint16_t)(c2_runtime.entries_offset
            + ordinal * 10u), directory, 10u)) return 0;
    /* A sum of exactly 65536 is valid; every other wrap is invalid.
     * These checks retain the baseline's zero-literal and transient domains. */
    if (directory[0] >= 64u
        || c2_u16(directory + 8) != c2_runtime.generation
        || ((uint16_t)(c2_u16(directory + 2) + c2_u16(directory + 4)) != 0u
            && (uint16_t)(c2_u16(directory + 2) + c2_u16(directory + 4))
                < c2_u16(directory + 2))
        || c2_u16(directory + 6) > resolution_limit
        || directory[1] > (uint16_t)(resolution_limit - c2_u16(directory + 6)))
        return 0;
    if (c2_u16(c2_code_cache_key) != (uint16_t)(ordinal | 0x8000u)) {
        for (i = 0; i < 10u; ++i) c2_code_cache_row[i] = directory[i];
        c2_code_cache_key[0] = (uint8_t)ordinal;
        c2_code_cache_key[1] = (uint8_t)((ordinal >> 8) | 0x80u);
    }
    *physical = ordinal; return 1;
}
'''


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('cache successor seam changed: ' + old[:100])
    return text.replace(old, new, 1)


def transform(source):
    if 'c2_code_cache_key' in source:
        raise ValueError('cache transform applied twice')
    begin = source.index('C2_KERNAL_RESIDENT uint8_t c2_product_entry_record(')
    end = source.index('\nC2_COLD_ENTRY_FN uint8_t c2_entry_records(', begin)
    before = source[begin:end]
    for token in ('directory[0] >= 64u', 'directory + 8', '65536UL',
                  'transient ? 4096u', 'C2_HANDLE_NORMALIZE'):
        if token not in before:
            raise ValueError('not the admitted V6 record path: ' + token)
    source = source[:begin] + RECORD + '\n' + source[end:]
    # Comma expressions preserve conditional single-statement assignments.
    # Invalidate on any context/readiness assignment, including changes to the
    # transient watermark without generation changes. Also cover all C2D
    # stores, so a record rewrite cannot survive in the cache.
    pattern = r'\bc2_(?:runtime(?:\.\w+)?|ready)\s*=(?!=)'
    sites = [dict(line=source[:m.start()].count('\n') + 1, lhs=m.group())
             for m in re.finditer(pattern, source)]
    if len(sites) != 22:
        raise ValueError(f'context assignment inventory drift: {len(sites)}')
    source = re.sub(pattern, lambda m: 'c2_code_cache_key[1] = 0u, ' + m.group(), source)
    source = once(source,
        'C2_KERNAL_RESIDENT uint8_t c2_stream_c2d_write(uint16_t offset, const void *src, uint16_t length) {',
        'C2_KERNAL_RESIDENT uint8_t c2_stream_c2d_write(uint16_t offset, const void *src, uint16_t length) {\n'
        '    c2_code_cache_key[1] = 0u; /* before any possible C2D mutation */')
    source = once(source, '    c2_stream_init(&c2_runtime,',
                  '    c2_code_cache_key[1] = 0u;\n    c2_stream_init(&c2_runtime,')
    source = once(source, 'static uint8_t LISP65_C2_FIXED_ZP("ready") c2_ready;',
                  'static uint8_t LISP65_C2_FIXED_ZP("ready") c2_ready;\n' + DECLARATIONS)
    # The only callers of the length wrapper are in ordinary VM code. Keep
    # its body and callable identity, while placing it outside the crowded
    # E000 capture gap. The object/link edge gates must confirm this remains
    # true for the complete consumed source set.
    source = once(source,
        'C2_KERNAL_RESIDENT uint16_t c2_product_entry_length(uint16_t ordinal)',
        '__attribute__((noinline, used)) uint16_t c2_product_entry_length(uint16_t ordinal)')
    return source, dict(context_assignments=sites, invalidation_classes=[
        'all C2D writes, including decoder and rollback',
        'runtime context assignments and same-generation watermark changes',
        'readiness assignments including failure and install', 'context initialization'])
