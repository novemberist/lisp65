/* MEGA65 HYPPO DOS file-load probe (diagnostic; NOT part of the REPL build).
 *
 * Reproduces the historical native (load "...") blocker. HYPPO traps use STA $D640 + NOP,
 * with the subfunction in A, results in A/X/Y/carry, and carry set for success. The filename
 * and Z length are build parameters so off-by-one, LFN, and 8.3 variants need no source edit.
 *
 * SETUP: place the raw file in the SD root (not in a D81; HYPPO reads FAT32 directly):
 *   printf '(defun sq (x) (* x x))\n' > demolib
 *   tools/m65tools/mega65_ftp -F -e -c "put demolib demolib" -c "exit"
 * BUILD:   make hyppo-probe-matrix
 * DEPLOY: tools/m65tools/etherload -r build/hyppo-probe-demolib-l7.prg
 *
 * DIAGNOSTICS use border ($D020) and background ($D021), which survive a crash:
 *   cyan(3) = selectdrive/open failure; red(2) = cdroot/findfirst failure;
 *   white(1) = setname failure; green(5)+orange(8) = successful read starting with '(';
 *   yellow(7) = zero-byte read; otherwise the border/background encode the error nibbles.
 * dos_errorcode_*: $05 not_two_fats, $85 invalid_cluster, $88 file_not_found, $FF eof.
 *
 * Trap A values (";; $XX" in mega65-core/src/hyppo/dos.asm): selectdrive $06,
 * setname $2E, findfirst $30, findfile $34, loadfile $36, openfile $18, readfile $1A,
 * geterrorcode $38, cdrootdir $3C.
 */
#include <stdint.h>
#define BORDER (*(volatile unsigned char *)0xD020)
#define BG     (*(volatile unsigned char *)0xD021)

#define HYPPO_PROBE_STR2(x) #x
#define HYPPO_PROBE_STR(x) HYPPO_PROBE_STR2(x)

#ifndef HYPPO_PROBE_NAME
#define HYPPO_PROBE_NAME "demolib"
#endif
#ifndef HYPPO_PROBE_NAMELEN
#define HYPPO_PROBE_NAMELEN 7
#endif

static const char fname[] = HYPPO_PROBE_NAME;

static unsigned char geterr(void) {
    unsigned char e;
    __asm__ volatile("lda #$38\n\t sta $d640\n\t nop\n\t sta %0\n\t" : "=m"(e)::"a");
    return e;
}

int main(void) {
    uint16_t fa = (uint16_t)fname;
    uint8_t dc = 0, cc = 0, sc = 0, ffc = 0, opc = 0, rc = 0, fd = 0, cnt = 0, err = 0;

    /* selectdrive 0; required to avoid not_two_fats */
    __asm__ volatile("ldx #0\n\t lda #$06\n\t sta $d640\n\t nop\n\t lda #0\n\t rol\n\t sta %0\n\t" : "=m"(dc)::"a","x");
    if (!dc) { BORDER = 3; BG = 15; for(;;){} }
    /* cdrootdir */
    __asm__ volatile("lda #$3c\n\t sta $d640\n\t nop\n\t lda #0\n\t rol\n\t sta %0\n\t" : "=m"(cc)::"a");
    if (!cc) { BORDER = 2; BG = 14; for(;;){} }
    /* setname: X/Y = NUL-terminated name, Z = length; matrix includes/excludes NUL */
    __asm__ volatile(
        "ldz #" HYPPO_PROBE_STR(HYPPO_PROBE_NAMELEN) "\n\t"
        "ldx %1\n\t ldy %2\n\t lda #$2e\n\t sta $d640\n\t nop\n\t"
        "lda #0\n\t rol\n\t sta %0\n\t"
        : "=m"(sc)
        : "r"((uint8_t)(fa & 0xff)), "r"((uint8_t)(fa >> 8))
        : "a","x","y");
    if (!sc) { BORDER = 1; BG = geterr() & 15; for(;;){} }
    /* findfirst */
    __asm__ volatile("lda #$30\n\t sta $d640\n\t nop\n\t lda #0\n\t rol\n\t sta %0\n\t" : "=m"(ffc)::"a");
    if (!ffc) { BORDER = 2; BG = geterr() & 15; for(;;){} }
    /* openfile -> A = file descriptor */
    __asm__ volatile("lda #$18\n\t sta $d640\n\t nop\n\t sta %0\n\t lda #0\n\t rol\n\t sta %1\n\t" : "=m"(fd), "=m"(opc)::"a");
    if (!opc) { BORDER = 3; BG = geterr() & 15; for(;;){} }
    /* readfile: X = descriptor, returns low byte count in X, data at $DE00 */
    __asm__ volatile(
        "ldx %2\n\t lda #$1a\n\t sta $d640\n\t nop\n\t stx %0\n\t"
        "lda #0\n\t rol\n\t sta %1\n\t"
        : "=m"(cnt), "=m"(rc)
        : "m"(fd)
        : "a","x","y");
    if (!rc) {
        err = geterr();
        BORDER = err >> 4;
        BG = err & 15;
        for(;;){}
    }
    BORDER = cnt ? 5 : 7;
    BG = (*(volatile unsigned char *)0xDE00) & 15;
    for(;;){}
    return 0;
}
