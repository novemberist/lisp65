/* Real reader + extracted, unchanged IO predicate; no MOS/ELF claim. */
#include <assert.h>
#define LISP65_COMFORT_TRAMPOLINE 1
#include "reader.c"
static const char *source;
static uint16_t disk_file_pos, disk_file_len, disk_source_link;
static unsigned calls;
#define DISK_SOURCE_LINK_VALID 0x8000u
static char disk_source_fetch(void) {
    ++calls;
    return disk_file_pos < disk_file_len ? source[disk_file_pos++] : 0;
}
#include "io_terminal.c"
static void query(int expected) {
    const char *str = rd_str;
    char sc = rd_sc, sn = rd_sn;
    char (*sf)(void) = rd_sf;
    unsigned p = disk_file_pos, l = disk_file_len, link = disk_source_link, c = calls;
    unsigned status = reader_status, error = reader_error_code, depth = rd_depth;
    assert(io_source_terminal() == expected);
    assert(str == rd_str && sc == rd_sc && sn == rd_sn && sf == rd_sf);
    assert(status == reader_status && error == reader_error_code && depth == rd_depth);
    assert(p == disk_file_pos && l == disk_file_len && link == disk_source_link && c == calls);
}
static void run(const char *tail, uint16_t length, int terminal) {
    source = tail; disk_file_len = length; disk_file_pos = 0; calls = 0;
    disk_source_link = DISK_SOURCE_LINK_VALID;
    reader_from_fetch(disk_source_fetch);
    query(0); /* No whitespace consumption within the query. */
    if (length == 2) assert(disk_file_pos == disk_file_len);
    (void)reader_skip_peek(); /* Loader boundary before evaluation. */
    query(terminal); query(terminal);
}
int main(void) {
    run("  ", 2, 1);
    run(" 7", 2, 0); /* File position == length, yet an unread form exists. */
    run("                    ", 20, 1);
    disk_source_link = 0; query(0);
    disk_source_link = DISK_SOURCE_LINK_VALID;
    reader_status = READER_ERROR; reader_error_code = READER_ERR_UNCLOSED_LIST;
    query(0);
    return 0;
}
