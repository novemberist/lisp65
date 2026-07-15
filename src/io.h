/* lisp65 — Datei-Eingabe-Naht (Lane K)
 * Plattform-Backend für `load`: öffnet eine Quelldatei und liefert ihren Inhalt als
 * NUL-terminierten String. Hält load_source plattformunabhängig.
 */
#ifndef LISP65_IO_H
#define LISP65_IO_H

/* Liest die ganze Datei <name> in einen internen NUL-terminierten Puffer und gibt ihn
 * zurück, oder NULL bei Fehler (Open/Read). Die Puffergröße IO_BUF_MAX begrenzt die
 * Dateigröße. NICHT reentrant (ein statischer Puffer) -> kein verschachteltes load. */
const char *io_load_file(const char *name);

/* Regel-B-Disk-Primitive (nur MEGA65_F011_LOAD; s. docs/load-rule-b-design.md). Bytecode-Lisp
 * treibt die 1581-Logik ueber diese; io.c haelt nur F011-Read + einen Bank-0-Puffer. */
unsigned char io_disk_read_sector(unsigned char track, unsigned char sector);
unsigned char io_disk_byte(unsigned char i);
/* D68B..D68F remains a private token of the guarded write capability. */
/* Datei ab (track,sektor) folgen, in EXT akkumulieren und via load_source_stream auswerten. 1=ok. */
unsigned char io_disk_load_chain(unsigned char track, unsigned char sector);
/* Boot-Ladeanzeige (S5): Reader-Fortschritt durch die Disk-Quelle in Promille (0..1000). */
unsigned int io_disk_load_permille(void);
/* Eine bereits nach DISK_EXT_FILE gestagete Quelle (len Bytes) kompilieren (Test/Boot ohne F011-Read). */
unsigned char io_disk_load_staged(unsigned int len);
/* S5-Boot: 1581-Directory (ab Track 40) nach `name` durchsuchen + laden+kompilieren (C-Dir-Lookup).
 * 1=gefunden+geladen, 0=nicht gefunden. */
unsigned char io_disk_load_named(const char *name);

#ifdef LISP65_DISK_LIBS
#include "l65m_validate.h"
/* Stufe 2: eine Bytecode-Lib ab (track,sektor) laden — nach Bank 5 stagen + vm_load_lib_ext. 1=ok. */
unsigned char io_disk_load_lib(unsigned char track, unsigned char sector);
/* Lib-Registrierung ab bereits gestageter Datei (Test-Naht: xemu ohne F011). */
unsigned char io_disk_lib_staged(unsigned int n);
l65m_status io_disk_lib_status(void);       /* letzter stabile L65M-Status */
#endif

#ifdef MEGA65_F011_WRITE
#ifndef MEGA65_F011_LOAD
#error "MEGA65_F011_WRITE braucht MEGA65_F011_LOAD (F011-Lese-Infrastruktur + EXT-Scratch)"
#endif
/* SAVE-Kern (Prio 1, docs/two-product-workflow.md): Byte in den EXT-Dir-Scratch stellen;
 * Scratch als CBM-Logiksektor (T,S) schreiben (Read-Modify-Write + Readback-Verify;
 * 1 = bitgenau auf Disk gelandet, 0 = Fehlversuch — nie stille Korruption). */
void io_disk_scratch_poke(unsigned char i, unsigned char v);
unsigned char io_disk_write_sector(unsigned char track, unsigned char sector);
/* Transaction-bound variant. Capture stores exact D68B..D68F in five Bank-0
 * bytes; every guarded write returns stable persistence status 0, 7 or 12. */
void io_disk_transaction_capture_mount_token(void);
unsigned char io_disk_transaction_classify_status(unsigned char status);
unsigned char io_disk_write_sector_guarded(unsigned char track, unsigned char sector);
/* SAVE-Datei-Ebene (MVP Overwrite-in-place): Quelltext byteweise in den EXT-Datei-Puffer
 * stagen (0 = Deckel), dann als BESTEHENDE Datei `name` schreiben (Kette/Endmarke bleiben,
 * Rest = Leerzeichen-Padding; jeder Sektor RMW + Verify). 1 = komplett verifiziert auf Disk. */
unsigned char io_disk_stage_put(unsigned int i, unsigned char v);
unsigned char io_disk_save_named(const char *name, unsigned int len);
#ifdef LISP65_FASL
/* FASL-B2 (docs/device-fasl-design.md): Datei-Fenster-Bereich [base..base+len) des
 * EXT-Puffers als BESTEHENDE Datei schreiben (Overwrite-in-place wie save). FASL-only;
 * Workbench (compile-string) nutzt io_disk_save_named (base=0) via %save-staged. */
unsigned char io_disk_save_range(const char *name, unsigned int base, unsigned int len);
/* Quelle `name` in den Datei-Puffer stagen (Deckel 0x2000 — der Rest des Fixnum-Fensters gehoert der
 * Fasl-Ausgabe, s. lib/lcc-fasl.lisp) + Stream-Reader initialisieren. Bytes oder 0. */
unsigned int  io_fasl_open_source(const char *name);
/* Dir-Lookup-Export (B3-Selftest laedt die Fasl C-seitig: find + io_disk_load_lib —
 * die Lisp-load-lib-Kette passt (noch) nicht ins Symbol-Budget des fasl-Profils). */
unsigned char io_fasl_find(const char *name, unsigned char *t, unsigned char *s);
#endif
#endif

#endif /* LISP65_IO_H */
