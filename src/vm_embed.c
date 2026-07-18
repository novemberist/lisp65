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

/* --- Bank-5-Code-Append-Allokator (GEMEINSAM: Disk-Libs + Compiled-Fn-Region; S0 in
 * docs/bank0-full-suite-strategy.md). Beide Quellen appenden hinter dem Stdlib-Blob (DATEI-Ende
 * inkl. L65M-Trailer!) bis zum Namepool-Deckel @ 0x8000. Frueher hatte io.c einen eigenen
 * disk_lib_hw-Zeiger und die Region einen zweiten -> sie haetten sich gegenseitig ueberschrieben.
 * persist=0: nur Platz am aktuellen Ende ausgeben (transientes Ausdrucks-Main), Zeiger bleibt.
 * Rueckgabe: Offset in der Code-Bank, 0xFFFF = Region voll. Gegatet: nur Profile mit einer zweiten
 * Code-Quelle brauchen ihn (Default = budgetneutral). */
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
/* Transiente Ausdrucks-Mains: ABWAERTS-Stapel vom Regions-Deckel (M4-Fund #2: lagen sie im
 * Aufwaerts-Kontinuum, riss jede Wrapper-Luecke die sparse dir_off-Rekonstruktion -> align8
 * verbrannte ~8 Dir-Slots je (lcc-run '(defun ...)) und das Directory war nach 2 Formen voll).
 * Kein Dir-Eintrag, keine Luecke, echte Freigabe nach dem Lauf, verschachtelbar (eval in
 * kompiliertem Code). Persistente Allocs pruefen die Kreuzung (oben). */
uint16_t vm_ext_code_alloc_transient(uint16_t len) {
    uint16_t top = ext_code_tsp ? ext_code_tsp : VM_EXT_CODE_LIMIT, at;
    if (!ext_code_init) vm_ext_code_alloc(0, 0);             /* Watermark lazy initialisieren */
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

/* BOOTFN unabhaengig vom Metadata-Modus definieren (vm_load_embedded_stdlib nutzt es immer). */
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

/* Heap-Literale (String/Liste/Cons) PERMANENT verankern: an die Wertzelle des Halte-Symbols
 * %lit-keep (symval = echter GC-Root). GC_PUSH war FALSCH-permanent: der Rootstack wird von
 * apply/repl zurückgesetzt — bei on-demand-Lib-Loads (im eval-Frame!) verloren die Literale
 * SOFORT ihre Wurzel -> GC recycelte sie -> "vm: type error" in (ide) (B4-Handtest-Fund). */
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
        /* Nicht-Symbol-Heap-Literale (String/Liste/Cons) sind nur vom erw. RAM referenziert (GC-blind)
         * -> permanent rooten. Symbole sind interniert, Immediates brauchen nichts. */
        vm_lit_keep(o);   /* permanent via Halte-Symbol (NICHT Rootstack!) */
        w[0] = (unsigned char)(uint16_t)o; w[1] = (unsigned char)((uint16_t)o >> 8);
        vm_ext_write(w, 2, lisp65_stdlib_bank, (uint16_t)(lisp65_stdlib_off + p->blob_offset));
    }
}
#else
static void vm_resolve_littab_symbols(void) { /* keine Metadaten (Mock-Test): No-op */ }
#endif

/* md_lit_node ist normal BOOTFN (nur der Boot materialisiert Stdlib-Literale). Mit Disk-Libs
 * (Stufe 2) ruft es AUCH der residente Runtime-Lib-Loader nach dem Boot -> dann darf es NICHT im
 * recycelten Boot-Overlay liegen (s. docs/disk-bytecode-libs-design.md, Knackpunkt BOOTFN). */
#if defined(LISP65_DISK_LIBS) && !defined(LISP65_RUNTIME_OVERLAY)
#define MDLITFN
#define MDHELPFN
#else
#define MDLITFN BOOTFN
#define MDHELPFN BOOTFN
#endif

#ifdef LISP65_STDLIB_EXT_METADATA
/* BOOT-ONLY-CODE ins Boot-Overlay (2026-07-02): der komplette Trailer-Loader laeuft genau
 * einmal (vor der REPL, Stack noch flach) — im Overlay hinter .noinit kostet er nach dem
 * Boot KEIN Bank-0-Budget (der Bereich gehoert dann dem Soft-Stack). Setzt das gehaertete
 * Overlay-Linkerscript voraus (scripts/lisp65-mega65-boot-overlay.ld); das PRG-File-Ende
 * bleibt unter der $C000-etherload-Grenze (Footprint-Gate). noinline: LTO darf Overlay-
 * Code NICHT in residente Aufrufer ziehen. */
#ifndef LISP65_PROFILED_BOOT_FASTPATH
/* --- L65M-Trailer-Loader (Option a): Boot-Metadaten direkt aus dem erw. RAM lesen. ---
 * Der `.ext.bin`-Preload legt hinter das Code-Blob einen pointerfreien little-endian-Trailer
 * (Vertrag: tools/host-lisp/bytecode_p0_stdlib.py, _build_ext_metadata): Header 38 B
 * (Magic "L65M", Version 1, Zaehler + Sektions-Offsets relativ zum Trailer-Start), dann
 * entries (8 B: name_off u16, bank u8, 0, off u16, len u16), literal_index (u16),
 * literal_nodes (10 B: kind u8, 0, value i16, first u16, count u16, name_off u16),
 * literal_patches (4 B: blob_offset u16, node u16), strings (NUL-terminiert; 0xFFFF = kein Name).
 * Damit traegt das PRG weder Embed-Tabelle noch littab-Metadaten -> kein Boot-Overlay,
 * kein $C000-File-Problem, Heap-Budget frei. Alles kalter Boot-Pfad: viele kleine DMA-Reads ok. */
#include "stdlib-p0.h"   /* LISP65_BC_LIT_*-Kind-Codes (ungegated im generierten Header) */

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
    vm_code_load(lisp65_stdlib_bank, (uint16_t)(md_base + off), len, (uint8_t *)dst);
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
        vm_lit_keep(o);   /* permanent via Halte-Symbol (NICHT Rootstack!) */
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
/* --- Runtime-Lib-Loader (Stufe 2; docs/disk-bytecode-libs-design.md) ---
 * Registriert eine bereits nach Bank 5 (lisp65_stdlib_bank) gestagete Bytecode-Lib: Blob @ code_base,
 * L65M-Trailer @ md_at (beide within-bank-Offsets). RESIDENT (nicht BOOTFN!): laeuft nach dem Boot,
 * wenn das Boot-Overlay bereits Soft-Stack ist. Spiegelt vm_load_ext_metadata, ABER:
 *  - relokiert je Eintrag/Patch um code_base (Lib-Metadaten tragen BLOB-RELATIVE 0-Offsets),
 *  - richtet dir_n vorher auf die 8er-Block-Grenze aus (vm_dir_align8) -> Lib = eigener Block,
 *  - forciert Bank = lisp65_stdlib_bank (Lib liegt kontinuierlich hinter dem Stdlib-Blob).
 * Ohne Runtime-Overlay nutzt der direkte Host-/Referenzpfad weiterhin md_lit_node/md_read/md_name.
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
        vm_lit_keep(o);   /* permanent via Halte-Symbol (NICHT Rootstack!) */
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

/* --- Plattform-DMA (mega65). NUR im Geraete-Build (LISP65_EMBED_DMA); Host-Tests liefern eigene
 *     vm_code_load/vm_ext_write. Identisches F018-DMA-Muster wie die HW-bewiesenen Streaming-Tests. --- */
#ifdef LISP65_EMBED_DMA
/* NICHT static + used: garantierter Assembler-Symbolname fuer den registerfreien Trigger
 * unten (die Inline-Asm-Referenz ist fuer LTO unsichtbar). */
__attribute__((used)) unsigned char vm_dma_list[12];
#ifdef LISP65_DMA_PROF
/* Diagnose-Naht (2026-07-03): DMA-Jobs nach Klasse zaehlen — die Geraete-Waehrung des
 * Perf-Befunds (Call-Return-Reloads). Nur mit -DLISP65_DMA_PROF im Binary. */
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
    vm_dma((uint16_t)(SYMPOOL_EXT_OFF + off), SYMPOOL_EXT_BANK, (uint16_t)(uintptr_t)dst, 0, len);
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
    vm_dma((uint16_t)(SYMVAL_EXT_OFF + i * 2u), SYMVAL_EXT_BANK, (uint16_t)(uintptr_t)&v, 0, 2);
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
    vm_dma((uint16_t)(NAMEOFF_EXT_OFF + i * 2u), NAMEOFF_EXT_BANK, (uint16_t)(uintptr_t)&v, 0, 2);
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
    vm_dma((uint16_t)(SYMFN_EXT_OFF + i * 2u), SYMFN_EXT_BANK, (uint16_t)(uintptr_t)&v, 0, 2);
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
