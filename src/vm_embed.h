/* lisp65 — Boot-Loader fuer die eingebettete Bytecode-Stdlib (K3-B, Runtime-Seite / Lane K).
 * Vertrag mit Codex' Embed-Artefakt: docs/bytecode-embed-loader.md. Gegatet -DLISP65_VM. */
#ifndef LISP65_VM_EMBED_H
#define LISP65_VM_EMBED_H
#ifdef LISP65_VM

#include "obj.h"
#include "l65m_validate.h"
#include "vm_registry.h"

/* --- Artefakt (vom Build erzeugt: `embed_gen.{h,c}`). Diese Symbole MUSS Codex' Emitter liefern.
 *     Die Code-Objekte liegen konkateniert im Blob (hot, im PRG); `bank/off` = ihr Ziel im erw. RAM. --- */
extern const uint8_t  lisp65_stdlib_blob[];     /* konkatenierte Code-Objekte             */
extern const uint16_t lisp65_stdlib_blob_len;   /* Blob-Laenge in Bytes                    */
extern const uint8_t  lisp65_stdlib_bank;       /* Ziel-Bank im erw. RAM (z.B. 5)          */
extern const uint16_t lisp65_stdlib_off;        /* Ziel-Offset im erw. RAM (z.B. 0)        */
extern const vm_embed_entry lisp65_embed[];     /* je Entry: {name, bank, flags, off, len} */
extern const uint16_t lisp65_embed_count;

/* Plattform-Naht: Blob (hot) ins erweiterte RAM schreiben. mega65: F018-Bulk-DMA (siehe
 * LISP65_EMBED_DMA); Host-Test: memcpy in ein simuliertes erw.-RAM. Spiegelbild zu vm_code_load.
 * Typen exakt wie vm.h (uint16_t = auf llvm-mos 16-bit unsigned int, != unsigned short!). */
void vm_ext_write(const uint8_t *src, uint16_t len, uint8_t bank, uint16_t off);

/* Bank-5-Code-Append-Allokator (GEMEINSAM fuer Disk-Libs + Compiled-Fn-Region; S0 in
 * docs/bank0-full-suite-strategy.md): Platz hinter dem residenten Stdlib-Blob; nach dem Boot
 * wird der L65M-Trailer freigegeben. Obergrenze ist der Namepool-Deckel @0x8000. persist=0 =
 * transient (Zeiger bleibt stehen). Rueckgabe: Offset in der Code-Bank, 0xFFFF = Region voll. */
uint16_t vm_ext_code_alloc(uint16_t len, uint8_t persist);
uint8_t  vm_ext_code_preview(uint16_t len, uint16_t *base);    /* read-only reservation check */
uint16_t vm_ext_code_watermark(void);                          /* read-only current append point */
#ifdef LISP65_C1_COMPILER_TIER
uint8_t  vm_ext_code_truncate(uint16_t watermark);             /* C1-only checked LIFO rollback */
#ifdef LISP65_C1_LEASE_ALLOC_GUARD
void     vm_ext_code_lease_begin(void);
uint8_t  vm_ext_code_lease_active(void);
#endif
#endif
uint16_t vm_ext_code_alloc_transient(uint16_t len);             /* Ausdrucks-Main: Abwaerts-Stapel, 0xFFFF = voll */
void     vm_ext_code_pop_transient(uint16_t at, uint16_t len);  /* nach dem Lauf freigeben (LIFO) */
#ifdef LISP65_VM_EXT_CODE_TEST
void     vm_ext_code_test_state(uint16_t watermark, uint16_t transient);
uint16_t vm_ext_code_test_transient(void);
#ifdef LISP65_C1_LEASE_ALLOC_GUARD
uint8_t  vm_ext_code_test_lease(void);
#endif
#endif

/* Boot-Einstieg (nach mem_init + vm_init oder dem umfassenderen eval_init):
 * 1) Blob ins erw. RAM stagen, 2) Directory registrieren, 3) littab-Symbole aufloesen. */
void vm_load_embedded_stdlib(void);
#if defined(LISP65_DIRECTORY_ONLY_HARNESS) && defined(LISP65_STDLIB_EXT_METADATA)
/* Host product-path fixture: model the profiled boot's post-validation trailer
 * reclaim before sequential disk-library commits. */
void vm_directory_only_test_reclaim_boot_metadata(void);
#endif

#if defined(LISP65_STAGED_BOOT_OVERLAY) && defined(LISP65_RUNTIME_OVERLAY)
/* Profile-bound preload: one full-image CRC, then four batched boot slices. */
uint8_t vm_load_profiled_boot_stdlib(void);
#endif

#if defined(LISP65_STDLIB_EXT_METADATA) && defined(LISP65_DISK_LIBS)
/* Runtime disk-lib transaction. Preflight reads the complete file without mutation. After the
 * caller stages plan->blob_len bytes at plan->code_base, commit verifies source and staged blob,
 * reserves that Bank-5 range, materializes patches, then publishes entries. */
l65m_status vm_preflight_lib_ext(const l65m_source *source, l65m_plan *plan);
l65m_status vm_load_lib_ext(const l65m_source *source, const l65m_plan *plan);
#ifdef L65M_COMMIT_OVERLAY_HOST_DIRECT
uint8_t vm_l65m_commit_batch_repeat_test(void *context, uint8_t slot,
                                         uint8_t entry_result);
#endif
#endif

#endif /* LISP65_VM */
#endif /* LISP65_VM_EMBED_H */
