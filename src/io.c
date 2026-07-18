/* lisp65 — Datei-Eingabe-Naht (Lane K). Siehe io.h. */
#include "io.h"
#ifdef MEGA65_F011_LOAD
#include "obj.h"     /* ext_disk_put/get/stage (EXT-Disk-Scratch) */
#include "mem.h"     /* shared Bank-4 disk-scratch layout contract */
#include "eval.h"    /* load_source_stream */
#include "reader.h"  /* reader_from_fetch (FASL compile-file source stream) */
#include "vm_runtime_overlay.h" /* persistent source fetch across C1 overlay swaps */
#ifdef LISP65_DISK_LIBS
#include "vm_embed.h" /* vm_load_lib_ext + lisp65_stdlib_* (Stufe 2: Bytecode-Libs von Disk) */
#ifdef LISP65_ATTIC_LIBRARY_SHELF
#include "attic_library_shelf.h"
#endif
#endif
#endif

#ifndef IO_BUF_MAX
#ifdef LISP65_XEMU_TEST
#define IO_BUF_MAX 1        /* Test-Builds rufen load nie auf -> kein BSS verschwenden
                             * (sonst sprengen io_buf + tsink_buf den c64-Test-Build) */
#else
#define IO_BUF_MAX 512      /* begrenzt die Dateigröße; -D überschreibbar */
#endif
#endif

static char io_buf[IO_BUF_MAX] __attribute__((unused));

#if defined(__MEGA65__)
/* MEGA65-NATIV: C64-Stil-KERNAL-Datei-I/O (OPEN $FFC0) crasht hier (C65-MAP/Bank). Der
 * native Weg ist das hyppo-Hypervisor-DOS (Trap via STA $D640 + NOP; A=Subfunktion;
 * Ergebnis in A/X/Y/Carry; Erfolg=Carry SET). Siehe docs/mega65-file-io-research.md.
 *
 * STAND 2026-06-30: in xemu (Kaltboot von echter SD) END-zu-END bestätigt — selectdrive(0),
 * cdrootdir, setname, findfirst, openfile, readfile liefern alle carry SET; 23-Byte-Testdatei
 * korrekt gelesen (Beweis-Log native-load-proof). ZWEI ABI-Funde:
 *   1) Der setname-Name-Puffer muss PAGE-ALIGNED sein: hyppo liest den Namen ab der
 *      Page-Basis (Low-Byte des X/Y-Pointers wird verworfen). Nicht-ausgerichteter Name ->
 *      leerer Name -> findfirst $88 file_not_found. Darum unten namebuf @ aligned(256).
 *   2) selectdrive(0)/cdrootdir MÜSSEN carry SET liefern (Disk-Liste vom Boot befüllt).
 * Per Default AUS, weil real-HW-Start via etherload selectdrive bisher carry CLEAR gab
 * (dos_disk_count==0 im Inject-Kontext); das ist ein START-/Deploy-Kontext-Problem, KEINE
 * Unmöglichkeit. Mit -DMEGA65_HYPPO_LOAD einschalten, sobald der Geräte-Startpfad bestätigt
 * ist. hyppo matcht Namen case-sensitiv -> Name NICHT hochcasen. */
/* BEVORZUGTER PFAD (MEGA65_F011_LOAD): liest die EINGELEGTE Disk ueber den F011-
 * Floppy-Controller — KEIN ROM/KERNAL/hyppo, KEIN rohes SD/FAT. Der Controller liest das
 * gemountete D81-Image selbst (Mount + SD-Fragmentierung sind SEINE Sache) und erzwingt so
 * die Disk-Grenze: Lisp/User sieht nur die eingelegte Disk, nie die rohe SD. Produkt-korrekt
 * (bleibt gueltig, wenn das ROM fuer RAM ausgeblendet wird).
 *
 * HW-BEWIESEN 2026-07-04, Kontext gehaertet 2026-07-13 (docs/mega65-file-io-research.md):
 *  - Leseweg: I/O neu freischalten, $D689=0 (F011), F011-Read-Kmd, $D680=$81, $DE00 lesen,
 *    danach $D680=$82. Der fruehere rohe $D680=2-Zwischenschritt erbte SD-Slot/BUFSEL-Zustand
 *    und ist verboten. NICHT via $D087 / Flat-$FFD6C00. Jeder Vorgang besitzt seinen Kontext.
 *  - Geometrie (per Kalibrier-Disk vermessen): CBM-1581 logisch (Track L 1..80, Sektor S
 *    0..39, je 256 B) -> f011_track=L-1; b=S>>1; half=S&1; seite=(b>=10)?1:0;
 *    f011_sektor=(b%10)+1. (=> block = f011_track*20 + seite*10 + (sektor-1), Standard-D81.)
 * Kein residenter Sektorpuffer / keine FAT-Kette mehr (vs. altem SD-direkt-Weg: -1348 B BSS).
 * Offline in xemu NICHT testbar (virtueller Mount-Pool) -> HW-Validierung via etherload -m. */
#ifdef MEGA65_F011_LOAD
static void m65_io_enable(void) {
    __asm__ volatile("lda #$47\n\t sta $d02f\n\t lda #$53\n\t sta $d02f\n\t" ::: "a");
}
#include "f011_context.h"
/* F011-Read EINES CBM-Logiksektors (T 1..80, S 0..39). Die 256-B-Logikhaelfte liegt danach im
 * $DE00-Fenster ab dem ZURUeCKGEGEBENEN Offset (0 oder 256) — KEINE Kopie (Regel-B-Redesign:
 * die Primitive/der Chain-Leser kopieren direkt aus $DE00, spart Stack-Scratch). */
static unsigned int f011_read_at(unsigned char T, unsigned char S) {
    unsigned char b    = (unsigned char)(S >> 1);              /* 0..19  512-B-Block im Track */
    unsigned char half = (unsigned char)(S & 1);              /* 0=untere, 1=obere 256 B */
    unsigned char side = (unsigned char)(b >= 10 ? 1 : 0);
    unsigned char fsec = (unsigned char)((b >= 10 ? b - 10 : b) + 1);   /* 1..10 */
    unsigned int  g;
    m65_io_enable();
    lisp65_f011_take_context();                               /* Drive 0 + F011-Puffer */
    *((volatile unsigned char *)0xD081) = 0x20;               /* spinup */
    for (g = 0; g < 20000; g++) {}
    *((volatile unsigned char *)0xD084) = (unsigned char)(T - 1);      /* f011 track 0..79 */
    *((volatile unsigned char *)0xD085) = fsec;                        /* f011 sektor 1..10 */
    *((volatile unsigned char *)0xD086) = side;                        /* seite 0/1 */
    *((volatile unsigned char *)0xD081) = 0x40;                        /* read */
    for (g = 0; g < 60000 && (*((volatile unsigned char *)0xD082) & 0x80); g++) {}   /* BUSY */
    lisp65_f011_map_buffer();                                          /* F011-Puffer -> $DE00 */
    return (unsigned int)half << 8;
}

/* ==== Regel-B-Disk-Primitive (Bytecode-Lisp treibt die 1581-Logik; s. docs/load-rule-b-design.md
 * + docs/bytecode-abi.md §4a fuer die frozen IDs). EIN Bank-0-Puffer DBUF: Dir-Scan-Ziel UND
 * Datei-Parse-Puffer (sequenziell). ==== */
/* Step 2 (EXT-Streaming): KEIN grosser Bank-0-Puffer mehr. Dir-Sektor (256 B) + Datei liegen im
 * EXT-RAM (ext_disk_put/get, Bank oberhalb des Zell-Heaps). Die Datei wird ueber load_source_stream
 * in den Reader gestreamt -> beliebige Dateigroesse. Alles KALT (Ladezeit) -> DMA/Byte ok. */
#define DISK_EXT_DIR   0u        /* Dir-Sektor: EXT-Offset 0..255 */
#define DISK_EXT_FILE  LISP65_EXT_DISK_FILE_OFFSET /* Datei nach dem 256-B-Directory-Sektor */
#define DISK_FILE_MAX  DISK_EXT_FILE_MAX
#define DISK_CHAIN_FUEL ((unsigned int)(DISK_FILE_MAX / 254u + 2u))

/* Decode one 1581 file-chain link without ever treating a corrupt 0/0 tail
 * as 255 payload bytes.  Product file APIs are capped by DISK_FILE_MAX, so
 * their walker fuel is derived from that public byte ceiling rather than an
 * 8-bit magic number. */
static unsigned int disk_chain_count(unsigned char t, unsigned char s,
                                     unsigned char nt, unsigned char ns) {
    if (!nt) {
        if (!ns) return 255u;
        return (unsigned int)(ns - 1u);
    }
    if (nt > 80u || ns > 39u || (nt == t && ns == s)) return 255u;
    return 254u;
}

/* %disk-read-sector: liest CBM-Logiksektor (T,S), legt die 256 B in den EXT-Dir-Scratch. */
unsigned char io_disk_read_sector(unsigned char track, unsigned char sector) {
    unsigned int off, i;
    off = f011_read_at(track, sector);
    for (i = 0; i < 256; i++)
        ext_disk_put((unsigned int)(DISK_EXT_DIR + i), ((volatile unsigned char *)0xDE00)[off + i]);
    lisp65_f011_unmap_buffer();
    return 1;
}
/* %disk-byte: Byte i (0..255) aus dem EXT-Dir-Scratch. */
unsigned char io_disk_byte(unsigned char i) { return ext_disk_get((unsigned int)(DISK_EXT_DIR + i)); }

#ifdef MEGA65_F011_WRITE
/* ==== SAVE-Kern (Prio 1, docs/two-product-workflow.md): F011-Write EINES CBM-Logiksektors ====
 * Schliesst den Werkbank->Maschinenraum-Loop (IDE speichert Quelle, Compiler-REPL laedt sie).
 * Read-Modify-Write: f011_read_at holt den physischen 512-B-Block (BEIDE 256-B-Logikhaelften)
 * und mappt ihn nach $DE00; wir ueberschreiben NUR unsere Haelfte aus dem EXT-Dir-Scratch und
 * schieben den Block per F011-Write-Kommando zurueck.
 * HW-UNSICHERHEIT (Variante A; xemu-F011 hier defekt -> nur am Geraet klaerbar, Rezept in
 * docs/f011-write-calibration.md): ob das $DE00-Fenster beschreibbar ist und ob Kommando $84
 * aus DIESEM Puffer schreibt, ist Analogie zum HW-bewiesenen Leseweg. Das Readback-Verify in
 * io_disk_write_sector macht einen falschen Weg als sauberes 0 sichtbar -- NIE stille Korruption. */
void io_disk_scratch_poke(unsigned char i, unsigned char v) {
    ext_disk_put((unsigned int)(DISK_EXT_DIR + i), v);
}
static unsigned char disk_dir_find(const char *name, unsigned char *st, unsigned char *ss);   /* s. unten */
enum {
    LISP65_DISK_STATUS_OK = 0,
    LISP65_DISK_STATUS_READ_INVALID = 6,
    LISP65_DISK_STATUS_WRITE_VERIFY_FAILED = 7,
    LISP65_DISK_STATUS_MEDIA_CHANGED = 12
};

#ifdef LISP65_F011_GUARD_ASM
extern unsigned char lisp65_f011_mount_token_op(unsigned char mode);
#define disk_transaction_mount_token_op lisp65_f011_mount_token_op
#else
static unsigned char disk_transaction_mount_token[5];
static unsigned char disk_transaction_mount_token_valid;
static __attribute__((noinline)) unsigned char disk_transaction_mount_token_op(unsigned char capture) {
    unsigned char i;
    if (capture) {
        for (i = 0; i < 5u; i++)
            disk_transaction_mount_token[i] =
                LISP65_F011_READ8((unsigned int)(LISP65_SD_REG_MOUNT_CONTROL + i));
        disk_transaction_mount_token_valid = 1;
    } else {
        if (!disk_transaction_mount_token_valid) return 0;
        for (i = 0; i < 5u; i++)
            if (LISP65_F011_READ8((unsigned int)(LISP65_SD_REG_MOUNT_CONTROL + i)) !=
                disk_transaction_mount_token[i]) return 0;
    }
    return 1;
}
#endif

void io_disk_transaction_capture_mount_token(void) {
    (void)disk_transaction_mount_token_op(1);
}

__attribute__((noinline)) unsigned char io_disk_transaction_classify_status(unsigned char status) {
    if (status == LISP65_DISK_STATUS_READ_INVALID &&
        !disk_transaction_mount_token_op(0))
        return LISP65_DISK_STATUS_MEDIA_CHANGED;
    return status;
}

#ifdef LISP65_F011_GUARD_ASM
extern unsigned char lisp65_f011_scratch_buffer(unsigned int off, unsigned char write);
#define f011_scratch_buffer lisp65_f011_scratch_buffer
#else
static __attribute__((noinline)) unsigned char f011_scratch_buffer(unsigned int off, unsigned char write) {
    unsigned int i;
    for (i = 0; i < 256; i++) {
        unsigned char value = ext_disk_get((unsigned int)(DISK_EXT_DIR + i));
        if (write)
            ((volatile unsigned char *)0xDE00)[off + i] = value;
        else if (((volatile unsigned char *)0xDE00)[off + i] != value)
            return 0;
    }
    return 1;
}
#endif

static __attribute__((noinline)) unsigned char f011_issue_write_guarded(
    unsigned char T, unsigned char S
) {
    unsigned char b, side, fsec;
    unsigned int g;
    b = (unsigned char)(S >> 1);
    side = (unsigned char)(b >= 10 ? 1 : 0);
    fsec = (unsigned char)((b >= 10 ? b - 10 : b) + 1);
    m65_io_enable();
    lisp65_f011_take_context();                               /* eigener Kontext auch fuer Write */
    *((volatile unsigned char *)0xD084) = (unsigned char)(T - 1);
    *((volatile unsigned char *)0xD085) = fsec;
    *((volatile unsigned char *)0xD086) = side;
    /* This is the final predicate before the trigger.  The product disassembly
     * gate cycle-counts the last D68F read through the D081 store. */
#ifdef LISP65_F011_GUARD_ASM
    if (!disk_transaction_mount_token_op(2))
        return LISP65_DISK_STATUS_MEDIA_CHANGED;
#else
    if (!disk_transaction_mount_token_op(0))
        return LISP65_DISK_STATUS_MEDIA_CHANGED;
    *((volatile unsigned char *)0xD081) = 0x84;               /* write sector (Variante A) */
#endif
    for (g = 0; g < 60000 && (*((volatile unsigned char *)0xD082) & 0x80); g++) {}   /* BUSY */
    if (!disk_transaction_mount_token_op(0))
        return LISP65_DISK_STATUS_MEDIA_CHANGED;
    return LISP65_DISK_STATUS_OK;
}

static unsigned char f011_write_at_guarded(unsigned char T, unsigned char S) {
    unsigned int off;
    if (!disk_transaction_mount_token_op(0))
        return LISP65_DISK_STATUS_MEDIA_CHANGED;
    off = f011_read_at(T, S);                                 /* RMW: Block holen, $DE00 aktiv */
    if (!disk_transaction_mount_token_op(0)) {
        lisp65_f011_unmap_buffer();
        return LISP65_DISK_STATUS_MEDIA_CHANGED;
    }
    (void)f011_scratch_buffer(off, 1);
    lisp65_f011_unmap_buffer();
    return f011_issue_write_guarded(T, S);
}
/* Tokengebundener Write. Verify per echtem Readback; jeder Eintritt in einen
 * weiteren F011-Schritt wird erneut vom Mount-Token bewacht. */
unsigned char io_disk_write_sector_guarded(unsigned char track, unsigned char sector) {
    unsigned int off;
    unsigned char status = f011_write_at_guarded(track, sector);
    if (status != LISP65_DISK_STATUS_OK) return status;
    off = f011_read_at(track, sector);
    if (!disk_transaction_mount_token_op(0)) {
        lisp65_f011_unmap_buffer();
        return LISP65_DISK_STATUS_MEDIA_CHANGED;
    }
    if (!f011_scratch_buffer(off, 0)) {
        lisp65_f011_unmap_buffer();
        return LISP65_DISK_STATUS_WRITE_VERIFY_FAILED;
    }
    lisp65_f011_unmap_buffer();
    return LISP65_DISK_STATUS_OK;
}

/* Historische 2-Argument-Naht: ihr Ergebnis bleibt t/nil. Sie bindet jeden
 * einzelnen Sektor intern an den bei Aufruf sichtbaren Mount-Token; M65D nutzt
 * dagegen den oben exponierten Transaktions-Token und kann Status 12 melden. */
unsigned char io_disk_write_sector(unsigned char track, unsigned char sector) {
    io_disk_transaction_capture_mount_token();
    return (unsigned char)(io_disk_write_sector_guarded(track, sector) ==
                           LISP65_DISK_STATUS_OK);
}

/* Quelltext-Byte i in den EXT-Datei-Puffer stellen (SAVE-Staging; 0 = Puffer-Deckel erreicht). */
unsigned char io_disk_stage_put(unsigned int i, unsigned char v) {
    if (i >= DISK_FILE_MAX) return 0;
    ext_disk_put((unsigned int)(DISK_EXT_FILE + i), v);
    return 1;
}

/* Nutz-Kapazitaet einer bestehenden Sektorkette: 254 B je Vollsektor + (Endmarke-1) im Endsektor. */
static unsigned int disk_chain_capacity(unsigned char t, unsigned char s) {
    unsigned int cap = 0, count, fuel = DISK_CHAIN_FUEL;
    unsigned char nt, ns;
    while (t && fuel--) {
        if (!io_disk_read_sector(t, s)) return 0;
        nt = io_disk_byte(0); ns = io_disk_byte(1);
        count = disk_chain_count(t, s, nt, ns);
        if (count > 254u) return 0;
        if (count > DISK_FILE_MAX - cap) return 0;
        cap += count;
        t = nt; s = ns;
    }
    return t ? 0 : cap;
}

/* SAVE (MVP Overwrite-in-place, docs/two-product-workflow.md Prio 1): schreibt len Bytes aus dem
 * EXT-Datei-Puffer in die BESTEHENDE Kette der Datei `name`. Die Kette wird NIE veraendert —
 * Links + Endmarke bleiben (Slot-Kapazitaet = die Dateigroesse bei Anlage, schrumpft nie);
 * ungenutzter Rest wird mit Leerzeichen gefuellt, das der Regel-B-(load) als Whitespace
 * ueberliest. Jeder Sektor geht durch den HW-kalibrierten io_disk_write_sector (RMW + Verify).
 * 0 = nicht gefunden / passt nicht in den Slot / Verify-Fehlschlag. */
static unsigned char io_disk_save_impl(const char *name, unsigned int base, unsigned int len) {
    unsigned char t, s, nt, ns;
    unsigned int fuel = DISK_CHAIN_FUEL;
    unsigned int n = 0, i, use;
    if (!disk_dir_find(name, &t, &s)) return 0;
    if (len > disk_chain_capacity(t, s)) return 0;
    while (t && fuel--) {
        if (!io_disk_read_sector(t, s)) return 0;       /* Links + Altinhalt in den Scratch (RMW) */
        nt = io_disk_byte(0); ns = io_disk_byte(1);
        use = disk_chain_count(t, s, nt, ns);
        if (use > 254u) return 0;
        for (i = 0; i < use; i++, n++)
            io_disk_scratch_poke((unsigned char)(2u + i),
                                 n < len ? ext_disk_get((unsigned int)(DISK_EXT_FILE + base + n)) : 32u);
        if (!io_disk_write_sector(t, s)) return 0;
        t = nt; s = ns;
    }
    return t == 0;
}
unsigned char io_disk_save_named(const char *name, unsigned int len) {
    return io_disk_save_impl(name, 0, len);
}
#ifdef LISP65_FASL
/* FASL-B2: Fasl-Ausgabe liegt HINTER der Quelle im Datei-Fenster -> base-Variante (binärsicher,
 * gleiche RMW+Verify-Kette wie save). NUR FASL-Diagnoseprofil; der Workbench-Slow-Path
 * (compile-string) legt die Ausgabe bei base=0 und nutzt %save-staged -> io_disk_save_named. */
unsigned char io_disk_save_range(const char *name, unsigned int base, unsigned int len) {
    if (base >= DISK_FILE_MAX || len > DISK_FILE_MAX - base) return 0;
    return io_disk_save_impl(name, base, len);
}
#endif
#endif /* MEGA65_F011_WRITE */

/* Datei-Stream: der Reader zieht Zeichen; wir liefern das naechste aus dem EXT-Datei-Puffer. */
static unsigned int disk_file_len = 0, disk_file_pos = 0;
static char disk_file_fetch(void) {
    if (disk_file_pos >= disk_file_len) return '\0';
    return (char)ext_disk_get((unsigned int)(DISK_EXT_FILE + disk_file_pos++));
}

/* Source loads and L65M staging must not share a lifetime.  In the dialect-v2
 * product every top-level source form is evaluated through lcc-run; C1 may
 * therefore replace DISK_EXT_FILE with the compiler container between two
 * reader fetches.  Keep the source stream in the disjoint 256-byte directory
 * scratch instead.  The two-byte reader lookahead and the current sector stay
 * valid while C1 owns the file window; the next sector is fetched only when
 * the reader asks for it. */
static unsigned char disk_source_pos, disk_source_len;
static LISP65_RESIDENT_ISLAND_FN char disk_source_fetch(void) {
    unsigned char nt, ns;
    if (disk_file_pos >= disk_file_len) return '\0';
    if (disk_source_pos >= disk_source_len) {
        nt = io_disk_byte(0); ns = io_disk_byte(1);
        if (!nt || !io_disk_read_sector(nt, ns)) return '\0';
        nt = io_disk_byte(0); ns = io_disk_byte(1);
        if (!nt && !ns) return '\0';
        disk_source_pos = 0;
        disk_source_len = nt ? 254u : (unsigned char)(ns - 1u);
    }
    ++disk_file_pos;
    return (char)io_disk_byte((unsigned char)(2u + disk_source_pos++));
}

/* Folgt der 1581-Sektorkette ab (T,S) und akkumuliert die Datenbytes DIREKT aus $DE00 in den
 * EXT-Datei-Puffer (kein Bank-0-Puffer). Rueckgabe = Anzahl akkumulierter Bytes (0 = leer). */
static unsigned int disk_chain_to_scratch(unsigned char track, unsigned char sector) {
    unsigned int n = 0, off, i, cnt, remaining;
    unsigned char t = track, s = sector, nt, ns;
    while (t) {
        off = f011_read_at(t, s);
        nt = ((volatile unsigned char *)0xDE00)[off];
        ns = ((volatile unsigned char *)0xDE00)[off + 1];
        if ((!nt && !ns) ||
            (nt && (nt > 80u || ns > 39u || (nt == t && ns == s)))) {
            lisp65_f011_unmap_buffer();
            return 0;
        }
        cnt = nt ? 254u : (unsigned int)(ns - 1u);
        remaining = (unsigned int)(DISK_FILE_MAX - n);
        if (cnt > remaining) {
            lisp65_f011_unmap_buffer();
            return 0;
        }
        for (i = 0; i < cnt; i++)
            ext_disk_put((unsigned int)(DISK_EXT_FILE + n++), ((volatile unsigned char *)0xDE00)[off + 2 + i]);
        lisp65_f011_unmap_buffer();
        t = nt; s = ns;
    }
    return n;
}

/* %disk-load-file: Datei ab (T,S) in den EXT-Puffer folgen, dann via load_source_stream in den
 * Reader streamen (Quelltext-LOAD). 1=ok, 0=leer. */
unsigned char io_disk_load_chain(unsigned char track, unsigned char sector) {
    unsigned char nt, ns;
    unsigned int n = disk_chain_to_scratch(track, sector);
    if (!n) return 0;
    disk_file_len = n; disk_file_pos = 0;
    if (!io_disk_read_sector(track, sector)) return 0;
    nt = io_disk_byte(0); ns = io_disk_byte(1);
    disk_source_pos = 0;
    disk_source_len = nt ? 254u : (unsigned char)(ns - 1u);
    load_source_stream(disk_source_fetch);
    return 1;
}

/* Boot-Ladeanzeige (S5): wie weit hat der Reader die Disk-Quelle konsumiert, in Promille (0..1000).
 * disk_file_pos/_len sind der EXT-Datei-Puffer-Fortschritt -> exakter Balken beim Boot-Kompilieren. */
unsigned int io_disk_load_permille(void) {
    return disk_file_len ? (unsigned int)((unsigned long)disk_file_pos * 1000ul / disk_file_len) : 1000u;
}

/* Test-/Boot-Naht (S5): eine bereits in DISK_EXT_FILE gestagete Quelle (len Bytes) kompilieren --
 * ohne F011-Read (xemu-Proof stagt per Monitor; das Geraet nutzt io_disk_load_chain mit echtem Disk). */
unsigned char io_disk_load_staged(unsigned int len) {
    if (!len) return 0;
    disk_file_len = len; disk_file_pos = 0;
    load_source_stream(disk_file_fetch);
    return 1;
}

#if defined(MEGA65_F011_WRITE) && defined(LISP65_FASL)
/* FASL-B2: Quelle stagen (Deckel 0x2000 — Rest des Fixnum-Fensters = Fasl-Ausgabe + Staging,
 * s. lib/lcc-fasl.lisp) und den Stream-Reader auf den Anfang setzen; compile-file liest
 * dann via %fasl-read-form Form fuer Form OHNE Auswertung. Bytes oder 0. */
unsigned int io_fasl_open_source(const char *name) {
    unsigned char t, s;
    unsigned int n;
    if (!disk_dir_find(name, &t, &s)) return 0;
    n = disk_chain_to_scratch(t, s);
    if (!n || n >= 0x2000u) return 0;   /* zu gross: Fixnum-Fenster — Quelle max 8 KB (lcc-fasl-Layout) */
    disk_file_len = n; disk_file_pos = 0;
    reader_from_fetch(disk_file_fetch);
    return n;
}
unsigned char io_fasl_find(const char *name, unsigned char *t, unsigned char *s) {
    return disk_dir_find(name, t, s);
}
#endif

/* Namens-Faltung wie stdlib-load.lisp (%load-fold-code): high-bit weg (0xA0-Padding -> Space),
 * Kleinbuchstaben -> Gross (case-insensitiver 1581-Namensvergleich). */
static unsigned char disk_fold(unsigned char c) {
    if (c > 127) c = (unsigned char)(c - 128);
    if (c >= 97 && c <= 122) c = (unsigned char)(c - 32);
    return c;
}
/* S5-Boot-Dir-Lookup (C-Port von stdlib-load.lisp fuer den Boot, da die Stdlib noch nicht geladen ist):
 * die 1581-Directory ab Track 40 nach `name` durchsuchen (32-B-Eintraege, Name @+5..+20 gefaltet,
 * Start-(track,sektor) @+3/+4), gefunden -> io_disk_load_chain (laedt + kompiliert). fuel begrenzt die
 * Sektorkette (Kettenende per next-track==0, NICHT Truthiness). 1=gefunden+geladen, 0=nicht gefunden. */
/* 1581-Dir-Walk (Track 40): findet den Eintrag zu `name` (gefaltet, wie beim Load) und liefert
 * Start-Track/-Sektor der Datei. Aus io_disk_load_named extrahiert — geteilt mit dem SAVE-Pfad. */
static unsigned char disk_dir_find(const char *name, unsigned char *st, unsigned char *ss) {
    unsigned char track = 40, sector = 0, fuel = 64;
    while (fuel--) {
        unsigned int e; unsigned char nt, ns;
        if (!io_disk_read_sector(track, sector)) return 0;
        for (e = 0; e < 8u; e++) {
            unsigned int base = e * 32u, i; unsigned char match = 1, ended = 0;
            if ((io_disk_byte((unsigned char)(base + 2)) & 7u) == 0) continue;   /* Eintrag frei */
            for (i = 0; i < 16u; i++) {
                unsigned char nc;
                if (!ended && name[i] == '\0') ended = 1;
                nc = ended ? 32u : disk_fold((unsigned char)name[i]);
                if (disk_fold(io_disk_byte((unsigned char)(base + 5u + i))) != nc) { match = 0; break; }
            }
            if (match) {
                *st = io_disk_byte((unsigned char)(base + 3));
                *ss = io_disk_byte((unsigned char)(base + 4));
                return 1;
            }
        }
        nt = io_disk_byte(0); ns = io_disk_byte(1);
        if (nt == 0) return 0;
        if (nt != 40u || ns >= 40u || (nt == track && ns == sector)) return 0;
        track = nt; sector = ns;
    }
    return 0;
}

unsigned char io_disk_load_named(const char *name) {
    unsigned char t, s;
    if (!disk_dir_find(name, &t, &s)) return 0;
    return io_disk_load_chain(t, s);
}

#ifdef LISP65_DISK_LIBS
/* %disk-load-lib: der komplette Container bleibt bis zum Ruecklauf im EXT-Scratch. Preflight
 * liest Blob+Trailer dort ohne Mutation; danach wird nur das Blob nach Bank 5 gestagt. Der Commit
 * liest denselben Trailer aus Scratch, registriert und patcht das gestagte Blob. */
/* Lib-Registrierung ab BEREITS GESTAGETER Datei (n Bytes im EXT-Fenster): Prefix parsen,
 * Preflight, Bank-5-Stage, Trailer registrieren. Geteilt von io_disk_load_lib und der
 * Test-Naht %lib-staged (xemu kann kein F011 — der Monitor stagt die Lib direkt in Bank 4). */
/* C1 reuses this already-resident preflight record as its transaction
 * checkpoint.  source.ctx is normally unused by both readers; while the
 * temporary compiler is active it carries the pre-existing export symbol.
 * Reset clears both objects, so no stale compiler lifetime can cross reset. */
l65m_plan lisp65_disk_lib_plan;
l65m_source lisp65_disk_lib_source;
static l65m_status disk_lib_last_status = L65M_OK;
static uint8_t disk_lib_read(void *ctx, uint16_t off, uint8_t *dst, uint16_t len) {
    (void)ctx;
    ext_disk_read((uint16_t)(DISK_EXT_FILE + off), dst, len);
    return 1;
}
l65m_status io_disk_lib_status(void) { return disk_lib_last_status; }
unsigned char io_disk_lib_staged(unsigned int n) {
    if (n > DISK_FILE_MAX) { disk_lib_last_status = L65M_ERR_CONTAINER; return 0; }
    lisp65_disk_lib_source.read = disk_lib_read;
    lisp65_disk_lib_source.length = (uint16_t)n;
    disk_lib_last_status = vm_preflight_lib_ext(
        &lisp65_disk_lib_source, &lisp65_disk_lib_plan);
    if (disk_lib_last_status != L65M_OK) return 0;
    lisp65_disk_lib_source.length = lisp65_disk_lib_plan.source_length;
    ext_disk_stage((uint16_t)(DISK_EXT_FILE + lisp65_disk_lib_plan.source_blob_off),
                   lisp65_stdlib_bank, lisp65_disk_lib_plan.code_base,
                   lisp65_disk_lib_plan.blob_len);
    /* vm_load_lib_ext reserves the verified staged blob before any publish step.
     * On a later fail-stop error the region remains owned, so partial entries
     * can never point into storage reused by a subsequent load. */
    disk_lib_last_status = vm_load_lib_ext(
        &lisp65_disk_lib_source, &lisp65_disk_lib_plan);
    return disk_lib_last_status == L65M_OK;
}
unsigned char io_disk_load_lib(unsigned char track, unsigned char sector) {
    unsigned char loaded;
    /* Private synchronous grant: this reader ignores ctx, while phase 0 may
     * frame one exact container inside the reusable disk allocation chain. */
    lisp65_disk_lib_source.ctx = (void *)1;
    loaded = io_disk_lib_staged(disk_chain_to_scratch(track, sector));
    lisp65_disk_lib_source.ctx = 0;
    return loaded;
}

#ifdef LISP65_ATTIC_LIBRARY_SHELF_RESIDENT_PROBE
/* Rejected 1.1-A price probe. The production implementation lives in the
 * profile-bound runtime-overlay slice; keeping this code behind an explicit
 * probe macro makes the measured 1,866-byte resident alternative reproducible. */
static uint16_t attic_lib_off;
static uint8_t attic_crc_buf[16];

#ifdef __MEGA65__
/* Enhanced DMA is required here: the shelf lives above the 24-bit Bank-5
 * address space. One shared descriptor handles both Attic reads and the final
 * Attic-to-Bank-5 blob stage. */
__attribute__((used)) static uint8_t attic_edma_job[20] = {
    0x0b, 0x80, 0x81, 0x81, 0x00, 0x85, 0x01, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00
};

static void attic_copy(uint32_t source, uint32_t target, uint16_t length) {
    attic_edma_job[2] = (uint8_t)(source >> 20);
    attic_edma_job[4] = (uint8_t)(target >> 20);
    attic_edma_job[9] = (uint8_t)length;
    attic_edma_job[10] = (uint8_t)(length >> 8);
    attic_edma_job[11] = (uint8_t)source;
    attic_edma_job[12] = (uint8_t)(source >> 8);
    attic_edma_job[13] = (uint8_t)((source >> 16) & 0x0fu);
    attic_edma_job[14] = (uint8_t)target;
    attic_edma_job[15] = (uint8_t)(target >> 8);
    attic_edma_job[16] = (uint8_t)((target >> 16) & 0x0fu);
    __asm__ volatile(
        "lda #1\n\tsta $d703\n\tlda #0\n\tsta $d702\n\tsta $d704\n\t"
        "lda #mos16hi(attic_edma_job)\n\tsta $d701\n\t"
        "lda #mos16lo(attic_edma_job)\n\tsta $d705\n\t"
        ::: "a", "memory");
}
#else
/* Host-only seam for the focused shelf loader test. Product builds use EDMA. */
static const uint8_t *attic_host_bytes;
static uint16_t attic_host_length;
void io_attic_shelf_host_bind(const uint8_t *bytes, uint16_t length) {
    attic_host_bytes = bytes; attic_host_length = length;
}
static void attic_copy(uint32_t source, uint32_t target, uint16_t length) {
    uint16_t off = (uint16_t)(source - L65S_ATTIC_BASE), i;
    uint8_t *dst = (uint8_t *)(uintptr_t)target;
    if (!attic_host_bytes || (uint32_t)off + length > attic_host_length) return;
    for (i = 0; i < length; i++) dst[i] = attic_host_bytes[(uint16_t)(off + i)];
}
#endif

static void attic_read_at(uint16_t off, uint8_t *dst, uint16_t length) {
    attic_copy(L65S_ATTIC_BASE + off, (uint32_t)(uintptr_t)dst, length);
}

static uint8_t attic_lib_read(void *ctx, uint16_t off, uint8_t *dst, uint16_t len) {
    (void)ctx;
    attic_read_at((uint16_t)(attic_lib_off + off), dst, len);
    return 1;
}

static uint8_t attic_u8(uint16_t off) {
    attic_read_at(off, attic_crc_buf, 1);
    return attic_crc_buf[0];
}

static uint16_t attic_u16(uint16_t off) {
    attic_read_at(off, attic_crc_buf, 2);
    return (uint16_t)attic_crc_buf[0] | ((uint16_t)attic_crc_buf[1] << 8);
}

static uint32_t attic_u32(uint16_t off) {
    attic_read_at(off, attic_crc_buf, 4);
    return (uint32_t)attic_crc_buf[0] | ((uint32_t)attic_crc_buf[1] << 8)
        | ((uint32_t)attic_crc_buf[2] << 16) | ((uint32_t)attic_crc_buf[3] << 24);
}

static uint32_t attic_crc32_step(uint32_t crc, uint8_t value) {
    uint8_t bit;
    crc ^= value;
    for (bit = 0; bit < 8; bit++)
        crc = (crc >> 1) ^ (0xedb88320ul & (uint32_t)-(int32_t)(crc & 1u));
    return crc;
}

static uint32_t attic_crc32(uint16_t off, uint16_t length) {
    uint32_t crc = 0xfffffffful;
    uint16_t chunk, index;
    while (length) {
        chunk = length > sizeof attic_crc_buf ? sizeof attic_crc_buf : length;
        attic_read_at(off, attic_crc_buf, chunk);
        for (index = 0; index < chunk; index++)
            crc = attic_crc32_step(crc, attic_crc_buf[index]);
        off = (uint16_t)(off + chunk); length = (uint16_t)(length - chunk);
    }
    return crc ^ 0xfffffffful;
}

static uint8_t attic_name_equal(uint16_t record, const char *name) {
    uint8_t index, expected, actual;
    for (index = 0; index < 8; index++) {
        expected = (uint8_t)name[index]; actual = attic_u8((uint16_t)(record + index));
        if (actual != expected) return 0;
        if (!actual) return 1;
    }
    return 0;
}

unsigned char io_attic_load_lib(const char *name) {
    uint8_t index;
    uint16_t record, total, off, length;
    uint32_t expected_crc;
    if (!name || !name[0] || name[7]) return 0;
    if (attic_u8(0) != L65S_MAGIC_0 || attic_u8(1) != L65S_MAGIC_1
        || attic_u8(2) != L65S_MAGIC_2 || attic_u8(3) != L65S_MAGIC_3
        || attic_u8(4) != L65S_VERSION || attic_u8(5) != L65S_HEADER_BYTES
        || attic_u8(6) != L65S_RECORD_BYTES || attic_u8(7) != L65S_RECORDS
        || attic_u16(8) != L65S_HEADER_BYTES || attic_u16(10) != L65S_PAYLOAD_OFF) {
        disk_lib_last_status = L65M_ERR_SOURCE; return 0;
    }
    total = (uint16_t)attic_u32(12);
    if (total < L65S_PAYLOAD_OFF
        || attic_crc32(L65S_HEADER_BYTES,
                       (uint16_t)(L65S_RECORD_BYTES * L65S_RECORDS)) != attic_u32(20)) {
        disk_lib_last_status = L65M_ERR_SOURCE; return 0;
    }
    record = L65S_HEADER_BYTES;
    for (index = 0; index < L65S_RECORDS; index++, record += L65S_RECORD_BYTES)
        if (attic_name_equal(record, name)) break;
    if (index == L65S_RECORDS) { disk_lib_last_status = L65M_ERR_SOURCE; return 0; }
    off = attic_u16((uint16_t)(record + 8));
    length = attic_u16((uint16_t)(record + 10));
    expected_crc = attic_u32((uint16_t)(record + 12));
    if (off < L65S_PAYLOAD_OFF || length < 4u || (uint32_t)off + length > total
        || attic_crc32(off, length) != expected_crc) {
        disk_lib_last_status = L65M_ERR_SOURCE; return 0;
    }
    attic_lib_off = off;
    lisp65_disk_lib_source.read = attic_lib_read;
    lisp65_disk_lib_source.length = length;
    disk_lib_last_status = vm_preflight_lib_ext(
        &lisp65_disk_lib_source, &lisp65_disk_lib_plan);
    if (disk_lib_last_status != L65M_OK) return 0;
    attic_copy(L65S_ATTIC_BASE + off + lisp65_disk_lib_plan.source_blob_off,
               ((uint32_t)lisp65_stdlib_bank << 16)
                   + lisp65_disk_lib_plan.code_base,
               lisp65_disk_lib_plan.blob_len);
    disk_lib_last_status = vm_load_lib_ext(
        &lisp65_disk_lib_source, &lisp65_disk_lib_plan);
    return disk_lib_last_status == L65M_OK;
}
#endif
#endif
/* F011-Build: `(load)` ist jetzt Bytecode-Lisp (nutzt %disk-read-sector/-byte/-load-file); der
 * alte C-1581-Dir-Walk ist RAUS (Regel-B-Redesign, spart ~816 B .text). io_load_file bleibt nur
 * als abort-sicherer Stub fuer die C-P_LOAD-Naht — die Lisp-(load) aus dem Stdlib-Blob
 * ueberschreibt die Funktionszelle ohnehin. */
const char *io_load_file(const char *name) { (void)name; return 0; }
#elif defined(MEGA65_HYPPO_LOAD)
const char *io_load_file(const char *name) {
    /* page-aligned, NUL-terminiert: hyppo liest den Namen ab der Page-Basis */
    static char namebuf[64] __attribute__((aligned(256)));
    unsigned int fa;
    unsigned char len = 0, ok, fd, cnt_lo, cnt_hi, rc;
    unsigned int n = 0, got, i;
    while (name[len] && len < sizeof(namebuf) - 1) { namebuf[len] = name[len]; len++; }
    namebuf[len] = '\0';
    fa = (unsigned int)namebuf;

    __asm__ volatile("ldx #0\n\t lda #$06\n\t sta $d640\n\t nop\n\t lda #0\n\t rol\n\t sta %0\n\t" /* selectdrive 0 */
        : "=m"(ok) :: "a","x");
    if (!ok) return 0;                                                              /* keine Disk ausgewählt */
    __asm__ volatile("lda #$3c\n\t sta $d640\n\t nop\n\t lda #0\n\t rol\n\t sta %0\n\t"            /* cdrootdir */
        : "=m"(ok) :: "a");
    if (!ok) return 0;
    __asm__ volatile("ldz %2\n\t ldx %0\n\t ldy %1\n\t lda #$2e\n\t sta $d640\n\t nop\n\t"   /* setname */
        :: "r"((unsigned char)(fa & 0xff)), "r"((unsigned char)(fa >> 8)), "r"(len) : "a","x","y");
    __asm__ volatile("lda #$30\n\t sta $d640\n\t nop\n\t lda #0\n\t rol\n\t sta %0\n\t"      /* findfirst */
        : "=m"(ok) :: "a");
    if (!ok) return 0;
    __asm__ volatile("lda #$18\n\t sta $d640\n\t nop\n\t sta %0\n\t lda #0\n\t rol\n\t sta %1\n\t" /* openfile -> A=fd */
        : "=m"(fd), "=m"(ok) :: "a");
    if (!ok) return 0;
    for (;;) {                                                                      /* readfile-Schleife */
        __asm__ volatile("ldx %3\n\t lda #$1a\n\t sta $d640\n\t nop\n\t stx %0\n\t sty %1\n\t lda #0\n\t rol\n\t sta %2\n\t"
            : "=m"(cnt_lo), "=m"(cnt_hi), "=m"(rc) : "m"(fd) : "a","x","y");
        got = (unsigned int)cnt_lo | ((unsigned int)cnt_hi << 8);                   /* gelesene Bytes (@ $DE00) */
        for (i = 0; i < got && n < IO_BUF_MAX - 1; i++)
            io_buf[n++] = (char)((volatile unsigned char *)0xDE00)[i];
        if (!rc || got == 0) break;                                                /* Carry clear = EOF */
    }
    __asm__ volatile("ldx %0\n\t lda #$20\n\t sta $d640\n\t nop\n\t" :: "m"(fd) : "a","x"); /* closefile */
    io_buf[n] = '\0';
    return n ? io_buf : 0;
}
#else
/* Default: sauberer Fehler statt Absturz, bis hyppo-Pfad bestätigt. io_buf NICHT
 * referenzieren — die (void)-Referenz hielt 512 B toten .bss im MVP am Leben
 * (LTO kann unreferenzierte Statics eliminieren, referenzierte nicht). */
const char *io_load_file(const char *name) { (void)name; return 0; }
#endif

#elif defined(__C64__) || defined(__CBM__)
#include <cbm.h>
/* Gerät: sequentielle Datei über KERNAL lesen. <name> -> "NAME,S,R", Gerät 8, LFN 2.
 * CBM-Dateinamen sind GROSS -> a-z hochcasen. */
const char *io_load_file(const char *name) {
    char petname[24];
    unsigned char i = 0, st;
    unsigned int n = 0;

    while (name[i] && i < 16) {
        char c = name[i];
        if (c >= 'a' && c <= 'z') c = (char)(c - 0x20);
        petname[i] = c; i++;
    }
    petname[i++] = ','; petname[i++] = 'S';
    petname[i++] = ','; petname[i++] = 'R';
    petname[i]   = '\0';

    cbm_k_setnam(petname);
    cbm_k_setlfs(2, 8, 2);
    if (cbm_k_open()) return 0;                       /* Open fehlgeschlagen */
    if (cbm_k_chkin(2)) { cbm_k_close(2); cbm_k_clrch(); return 0; }

    for (;;) {
        unsigned char ch = cbm_k_basin();
        st = cbm_k_readst();
        if (st & ~0x40) {                            /* echter Fehler (nicht nur EOF) */
            cbm_k_close(2); cbm_k_clrch();
            return 0;
        }
        if (n < IO_BUF_MAX - 1) io_buf[n++] = (char)ch;
        if (st & 0x40) break;                        /* EOF: letztes Byte ist gültig */
    }
    cbm_k_close(2);
    cbm_k_clrch();
    io_buf[n] = '\0';
    return io_buf;
}
#else
#include <stdio.h>
const char *io_load_file(const char *name) {
    FILE *f = fopen(name, "rb");
    size_t n;
    if (!f) return 0;
    n = fread(io_buf, 1, IO_BUF_MAX - 1, f);
    fclose(f);
    io_buf[n] = '\0';
    return io_buf;
}
#endif
