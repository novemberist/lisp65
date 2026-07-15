/* lisp65 — Symbole (interniert, Lane K)
 * Phase 1: lineare Symboltabelle mit Namens-Zeigern (klein, ausreichend).
 */
#include "symbol.h"
#include "mem.h"
#include "interrupt.h"


/* Index/nsym sind uint16 -> bis zu 65534 Symbole moeglich (Limit = MAX_SYM/NAMEPOOL).
 * Default klein gehalten, damit die c64-Smoke-Builds nicht im BSS ueberlaufen; der
 * mega65-/Voll-Lib-Build hebt per -DMAX_SYM / -DNAMEPOOL an (siehe docs/kernel-abi.md). */
#ifndef MAX_SYM
#define MAX_SYM   384
#endif
#ifndef NAMEPOOL
#define NAMEPOOL  3072
#endif
#if MAX_SYM > 0x1000
#error "MAX_SYM kollidiert mit dem SYMI-Immediate-Fenster (obj.h: Basis 0x7000, 4096 Indizes)"
#endif
/* nameoff ist jetzt ein VOLLER 16-Bit-Offset (Laenge liegt separat in namelen[]) -> NAMEPOOL
 * bis 65535 moeglich. Reale Grenze: die EXT-Layout-Pruefung in vm_embed.c (Bank-5-Fit) und das
 * SYMI-Fenster (MAX_SYM<=4096). Wachstum ist Bank-0-frei (Namepool liegt in EXT via SYMPOOL_EXT). */
#if NAMEPOOL > 65535
#error "NAMEPOOL > 65535: nameoff-Offset ist 16 Bit (uint16_t)"
#endif
/* Stufe 2b: internierte Symbole sind SYMI-IMMEDIATES (obj.h) — keine Heap-Zelle, kein
 * symobj[]-Array mehr; stattdessen traegt nameoff[] den Namens-Offset je Index (gleiche
 * .bss-Groesse wie das alte symobj[], aber ~174 Boot-Heap-Zellen frei). gensyms bleiben
 * T_SYM-Zellen (a=Index, b=Namens-Offset) — die Accessoren unten nehmen beide Formen. */
/* nameoff[i]: Bits 0-11 = Pool-Offset (NAMEPOOL<=4096), Bits 12-15 = Namenslaenge (Cap 15).
 * Der Laengen-Nibble ist der DMA-FREIE Vorfilter fuer intern: die lineare Suche machte
 * sonst je Kandidat einen 34-Byte-DMA-Read aus dem EXT-Sympool — bei ~300 Symbolen war
 * JEDER Reader-Token ~1/3 Sekunde HW-Zeit (Geraetemessung 2026-07-02). */
/* Split (2026-07-04): Laenge (Vorfilter) getrennt vom Offset. namelen[i] = volle Laenge 0..33,
 * bleibt Bank 0 (DMA-freier Vorfilter -> Boot-O(nsym^2) bleibt schnell). nameoff[i] = reiner
 * Offset (jetzt volle 16 Bit): mit -DLISP65_NAMEOFF_EXT nach EXT (Naht nameoff_get/set: Geraet=DMA,
 * Default/Host=Bank-0-Array). Netto -1 B/Symbol Bank-0 (nameoff 2 B -> namelen 1 B); zugleich
 * loest der 16-Bit-Offset perspektivisch die 4096-Namepool-Wand. docs/symbol-table-ext-design.md. */
/* 4-BIT-VORFILTER (2026-07-06): min(len,15) statt voller Laenge — halbiert das Bank-0-Array
 * (MAX_SYM/2 statt MAX_SYM Bytes; bei 560 Symbolen -280 B). Filterguete praktisch identisch:
 * Namen <15 Zeichen (fast alle) filtern exakt; laengere teilen sich den 15er-Eimer und kosten
 * schlimmstenfalls einen zusaetzlichen 34-B-DMA-Vergleich (selten). Konstante Shifts (>>4,<<4)
 * — der Miscompile-Bug betraf nur VARIABLE Shifts (markbit-Saga, mem.c). */
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
/* Funktions-Zelle (Lisp-2). Standard: Bank-0-Array, weil dir_find bei jedem CALL liest.
 * Workbench-Skalierung (2026-07-08): mit -DLISP65_SYMFN_EXT liegt die Tabelle in EXT.
 * Das ist ein bewusstes MVP-Budget-Ventil: CALL-Aufloesung kostet dann DMA, aber die volle
 * Workbench passt wieder. Eine Pointer-Bitmap verhindert, dass der GC die vielen
 * BCODE-Immediate-Zellen per DMA liest. */
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

/* Namens-Pool hinter einer Zugriffs-Naht: intern kopiert den Namen, damit Aufrufer (z. B. der
 * Reader aus einem fluechtigen Token-Puffer) keinen stabilen Speicher liefern muss. Der Pool ist
 * KALT (nur intern/symname, nach dem eq-Dispatch-Umbau NICHT im heissen eval-Pfad). Standard:
 * Bank-0-Array. Mit -DLISP65_SYMPOOL_EXT liegt er im erw. RAM (Bank 0 spart NAMEPOOL Bytes);
 * die Naht (sympool_read/write) macht dann DMA. Der Offset-basierte Code ist immer aktiv ->
 * host-testbar unabhaengig von der physischen Lage. */
#ifdef LISP65_SYMPOOL_EXT
/* Geraet/erw. RAM: Naht MUSS vom Build bereitgestellt werden (DMA); Host-Test simuliert. */
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

/* SYM_NAME_MAX = interner Deckel aus new_symbol (33) + NUL. Der Reader-Vertrag
 * bleibt separat bei 31 Zeichen. Ein Name-Vergleich/-Lesen ist
 * EIN Bulk-Transfer in einen Bank-0-Scratch (im EXT-Modus: eine Bulk-DMA statt 1 DMA/Byte —
 * Boot macht O(nsym^2) Vergleiche, byteweise waere das katastrophal). */
#define SYM_NAME_MAX 34
char sym_name_scratch[SYM_NAME_MAX];

/* Namen aus dem Pool mit einem C-String vergleichen (0 = gleich): 1 Bulk-Read + lokaler strcmp. */
static int sympool_streq(uint16_t off, const char *name) {
    char buf[SYM_NAME_MAX]; uint16_t i;
    sympool_read(off, buf, SYM_NAME_MAX);
    for (i = 0; i < SYM_NAME_MAX; i++) {
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
    while (name[len] && len <= 33) len++;
    if (len > 33 || nsym >= MAX_SYM || (uint16_t)(len + 1) > (uint16_t)(NAMEPOOL - npool)) {
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
    while (name[len] && len <= 33) len++;
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

/* symtab-Index aus beiden Symbolformen (SYMI-Immediate | gensym-T_SYM-Zelle). */
/* gensym-Zellen koennen mit LISP65_EXT_HEAP im erweiterten RAM liegen -> Accessoren
 * (cell_a/cell_b) statt direktem CELL()/heap[] (kalter Pfad, Inline-Zwang unnoetig). */
static uint16_t sidx(obj s) { return IS_SYMI(s) ? SYMI_IDX(s) : (uint16_t)cell_a(s); }

/* gensym: frisches UNINTERNIERTES Symbol als eigene Heap-Zelle -> der GC raeumt es ab,
 * sobald die Makro-Expansion es nicht mehr referenziert (KEIN permanenter Tabellen-Leak,
 * KEIN Aliasing). Die Zelle teilt sich einen EINZIGEN gueltigen symtab-Index (das
 * reservierte "#:g"-Symbol) -> die heissen Accessoren brauchen KEINEN Sonderfall/Guard
 * (der 0xFF-Guard hatte den 45gs02 zum Absturz gebracht). Identitaet = die Zelle selbst
 * (eq); globale Wert-/Funktionszellen werden fuer Gensyms nie genutzt (nur Env-Bindung). */
obj gensym(void) {
    static obj tag = NIL;
    obj o;
    if (tag == NIL) tag = intern("#:g");
    o = alloc(T_SYM);
    cell_set_a(o, (obj)SYMI_IDX(tag));            /* gueltiger, geteilter Index */
    cell_set_b(o, (obj)NOFF(SYMI_IDX(tag)));      /* geteilter Name ("#:g") fuer symname/print */
    return o;
}

/* Namen in einen kleinen Bank-0-Scratch holen (KALT: nur printer + VM-Diagnose). Nicht
 * reentrant (static buf) — die Nutzer rufen sequenziell + kopieren sofort. */
const char *symname(obj o) {
    uint16_t off = IS_SYMI(o) ? NOFF(SYMI_IDX(o)) : (uint16_t)cell_b(o);
    sympool_read(off, sym_name_scratch, SYM_NAME_MAX);
    sym_name_scratch[SYM_NAME_MAX - 1] = 0;
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
