/* lisp65 — file input seam (lane K)
 * Platform backend for `load`: opens a source file and returns its content as a
 * NUL-terminated string. Keeps load_source platform-independent.
 */
#ifndef LISP65_IO_H
#define LISP65_IO_H

/* Reads the whole file <name> into an internal NUL-terminated buffer and returns it,
 * or NULL on error (open/read). The buffer size IO_BUF_MAX bounds the file size.
 * NOT reentrant (one static buffer) -> no nested load. */
const char *io_load_file(const char *name);

/* Rule-B disk primitives (MEGA65_F011_LOAD only; see docs/load-rule-b-design.md). Bytecode Lisp
 * drives the 1581 logic through these; io.c holds only the F011 read plus one bank-0 buffer. */
unsigned char io_disk_read_sector(unsigned char track, unsigned char sector);
unsigned char io_disk_byte(unsigned char i);
/* D68B..D68F remains a private token of the guarded write capability. */
/* Datei ab (track,sektor) folgen, in EXT akkumulieren und via load_source_stream auswerten. 1=ok. */
unsigned char io_disk_load_chain(unsigned char track, unsigned char sector);
/* C2 persistent-code seam: follow one 1581 chain into the canonical EXT
 * staging window without interpreting or publishing it.  The sole C2
 * decoder owns validation and the commit marker after this call. */
#ifdef LISP65_C2_PRODUCT_CUT
unsigned int io_disk_stage_chain(unsigned char track, unsigned char sector);
#endif
/* Boot progress (S5): the reader's progress through the disk source, in per mille (0..1000). */
unsigned int io_disk_load_permille(void);
/* Compile a source already staged into DISK_EXT_FILE (len bytes) (test/boot without an F011 read). */
unsigned char io_disk_load_staged(unsigned int len);
/* S5 boot: search the 1581 directory (from track 40) for `name`, then load and compile it
 * (the C-side directory lookup). 1=found and loaded, 0=not found. */
unsigned char io_disk_load_named(const char *name);

#ifdef LISP65_DISK_LIBS
#include "l65m_validate.h"
/* Stufe 2: eine Bytecode-Lib ab (track,sektor) laden — nach Bank 5 stagen + vm_load_lib_ext. 1=ok. */
unsigned char io_disk_load_lib(unsigned char track, unsigned char sector);
#ifdef LISP65_ATTIC_LIBRARY_SHELF
#include "obj.h"
/* Load a verified L65M container from the reset-persistent 1.1 Attic shelf. */
unsigned char io_attic_load_lib(obj name);
#endif
/* Library registration from an already staged file (test seam: xemu has no F011). */
unsigned char io_disk_lib_staged(unsigned int n);
l65m_status io_disk_lib_status(void);       /* the last stable L65M status */
#ifdef LISP65_C1_COMPILER_TIER
/* Private C1 lifetime binding. No new resident record: the temporary compiler
 * consumes the exact preflight plan of the most recent shelf load. */
extern l65m_plan lisp65_disk_lib_plan;
extern l65m_source lisp65_disk_lib_source;
#endif
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
/* SAVE file level (MVP overwrite-in-place): stage the source text byte by byte into the EXT file
 * buffer (0 = cap), then write it to the EXISTING file `name` (chain and end marker stay, the
 * remainder is space padding; every sector RMW + verify). 1 = fully verified on disk. */
unsigned char io_disk_stage_put(unsigned int i, unsigned char v);
unsigned char io_disk_save_named(const char *name, unsigned int len);
#ifdef LISP65_FASL
/* FASL-B2 (docs/device-fasl-design.md): write the file-window range [base..base+len) of the
 * EXT buffer to the EXISTING file (overwrite-in-place, as save does). FASL only; the workbench
 * (compile-string) uses io_disk_save_named (base=0) via %save-staged. */
unsigned char io_disk_save_range(const char *name, unsigned int base, unsigned int len);
/* Stage the source `name` into the file buffer (cap 0x2000 — the rest of the fixnum window belongs
 * to the FASL output, see lib/lcc-fasl.lisp) and initialise the stream reader. Bytes or 0. */
unsigned int  io_fasl_open_source(const char *name);
/* Directory lookup export (the B3 selftest loads the FASL from the C side: find +
 * io_disk_load_lib — the Lisp load-lib chain does not (yet) fit the FASL profile's
 * symbol budget). */
unsigned char io_fasl_find(const char *name, unsigned char *t, unsigned char *s);
#endif
#endif

#endif /* LISP65_IO_H */
