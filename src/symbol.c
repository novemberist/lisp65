/* lisp65 — Symbole (interniert, Lane K)
 * Phase 1: lineare Symboltabelle mit Namens-Zeigern (klein, ausreichend).
 */
#include "symbol.h"
#include "mem.h"
#include "interrupt.h"
#include "c2_kernal_layout.h"


/* Index and nsym are uint16 -> up to 65534 symbols are possible (the limit is MAX_SYM/NAMEPOOL).
 * Kept small by default so the c64 smoke builds do not overflow .bss; the mega65 / full-library
 * build raises it with -DMAX_SYM / -DNAMEPOOL (see docs/kernel-abi.md). */
#ifndef MAX_SYM
#define MAX_SYM   384
#endif
#ifndef NAMEPOOL
#define NAMEPOOL  3072
#endif
#if MAX_SYM > 0x1000
#error "MAX_SYM collides with the SYMI immediate window (obj.h: base 0x7000, 4096 indices)"
#endif
/* nameoff is now a FULL 16-bit offset (the length lives separately in namelen[]) -> NAMEPOOL up to
 * 65535 is possible. The real limits are the EXT layout check in vm_embed.c (bank-5 fit) and the
 * SYMI window (MAX_SYM<=4096). Growth is bank-0-free (the name pool lives in EXT via SYMPOOL_EXT). */
#if NAMEPOOL > 65535
#error "NAMEPOOL > 65535: the nameoff offset is 16 bits (uint16_t)"
#endif
/* Stage 2b: interned symbols are SYMI IMMEDIATES (obj.h) — no heap cell and no symobj[] array any
 * more; instead nameoff[] carries the name offset per index (the same .bss size as the old symobj[],
 * but about 174 boot heap cells freed). Gensyms remain T_SYM cells (a=index, b=name offset) — the
 * accessors below take both forms. */
/* nameoff[i]: bits 0-11 = pool offset (NAMEPOOL<=4096), bits 12-15 = name length (cap 15).
 * The length nibble is the DMA-FREE prefilter for intern: otherwise the linear search did a
 * 34-byte DMA read from the EXT symbol pool per candidate — at about 300 symbols EVERY reader
 * token cost roughly a third of a second of device time (device measurement 2026-07-02). */
/* Split (2026-07-04): the length (prefilter) is separated from the offset. namelen[i] = the full
 * length 0..33, staying in bank 0 (a DMA-free prefilter -> the boot's O(nsym^2) stays fast).
 * nameoff[i] = the pure offset (now a full 16 bits): with -DLISP65_NAMEOFF_EXT it moves to EXT
 * (seam nameoff_get/set: device=DMA, default/host=bank-0 array). Net -1 byte of bank 0 per symbol
 * (nameoff 2 B -> namelen 1 B); at the same time the 16-bit offset eventually removes the 4096-byte
 * name-pool wall. docs/symbol-table-ext-design.md. */
/* 4-BIT PREFILTER (2026-07-06): min(len,15) instead of the full length — halves the bank-0 array
 * (MAX_SYM/2 instead of MAX_SYM bytes; -280 B at 560 symbols). The filter quality is practically
 * identical: names under 15 characters (almost all of them) filter exactly; longer ones share the
 * 15 bucket and at worst cost one extra 34-byte DMA comparison (rare). The shifts are constant
 * (>>4, <<4) — the miscompile bug affected only VARIABLE shifts (the markbit saga, mem.c). */
static uint8_t      namelen4[(MAX_SYM + 1) / 2];
#define NLEN4_CAP(l)  ((uint8_t)((l) < 15 ? (l) : 15))
static uint8_t nlen4_get(uint16_t i) {
    return (uint8_t)((i & 1) ? (namelen4[i >> 1] >> 4) : (namelen4[i >> 1] & 0x0F));
}
static void nlen4_set(uint16_t i, uint8_t l) {
    uint8_t *p = &namelen4[i >> 1];
    if (i & 1) *p = (uint8_t)((*p & 0x0F) | (uint8_t)(l << 4));
    else       *p = (uint8_t)((*p & 0xF0) | l);
}
#ifdef LISP65_NAMEOFF_EXT
uint16_t nameoff_get(uint16_t i);
void     nameoff_set(uint16_t i, uint16_t off);
#else
static uint16_t     nameoff_arr[MAX_SYM];
static uint16_t nameoff_get(uint16_t i)             { return nameoff_arr[i]; }
static void     nameoff_set(uint16_t i, uint16_t o) { nameoff_arr[i] = o; }
#endif
#define NOFF(i)  nameoff_get(i)
/* symval (globale Wert-Zelle, Lisp-2) ist KALT fuer Bytecode (nur Interpreter+GC lesen es) ->
 * mit -DLISP65_SYMVAL_EXT ins erw. RAM (spart MAX_SYM*2 B Bank-0; docs/symbol-table-ext-design.md).
 * Naht symval_get/set: Geraet=DMA (vm_embed.c stellt sie bereit), Default/Host=Bank-0-Array
 * (host-testbar). Der Offset-basierte Code ist immer aktiv. new_symbol initialisiert jede Zelle
 * auf NIL (EXT ist nicht zero-init). */
#ifdef LISP65_SYMVAL_EXT
obj  symval_get(uint16_t i);
void symval_set(uint16_t i, obj v);
#else
static obj          symval[MAX_SYM];    /* Wert-Zelle (Lisp-2), Default NIL    */
static obj  symval_get(uint16_t i)        { return symval[i]; }
static void symval_set(uint16_t i, obj v) { symval[i] = v; }
#endif
/* Function cell (Lisp-2). Default: a bank-0 array, because dir_find reads it on every CALL.
 * Workbench scaling (2026-07-08): with -DLISP65_SYMFN_EXT the table lives in EXT. That is a
 * deliberate MVP budget valve: CALL resolution then costs DMA, but the full workbench fits again.
 * A pointer bitmap keeps the GC from reading the many BCODE immediate cells over DMA. */
#ifdef LISP65_SYMFN_EXT
obj  symfn_ext_get(uint16_t i);
void symfn_ext_set(uint16_t i, obj v);
static uint8_t  symfnptr[(MAX_SYM + 7) / 8];
static obj  symfn_get(uint16_t i)        { return symfn_ext_get(i); }
static void symfn_set(uint16_t i, obj v) { symfn_ext_set(i, v); }
#else
static obj          symfn[MAX_SYM];
static obj  symfn_get(uint16_t i)        { return symfn[i]; }
static void symfn_set(uint16_t i, obj v) { symfn[i] = v; }
#endif
static uint8_t      symbnd[(MAX_SYM + 7) / 8];  /* Bitmap: 1 = Wert-Zelle gebunden (spart ~200 B .bss) */
/* Bit-Lookup statt variablem Shift: `1u << (i&7)` war auf dieser Toolchain nachweislich
 * miscompiled (Saga: markbit-Bug) — gleiches sicheres Muster wie mem.c. */
static const uint8_t bndbit[8] = {1,2,4,8,16,32,64,128};
static uint16_t     nsym = 0;
static uint16_t     npool = 0;

/* Name pool behind an access seam: intern copies the name, so callers (for instance the reader
 * working from a transient token buffer) need not provide stable storage. The pool is COLD (only
 * intern/symname; since the eq-dispatch rework it is NOT in the hot eval path). Default: a bank-0
 * array. With -DLISP65_SYMPOOL_EXT it lives in extended RAM (bank 0 saves NAMEPOOL bytes) and the
 * seam (sympool_read/write) then does DMA. The offset-based code is always active -> host-testable
 * regardless of the physical location. */
#ifdef LISP65_SYMPOOL_EXT
/* Device / extended RAM: the seam MUST be provided by the build (DMA); the host test simulates it. */
void sympool_read(uint16_t off, char *dst, uint16_t len);
void sympool_write(uint16_t off, const char *src, uint16_t len);
#else
static char namepool[NAMEPOOL];
static void sympool_read(uint16_t off, char *dst, uint16_t len) {   /* OOB-sicher (clamp -> 0) */
    uint16_t i; for (i = 0; i < len; i++) dst[i] = (uint16_t)(off + i) < NAMEPOOL ? namepool[(uint16_t)(off + i)] : 0;
}
static void sympool_write(uint16_t off, const char *src, uint16_t len) {
    uint16_t i; for (i = 0; i < len; i++) namepool[(uint16_t)(off + i)] = src[i];
}
#endif

/* The reader contract remains separately capped at 31 characters.  Name
 * comparison and lookup use one bulk transfer into a Bank-0 scratch buffer;
 * EXT mode therefore performs one DMA instead of one DMA per byte. */
char LISP65_C2_FIXED_BANK0("sym_name_scratch")
    sym_name_scratch[LISP65_SYMBOL_NAME_BUFFER];

#ifdef LISP65_V200_SYMBOL22_FIRST_FAULT
/* The first-fault helper is handwritten because the MOS backend cannot
 * materialize the caller's return address through __builtin_return_address.
 * It returns directly into the existing numeric-abort edge, retaining that
 * path's active/no-toplevel behavior without carrying a second abort tail. */
extern void lisp65_symbol22_latch_capture(void);
#endif

/* Namen aus dem Pool mit einem C-String vergleichen (0 = gleich): 1 Bulk-Read + lokaler strcmp. */
static int sympool_streq(uint16_t off, const char *name) {
    char buf[LISP65_SYMBOL_NAME_BUFFER]; uint16_t i;
    sympool_read(off, buf, LISP65_SYMBOL_NAME_BUFFER);
    for (i = 0; i < LISP65_SYMBOL_NAME_BUFFER; i++) {
        if (buf[i] != name[i]) return 0;
        if (buf[i] == 0) return 1;
    }
    return 1;   /* laengere Namen sind durch den internen 33-Zeichen-Deckel ausgeschlossen */
}

/* Legt ein neues Symbol an (ohne Dedup-Suche); kopiert den Namen in den Pool.
 * Bei voller Tabelle/Pool: sauberer Abbruch statt Speicher-Korruption. */
static obj new_symbol(const char *name) {
    /* strnlen mit Deckel: ein Muell-/unterminierter Name darf NIE zu einem 64K-strcpy
     * fuehren. Vorher wrappte `npool + len + 1` bei len~0xFFFF auf npool -> Check bestand
     * -> strcpy walzte den Speicher (HW-Diagnose 2026-07-01). Reader-Tokens sind <=31. */
    uint16_t len = 0, off;
    while (name[len] && len <= LISP65_SYMBOL_NAME_MAX) len++;
    if (len > LISP65_SYMBOL_NAME_MAX || nsym >= MAX_SYM
        || (uint16_t)(len + 1) > (uint16_t)(NAMEPOOL - npool)) {
#ifdef LISP65_V200_SYMBOL22_FIRST_FAULT
        lisp65_symbol22_latch_capture();
#endif
        lisp_abort_static(LISP65_ERR_TOO_MANY_SYMBOLS, "too many symbols");
        return NIL;                      /* falls kein Toplevel aktiv (Host/Smoke) */
    }
    off = npool;
    sympool_write(off, name, (uint16_t)(len + 1));   /* Name inkl. NUL in den Pool */
    npool = (uint16_t)(npool + len + 1);

    nlen4_set(nsym, NLEN4_CAP(len));     /* 4-Bit-Vorfilter (Bank 0) */
    nameoff_set(nsym, off);              /* reiner Offset (ggf. EXT) */
    symval_set(nsym, NIL);               /* Wert-Zelle explizit NIL (EXT ist nicht zero-init) */
    symfn_set(nsym, NIL);                /* Funktions-Zelle explizit NIL (EXT ist nicht zero-init) */
    return MK_SYMI(nsym++);              /* Immediate: keine Heap-Zelle */
}

uint8_t sym_lookup(const char *name, obj *out) {
    uint16_t i, len = 0;
    while (name[len] && len <= LISP65_SYMBOL_NAME_MAX) len++;
    for (i = 0; i < nsym; i++) {
        if (nlen4_get(i) != NLEN4_CAP(len)) continue;  /* 4-Bit-Laengen-Vorfilter: kein DMA (Bank 0) */
        if (sympool_streq(NOFF(i), name)) {
            if (out) *out = MK_SYMI(i);
            return 1;
        }
    }
    return 0;
}

obj intern(const char *name) {
    obj found;
    if (sym_lookup(name, &found)) return found;
    return new_symbol(name);
}

/* The symtab index from either symbol form (SYMI immediate | gensym T_SYM cell). */
/* With LISP65_EXT_HEAP gensym cells can live in extended RAM -> use the accessors
 * (cell_a/cell_b) instead of CELL()/heap[] directly (cold path, no need to force inlining). */
static uint16_t sidx(obj s) { return IS_SYMI(s) ? SYMI_IDX(s) : (uint16_t)cell_a(s); }

/* gensym: a fresh UNINTERNED symbol as its own heap cell -> the GC reclaims it as soon as the
 * macro expansion stops referencing it (NO permanent table leak, NO aliasing). The cell shares a
 * SINGLE valid symtab index (the reserved "#:g" symbol) -> the hot accessors need NO special case
 * or guard (the 0xFF guard had crashed the 45gs02). Identity is the cell itself (eq); global value
 * and function cells are never used for gensyms (only environment bindings). */
obj gensym(void) {
    static obj tag = NIL;
    obj o;
    if (tag == NIL) tag = intern("#:g");
    o = alloc(T_SYM);
    cell_set_a(o, (obj)SYMI_IDX(tag));            /* a valid, shared index */
    cell_set_b(o, (obj)NOFF(SYMI_IDX(tag)));      /* shared name ("#:g") for symname/print */
    return o;
}

/* Fetch a name into a small bank-0 scratch buffer (COLD: printer and VM diagnostics only).
 * Not reentrant (a static buffer) — callers invoke it sequentially and copy immediately. */
const char *symname(obj o) {
    uint16_t off = IS_SYMI(o) ? NOFF(SYMI_IDX(o)) : (uint16_t)cell_b(o);
    sympool_read(off, sym_name_scratch, LISP65_SYMBOL_NAME_BUFFER);
    sym_name_scratch[LISP65_SYMBOL_NAME_BUFFER - 1u] = 0;
    return sym_name_scratch;
}

obj  sym_value(obj s)              { return symval_get(sidx(s)); }
void set_sym_value(obj s, obj v)   { uint16_t i = sidx(s); symval_set(i, v); symbnd[i >> 3] |= bndbit[i & 7u]; }
uint8_t sym_boundp(obj s)          { uint16_t i = sidx(s); return (symbnd[i >> 3] & bndbit[i & 7u]) != 0; }
obj  sym_function(obj s)           { return symfn_get(sidx(s)); }
void set_sym_function(obj s, obj v){
    uint16_t i = sidx(s);
    symfn_set(i, v);
#ifdef LISP65_SYMFN_EXT
    if (IS_PTR(v)) symfnptr[i >> 3] |= bndbit[i & 7u];
    else           symfnptr[i >> 3] &= (uint8_t)~bndbit[i & 7u];
#endif
}
uint8_t sym_function_ptrp(obj s) {
    uint16_t i = sidx(s);
#ifdef LISP65_SYMFN_EXT
    return (symfnptr[i >> 3] & bndbit[i & 7u]) != 0;
#else
    return IS_PTR(symfn_get(i));
#endif
}

uint16_t sym_count(void) { return nsym; }
uint16_t sym_pool_used(void) { return npool; }   /* Diagnose/Budget */
uint16_t sym_max(void) { return MAX_SYM; }        /* Symbol-Cap (Budget-Anzeige, O(1)) */
uint16_t sym_pool_capacity(void) { return NAMEPOOL; }
obj      sym_nth(uint16_t i) { return MK_SYMI(i); }
