/* lisp65 — Boot-Loader fuer die eingebettete Bytecode-Stdlib (K3-B, Runtime-Seite / Lane K). */
#include "vm_embed.h"
#ifdef LISP65_VM
#include "vm.h"

#ifdef LISP65_HEARTBEAT
#define LA(c) (*(volatile unsigned char *)(0x0800 + 50) = (unsigned char)(c))
#else
#define LA(c) ((void)0)
#endif

#include "mem.h"      /* alloc, cons, GC_* */
#include "symbol.h"   /* intern */
#include "interrupt.h" /* lisp_abort (kalter Boot-Pfad; kein LTO-Risiko wie bei mem.c) */
#ifdef LISP65_CODE_WINDOW_CONVERGENCE
#include "ship_runtime_io.h"
#endif

#if defined(LISP65_RUNTIME_OVERLAY) || defined(L65M_COMMIT_OVERLAY_HOST_DIRECT)
#include "l65m_batch_contract.h"
#endif
#ifdef LISP65_RUNTIME_OVERLAY
#include "vm_boot_fastpath.h"
_Static_assert(VM_RTOV_REQUIRED_SLOT_COUNT <= LISP65_RUNTIME_OVERLAY_HARD_MAX_SLICES,
               "runtime overlay catalog exceeds transport slot capacity");
#if defined(LISP65_STAGED_BOOT_OVERLAY) && !defined(LISP65_BOOT_FASTPATH_SLOT_BASE)
#error "profile-bound boot requires LISP65_BOOT_FASTPATH_SLOT_BASE"
#endif
#endif
#ifdef LISP65_RUNTIME_CORE
#include "vm_registry_impl.inc"
#endif

/* --- Bank-5 code append allocator (SHARED: disk libraries + the compiled-fn region; S0 in
 * docs/bank0-full-suite-strategy.md). Both sources append behind the stdlib blob (the FILE end,
 * including the L65M trailer!) up to the name-pool cap @ 0x8000. Earlier io.c had its own
 * disk_lib_hw pointer and the region had a second one -> they would have overwritten each other.
 * persist=0: hand out space at the current end only (a transient expression main), the pointer
 * stays. Returns an offset in the code bank; 0xFFFF = the region is full. Gated: only profiles with
 * a second code source need it (default = budget-neutral). */
#if defined(LISP65_DISK_LIBS) || defined(LISP65_COMPILE_REPL) || defined(LISP65_LCC_INSTALL)
/* Regions-Deckel = Start des Bank-5-Namepools. Historisch hart 0x8000; seit dem Trailer-
 * Umzug (SYMPOOL_EXT_OFF=0xa000, b3f99b4) endet das Stdlib-IMAGE (~0x92df im Full-Profil)
 * HINTER 0x8000 -> der DISK_LIBS-Seed (Datei-Ende) lag ueber dem Deckel und JEDE Alloc
 * schlug fehl ("lcc-install: region voll", M4-Fund). Profile mit explizitem Pool-Offset
 * bekommen den Deckel dort; alle anderen behalten 0x8000 (altes Verhalten). */
#if defined(LISP65_SYMPOOL_EXT) && defined(SYMPOOL_EXT_OFF)
#define VM_EXT_CODE_LIMIT ((uint16_t)(SYMPOOL_EXT_OFF))
#else
#define VM_EXT_CODE_LIMIT 0x8000u
#endif
static uint16_t ext_code_hw = 0;
static uint16_t ext_code_tsp = 0;   /* transienter Abwaerts-Stapel (0 = leer, s. unten) */
static uint8_t  ext_code_init = 0;
static uint16_t vm_ext_code_initial(void) {
#ifdef LISP65_EMBED_STDLIB
    return (uint16_t)(lisp65_stdlib_off + lisp65_stdlib_blob_len);
#else
    return 0;
#endif
}
uint16_t vm_ext_code_watermark(void) {
    return ext_code_init ? ext_code_hw : vm_ext_code_initial();
}
#ifdef LISP65_C1_COMPILER_TIER
#if defined(__mos__) && defined(LISP65_RUNTIME_OVERLAY)
#define C1_EXT_FN __attribute__((section(".lisp65_rt_c1_compiler"), noinline))
#else
#define C1_EXT_FN
#endif
C1_EXT_FN uint8_t vm_ext_code_truncate(uint16_t watermark) {
    uint16_t initial = vm_ext_code_initial();
    uint16_t current = vm_ext_code_watermark();
    /* A running expression occupies [ext_code_tsp, VM_EXT_CODE_LIMIT), while
     * persistent code occupies [initial, current).  C1 retirement is safe
     * under a nested eval frame precisely while those ranges do not overlap.
     * Keep the transient stack intact: only the persistent high-water mark is
     * rolled back. */
    if (watermark < initial || watermark > current ||
        (ext_code_tsp && current > ext_code_tsp))
        return 0;
    ext_code_init = 1; /* also clears the probe-only lease ownership bit */
    ext_code_hw = watermark;
    return 1;
}
#ifdef LISP65_C1_LEASE_ALLOC_GUARD
C1_EXT_FN void vm_ext_code_lease_begin(void) {
    ext_code_init |= 0x80u;
}
C1_EXT_FN uint8_t vm_ext_code_lease_active(void) {
    return (uint8_t)((ext_code_init & 0x80u) != 0);
}
#endif
#undef C1_EXT_FN
#endif
uint8_t vm_ext_code_preview(uint16_t len, uint16_t *base) {
    uint16_t at = vm_ext_code_watermark();
    if (!base || (uint32_t)at + len > (uint32_t)(ext_code_tsp ? ext_code_tsp : VM_EXT_CODE_LIMIT))
        return 0;
    *base = at;
    return 1;
}
uint16_t vm_ext_code_alloc(uint16_t len, uint8_t persist) {
    uint16_t at;
    if (!ext_code_init) {
        ext_code_init = 1;
        ext_code_hw = vm_ext_code_initial();
    }
    at = ext_code_hw;
#if defined(LISP65_C1_COMPILER_TIER) && defined(LISP65_C1_LEASE_ALLOC_GUARD)
    /* The overlay sets bit 7 only after exact compiler validation. Persistent
     * callers must retire first; appending above a lease would make rollback
     * erase foreign code. The tag reuses the existing init byte. */
    if (persist && (ext_code_init & 0x80u))
        return 0xFFFF;
#endif
    if ((unsigned long)at + len > (unsigned long)(ext_code_tsp ? ext_code_tsp : VM_EXT_CODE_LIMIT))
        return 0xFFFF;   /* Kreuzung: nie in einen LAUFENDEN transienten Main schreiben */
    if (persist) ext_code_hw = (uint16_t)(at + len);
    return at;
}
/* Transient expression mains: a DOWNWARD stack from the region cap (M4 finding #2: when they lay
 * in the upward continuum, every wrapper gap broke the sparse dir_off reconstruction -> align8
 * burned about 8 directory slots per (lcc-run '(defun ...)) and the directory was full after two
 * forms). No directory entry, no gap, real release after the run, and nestable (eval inside
 * compiled code). Persistent allocations check for the crossing (above). */
uint16_t vm_ext_code_alloc_transient(uint16_t len) {
    uint16_t top = ext_code_tsp ? ext_code_tsp : VM_EXT_CODE_LIMIT, at;
    if (!ext_code_init) vm_ext_code_alloc(0, 0);             /* initialise the watermark lazily */
    if (len > top || (at = (uint16_t)(top - len)) < ext_code_hw) return 0xFFFF;
    ext_code_tsp = at;
    return at;
}
void vm_ext_code_pop_transient(uint16_t at, uint16_t len) {
    if (ext_code_tsp == at) {
        ext_code_tsp = (uint16_t)(at + len);
        if (ext_code_tsp >= VM_EXT_CODE_LIMIT) ext_code_tsp = 0;   /* Stapel leer */
    }
}
#ifdef LISP65_VM_EXT_CODE_TEST
/* Host-only negative-fixture seam.  Normal allocators cannot create an
 * overlap; the test deliberately injects one to prove truncate fails closed. */
void vm_ext_code_test_state(uint16_t watermark, uint16_t transient) {
    ext_code_init = 1;
    ext_code_hw = watermark;
    ext_code_tsp = transient;
}
uint16_t vm_ext_code_test_transient(void) {
    return ext_code_tsp;
}
#ifdef LISP65_C1_LEASE_ALLOC_GUARD
uint8_t vm_ext_code_test_lease(void) {
    return (uint8_t)((ext_code_init & 0x80u) != 0);
}
#endif
#endif
#ifdef LISP65_STDLIB_EXT_METADATA
/* Exakten Startpunkt setzen (Boot): vm_load_ext_metadata kennt aus dem L65M-Header die Trailer-
 * Laenge -> Datei-Ende = md_base + metadata_bytes. Der lazy blob_len-Fallback oben deckt nur den
 * PRG-Metadaten-Fall (dort liegt im EXT wirklich nur der Code-Blob). */
static void vm_ext_code_seed(uint16_t at) {
    ext_code_init = 1;
    ext_code_hw = at;
}
#ifdef LISP65_DIRECTORY_ONLY_HARNESS
void vm_directory_only_test_reclaim_boot_metadata(void) {
    vm_ext_code_seed((uint16_t)(lisp65_stdlib_off + lisp65_stdlib_blob_len));
}
#endif
#endif
#endif /* LISP65_DISK_LIBS || LISP65_COMPILE_REPL */

/* Define BOOTFN independently of the metadata mode (vm_load_embedded_stdlib always uses it). */
#ifdef LISP65_STDLIB_BOOT_OVERLAY_CODE
#define BOOTFN __attribute__((section(".lisp65_boot"), noinline, used))
#else
#define BOOTFN
#endif
#if defined(LISP65_STAGED_BOOT_OVERLAY) && defined(LISP65_RUNTIME_OVERLAY)
#define LISP65_PROFILED_BOOT_FASTPATH 1
#endif
#if defined(LISP65_DISK_LIBS) && !defined(LISP65_RUNTIME_OVERLAY)
#define LITKEEPFN
#else
#define LITKEEPFN BOOTFN
#endif

/* Anchor heap literals (string/list/cons) PERMANENTLY: to the value cell of the holding symbol
 * %lit-keep (symval = a real GC root). GC_PUSH was WRONGLY permanent: apply/repl reset the root
 * stack — on on-demand library loads (inside the eval frame!) the literals lost their root
 * IMMEDIATELY -> the GC recycled them -> "vm: type error" in (ide) (B4 hand-test finding). */
#ifndef LISP65_PROFILED_BOOT_FASTPATH
static LITKEEPFN void vm_lit_keep(obj o) {
#ifdef LISP65_RUNTIME_OVERLAY
    obj keep_sym;
#else
    static obj keep_sym = NIL;
#endif
    if (!IS_PTR(o) || cell_type(o) == T_SYM) return;   /* Symbole interniert, Immediates frei */
    GC_PUSH(o);                                        /* intern() kann GC ausloesen */
#ifdef LISP65_RUNTIME_OVERLAY
    keep_sym = intern("%lit-keep");
#else
    if (keep_sym == NIL) keep_sym = intern("%lit-keep");
#endif
    o = gc_rootstack[GC_TOP];
    set_sym_value(keep_sym, cons(o, sym_value(keep_sym)));
    GC_POPN(1);
}
#endif

/* littab-Symbolaufloesung (Option 1, von Codex gepinnt; docs/bytecode-embed-loader.md).
 * Codex' Artefakt liefert `literal_patches[]` (blob_offset -> node) + `literal_nodes[]`; jeder Patch
 * ueberschreibt EIN 16-bit-obj-Wort im gestageten Blob mit dem zur Laufzeit materialisierten Literal.
 * Ohne Metadaten (z.B. Mock-Test) bleibt es ein No-op. Mit LISP65_STDLIB_EXT_METADATA
 * kommt der komplette Pfad stattdessen aus dem L65M-Trailer im erw. RAM (s. u.). */
#ifdef LISP65_STDLIB_EXT_METADATA
/* PRG-seitige littab-Metadaten ungenutzt (L65M-Trailer-Pfad unten). */
#elif defined(LISP65_BYTECODE_STDLIB_EMIT_METADATA)
#include "stdlib-p0.h"   /* Codex' Artefakt: literal_patches/_nodes/_index + Kind-Codes */

/* Ein Literal-Node rekursiv in einen Laufzeit-obj materialisieren. */
static obj vm_lit_node(uint16_t idx) {
    const lisp65_bc_literal_node *n = &lisp65_bytecode_stdlib_literal_nodes[idx];
    switch (n->kind) {
    case LISP65_BC_LIT_FIX:    return MKFIX(n->value);
    case LISP65_BC_LIT_NIL:    return NIL;
    case LISP65_BC_LIT_T:      return intern("t");
    case LISP65_BC_LIT_SYMBOL: return intern(n->name);    /* interniert -> permanenter Root */
    case LISP65_BC_LIT_STRING: {                          /* T_STR: a=Zeichenliste(Fixnums) */
#ifdef LISP65_STRING_ARENA
        const char *s = n->name; uint16_t len = 0;
        while (s[len]) len++;
        return str_from_bytes((const uint8_t *)s, len);
#else
        obj lst = NIL; const char *s = n->name; uint16_t i, len = 0;
        while (s[len]) len++;
        GC_PUSH(lst);
        for (i = len; i > 0; i--) { lst = cons(MKFIX((unsigned char)s[i-1]), gc_rootstack[GC_TOP]); GC_SET(GC_TOP, lst); }
        { obj str = alloc(T_STR); cell_set_a(str, gc_rootstack[GC_TOP]); cell_set_b(str, NIL); GC_POPN(1); return str; }
#endif
    }
    case LISP65_BC_LIT_CONS: {
        obj a = vm_lit_node(lisp65_bytecode_stdlib_literal_index[n->first]), b;
        GC_PUSH(a);
        b = vm_lit_node(lisp65_bytecode_stdlib_literal_index[n->first + 1]);
        a = gc_rootstack[GC_TOP]; GC_POPN(1);
        return cons(a, b);
    }
    case LISP65_BC_LIT_LIST: {
        obj out = NIL; uint16_t i;
        GC_PUSH(out);
        for (i = n->count; i > 0; i--) {
            obj item = vm_lit_node(lisp65_bytecode_stdlib_literal_index[n->first + i - 1]);
            out = cons(item, gc_rootstack[GC_TOP]); GC_SET(GC_TOP, out);
        }
        GC_POPN(1); return out;
    }
    default: return NIL;   /* INVALID */
    }
}

static void vm_resolve_littab_symbols(void) {
    uint16_t k;
    for (k = 0; k < LISP65_BYTECODE_STDLIB_LITERAL_PATCH_COUNT; k++) {
        const lisp65_bc_literal_patch *p = &lisp65_bytecode_stdlib_literal_patches[k];
        obj o = vm_lit_node(p->node);
        unsigned char w[2];
        /* Non-symbol heap literals (string/list/cons) are referenced only from extended RAM
         * (GC-blind) -> root them permanently. Symbols are interned; immediates need nothing. */
        vm_lit_keep(o);   /* permanent, via the holding symbol (NOT the root stack!) */
        w[0] = (unsigned char)(uint16_t)o; w[1] = (unsigned char)((uint16_t)o >> 8);
        vm_ext_write(w, 2, lisp65_stdlib_bank, (uint16_t)(lisp65_stdlib_off + p->blob_offset));
    }
}
#else
static void vm_resolve_littab_symbols(void) { /* no metadata (mock test): a no-op */ }
#endif

/* md_lit_node is normally BOOTFN (only the boot materialises stdlib literals). With disk libraries
 * (stage 2) the resident runtime library loader ALSO calls it after the boot -> then it must NOT
 * live in the recycled boot overlay (see docs/disk-bytecode-libs-design.md, the BOOTFN crux). */
#if defined(LISP65_DISK_LIBS) && !defined(LISP65_RUNTIME_OVERLAY)
#define MDLITFN
#define MDHELPFN
#else
#define MDLITFN BOOTFN
#define MDHELPFN BOOTFN
#endif

#ifdef LISP65_STDLIB_EXT_METADATA
/* BOOT-ONLY CODE into the boot overlay (2026-07-02): the complete trailer loader runs exactly
 * once (before the REPL, while the stack is still shallow) — in the overlay behind .noinit it
 * costs NO bank-0 budget after the boot (the area then belongs to the soft stack). This requires
 * the hardened overlay linker script (scripts/lisp65-mega65-boot-overlay.ld); the PRG file end
 * stays below the $C000 etherload boundary (footprint gate). noinline: LTO must NOT pull overlay
 * code into resident callers. */
#ifndef LISP65_PROFILED_BOOT_FASTPATH
/* --- L65M trailer loader (option a): read the boot metadata straight from extended RAM. ---
 * The `.ext.bin` preload places a pointer-free little-endian trailer behind the code blob
 * (contract: tools/host-lisp/bytecode_p0_stdlib.py, _build_ext_metadata): a 38-byte header
 * (magic "L65M", version 1, counters and section offsets relative to the trailer start), then
 * entries (8 B: name_off u16, bank u8, 0, off u16, len u16), literal_index (u16),
 * literal_nodes (10 B: kind u8, 0, value i16, first u16, count u16, name_off u16),
 * literal_patches (4 B: blob_offset u16, node u16), strings (NUL-terminated; 0xFFFF = no name).
 * The PRG therefore carries neither an embed table nor littab metadata -> no boot overlay, no
 * $C000 file problem, and the heap budget stays free. All of it is the cold boot path, so many
 * small DMA reads are fine. */
#include "stdlib-p0.h"   /* LISP65_BC_LIT_* kind codes (ungated in the generated header) */

#define MD_NAME_MAX LISP65_SYMBOL_NAME_BUFFER

static uint16_t md_base;                 /* Trailer-Start im Bank-Fenster (= off + blob_len)  */
static uint16_t md_index, md_nodes, md_strings;   /* Sektions-Offsets aus dem Header          */
#if defined(LISP65_DISK_LIBS) && !defined(LISP65_RUNTIME_OVERLAY)
static const l65m_source *md_source;      /* Runtime-Lib: Trailer bleibt im Disk-Scratch      */
static uint16_t md_source_base;
#endif

static MDHELPFN void md_read(uint16_t off, void *dst, uint16_t len) {
#if defined(LISP65_DISK_LIBS) && !defined(LISP65_RUNTIME_OVERLAY)
    if (md_source) {
        uint32_t at = (uint32_t)md_source_base + off;
        if (at <= 0xffffu && at + len <= md_source->length
            && md_source->read(md_source->ctx, (uint16_t)at, (uint8_t *)dst, len)) return;
        { uint16_t i; for (i = 0; i < len; i++) ((uint8_t *)dst)[i] = 0; }
        return;
    }
#endif
#ifdef LISP65_CODE_WINDOW_CONVERGENCE
    if (!vm_code_load_converged(lisp65_stdlib_bank,
                                (uint16_t)(md_base + off), len,
                                (uint8_t *)dst))
        lisp_abort_static(LISP65_ERR_RUNTIME_OVERLAY_TIMEOUT,
                          "DMA content did not converge; reboot");
#else
    vm_code_load(lisp65_stdlib_bank, (uint16_t)(md_base + off), len, (uint8_t *)dst);
#endif
}
static inline uint16_t md_u16(const uint8_t *b) { return (uint16_t)(b[0] | ((uint16_t)b[1] << 8)); }
static MDHELPFN uint16_t md_idx(uint16_t i) {
    uint8_t b[2]; md_read((uint16_t)(md_index + i * 2u), b, 2); return md_u16(b);
}
/* Namen sind im Preflight auf <=32+NUL begrenzt. Byteweise lesen vermeidet den frueheren
 * 34-Byte-OOB-Read am Ende des Trailers und funktioniert fuer Bank-5- und Scratch-Sources. */
static MDHELPFN void md_name(uint16_t name_off, char *dst) {
    uint16_t i;
    for (i = 0; i < MD_NAME_MAX - 1; i++) {
        md_read((uint16_t)(md_strings + name_off + i), dst + i, 1);
        if (!dst[i]) return;
    }
    dst[MD_NAME_MAX - 1] = 0;
}

/* Spiegel von vm_lit_node, nur mit DMA-Reads statt C-Arrays (identisches GC-Rooting-Muster). */
static MDLITFN obj md_lit_node(uint16_t idx) {
    uint8_t nb[10];
    md_read((uint16_t)(md_nodes + idx * 10u), nb, 10);
    switch (nb[0]) {
    case LISP65_BC_LIT_FIX:    return MKFIX((int16_t)md_u16(nb + 2));
    case LISP65_BC_LIT_NIL:    return NIL;
    case LISP65_BC_LIT_T:      return intern("t");
    case LISP65_BC_LIT_SYMBOL: { char nm[MD_NAME_MAX]; md_name(md_u16(nb + 8), nm); return intern(nm); }
    case LISP65_BC_LIT_STRING: {                       /* T_STR: a=Zeichenliste(Fixnums) */
        uint16_t soff = (uint16_t)(md_strings + md_u16(nb + 8)), len = 0;
#ifdef LISP65_STRING_ARENA
        {   /* DMA-Bytes direkt in die Arena streamen (kein Festpuffer, keine Truncation) */
            obj s = str_open();
            if (s == NIL) return NIL;
            for (;;) { uint8_t ch; md_read((uint16_t)(soff + len), &ch, 1); if (!ch) break; if (!str_putc(s, ch)) break; len++; }
            return str_close(s);
        }
#else
        obj lst = NIL;
        for (;;) { uint8_t ch; md_read((uint16_t)(soff + len), &ch, 1); if (!ch) break; len++; }
        GC_PUSH(lst);
        while (len > 0) {
            uint8_t ch; len--;
            md_read((uint16_t)(soff + len), &ch, 1);
            lst = cons(MKFIX(ch), gc_rootstack[GC_TOP]); GC_SET(GC_TOP, lst);
        }
        { obj str = alloc(T_STR); cell_set_a(str, gc_rootstack[GC_TOP]); cell_set_b(str, NIL); GC_POPN(1); return str; }
#endif
    }
    case LISP65_BC_LIT_CONS: {
        uint16_t first = md_u16(nb + 4);
        obj a = md_lit_node(md_idx(first)), b;
        GC_PUSH(a);
        b = md_lit_node(md_idx((uint16_t)(first + 1)));
        a = gc_rootstack[GC_TOP]; GC_POPN(1);
        return cons(a, b);
    }
    case LISP65_BC_LIT_LIST: {
        uint16_t first = md_u16(nb + 4), i = md_u16(nb + 6);
        obj out = NIL;
        GC_PUSH(out);
        for (; i > 0; i--) {
            obj item = md_lit_node(md_idx((uint16_t)(first + i - 1)));
            out = cons(item, gc_rootstack[GC_TOP]); GC_SET(GC_TOP, out);
        }
        GC_POPN(1); return out;
    }
    default: return NIL;   /* INVALID */
    }
}

static BOOTFN void vm_load_ext_metadata(void) {
    uint8_t hdr[38];
    uint16_t entry_count, patch_count, md_entries, patches_off, k;
    md_base = (uint16_t)(lisp65_stdlib_off + lisp65_stdlib_blob_len);
    md_read(0, hdr, 38);
    if (hdr[0] != 'L' || hdr[1] != '6' || hdr[2] != '5' || hdr[3] != 'M' || hdr[4] != 1) {
        lisp_abort_static(LISP65_ERR_STDLIB_METADATA,
                          "stdlib: no L65M metadata (ext.bin vorladen!)");
        return;
    }
    entry_count = md_u16(hdr + 16);
    patch_count = md_u16(hdr + 22);
    md_entries  = md_u16(hdr + 24);
    md_index    = md_u16(hdr + 26);
    md_nodes    = md_u16(hdr + 28);
    patches_off = md_u16(hdr + 30);
    md_strings  = md_u16(hdr + 32);
#if defined(LISP65_DISK_LIBS) || defined(LISP65_COMPILE_REPL)
    /* Code-Append-Allokator EXAKT hinter das Datei-Ende seeden: hdr+14 = metadata_bytes (Trailer-
     * Laenge aus dem Emitter-Header) -> md_base + metadata_bytes = Ende von [Code|Trailer]. Vorher
     * appendeten Disk-Libs ab blob_len = TRAILER-START und haetten ihn ueberschrieben (S0-Fix,
     * docs/bank0-full-suite-strategy.md §5-K2). Gegatet wie der Allokator (Default: keine 2. Quelle). */
    vm_ext_code_seed((uint16_t)(md_base + md_u16(hdr + 14)));
#endif
    /* 1) Directory registrieren — je Eintrag ueber die bestehende (abort-sichere) Naht. */
    for (k = 0; k < entry_count; k++) {
        uint8_t eb[8]; char nm[MD_NAME_MAX]; vm_embed_entry e;
        md_read((uint16_t)(md_entries + k * 8u), eb, 8);
        md_name(md_u16(eb), nm);
        e.name = nm; e.bank = eb[2]; e.flags = eb[3]; e.off = md_u16(eb + 4); e.len = md_u16(eb + 6);
        if (!vm_register_embedded(&e, 1)) {
            lisp_abort_static(LISP65_ERR_STDLIB_REGISTER,
                              "stdlib: register failed");
            return;
        }
    }
    /* 2) littab-Patches — Spiegel von vm_resolve_littab_symbols (inkl. Permanent-Rooting). */
    for (k = 0; k < patch_count; k++) {
        uint8_t pb[4]; obj o; unsigned char w[2];
        md_read((uint16_t)(patches_off + k * 4u), pb, 4);
        o = md_lit_node(md_u16(pb + 2));
        vm_lit_keep(o);   /* permanent, via the holding symbol (NOT the root stack!) */
        w[0] = (unsigned char)(uint16_t)o; w[1] = (unsigned char)((uint16_t)o >> 8);
        vm_ext_write(w, 2, lisp65_stdlib_bank, (uint16_t)(lisp65_stdlib_off + md_u16(pb)));
    }
#if defined(LISP65_DISK_LIBS) || defined(LISP65_COMPILE_REPL) || defined(LISP65_LCC_INSTALL)
    /* 3) TRAILER-RECLAIM (A1, projekt-bestandsaufnahme §4): nach Registrierung+Patches ist
     * der Stdlib-Trailer TOT (Namen -> Sympool, Literale -> Heap/Blob-Patches). Die Region
     * beginnt am Trailer-START statt am Datei-Ende -> Session-Kapazitaet ~2,3 KB -> ~25 KB.
     * Preis (dokumentiert): Warm-Re-SYS ohne erneutes Blob-Preload endet im sauberen
     * L65M-Magic-Abort — Neu-Preload noetig, sobald installiert wurde. */
    vm_ext_code_seed(md_base);
#endif
}
#endif

#ifdef LISP65_DISK_LIBS
/* --- Runtime library loader (stage 2; docs/disk-bytecode-libs-design.md) ---
 * Registers a bytecode library already staged into bank 5 (lisp65_stdlib_bank): blob @ code_base,
 * L65M trailer @ md_at (both within-bank offsets). RESIDENT (not BOOTFN!): it runs after the boot,
 * when the boot overlay has already become soft stack. It mirrors vm_load_ext_metadata, BUT:
 *  - relocates each entry/patch by code_base (library metadata carries BLOB-RELATIVE 0 offsets),
 *  - aligns dir_n to the 8-entry block boundary first (vm_dir_align8) -> the library is its own block,
 *  - forces bank = lisp65_stdlib_bank (the library sits contiguously behind the stdlib blob).
 * Without a runtime overlay the direct host/reference path still uses md_lit_node/md_read/md_name.
 * Das Produkt delegiert denselben Commit an die l65c-Slices; die Boot-Helfer bleiben BOOTFN. */
#if !defined(__mos__) || defined(LISP65_RUNTIME_OVERLAY)
#ifdef LISP65_RUNTIME_OVERLAY
static LISP65_RESIDENT_ISLAND_FN
#else
static
#endif
uint8_t lib_symbol_exists(void *ctx, const char *name) {
    (void)ctx;
    return sym_lookup(name, 0);
}
#endif

#ifdef LISP65_RUNTIME_OVERLAY
#ifdef __mos__
uint8_t vm_l65m_batch_repeat(void *context, uint8_t slot,
                             uint8_t entry_result);
#else
static LISP65_RESIDENT_ISLAND_FN
uint8_t vm_l65m_batch_repeat(void *context, uint8_t slot,
                             uint8_t entry_result) {
    vm_l65m_batch_header *work = context;
    uint8_t phase, base;
    if (!work) return 0;
    if (work->abi_version == L65M_OVERLAY_ABI_VERSION) {
        base = VM_RTOV_PREFLIGHT_SLOT_BASE;
    } else if (work->abi_version == L65M_COMMIT_OVERLAY_ABI_VERSION) {
        base = VM_RTOV_COMMIT_SLOT_BASE;
    } else return 0;
    phase = (uint8_t)(slot - base);
    return (uint8_t)(entry_result == L65M_OK && work->expected_phase == phase
                     && !work->busy && !work->transport_status
                     && work->repeat_phase);
}
#endif

#define vm_l65m_commit_batch_repeat vm_l65m_batch_repeat
#elif defined(L65M_COMMIT_OVERLAY_HOST_DIRECT)
uint8_t vm_l65m_commit_batch_repeat_test(void *context, uint8_t slot,
                                         uint8_t entry_result) {
    l65m_commit_work *work = context;
    uint8_t phase;
    if (!work || work->abi_version != L65M_COMMIT_OVERLAY_ABI_VERSION)
        return 0;
    phase = (uint8_t)(slot - VM_RTOV_COMMIT_SLOT_BASE);
    return (uint8_t)(entry_result == L65M_OK
                     && phase < L65M_COMMIT_PHASE_COUNT
                     && work->expected_phase == phase
                     && !work->busy
                     && work->transport_status == L65M_COMMIT_TRANSPORT_OK
                     && work->repeat_phase);
}
#endif

l65m_status vm_preflight_lib_ext(const l65m_source *source, l65m_plan *plan) {
#if defined(__mos__) && !defined(LISP65_RUNTIME_OVERLAY)
    /* A MOS image without the profile-bound Bank-3 catalog cannot safely run
     * the full validator. Historical diagnostic profiles fail closed. */
    if (!source || !source->read || !plan) return L65M_ERR_ARGUMENT;
    return L65M_ERR_STATE;
#else
    l65m_limits limits;
#ifndef LISP65_RUNTIME_OVERLAY
    uint16_t blob_len, metadata_len, base;
    l65m_status st = l65m_probe(source, &blob_len, &metadata_len);
    (void)metadata_len;
    if (st != L65M_OK) return st;
    if (!vm_ext_code_preview(blob_len, &base)) return L65M_ERR_REGION;
#else
    l65m_overlay_work work;
    uint16_t base, preview;
    uint8_t phase, result;
    vm_runtime_overlay_status transport;
    if (!source || !source->read || !plan) return L65M_ERR_ARGUMENT;
    base = vm_ext_code_watermark();
#endif
    limits.dir_count = vm_dir_count(); limits.dir_capacity = vm_dir_capacity();
    limits.symbol_count = sym_count(); limits.symbol_capacity = sym_max();
    limits.namepool_used = sym_pool_used(); limits.namepool_capacity = sym_pool_capacity();
    limits.heap_free = mem_free_cells();
#ifdef LISP65_STRING_ARENA
    limits.arena_used = str_arena_used(); limits.arena_capacity = str_arena_capacity();
    limits.string_arena = 1;
#else
    limits.arena_used = limits.arena_capacity = 0; limits.string_arena = 0;
#endif
    limits.roots_used = gc_rootsp; limits.roots_capacity = GC_ROOTS;
    limits.symbol_exists = lib_symbol_exists; limits.symbol_ctx = 0;
#ifdef LISP65_RUNTIME_OVERLAY
    l65m_overlay_work_init(&work, source, base, &limits, plan);
    for (phase = 0; phase < L65M_OVERLAY_PHASE_COUNT; phase++) {
        uint8_t slot = (uint8_t)(VM_RTOV_PREFLIGHT_SLOT_BASE + phase);
        transport = vm_runtime_overlay_exec_batch(
            slot, &work, &result, VM_RUNTIME_OVERLAY_BATCH_L65M,
            vm_l65m_batch_repeat);
        if (transport != VM_RUNTIME_OVERLAY_OK
            || work.abi_version != L65M_OVERLAY_ABI_VERSION
            || work.context_size != L65M_OVERLAY_CONTEXT_SIZE
            || work.transport_status != L65M_OV_TRANSPORT_OK)
            return L65M_ERR_STATE;
        if (result != L65M_OK) return (l65m_status)result;
        if (work.finished) break;
        if (work.repeat_phase || work.expected_phase != (uint8_t)(phase + 1u))
            return L65M_ERR_STATE;
    }
    if (!work.finished || work.expected_phase != L65M_OVERLAY_PHASE_COUNT)
        return L65M_ERR_STATE;
    if (!vm_ext_code_preview(plan->blob_len, &preview)) return L65M_ERR_REGION;
    if (preview != plan->code_base) return L65M_ERR_STATE;
    return L65M_OK;
#else
    return l65m_validate(source, base, &limits, plan);
#endif
#endif /* __mos__ && !LISP65_RUNTIME_OVERLAY */
}

l65m_status vm_load_lib_ext(const l65m_source *source, const l65m_plan *plan) {
#ifdef L65M_COMMIT_OVERLAY_HOST_DIRECT
    return l65m_commit_run_direct(source, plan);
#elif defined(LISP65_RUNTIME_OVERLAY)
    l65m_commit_work work;
    l65m_status status;
    vm_runtime_overlay_status transport;
    uint8_t result, phase;
    status = l65m_commit_work_prepare(&work, source, plan);
    if (status != L65M_OK) return status;
    while (!work.finished) {
        phase = work.expected_phase;
        if (phase >= L65M_COMMIT_PHASE_COUNT) {
            status = L65M_ERR_STATE;
            break;
        }
        transport = vm_runtime_overlay_exec_batch(
            (uint8_t)(VM_RTOV_COMMIT_SLOT_BASE + phase), &work, &result,
            VM_RUNTIME_OVERLAY_BATCH_COMMIT, vm_l65m_commit_batch_repeat);
        if (transport != VM_RUNTIME_OVERLAY_OK
            || work.abi_version != L65M_COMMIT_OVERLAY_ABI_VERSION
            || work.context_size != L65M_COMMIT_CONTEXT_SIZE
            || work.transport_status != L65M_COMMIT_TRANSPORT_OK) {
            status = L65M_ERR_STATE;
            break;
        }
        status = (l65m_status)result;
        if (status != L65M_OK) break;
    }
    if (status == L65M_OK
        && (!work.finished
            || work.context_size != L65M_COMMIT_CONTEXT_SIZE
            || work.expected_phase != L65M_COMMIT_PHASE_COUNT))
        status = L65M_ERR_STATE;
    l65m_commit_work_release();
    return status;
#else
    uint16_t k;
    if (!source || !plan || source->length != plan->source_length
        || vm_ext_code_watermark() != plan->code_base || vm_dir_count() != plan->dir_before
        || sym_count() != plan->symbols_before || sym_pool_used() != plan->namepool_before
        || mem_free_cells() != plan->heap_free_before || gc_rootsp != plan->roots_before
#ifdef LISP65_STRING_ARENA
        || str_arena_used() != plan->arena_used_before
#endif
       ) return L65M_ERR_STATE;
    if (vm_ext_code_alloc(plan->blob_len, 1) != plan->code_base) return L65M_ERR_STATE;
    md_source = source; md_source_base = plan->source_metadata_off;
    md_index = plan->index_off; md_nodes = plan->nodes_off; md_strings = plan->strings_off;
    vm_dir_align8();                              /* Lib startet als eigener 8er-Block (K2/sparse) */
    for (k = 0; k < plan->entry_count; k++) {
        uint8_t eb[8]; char nm[MD_NAME_MAX]; vm_embed_entry e;
        md_read((uint16_t)(plan->entries_off + k * 8u), eb, 8);
        md_name(md_u16(eb), nm);
        e.name = nm; e.bank = lisp65_stdlib_bank; e.flags = eb[3];
        e.off = (uint16_t)(plan->code_base + md_u16(eb + 4)); e.len = md_u16(eb + 6);
        if (!vm_register_embedded(&e, 1)) { md_source = 0; return L65M_ERR_STATE; }
    }
    for (k = 0; k < plan->patch_count; k++) {
        uint8_t pb[4]; obj o; unsigned char w[2];
        md_read((uint16_t)(plan->patches_off + k * 4u), pb, 4);
        o = md_lit_node(md_u16(pb + 2));
        vm_lit_keep(o);   /* permanent, via the holding symbol (NOT the root stack!) */
        w[0] = (unsigned char)(uint16_t)o; w[1] = (unsigned char)((uint16_t)o >> 8);
        vm_ext_write(w, 2, lisp65_stdlib_bank, (uint16_t)(plan->code_base + md_u16(pb)));
    }
    md_source = 0;
    return L65M_OK;
#endif
}
#endif /* LISP65_DISK_LIBS */
#endif /* LISP65_STDLIB_EXT_METADATA */

#if defined(LISP65_RUNTIME_OVERLAY) && defined(LISP65_STAGED_BOOT_OVERLAY) && \
    defined(LISP65_STDLIB_EXT_METADATA)
uint8_t vm_load_profiled_boot_stdlib(void) {
    vm_boot_fastpath_work work;
    vm_runtime_overlay_status transport;
    uint8_t result, phase;
    vm_boot_fastpath_prepare(&work);
    for (phase = 0; phase < VM_BOOT_FASTPATH_PHASE_COUNT; phase++) {
        transport = vm_runtime_overlay_exec(
            (uint8_t)(LISP65_BOOT_FASTPATH_SLOT_BASE + phase), &work, &result);
        if (transport != VM_RUNTIME_OVERLAY_OK)
            return vm_boot_fastpath_transport_status(transport);
        if (result != VM_BOOT_FASTPATH_OK) return result;
    }
    if (!work.finished || work.expected_phase != VM_BOOT_FASTPATH_PHASE_COUNT
        || work.overlay_calls != VM_BOOT_FASTPATH_OVERLAY_CALLS
        || work.crc_passes != VM_BOOT_FASTPATH_CRC_PASSES
        || work.crc_bytes != LISP65_BOOT_STDLIB_IMAGE_BYTES)
        return VM_BOOT_FASTPATH_ERR_STATE;
    /* The build-bound trailer is dead after all names/literals were consumed. */
    vm_ext_code_seed((uint16_t)(LISP65_BOOT_STDLIB_OFF +
                                LISP65_BOOT_STDLIB_BLOB_BYTES));
    return VM_BOOT_FASTPATH_OK;
}
#endif

#ifndef LISP65_PROFILED_BOOT_FASTPATH
BOOTFN void vm_load_embedded_stdlib(void) {
    /* 1) Code-Objekt-Blob als Ganzes ins erweiterte RAM stagen (Bulk-Write, HW-bewiesenes Muster). */
#ifndef LISP65_STDLIB_EXTERNAL_BLOB
    vm_ext_write(lisp65_stdlib_blob, lisp65_stdlib_blob_len,
                 lisp65_stdlib_bank, lisp65_stdlib_off);
#else
    /* Produktprofil: das Blob wurde vor dem PRG per etherload -b nach EXT-RAM vorgeladen. */
#endif
#ifdef LISP65_STDLIB_EXT_METADATA
    /* 2+3) Directory + littab komplett aus dem L65M-Trailer im erw. RAM (kein PRG-Ballast). */
    vm_load_ext_metadata();
#else
    /* 2) Directory registrieren: je Funktion intern(name) -> vm_dir_add -> T_BCODE aufs Symbol. */
    if (!vm_register_embedded(lisp65_embed, lisp65_embed_count)) {
        lisp_abort_static(LISP65_ERR_STDLIB_REGISTER,
                          "stdlib: register failed");
        return;
    }
    /* 3) Symbol-Referenzen in den Code-Objekten aufloesen (Stub, s. o.). */
    vm_resolve_littab_symbols();
#endif
#ifdef LISP65_LCC_INSTALL
    vm_dir_align8();                            /* lcc-install schreibt spaeter eine zweite Code-Region. */
#endif
}
#endif

/* --- Platform DMA (mega65). Device build ONLY (LISP65_EMBED_DMA); host tests provide their own
 *     vm_code_load/vm_ext_write. The same F018 DMA pattern as the hardware-proven streaming tests. --- */
#ifdef LISP65_EMBED_DMA
/* NOT static, plus used: guarantees an assembler symbol name for the register-free trigger
 * below (the inline-asm reference is invisible to LTO). */
__attribute__((used)) unsigned char vm_dma_list[12];
#ifdef LISP65_DMA_PROF
/* Diagnostic seam (2026-07-03): count DMA jobs by class — the device currency of the performance
 * finding (call-return reloads). Only in the binary with -DLISP65_DMA_PROF. */
uint16_t dma_code = 0, dma_wr = 0, dma_sym = 0;
#define DMA_COUNT(v) ((v)++)
#else
#define DMA_COUNT(v) ((void)0)
#endif
static void vm_dma(uint16_t sa, uint8_t sb, uint16_t da, uint8_t db, uint16_t n) {
    vm_dma_list[0]=0; vm_dma_list[1]=(uint8_t)n; vm_dma_list[2]=(uint8_t)(n>>8);
    vm_dma_list[3]=(uint8_t)sa; vm_dma_list[4]=(uint8_t)(sa>>8); vm_dma_list[5]=sb;
    vm_dma_list[6]=(uint8_t)da; vm_dma_list[7]=(uint8_t)(da>>8); vm_dma_list[8]=db;
    vm_dma_list[9]=0; vm_dma_list[10]=0; vm_dma_list[11]=0;
    /* REGISTERFREIER Trigger + "memory"-Clobber. Der Clobber ist ESSENZIELL: ohne ihn darf
     * der Optimizer (LTO inlined vm_dma ueberall) die vm_dma_list-Stores HINTER den Trigger
     * verschieben -> die DMA liest eine halb geschriebene Liste -> wilde Transfers ->
     * Speicherzerstoerung (exakt der HW-Freeze bei Fall ~10; Host nutzt memcpy -> nie betroffen). */
    LA(1);   /* A: vor DMA-Trigger */
    __asm__ volatile(
        "lda #0\n\t"
        "sta $d702\n\t"
        "lda #mos16hi(vm_dma_list)\n\t"
        "sta $d701\n\t"
        "lda #mos16lo(vm_dma_list)\n\t"
        "sta $d700\n\t"
        ::: "a", "memory");
    LA(2);   /* B: DMA kehrte zurueck */
}
/* Code-Objekt/Fenster aus erw. RAM (bank:off) in den hot-Puffer holen (VM-Naht). */
void vm_code_load(uint8_t bank, uint16_t off, uint16_t len, uint8_t *dst) {
#ifdef LISP65_DMA_PROF
    DMA_COUNT(dma_code);
#endif
    vm_dma(off, bank, (uint16_t)(uintptr_t)dst, 0, len);
}
#ifdef LISP65_CODE_WINDOW_CONVERGENCE
#ifndef LISP65_SHIP_RUNTIME_IO
#error "code-window convergence requires the Ship-owned advancing frame source"
#endif
#ifndef VM_CODEBUF
#error "code-window convergence requires the linked VM_CODEBUF bound"
#endif
#define VM_CODE_CONVERGENCE_TIMEOUT_FRAMES 64u

/* The source discriminator owns a distinct descriptor.  Consumers own no
 * proof buffer and cannot bypass this one convergence primitive. */
__attribute__((used)) unsigned char vm_dma_verify_list[24];
static volatile uint8_t vm_code_verify;
static volatile uint8_t vm_code_verify_done;
static const uint8_t vm_code_verify_marker = 0xa5u;

static void vm_dma_verify_submit(uint16_t source, uint8_t source_bank,
                                 uint8_t *destination) {
    uint8_t *next = vm_dma_verify_list + 12u;
    vm_dma_verify_list[0] = 4u;
    vm_dma_verify_list[1] = 1u;
    vm_dma_verify_list[2] = 0u;
    vm_dma_verify_list[3] = (uint8_t)source;
    vm_dma_verify_list[4] = (uint8_t)(source >> 8);
    vm_dma_verify_list[5] = source_bank;
    vm_dma_verify_list[6] = (uint8_t)(uintptr_t)destination;
    vm_dma_verify_list[7] =
        (uint8_t)((uint16_t)(uintptr_t)destination >> 8);
    vm_dma_verify_list[8] = 0u;
    vm_dma_verify_list[9] = 0u;
    vm_dma_verify_list[10] = 0u;
    vm_dma_verify_list[11] = 0u;
    next[0] = 0u;
    next[1] = 1u;
    next[2] = 0u;
    next[3] = (uint8_t)(uintptr_t)&vm_code_verify_marker;
    next[4] =
        (uint8_t)((uint16_t)(uintptr_t)&vm_code_verify_marker >> 8);
    next[5] = 0u;
    next[6] = (uint8_t)(uintptr_t)&vm_code_verify_done;
    next[7] = (uint8_t)((uint16_t)(uintptr_t)&vm_code_verify_done >> 8);
    next[8] = 0u;
    next[9] = 0u;
    next[10] = 0u;
    next[11] = 0u;
    __asm__ volatile(
        "lda #0\n\t"
        "sta $d702\n\t"
        "lda #mos16hi(vm_dma_verify_list)\n\t"
        "sta $d701\n\t"
        "lda #mos16lo(vm_dma_verify_list)\n\t"
        "sta $d700\n\t"
        ::: "a", "memory");
}

static uint8_t vm_dma_source_byte(uint8_t bank, uint16_t off,
                                  uint8_t *value) {
    uint16_t start = lisp65_ship_io_frame_count();
    vm_code_verify_done = (uint8_t)~vm_code_verify_marker;
    vm_dma_verify_submit(off, bank, (uint8_t *)&vm_code_verify);
    while (vm_code_verify_done != vm_code_verify_marker) {
        if ((uint16_t)(lisp65_ship_io_frame_count() - start)
            >= VM_CODE_CONVERGENCE_TIMEOUT_FRAMES) return 0u;
    }
    *value = vm_code_verify;
    return 1u;
}

/* Resident sufficiency uses one source-derived discriminator byte.  The
 * source scan precedes the one primary submission; an already-equal span is
 * trivially converged.  The match test precedes the timeout test, so exact
 * convergence on frame 64 succeeds.  There is no primary resubmission loop. */
uint8_t vm_code_load_converged(uint8_t bank, uint16_t off, uint16_t len,
                               uint8_t *dst) {
    volatile uint8_t *observed = (volatile uint8_t *)dst;
    uint8_t expected;
    uint16_t start;
    uint16_t i;
    if (!dst || !len) return 0u;

    for (i = 0u; i < len; ++i) {
        if (!vm_dma_source_byte(bank, (uint16_t)(off + i), &expected))
            return 0u;
        if (observed[i] != expected) break;
    }
    if (i == len) return 1u;

    start = lisp65_ship_io_frame_count();
    vm_code_load(bank, off, len, dst);
    while (observed[i] != expected) {
        if ((uint16_t)(lisp65_ship_io_frame_count() - start)
            >= VM_CODE_CONVERGENCE_TIMEOUT_FRAMES) return 0u;
    }
    return 1u;
}
#endif
/* Blob (hot) ins erw. RAM schreiben (Staging-Naht). */
void vm_ext_write(const uint8_t *src, uint16_t len, uint8_t bank, uint16_t off) {
#ifdef LISP65_DMA_PROF
    DMA_COUNT(dma_wr);
#endif
    vm_dma((uint16_t)(uintptr_t)src, 0, off, bank, len);
}

#ifndef SYMPOOL_EXT_BANK
#define SYMPOOL_EXT_BANK 5u
#endif
#ifndef SYMPOOL_EXT_OFF
#define SYMPOOL_EXT_OFF  0x8000u
#endif
#ifdef LISP65_SYMPOOL_EXT
/* Namens-Pool-Naht (symbol.c) auf dieselbe DMA. Eigener EXT-Bereich, weit hinter dem Code-Blob.
 * Default off 0x8000 laesst >29 KB Abstand; groessere Blob+Metadaten-Profile koennen ihn per
 * SYMPOOL_EXT_OFF nach hinten schieben. Zugriffe sind KALT (intern beim Boot + Reader; nach dem
 * eq-Dispatch-Umbau NICHT im heissen eval-Pfad) und je EIN Bulk-Transfer. */
void sympool_read(uint16_t off, char *dst, uint16_t len) {
#ifdef LISP65_DMA_PROF
    DMA_COUNT(dma_sym);
#endif
#ifdef LISP65_CODE_WINDOW_CONVERGENCE
    if (!vm_code_load_converged(SYMPOOL_EXT_BANK,
                                (uint16_t)(SYMPOOL_EXT_OFF + off), len,
                                (uint8_t *)dst))
        lisp_abort_static(LISP65_ERR_RUNTIME_OVERLAY_TIMEOUT,
                          "DMA content did not converge; reboot");
#else
    vm_dma((uint16_t)(SYMPOOL_EXT_OFF + off), SYMPOOL_EXT_BANK, (uint16_t)(uintptr_t)dst, 0, len);
#endif
}
void sympool_write(uint16_t off, const char *src, uint16_t len) {
    vm_dma((uint16_t)(uintptr_t)src, 0, (uint16_t)(SYMPOOL_EXT_OFF + off), SYMPOOL_EXT_BANK, len);
}
#endif /* LISP65_SYMPOOL_EXT */

#ifdef LISP65_SYMVAL_EXT
/* symval-Naht (symbol.c) auf dieselbe gehaertete DMA. EXT-Bereich in Bank 5 HINTER dem Namepool
 * (SYMPOOL_EXT_OFF + NAMEPOOL), je 2 B/Symbol. Zugriffe KALT:
 * nur Treewalk-Interpreter (eval.c) + GC (mem.c, periodisch) -- Bytecode fasst symval NICHT an.
 * s. docs/symbol-table-ext-design.md. */
#ifndef SYMVAL_EXT_BANK
#define SYMVAL_EXT_BANK 5u
#endif
#ifndef SYMVAL_EXT_OFF
#define SYMVAL_EXT_OFF  ((uint16_t)(SYMPOOL_EXT_OFF + NAMEPOOL))
#endif
obj symval_get(uint16_t i) {
    uint16_t v;
#ifdef LISP65_CODE_WINDOW_CONVERGENCE
    if (!vm_code_load_converged(SYMVAL_EXT_BANK,
                                (uint16_t)(SYMVAL_EXT_OFF + i * 2u), 2u,
                                (uint8_t *)&v))
        lisp_abort_static(LISP65_ERR_RUNTIME_OVERLAY_TIMEOUT,
                          "DMA content did not converge; reboot");
#else
    vm_dma((uint16_t)(SYMVAL_EXT_OFF + i * 2u), SYMVAL_EXT_BANK, (uint16_t)(uintptr_t)&v, 0, 2);
#endif
    return (obj)v;
}
void symval_set(uint16_t i, obj val) {
    uint16_t v = (uint16_t)val;
    vm_dma((uint16_t)(uintptr_t)&v, 0, (uint16_t)(SYMVAL_EXT_OFF + i * 2u), SYMVAL_EXT_BANK, 2);
}
#endif /* LISP65_SYMVAL_EXT */

#ifdef LISP65_NAMEOFF_EXT
/* nameoff-Naht (symbol.c): reiner 16-Bit-Namepool-Offset im erw. RAM, Bank 5 HINTER symval
 * (SYMPOOL_EXT_OFF + NAMEPOOL + MAX_SYM*2), je 2 B/Symbol. Zugriff KALT: nur bei Laengen-TREFFER im
 * Intern-Scan (Vorfilter ist Bank-0-namelen -> selten) + symname/print. Der Boot-O(nsym^2)-Scan
 * bleibt dank namelen DMA-frei. s. docs/symbol-table-ext-design.md. */
#ifndef NAMEOFF_EXT_BANK
#define NAMEOFF_EXT_BANK 5u
#endif
#ifndef NAMEOFF_EXT_OFF
#define NAMEOFF_EXT_OFF  ((uint16_t)(SYMPOOL_EXT_OFF + NAMEPOOL + MAX_SYM * 2u))
#endif
uint16_t nameoff_get(uint16_t i) {
    uint16_t v;
#ifdef LISP65_CODE_WINDOW_CONVERGENCE
    if (!vm_code_load_converged(NAMEOFF_EXT_BANK,
                                (uint16_t)(NAMEOFF_EXT_OFF + i * 2u), 2u,
                                (uint8_t *)&v))
        lisp_abort_static(LISP65_ERR_RUNTIME_OVERLAY_TIMEOUT,
                          "DMA content did not converge; reboot");
#else
    vm_dma((uint16_t)(NAMEOFF_EXT_OFF + i * 2u), NAMEOFF_EXT_BANK, (uint16_t)(uintptr_t)&v, 0, 2);
#endif
    return v;
}
void nameoff_set(uint16_t i, uint16_t off) {
    uint16_t v = off;
    vm_dma((uint16_t)(uintptr_t)&v, 0, (uint16_t)(NAMEOFF_EXT_OFF + i * 2u), NAMEOFF_EXT_BANK, 2);
}
#endif /* LISP65_NAMEOFF_EXT */

#ifdef LISP65_SYMFN_EXT
/* symfn-Naht (symbol.c): Funktionszellen in EXT. Der CALL-Hotpath zahlt damit DMA;
 * das ist als MVP-Budget-Ventil akzeptiert. GC liest nur Pointer-Funktionszellen
 * (symfnptr-Bitmap), nicht alle BCODE-Immediates. */
#ifndef SYMFN_EXT_BANK
#define SYMFN_EXT_BANK 5u
#endif
#ifndef SYMFN_EXT_OFF
#ifdef LISP65_NAMEOFF_EXT
#define SYMFN_EXT_OFF ((uint16_t)(NAMEOFF_EXT_OFF + MAX_SYM * 2u))
#elif defined(LISP65_SYMVAL_EXT)
#define SYMFN_EXT_OFF ((uint16_t)(SYMVAL_EXT_OFF + MAX_SYM * 2u))
#else
#define SYMFN_EXT_OFF ((uint16_t)(SYMPOOL_EXT_OFF + NAMEPOOL))
#endif
#endif
/* Layout ab SYMPOOL_EXT_OFF muss in Bank 5 bleiben. Aktuelles Workbench-Layout:
 * namepool + symval + nameoff + symfn. Die #if-Ausdruecke bleiben bewusst castfrei,
 * weil der Praeprozessor C-Typnamen in Konstantenausdruecken nicht akzeptiert. */
#if defined(LISP65_NAMEOFF_EXT)
#if (SYMPOOL_EXT_OFF + NAMEPOOL + MAX_SYM * 6u) > 0x10000
#error "EXT-Symbol-Layout sprengt Bank 5 (symfn-Ende > 64K) -- NAMEPOOL/MAX_SYM/SYMPOOL_EXT_OFF senken"
#endif
#elif defined(LISP65_SYMVAL_EXT)
#if (SYMPOOL_EXT_OFF + NAMEPOOL + MAX_SYM * 4u) > 0x10000
#error "EXT-Symbol-Layout sprengt Bank 5 (symfn-Ende > 64K) -- NAMEPOOL/MAX_SYM/SYMPOOL_EXT_OFF senken"
#endif
#else
#if (SYMPOOL_EXT_OFF + NAMEPOOL + MAX_SYM * 2u) > 0x10000
#error "EXT-Symbol-Layout sprengt Bank 5 (symfn-Ende > 64K) -- NAMEPOOL/MAX_SYM/SYMPOOL_EXT_OFF senken"
#endif
#endif
obj symfn_ext_get(uint16_t i) {
    uint16_t v;
#ifdef LISP65_CODE_WINDOW_CONVERGENCE
    if (!vm_code_load_converged(SYMFN_EXT_BANK,
                                (uint16_t)(SYMFN_EXT_OFF + i * 2u), 2u,
                                (uint8_t *)&v))
        lisp_abort_static(LISP65_ERR_RUNTIME_OVERLAY_TIMEOUT,
                          "DMA content did not converge; reboot");
#else
    vm_dma((uint16_t)(SYMFN_EXT_OFF + i * 2u), SYMFN_EXT_BANK, (uint16_t)(uintptr_t)&v, 0, 2);
#endif
    return (obj)v;
}
void symfn_ext_set(uint16_t i, obj val) {
    uint16_t v = (uint16_t)val;
    vm_dma((uint16_t)(uintptr_t)&v, 0, (uint16_t)(SYMFN_EXT_OFF + i * 2u), SYMFN_EXT_BANK, 2);
}
#elif defined(LISP65_NAMEOFF_EXT)
/* Layout ohne symfn-EXT: namepool + symval + nameoff. */
#if (SYMPOOL_EXT_OFF + NAMEPOOL + MAX_SYM * 4u) > 0x10000
#error "EXT-Symbol-Layout sprengt Bank 5 (SYMPOOL_EXT_OFF+NAMEPOOL+MAX_SYM*4 > 64K) -- NAMEPOOL/MAX_SYM senken"
#endif
#endif /* LISP65_SYMFN_EXT */
#endif /* LISP65_EMBED_DMA */

#endif /* LISP65_VM */
