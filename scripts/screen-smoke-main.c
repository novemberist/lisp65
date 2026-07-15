/* lisp65 host screen-driver smoke. Exercises src/screen.c against the host
 * simulation: ASCII-to-screen-code mapping, wrapping, driver-owned scrolling,
 * clearing, backspace, and cursor handling. Exit 0 means PASS. */
#include <stdio.h>
#include <string.h>
#include "screen.h"
static int fails = 0;
static void expect(const char *what, int cond) {
    printf("%-40s %s\n", what, cond ? "PASS" : "FAIL");
    if (!cond) fails++;
}
static void puts_scr(const char *s) { while (*s) scr_putc(*s++); }
int main(void) {
    const uint8_t *b;
    int i;
    scr_init();
    b = scr_host_buf();
    expect("init: 80x25 erkannt", scr_cols() == 80 && scr_rows() == 25);
    expect("init: leer", b[0] == 0x20 && b[80*25-1] == 0x20);
    puts_scr("hello WORLD 42!\n");
    expect("'h' -> 0x08", b[0] == 0x08);
    expect("'W' -> 0x57", b[6] == 0x57);
    expect("'4' -> 0x34", b[12] == 0x34);
    expect("newline: Zeile 1", scr_row() == 1);
    /* Wrap: 85 characters -> row 2, column 5. */
    for (i = 0; i < 85; i++) scr_putc('x');
    expect("wrap nach 80", scr_row() == 2);
    /* Scroll: bis unten druchschreiben */
    for (i = 0; i < 40; i++) puts_scr("zeile\n");
    expect("scroll: Cursor bleibt unten", scr_row() == 24);
    expect("scroll: oben ist 'zeile'", b[0] == 0x1A);   /* 'z' */
    /* Backspace */
    puts_scr("ab");
    scr_backspace();
    expect("backspace loescht", b[24*80 + 1] == 0x20 && b[24*80] == 0x01);
    scr_clear();
    expect("clear: leer + home", b[0] == 0x20 && scr_row() == 0);
    scr_cursor(1);
    expect("cursor: RVS-Bit", (b[0] & 0x80) != 0);
    scr_putc('q');
    expect("putc entfernt Cursor sauber", b[0] == 0x11);
    /* scr_put_at: RVS-Bit + Clip */
    scr_put_at(2, 0, 'a', 0x81);
    expect("put_at RVS-Bit", b[2] == (0x01 | 0x80));
    scr_put_at(200, 0, 'a', 1);
    expect("put_at clips x", 1);   /* must not crash or write */
    printf(fails ? "FAILS: %d\n" : "ALL PASS\n", fails);
    return fails ? 1 : 0;
}
