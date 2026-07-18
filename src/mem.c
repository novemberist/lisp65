/* lisp65 — Speicher/Allocator + GC (Lane K)
 * Mark-Sweep über einen festen Zellen-Pool mit Freelist und präzisem Shadow-Root-Stack.
 * GC läuft ausschließlich in alloc(), wenn die Freelist leer ist. Roots:
 *   (1) gc_rootstack (von eval/reader gepushte lebende obj),
 *   (2) alle internierten Symbole + ihre Wert-/Funktions-Zellen (permanent).
 * Mit -DGC_STRESS wird vor jeder Allokation ein GC erzwungen (Root-Lücken-Test).
 */
#include "mem.h"
#include "symbol.h"

#ifdef LISP65_STAGED_BOOT_OVERLAY
#define WORKBENCH_BOOTFN __attribute__((section(".lisp65_boot"), noinline, used))
#else
#define WORKBENCH_BOOTFN
#endif
#if defined(LISP65_STAGED_BOOT_OVERLAY) && defined(LISP65_RUNTIME_OVERLAY)
#define WORKBENCH_FREEZEFN \
    __attribute__((section(".lisp65_rt_boot_02"), noinline, used))
#else
#define WORKBENCH_FREEZEFN WORKBENCH_BOOTFN
#endif

#ifdef LISP65_HEARTBEAT   /* Diagnose: Schleifen-Ticker auf Bildschirm-RAM (Zeichen flackern) */
#define HB(i) (++*(volatile unsigned char *)(0x0800 + (i)))
#define LA(c) (*(volatile unsigned char *)(0x0800 + 50) = (unsigned char)(c))
#else
#define HB(i) ((void)0)
#define LA(c) ((void)0)
#endif


Cell heap[HEAP_CELLS];

#ifdef LISP65_EXT_HEAP
/* Erweiterter Heap-Ueberlauf: flach in EXT_BANK, 8-Byte-Zellen (type@0, a@2, b@4),
 * Zugriff ausschliesslich via F018-DMA — der EINZIGE Weg, der erweitertes RAM zuverlaessig in
 * beide Richtungen erreicht (zp-indirekt/MAP-Read/Flat scheitern; siehe
 * docs/mega65-extram-access.md). Nur dieser kalte Pfad benutzt DMA; heisser Bank-0-Zweig inline.
 * BANK 4 (nicht 5!): Bank 5 gehoert inzwischen dem Stdlib-Blob (ab $50000, .ext.bin-Preload)
 * und dem Symbol-Namepool (ab $58000, LISP65_SYMPOOL_EXT) — der alte $50000-Default haette
 * beim ersten Ueberlauf das Code-Blob zerschrieben. Bank 4 ($40000..$4FFFF) ist frei:
 * EXT_CELLS*8 <= 64 KB. Host (kein __mos__): RAM-Simulation, macht die GC-Logik host-testbar. */
#define EXT_OFF(i) ((uint16_t)(((i) - HEAP_CELLS) * 8))
#ifndef __mos__
/* Host-Simulation: gleiche 8-Byte-Zellen in einem Array (GC-/Ueberlauf-Logik host-testbar). */
static uint8_t ext_sim[(uint32_t)EXT_CELLS * 8u];
uint8_t ext_type(uint16_t i){ return ext_sim[(uint32_t)EXT_OFF(i)]; }
obj     ext_a(uint16_t i)   { uint32_t o=(uint32_t)EXT_OFF(i)+2; return (obj)(uint16_t)(ext_sim[o]|((uint16_t)ext_sim[o+1]<<8)); }
obj     ext_b(uint16_t i)   { uint32_t o=(uint32_t)EXT_OFF(i)+4; return (obj)(uint16_t)(ext_sim[o]|((uint16_t)ext_sim[o+1]<<8)); }
void    ext_set_type(uint16_t i,uint8_t t){ ext_sim[(uint32_t)EXT_OFF(i)]=t; }
void    ext_set_a(uint16_t i,obj v){ uint32_t o=(uint32_t)EXT_OFF(i)+2; ext_sim[o]=(uint8_t)(uint16_t)v; ext_sim[o+1]=(uint8_t)((uint16_t)v>>8); }
void    ext_set_b(uint16_t i,obj v){ uint32_t o=(uint32_t)EXT_OFF(i)+4; ext_sim[o]=(uint8_t)(uint16_t)v; ext_sim[o+1]=(uint8_t)((uint16_t)v>>8); }
/* Host: Disk-Scratch-Simulation (io.c-Disk ist geraet-only; hier nur fuer eventuelle Host-Tests). */
static uint8_t ext_disk_sim[256u + DISK_EXT_FILE_MAX];   /* Dir-Sektor + Datei-Fenster */
void    ext_disk_put(uint16_t off, uint8_t v){ if (off < sizeof(ext_disk_sim)) ext_disk_sim[off] = v; }
uint8_t ext_disk_get(uint16_t off){ return off < sizeof(ext_disk_sim) ? ext_disk_sim[off] : 0; }
void ext_disk_read(uint16_t off, uint8_t *dst, uint16_t len){
    uint16_t i; for (i = 0; i < len; i++) dst[i] = ext_disk_get((uint16_t)(off + i));
}
#else
/* NICHT static + used: garantierter Assembler-Symbolname fuer den registerfreien Trigger
 * (identische Haertung wie vm_dma_list in vm_embed.c). */
__attribute__((used)) unsigned char ext_dl[12];
static uint16_t ext_stg;
static uint8_t  ext_stg1;
#ifdef LISP65_DMA_PROF
uint16_t dma_cell = 0;   /* EXT-Zell-Zugriffe (Diagnose-Naht, s. vm_embed.c) */
#endif
static void ext_dma(uint16_t sa,uint8_t sb,uint16_t da,uint8_t db,uint16_t n){
#ifdef LISP65_DMA_PROF
    dma_cell++;
#endif
    ext_dl[0]=0; ext_dl[1]=(uint8_t)n; ext_dl[2]=(uint8_t)(n>>8);
    ext_dl[3]=(uint8_t)sa; ext_dl[4]=(uint8_t)(sa>>8); ext_dl[5]=sb;
    ext_dl[6]=(uint8_t)da; ext_dl[7]=(uint8_t)(da>>8); ext_dl[8]=db;
    ext_dl[9]=0; ext_dl[10]=0; ext_dl[11]=0;
    /* REGISTERFREIER Trigger + "memory"-Clobber — EXAKT wie vm_dma (vm_embed.c). Die alte
     * Fassung ("r"-Operanden, KEIN memory-Clobber) erlaubte LTO, die ext_dl-Stores HINTER
     * den Trigger zu schieben -> DMA las eine halb geschriebene Liste -> wilde Transfers.
     * HW-Symptom (2026-07-02): KERNAL-CLR loeschte nicht mehr (Editor-Zustand zerschossen),
     * waehrend Zell-Daten zufaellig intakt blieben (gc-stress gruen). */
    __asm__ volatile(
        "lda #0\n\t"
        "sta $d702\n\t"
        "lda #mos16hi(ext_dl)\n\t"
        "sta $d701\n\t"
        "lda #mos16lo(ext_dl)\n\t"
        "sta $d700\n\t"
        ::: "a", "memory");
}
uint8_t ext_type(uint16_t i){ ext_dma(EXT_OFF(i)+0,EXT_BANK,(uint16_t)(uintptr_t)&ext_stg1,0,1); return ext_stg1; }
obj     ext_a(uint16_t i)   { ext_dma(EXT_OFF(i)+2,EXT_BANK,(uint16_t)(uintptr_t)&ext_stg,0,2); return (obj)ext_stg; }
obj     ext_b(uint16_t i)   { ext_dma(EXT_OFF(i)+4,EXT_BANK,(uint16_t)(uintptr_t)&ext_stg,0,2); return (obj)ext_stg; }
void    ext_set_type(uint16_t i,uint8_t t){ ext_stg1=t; ext_dma((uint16_t)(uintptr_t)&ext_stg1,0,EXT_OFF(i)+0,EXT_BANK,1); }
void    ext_set_a(uint16_t i,obj v){ ext_stg=(uint16_t)v; ext_dma((uint16_t)(uintptr_t)&ext_stg,0,EXT_OFF(i)+2,EXT_BANK,2); }
void    ext_set_b(uint16_t i,obj v){ ext_stg=(uint16_t)v; ext_dma((uint16_t)(uintptr_t)&ext_stg,0,EXT_OFF(i)+4,EXT_BANK,2); }
/* Disk-Scratch: EXT_BANK ab $6c00. Das schliesst direkt an die zwei String-Arena-Fenster
 * ($2000..$6bff) an. Physisch bleiben nach dem 256-B-Directory-Sektor 0x9300
 * Datei-Bytes bis Bankende; der Produktpin nutzt dieses Fenster fuer die ladbare IDE-Lib.
 * Byteweise, kalt. */
void    ext_disk_put(uint16_t off, uint8_t v){ ext_stg1 = v; ext_dma((uint16_t)(uintptr_t)&ext_stg1, 0, (uint16_t)(DISK_EXT_BASE + off), EXT_BANK, 1); }
uint8_t ext_disk_get(uint16_t off){ ext_dma((uint16_t)(DISK_EXT_BASE + off), EXT_BANK, (uint16_t)(uintptr_t)&ext_stg1, 0, 1); return ext_stg1; }
void ext_disk_read(uint16_t off, uint8_t *dst, uint16_t len){
    if (len) ext_dma((uint16_t)(DISK_EXT_BASE + off), EXT_BANK, (uint16_t)(uintptr_t)dst, 0, len);
}
#ifdef LISP65_DISK_LIBS
/* Disk-Lib-Staging (Stufe 2): Blob+Trailer aus dem Disk-Scratch (EXT_BANK @ DISK_EXT_BASE+scratch_off)
 * in EINEM gehaerteten DMA nach (dbank, doff) kopieren — EXT->EXT, kein Bank-0-Umweg. n bis 64 KB. */
void    ext_disk_stage(uint16_t scratch_off, uint8_t dbank, uint16_t doff, uint16_t n){
    ext_dma((uint16_t)(DISK_EXT_BASE + scratch_off), EXT_BANK, doff, dbank, n);
}
#endif
#endif /* __mos__ */
#endif

static obj     freelist = NIL;
#ifdef LISP65_EXT_HEAP
/* Hoechster je vergebener Zellindex: der Sweep muss nur bis hier neu einfaedeln — die
 * NIE benutzte EXT-Region behaelt ihre jungfraeuliche mem_init-Kette (Zelle i -> i+1).
 * Ohne das kostete JEDER GC ~EXT_CELLS DMA-Writes (4096!), auch bei rein heisser Last —
 * auf HW der Grossteil der Tipp-Traegheit (51 GCs je 200 Editor-Zeichen). */
static uint16_t alloc_high = 0;
/* FROZEN-BOOT-REGION (2026-07-02): alles bis gc_frozen ist permanent (Boot-Littabs/Stdlib-
 * Bindungen — in sich geschlossen, zeigen nie auf Runtime-Zellen). Der GC ueberspringt die
 * Region komplett: kein Marking-DMA ueber die ~300 Boot-Permanents bei JEDEM Lauf (das
 * waren ~2000 DMAs/GC), kein Sweep dort. Gesetzt einmalig nach dem Stdlib-Boot. */
static uint16_t gc_frozen = 0;
/* Markierungs-Fenster im EXT-Bereich (2026-07-03): der Fixpoint scannte je Pass ALLE
 * EXT-Zellen (bei 3072: ~80 ms JE GC, xemu-$D7FA-Messung — mal 2-3 GCs je Editor-Taste
 * war DAS die "eine Sekunde"). Jetzt merkt sich gc_mark1 min/max markierter EXT-Indizes;
 * nach dem Boot-Freeze ist das Fenster fast immer leer/winzig. */
static uint16_t ext_mark_lo, ext_mark_hi;
static uint16_t allocs_since_gc = 0;   /* Hysterese der Nursery-Politik (s. alloc) */
WORKBENCH_FREEZEFN void gc_freeze_boot(void) {
    uint16_t i;
    gc_frozen = alloc_high;
#ifdef LISP65_STRING_ARENA
    str_arena_freeze();   /* Boot-Literal-String-Bytes als permanentes Arena-Praefix */
#endif
    /* Hot-Zellen (bisher absichtlich NICHT in der Freelist) jetzt an die Spitze:
     * Laufzeit-Allokationen laufen ab hier hot; Rest-EXT bleibt als Ueberlauf dahinter. */
    for (i = HEAP_CELLS - 1; i >= 1; i--) {
        heap[i].a = freelist;
        freelist = (obj)(i << 1);
    }
}
#endif
/* Mark-Bits. Erweiterter Heap: Bitmap (1 Bit/Zelle), damit grosse MAX_CELLS in Bank 0 passen.
 * Default (kein EXT): ein Byte/Zelle (byte-identisch zum bisherigen Verhalten). Mit
 * -DLISP65_MARK_BITMAP auch ohne EXT erzwingbar (Test).
 * WICHTIG: Bit-Lookup-Tabelle statt variabler Shift `1u<<(i&7)` — den generiert der 6502-Backend
 * als Shift-Schleife mit einem Codegen-Fehler, der reproduzierbar den GC/load-source-Pfad crashte
 * (Tabelle laeuft stabil). Siehe docs/mega65-extram-access.md. */
#if defined(LISP65_EXT_HEAP) || defined(LISP65_MARK_BITMAP)
static uint8_t marks[(MAX_CELLS + 7) / 8];
static const uint8_t markbit[8] = {1,2,4,8,16,32,64,128};
#define MARK_GET(i)  ((marks[(uint16_t)(i) >> 3] & markbit[(uint16_t)(i) & 7]) != 0)
#define MARK_SET(i)  (marks[(uint16_t)(i) >> 3] |= markbit[(uint16_t)(i) & 7])
#define MARK_CLEAR() do { uint16_t k_; for (k_ = 0; k_ < (MAX_CELLS + 7) / 8; k_++) marks[k_] = 0; } while (0)
#else
static uint8_t marks[MAX_CELLS];
#define MARK_GET(i)  (marks[(uint16_t)(i)])
#define MARK_SET(i)  (marks[(uint16_t)(i)] = 1)
#define MARK_CLEAR() do { uint16_t k_; for (k_ = 0; k_ < MAX_CELLS; k_++) marks[k_] = 0; } while (0)
#endif

/* Workbench only: keep this mutable root stack outside both resident BSS and
 * the immutable, CRC-bound island payload. Other profiles retain normal BSS. */
#if defined(__mos__) && defined(LISP65_STAGED_BOOT_OVERLAY) && \
    defined(LISP65_RUNTIME_OVERLAY)
typedef char workbench_rootstack_must_have_128_slots[(GC_ROOTS == 128) ? 1 : -1];
__attribute__((section(".lisp65_resident_island_annex.00_before"), aligned(2), used))
volatile uint16_t lisp65_rootstack_canary_before;
__attribute__((section(".lisp65_resident_island_annex.01_stack"), aligned(2), used))
obj gc_rootstack[GC_ROOTS];
__attribute__((section(".lisp65_resident_island_annex.02_after"), aligned(2), used))
volatile uint16_t lisp65_rootstack_canary_after;
#else
obj gc_rootstack[GC_ROOTS];
#endif
uint16_t gc_rootsp = 0;

void mem_init(void) {
    uint16_t i;
    freelist = NIL;
#if defined(__mos__) && defined(LISP65_STAGED_BOOT_OVERLAY) && \
    defined(LISP65_RUNTIME_OVERLAY)
    lisp65_rootstack_canary_before = 0x65a5u;
    lisp65_rootstack_canary_after = 0xa565u;
#endif
    gc_rootsp = 0;
#ifdef LISP65_EXT_HEAP
    /* EXT-FIRST (2026-07-02): der Boot vergibt ERWEITERTE Zellen — die Boot-Permanents
     * (Littabs, Prim-Zellen, ~300 Stueck) sind kalt und werden nach dem Boot eingefroren
     * (gc_freeze_boot). Der HOT-Bereich bleibt komplett dem Laufzeit-Churn vorbehalten
     * (vorher: Boot fuellte Hot, JEDES Runtime-Cons lief per DMA ins EXT — gemessen ~290
     * EXT-Conses je Editor-Taste = der Wandzeit-Loewenanteil). Hot kommt bei
     * gc_freeze_boot an die Freelist-Spitze. */
    for (i = MAX_CELLS - 1; i >= HEAP_CELLS; i--) {
        cell_set_a((obj)(i << 1), freelist);
        freelist = (obj)(i << 1);
    }
#else
    for (i = 1; i < HEAP_CELLS; i++) {   /* Zelle 0 = NIL reserviert */
        heap[i].a = freelist;
        freelist = (obj)(i << 1);
    }
#endif
}

/* VOLL iterativ (expliziter Mark-Stack, KEINE C-Rekursion): cdr-Kette per Schleife,
 * car per Push. Entscheidend auf dem 6502: der HW-Stack (Page 1, 256 B ~ 128 JSRs)
 * ist knapp; rekursives gc_mark wuerde bei GC mitten in tiefer eval-Rekursion den
 * HW-Stack ueberlaufen lassen. Iterativ traegt gc_mark 0 zur JSR-Tiefe bei. */
#define MARKSTACK 256
static obj markstack[MARKSTACK];
uint16_t gc_badobj = 0;   /* Diagnose: verworfene Nicht-Heap-"Pointer" (korrupte objs) */
uint16_t gc_runs = 0;     /* Statistik: Anzahl gc_collect-Laeufe */
#ifdef LISP65_GC_SCAN_PROBE
uint32_t gc_symbol_scan_visits = 0; /* Exakter Linearitaetszaehler fuer das Host-Timinggate. */
#endif
#ifdef LISP65_DMA_PROF
uint32_t perf_allocs = 0; /* alloc()-Aufrufe (Diagnose-Naht wie dma_cell; 32 Bit: Bursts > 64K) */
uint32_t perf_vm_ops = 0; /* VM-Instruktionen (vm.c-Dispatch; Kostenanteil Interpretation) */
#endif


void gc_mark(obj o) {
#ifdef GC_MARK_STUB
    (void)o; return;   /* Bisektion: leerer Body */
#endif
    uint16_t sp = 0;
    markstack[sp++] = o;
    while (sp) {
        o = markstack[--sp];
        while (IS_PTR(o)) {
            uint16_t i = (uint16_t)o >> 1;
            if (i >= MAX_CELLS) { gc_badobj++; break; }   /* korruptes obj: NIE OOB marken/traversieren
                                                           * (MARK_SET haette wild in .bss geschrieben) */
            if (MARK_GET(i)) break;
            MARK_SET(i);
            switch (cell_type(o)) {
            case T_CONS: case T_CLOSURE: case T_MACRO:
#ifndef LISP65_STRING_ARENA
            case T_STR:   /* char-listen-String: a wie CONS traversieren (Arena: Leaf) */
#endif
                if (sp < MARKSTACK) markstack[sp++] = cell_a(o);   /* car/Zeichenliste spaeter */
                o = cell_b(o);                                     /* cdr jetzt   */
                break;
            default:
                o = NIL;          /* T_SYM/T_PRIM: nicht traversieren */
                break;
            }
        }
    }
}

/* Ein einzelnes obj markieren (OHNE Nachfolger). 1 = neu markiert. Flach, kein Stack. */
static uint8_t gc_mark_children_hot(uint16_t i);
#ifdef LISP65_EXT_HEAP
static uint8_t gc_mark_children_ext(uint16_t i);
#endif

static uint8_t gc_mark1(obj o) {
    uint16_t i;
    if (!IS_PTR(o)) return 0;
    i = (uint16_t)o >> 1;
    if (i >= MAX_CELLS) { gc_badobj++; return 0; }   /* korruptes obj: verwerfen */
#ifdef LISP65_EXT_HEAP
    if (i >= HEAP_CELLS && i <= gc_frozen) return 0; /* Boot-Permanent (EXT): nie traversieren */
#endif
#ifdef LISP65_EXT_HEAP
    if (i >= HEAP_CELLS) {                           /* Markierungs-Fenster pflegen */
        if (i < ext_mark_lo) ext_mark_lo = i;
        if (i > ext_mark_hi) ext_mark_hi = i;
    }
#endif
    if (MARK_GET(i)) return 0;
    MARK_SET(i);
    return 1;
}

/* cdr-Spine ab obj b BIS ZUM ENDE markieren — STACKLOS (nur eine Schleife). Ohne das
 * schob der Fixpoint verstreut liegende Listen nur EINEN cdr-Hop je Voll-Pass -> O(Laenge)
 * Paesse ueber das EXT-Fenster (per DMA der "1-Sekunde-Haenger" beim Editor-Tippen;
 * 2026-07-03 gemessen: 2-6 GC/Taste, jede mit vielen Paessen). Jetzt folgt EIN Besuch die
 * ganze cdr-Kette; car-Teilbaeume werden 1 Hop angemarkt und vom naechsten Fixpoint-Pass
 * erfasst -> Konvergenz in ~2-3 Paessen statt O(Tiefe). Transparente Accessoren: eine
 * Kette, die hot->ext wechselt, laeuft korrekt weiter (dann per DMA).
 * Rueckgabe: 1 = mindestens eine neue Markierung. */
static uint8_t gc_mark_spine(obj b) {
    uint8_t ch = 0;
    while (gc_mark1(b)) {                 /* b IS_PTR & neu markiert (nonptr/frozen -> 0 -> Ende) */
        ch = 1;
        switch (cell_type(b)) {
        case T_CONS: case T_CLOSURE: case T_MACRO:
#ifndef LISP65_STRING_ARENA
        case T_STR:
#endif
            gc_mark1(cell_a(b));         /* car (Teilbaum) 1 Hop anmarken (ch bereits 1) */
            b = cell_b(b);               /* cdr weiter verfolgen */
            break;
        default:
            b = NIL; break;              /* T_SYM/T_PRIM: Kette endet */
        }
    }
    return ch;
}

/* Kinder EINER markierten traversierbaren Zelle nachmarkieren (1 = neue Markierung). */
static uint8_t gc_mark_children_hot(uint16_t i) {
    uint8_t ch = 0;
    if (!MARK_GET(i)) return 0;
    switch (heap[i].type) {
    case T_CONS: case T_CLOSURE: case T_MACRO:
#ifndef LISP65_STRING_ARENA
    case T_STR:
#endif
        if (gc_mark1(heap[i].a)) ch = 1;
        if (gc_mark_spine(heap[i].b)) ch = 1;   /* cdr-Kette in EINEM Besuch */
        break;
    default: break;
    }
    return ch;
}
#ifdef LISP65_EXT_HEAP
/* Erweiterte Zellen: auch sie MUESSEN nachmarkieren (Bugfix 2026-07-02 — vorher sah nur
 * die Hot-Schleife heap[] direkt und lebende EXT-Glieder verloren ihre Nachfahren an den
 * Sweep). Kosten: kalte DMA-Reads je markierter EXT-Zelle — dank Spine-Follow nur noch
 * ~einmal je Kette statt je Pass. */
static uint8_t gc_mark_children_ext(uint16_t i) {
    uint8_t ch = 0;
    if (!MARK_GET(i)) return 0;
    switch (ext_type(i)) {
    case T_CONS: case T_CLOSURE: case T_MACRO:
#ifndef LISP65_STRING_ARENA
    case T_STR:
#endif
        if (gc_mark1(ext_a(i))) ch = 1;
        if (gc_mark_spine(ext_b(i))) ch = 1;    /* cdr-Kette in EINEM Besuch */
        break;
    default: break;
    }
    return ch;
}
#endif

#ifdef LISP65_STRING_ARENA
static void str_arena_compact(void);
#endif

void gc_collect(void) {
#ifdef LISP65_EXT_HEAP
    allocs_since_gc = 0;
#endif
    HB(3); LA(17);   /* Q: gc entry */
    gc_runs++;
    uint16_t i;
    uint16_t s, n;
    uint8_t changed;

    MARK_CLEAR();
#ifdef LISP65_EXT_HEAP
    ext_mark_lo = 0xFFFF; ext_mark_hi = 0;
#endif

    /* FIXPOINT-SWEEP-MARKING statt Markstack-Traversierung: nur flache Voll-Scans —
     * die einzige Konstruktklasse, die auf echter mega65-HW nachweislich traegt
     * (Markstack-gc_mark fror dort deterministisch ein; docs/mvp-hw-findings.md).
     * Kosten O(HEAP_CELLS * Kettentiefe): bei <=512 Zellen ~ms-Bereich, irrelevant. */
    for (i = 0; i < gc_rootsp; i++) gc_mark1(gc_rootstack[i]);
    LA(18);   /* R: roots markiert */

    n = sym_count();
    for (s = 0; s < n; s++) {
#ifdef LISP65_GC_SCAN_PROBE
        gc_symbol_scan_visits++;
#endif
        obj sym = sym_nth(s);
        gc_mark1(sym);
        gc_mark1(sym_value(sym));
#ifdef LISP65_SYMFN_EXT
        if (sym_function_ptrp(sym))
            gc_mark1(sym_function(sym));
#else
        gc_mark1(sym_function(sym));
#endif
    }
    LA(19);   /* S: symbole markiert */

    /* Fixpunkt in EINER Richtung (absteigend). Die frueher noetige alternierende Richtung
     * ist mit dem cdr-Spine-Follow (gc_mark_spine) obsolet: eine Kette wird jetzt in EINEM
     * Besuch komplett markiert, egal wie sie im Speicher liegt -> Konvergenz in ~2-3 Paessen
     * unabhaengig von der Scan-Richtung. Das spart die zweite Schleifen-Kopie (.text). */
    do {
        changed = 0;
        for (i = HEAP_CELLS - 1; i >= 1; i--) changed |= gc_mark_children_hot(i);
#ifdef LISP65_EXT_HEAP
        if (ext_mark_hi >= ext_mark_lo)
            for (i = ext_mark_hi; i >= ext_mark_lo; i--) changed |= gc_mark_children_ext(i);
#endif
    } while (changed);

#ifdef LISP65_STRING_ARENA
    /* Arena-Kompaktierung: lebende (markierte) T_STR-Bytes low->high umkopieren, tote
     * fallen weg. Marks noch gueltig (MARK_CLEAR erst beim naechsten GC). Vor dem Sweep. */
    str_arena_compact();
#endif

    freelist = NIL;
#ifdef LISP65_EXT_HEAP
    /* Absteigend NUR bis zur Watermark: die Region darueber wurde nie vergeben und haengt
     * mit ihrer intakten mem_init-Kette (i -> i+1 -> ... -> NIL) hinten an. Spart
     * ~EXT_CELLS DMA-Writes je GC, solange der Ueberlauf unbenutzt ist. */
    {
        uint16_t lo = (gc_frozen > (uint16_t)(HEAP_CELLS - 1)) ? gc_frozen : (uint16_t)(HEAP_CELLS - 1);
        /* Pristine-Kette nur anhaengen, wenn je alloziert wurde (alloc_high>0) UND
         * mem_init die Kette geschrieben hat — sonst (Lazy-Init ohne mem_init, z. B.
         * Minimal-Harnesse) entstuende ein Freelist-Zyklus ueber Zelle alloc_high+1. */
        if (alloc_high > 0 && alloc_high + 1 < MAX_CELLS) freelist = (obj)((uint16_t)(alloc_high + 1) << 1);
        for (i = alloc_high; i > lo; i--) {          /* Runtime-EXT (Frozen-Region nie) */
            if (!MARK_GET(i)) { cell_set_a((obj)(i << 1), freelist); freelist = (obj)(i << 1); }
        }
        for (i = HEAP_CELLS - 1; i >= 1; i--) {      /* Hot immer; zuletzt -> Spitze */
            if (!MARK_GET(i)) { heap[i].a = freelist; freelist = (obj)(i << 1); }
        }
    }
#else
    for (i = 1; i < HEAP_CELLS; i++) {
        if (!MARK_GET(i)) {
            heap[i].a = freelist;
            freelist = (obj)(i << 1);
        }
    }
#endif
    LA(20);   /* T: sweep fertig */
}

/* OOM-FLAG statt longjmp: alloc setzt nur ein Byte (kein lisp_abort/interrupt-Import in
 * mem.c — der kippte LTO-Inlining-Schwellen um -374 B). Der REPL prueft das Flag nach der
 * Auswertung und meldet "*** out of memory" — stilles NIL zerlegte sonst Bindungen zu
 * Geister-nil-Ergebnissen (HW 2026-07-02). */
uint8_t mem_oom = 0;
/* Diagnose-Naht (Host-Harnesse zaehlen die Freeliste; LTO strippt sie in Geraete-Builds). */
obj mem_freelist_head(void) { return freelist; }
uint16_t mem_free_cells(void) {
    obj f = freelist;
    uint16_t n = 0;
    while (f != NIL && n < MAX_CELLS) { n++; f = cell_a(f); }
    return n;
}
__attribute__((noinline)) static obj alloc_oom(void) {
    mem_oom = 1;
    return NIL;
}

#ifdef LISP65_STACK_GUARD
#ifndef LISP65_STACK_MARGIN
#define LISP65_STACK_MARGIN 24u   /* Schmales Polster ueber heap[]-Top: nur der Ruecklauf des aktuellen
                                   * Frames muss noch passen. Groesser frisst die (in engen Profilen
                                   * ohnehin knappe) Reserve und feuert schon auf der Baseline. */
#endif
uint8_t lisp_stack_low(void) {
#ifdef __mos__
    /* llvm-mos haelt den SOFT-STACK-Pointer in __rc0/__rc1 (ZP $02/$03); er waechst von $D000 nach
     * unten Richtung residentem BSS-/Overlay-Floor. (&local geht NICHT — address-taken Locals landen
     * in ZP-Pseudo-Registern, nicht auf dem Soft-Stack.) __heap_start ist die Linkergrenze, die auch
     * die Workbench-Reserve-Audits verwenden. */
    extern uint8_t __heap_start[];
    uint16_t sp = *(volatile uint16_t *)0x0002u;
    return sp <= (uint16_t)((uintptr_t)__heap_start + LISP65_STACK_MARGIN);
#else
    return 0;   /* Host: nativer Stack fern von heap[] -> nie */
#endif
}
#endif

obj alloc(uint8_t type) {
    obj o;
    HB(4);
#ifdef LISP65_DMA_PROF
    perf_allocs++;
#endif
#ifdef GC_DISABLE
    if (freelist == NIL) return NIL;       /* Diagnose: GC aus, reiner Bump bis leer */
#else
#ifdef GC_STRESS
    gc_collect();
#endif
#ifdef LISP65_EXT_HEAP
    /* NURSERY-POLITIK (2026-07-02): ist der Hot-Bereich leergelaufen (Freelist-Spitze
     * zeigt ins EXT), lieber ernten als ins DMA-Land wandern — sonst laeuft der Editor-
     * Churn durch alle 4096 EXT-Zellen (gemessen: 290 EXT-Conses/Taste = Wandzeit).
     * Hysterese HEAP_CELLS/2: passt das lebende Set nicht in Hot, bleibt der GC-Abstand
     * trotzdem >= halbe Hot-Groesse (kein Thrash, Ueberlauf ins EXT dann gewollt). */
    if (gc_frozen && freelist != NIL
        && ((uint16_t)freelist >> 1) >= HEAP_CELLS
#ifdef LISP65_NURSERY_HYSTERESIS
        && allocs_since_gc >= (LISP65_NURSERY_HYSTERESIS)
#else
        && allocs_since_gc >= (HEAP_CELLS >> 1)
#endif
        ) {
        gc_collect();
    }
#endif
    if (freelist == NIL) {
        gc_collect();
        if (freelist == NIL) return alloc_oom();
    }
#endif
    o = freelist;
    freelist = cell_a(o);        /* Freelist-Link liegt im a-Feld (Hot: inline, Erw.: DMA) */
#ifdef LISP65_EXT_HEAP
    allocs_since_gc++;
#endif
#ifdef LISP65_EXT_HEAP
    { uint16_t i_ = (uint16_t)o >> 1; if (i_ > alloc_high) alloc_high = i_; }
#endif
    cell_set_type(o, type);
    cell_set_a(o, NIL);
    cell_set_b(o, NIL);
    return o;
}

obj cons(obj car, obj cdr) {
    obj o;
    GC_PUSH(car);
    GC_PUSH(cdr);
    o = alloc(T_CONS);
    GC_POPN(2);
    cell_set_a(o, car);
    cell_set_b(o, cdr);
    return o;
}

obj list_nreverse(obj list) {
    obj previous = NIL;
    while (IS_PTR(list) && cell_type(list) == T_CONS) {
        obj next = cell_b(list);
        cell_set_b(list, previous);
        previous = list;
        list = next;
    }
    return previous;
}

obj list_rplaca(obj cell, obj value) {
    cell_set_a(cell, value);
    return cell;
}

obj list_rplacd(obj cell, obj value) {
    cell_set_b(cell, value);
    return cell;
}

#ifdef LISP65_STRING_ARENA
/* ---- PACKED-BYTE-STRING-ARENA -------------------------------------------------------
 * Ein T_STR ist EINE Zelle: a = Laenge (Fixnum), b = Byte-Offset (Fixnum) in die Arena.
 * Bump-Alloc (Strings immutable -> append-only zwischen GCs). GC = mark-compact:
 * lebende Bytes werden umkopiert, tote fallen weg. Frozen-Praefix [0..str_frozen) haelt die
 * Boot-Literal-Strings und wird nie bewegt (mirror der Zell-Frozen-Region).
 * DOPPELPUFFER (Codex-Entscheid Device-P2): ordnungsfreie Kompaktierung. Geraete-Port
 * ersetzt NUR die Byte-Accessoren unten (MEGA65: Bank 4, Fenster $2000/$4800) — die Logik
 * (compact/open/putc/close) bleibt identisch. docs/ide-oom-packed-strings-design.md. */
#ifndef STR_ARENA_SIZE
#ifdef __mos__
/* MEGA65: zwei Fenster muessen in die freie Bank-4-Luecke $42000-$46BFF passen (zwischen den
 * EXT-Zellen $40000-$41FFF und dem Disk-Scratch $46C00). 2x 9.5 KB = 19 KB. */
#define STR_ARENA_SIZE 0x2600u   /* 9728 */
#else
#define STR_ARENA_SIZE 16384u    /* Host: volle Fixnum-Grenze fuer den ABI-Gate-Test */
#endif
#endif
/* Laenge (a) UND Offset (b) einer T_STR-Zelle sind positive Fixnums -> max darstellbar 16383
 * (15-bit signed, obj.h). Ein String darf also hoechstens 16383 Bytes lang sein und muss bei
 * einem Offset <= 16383 beginnen; sonst wraeppte MKFIX ins Negative (stiller ABI-Bruch statt
 * ehrlicher OOM — Codex-P1.1-Befund). STR_ARENA_SIZE darf 16384 sein: das Laengen-/Offset-Limit
 * greift vorher. */
#define STR_MAX_BYTES 0x3FFFu   /* 16383 */
#if STR_ARENA_SIZE > 0x4000u
#error "STR_ARENA_SIZE > 16384: Arena-Offsets sind nicht mehr als positiver Fixnum (<=16383) darstellbar"
#endif
#if defined(__mos__) && !defined(LISP65_EXT_HEAP)
#error "LISP65_STRING_ARENA on MEGA65 requires LISP65_EXT_HEAP so the hardened F018 DMA helper is available"
#endif

/* --- Byte-Backing-Accessoren: die EINZIGE Naht, die der Device-Port (EXT/DMA) ersetzt.
 * Host: zwei Arrays. MEGA65: Bank 4 (echtes Fast-RAM), zwei Fenster in der Luecke
 * $42000-$46BFF zwischen EXT-Zellen und Disk-Scratch. HW-BEFUND 2026-07-08: die urspruengliche
 * Wahl Bank 6 ($60000) ist NICHT bestueckt (MEGA65-Fast-RAM = 384 KB = Banks 0-5) -> jeder
 * Arena-Byte-Read lieferte 0, alle Lisp-String-Ops brachen (load-lib scannte nach Namen (0 0 0)).
 * Bank 4 wird bereits vom EXT-Zell-Heap benutzt und ist damit als RAM verifiziert. --- */
#ifndef __mos__
static uint8_t  str_buf_a[STR_ARENA_SIZE];
static uint8_t  str_buf_b[STR_ARENA_SIZE];
static uint8_t *str_cur = str_buf_a;   /* aktives Fenster (Lesen/Schreiben) */
static uint8_t *str_alt = str_buf_b;   /* Kompaktier-Ziel */
static uint8_t str_read_byte(uint16_t off)             { return str_cur[off]; }
static void    str_write_byte(uint16_t off, uint8_t b) { str_cur[off] = b; }
/* n Bytes vom aktiven Fenster[src] ins Alt-Fenster[dst] (Kompaktierung). */
static void    str_copy_to_alt(uint16_t dst, uint16_t src, uint16_t n) { uint16_t i; for (i = 0; i < n; i++) str_alt[dst + i] = str_cur[src + i]; }
static void    str_swap_buffers(void) { uint8_t *t = str_cur; str_cur = str_alt; str_alt = t; }
#else
#ifndef STR_ARENA_BANK
#define STR_ARENA_BANK 0x04       /* Bank 4 = echtes Fast-RAM (EXT-Zell-Heap liegt hier); NICHT Bank 6 */
#endif
#ifndef STR_ARENA_CUR_OFF
#define STR_ARENA_CUR_OFF 0x2000u /* hinter den EXT-Zellen ($40000-$41FFF bei EXT_CELLS=1024) */
#endif
#ifndef STR_ARENA_ALT_OFF
#define STR_ARENA_ALT_OFF (STR_ARENA_CUR_OFF + STR_ARENA_SIZE)  /* Offset $4600; Ende $6BFF, Disk-Scratch ab $6C00 */
#endif
/* Wenn Arena und EXT-Zellen in derselben Bank liegen, muss der Zell-Heap vor dem Arena-Fenster enden. */
#if STR_ARENA_BANK == EXT_BANK && (EXT_CELLS * 8u) > STR_ARENA_CUR_OFF
#error "String-Arena-Fenster kollidieren mit EXT_CELLS (EXT_CELLS*8 > STR_ARENA_CUR_OFF)"
#endif
/* Beide Fenster muessen unter dem Disk-Scratch bleiben. */
#if (STR_ARENA_ALT_OFF + STR_ARENA_SIZE) > DISK_EXT_BASE
#error "String-Arena-Fenster kollidieren mit dem Disk-Scratch in EXT-Bank"
#endif

static uint16_t str_cur_off = STR_ARENA_CUR_OFF;   /* aktives EXT-Fenster */
static uint16_t str_alt_off = STR_ARENA_ALT_OFF;   /* Kompaktier-Ziel */
static uint8_t  str_stg1;

static uint8_t str_read_byte(uint16_t off) {
    ext_dma((uint16_t)(str_cur_off + off), STR_ARENA_BANK,
            (uint16_t)(uintptr_t)&str_stg1, 0, 1);
    return str_stg1;
}
static void str_write_byte(uint16_t off, uint8_t b) {
    str_stg1 = b;
    ext_dma((uint16_t)(uintptr_t)&str_stg1, 0,
            (uint16_t)(str_cur_off + off), STR_ARENA_BANK, 1);
}
static void str_copy_to_alt(uint16_t dst, uint16_t src, uint16_t n) {
    if (!n) return;
    ext_dma((uint16_t)(str_cur_off + src), STR_ARENA_BANK,
            (uint16_t)(str_alt_off + dst), STR_ARENA_BANK, n);
}
static void str_swap_buffers(void) {
    uint16_t t = str_cur_off;
    str_cur_off = str_alt_off;
    str_alt_off = t;
}
#endif

static uint16_t str_top = 0;       /* naechster freier Offset (Bump-Pointer) */
static uint16_t str_frozen = 0;    /* permanentes Praefix (Boot-Strings) */
static obj      str_building = NIL; /* aktuell offener Streaming-String (bleibt beim Compact am Ende) */

uint16_t str_len(obj s)              { return (uint16_t)FIXVAL(cell_a(s)); }
uint8_t  str_byte(obj s, uint16_t i) { return str_read_byte((uint16_t)FIXVAL(cell_b(s)) + i); }
void     str_arena_freeze(void)      { str_frozen = str_top; }
uint16_t str_arena_used(void)        { return str_top; }
uint16_t str_arena_capacity(void)    { return STR_ARENA_SIZE; }

/* Eine lebende runtime-T_STR-Zelle ins Alt-Fenster relozieren; gibt den neuen Top zurueck. */
static uint16_t str_relocate(obj o, uint16_t ntop) {
    uint16_t off = (uint16_t)FIXVAL(cell_b(o));
    uint16_t len;
    if (off < str_frozen) return ntop;         /* Frozen-String: liegt schon im Praefix */
    len = (uint16_t)FIXVAL(cell_a(o));
    str_copy_to_alt(ntop, off, len);
    cell_set_b(o, MKFIX((int16_t)ntop));
    return (uint16_t)(ntop + len);
}

static void str_arena_compact(void) {
    uint16_t i, ntop;
    str_copy_to_alt(0, 0, str_frozen);           /* Frozen-Praefix verbatim */
    ntop = str_frozen;
    for (i = 1; i < MAX_CELLS; i++) {
        obj o;
        if (!MARK_GET(i)) continue;            /* nur lebende Zellen */
        o = (obj)(uint16_t)(i << 1);
#ifdef LISP65_FIRST_CLASS_BUFFER
        /* T_STR=5 and T_BUF=7 are the only current kinds whose bit-1-fold is
         * T_BUF. This preserves one EXT-aware type read in the hot compactor. */
        if ((uint8_t)(cell_type(o) | 2u) != T_BUF) continue;
#else
        if (cell_type(o) != T_STR) continue;
#endif
        if (o == str_building) continue;       /* in-Arbeit-String: kommt ZULETZT (bleibt anhaengbar) */
        ntop = str_relocate(o, ntop);
    }
    /* Offenen Streaming-String ans Ende legen, damit str_putc weiter contiguous anhaengen kann. */
    if (str_building != NIL) {
        uint16_t bi = (uint16_t)str_building >> 1;
        if (bi < MAX_CELLS && MARK_GET(bi) && cell_type(str_building) == T_STR)
            ntop = str_relocate(str_building, ntop);
    }
    str_swap_buffers();
    str_top = ntop;
}

/* STREAMING-BUILDER (kein Festpuffer -> keine stille Truncation, kein BSS-Risiko).
 * Muster: str_open() -> str_putc()* -> str_close(). Der Aufrufer alloziert zwischen open
 * und close NICHT selbst; str_putc darf aber bei Arena-Voll GC/Compaction ausloesen (der
 * offene String ist dabei via str_building gerootet-markiert und wird ans Arena-Ende
 * relociert, bleibt also anhaengbar). Erst wenn auch nach Compaction kein Platz ist -> mem_oom. */
obj str_open(void) {
    obj o = alloc(T_STR);                        /* kann Heap-GC ausloesen; str_building noch alt/NIL */
    if (o == NIL) return NIL;
    cell_set_a(o, MKFIX(0));
    cell_set_b(o, MKFIX(0));                     /* wohlgeformter Leerstring (0 Bytes) fuer evtl. Compaction */
    if (str_top > STR_MAX_BYTES) {               /* Startoffset waere nicht als Fixnum darstellbar */
        GC_PUSH(o); gc_collect(); GC_POPN(1);    /* toten Muell weg; o (0 Bytes) unbewegt-egal */
        if (str_top > STR_MAX_BYTES) { mem_oom = 1; return NIL; }   /* ehrlicher OOM statt Wrap */
    }
    cell_set_b(o, MKFIX((int16_t)str_top));      /* Start = Arena-Top NACH dem alloc/GC (<= 16383) */
    str_building = o;
    return o;
}
uint8_t str_putc(obj s, uint8_t c) {
    /* Laengen-Limit: a (Laenge) muss positiver Fixnum bleiben (<= 16383). Compaction hilft hier nicht. */
    if ((uint16_t)(str_top - (uint16_t)FIXVAL(cell_b(s))) >= STR_MAX_BYTES) { mem_oom = 1; return 0; }
    if (str_top >= STR_ARENA_SIZE) {
        GC_PUSH(s); gc_collect(); GC_POPN(1);    /* toten Arena-Muell kompaktieren; s wandert ans Ende */
        if (str_top >= STR_ARENA_SIZE) { mem_oom = 1; return 0; }   /* echt voll: ehrlicher OOM */
    }
    str_write_byte(str_top++, c);
    cell_set_a(s, MKFIX((int16_t)(str_top - (uint16_t)FIXVAL(cell_b(s)))));  /* Laenge inkrementell */
    return 1;
}
obj str_close(obj s) { str_building = NIL; return s; }

#ifdef LISP65_FIRST_CLASS_BUFFER
#if defined(__mos__) && defined(LISP65_RUNTIME_OVERLAY)
#define BUFFER_READ_FN __attribute__((section(".lisp65_rt_buffer_read"), noinline, used))
#define BUFFER_WRITE_FN __attribute__((section(".lisp65_rt_buffer_write"), noinline, used))
#define BUFFER_ALLOC_FN __attribute__((section(".lisp65_rt_buffer_alloc"), noinline, used))
#else
#define BUFFER_READ_FN
#define BUFFER_WRITE_FN
#define BUFFER_ALLOC_FN
#endif

/* One allocator owns both initialized public buffers and the two C1 bulk
 * paths.  The latter immediately overwrite every byte by DMA, so clearing
 * first would turn the otherwise batched handoff back into O(n) device work. */
static BUFFER_ALLOC_FN obj buf_allocate(uint16_t len, uint8_t clear) {
    obj buffer;
    uint16_t index, offset;
    if (len > STR_MAX_BYTES || len > STR_ARENA_SIZE) {
        mem_oom = 1;
        return NIL;
    }
    buffer = alloc(T_BUF);
    if (buffer == NIL) return NIL;
    /* Keep the new cell well-formed if the capacity check triggers GC. */
    cell_set_a(buffer, MKFIX(0));
    cell_set_b(buffer, MKFIX(0));
    GC_PUSH(buffer);
    if (len > (uint16_t)(STR_ARENA_SIZE - str_top)) gc_collect();
    if (len > (uint16_t)(STR_ARENA_SIZE - str_top)) {
        mem_oom = 1;
        GC_POPN(1);
        return NIL;
    }
    offset = str_top;
    cell_set_a(buffer, MKFIX((int16_t)len));
    cell_set_b(buffer, MKFIX((int16_t)offset));
    if (clear)
        for (index = 0; index < len; index++)
            str_write_byte((uint16_t)(offset + index), 0);
    str_top = (uint16_t)(offset + len);
    GC_POPN(1);
    return buffer;
}

BUFFER_ALLOC_FN obj buf_make(uint16_t len) {
    return buf_allocate(len, 1);
}

BUFFER_READ_FN uint16_t buf_len(obj buffer) { return (uint16_t)FIXVAL(cell_a(buffer)); }

BUFFER_READ_FN uint8_t buf_byte(obj buffer, uint16_t index) {
    return str_read_byte((uint16_t)(FIXVAL(cell_b(buffer)) + index));
}

BUFFER_WRITE_FN void buf_set(obj buffer, uint16_t index, uint8_t value) {
    str_write_byte((uint16_t)(FIXVAL(cell_b(buffer)) + index), value);
}

BUFFER_READ_FN obj buf_freeze(obj buffer) {
    uint16_t cell_index = (uint16_t)buffer >> 1;
    /* Keep this cold mutation inside the read overlay. Calling the generic
     * inline accessor here makes LLVM-MOS outline a 113-byte resident clone. */
    if (cell_index < HEAP_CELLS) heap[cell_index].type = T_STR;
#ifdef LISP65_EXT_HEAP
    else ext_set_type(cell_index, T_STR);
#endif
    return buffer;
}

BUFFER_ALLOC_FN obj buf_from_string(obj string) {
    obj buffer;
    uint16_t index, offset, length = str_len(string);
    GC_PUSH(string);
    buffer = buf_allocate(length, 0);
    if (buffer != NIL) {
        offset = (uint16_t)FIXVAL(cell_b(buffer));
        for (index = 0; index < length; index++)
            str_write_byte((uint16_t)(offset + index), str_byte(string, index));
    }
    GC_POPN(1);
    return buffer;
}

/* C1 bulk seam. Both functions share the allocator overlay with buf_make and
 * reuse the established register-free EXT DMA primitive.  Each completed
 * compiler result therefore crosses the boundary in one transfer. */
#ifdef LISP65_EXT_HEAP
BUFFER_ALLOC_FN obj buf_from_stage(uint16_t len) {
    obj buffer = buf_allocate(len, 0);
    uint16_t offset;
    if (buffer == NIL) return NIL;
    offset = (uint16_t)FIXVAL(cell_b(buffer));
#ifndef __mos__
    {
        uint16_t index;
        for (index = 0; index < len; index++)
            str_write_byte((uint16_t)(offset + index),
                           ext_disk_get((uint16_t)(256u + index)));
    }
#else
    if (len) ext_dma((uint16_t)(DISK_EXT_BASE + 256u), EXT_BANK,
                     (uint16_t)(str_cur_off + offset), EXT_BANK, len);
#endif
    return buffer;
}

BUFFER_ALLOC_FN uint16_t buf_to_stage(obj buffer) {
    uint16_t length = (uint16_t)FIXVAL(cell_a(buffer));
    uint16_t offset = (uint16_t)FIXVAL(cell_b(buffer));
#ifndef __mos__
    {
        uint16_t index;
        for (index = 0; index < length; index++)
            ext_disk_put((uint16_t)(256u + index),
                         str_read_byte((uint16_t)(offset + index)));
    }
#else
    if (length) ext_dma((uint16_t)(str_cur_off + offset), EXT_BANK,
                        (uint16_t)(DISK_EXT_BASE + 256u), EXT_BANK, length);
#endif
    return length;
}
#endif
#undef BUFFER_READ_FN
#undef BUFFER_WRITE_FN
#undef BUFFER_ALLOC_FN
#endif

obj str_from_bytes(const uint8_t *bytes, uint16_t len) {
    obj o = str_open(); uint16_t i;
    if (o == NIL) return NIL;
    for (i = 0; i < len; i++) if (!str_putc(o, bytes[i])) break;
    return str_close(o);
}

obj str_from_charlist(obj list) {
    obj o, c;
    GC_PUSH(list);                               /* Quellliste ueber alloc/Compaction-GC schuetzen */
    o = str_open();
    if (o == NIL) { GC_POPN(1); return NIL; }
    for (c = list; IS_PTR(c) && cell_type(c) == T_CONS; c = cell_b(c))
        if (!str_putc(o, (uint8_t)FIXVAL(cell_a(c)))) break;   /* str_putc kann GC ausloesen -> list gerootet */
    GC_POPN(1);
    return str_close(o);
}

/* String-Bytes in einen C-Puffer kopieren (fasl/save/load-Namen, screen-write-Span).
 * Kopiert min(len,max); Rueckgabe = kopierte Byte-Zahl (der Aufrufer nul-terminiert selbst). */
uint16_t str_copy_out(obj s, char *dst, uint16_t max) {
    uint16_t l = str_len(s), i;
    if (l > max) l = max;
    for (i = 0; i < l; i++) dst[i] = (char)str_byte(s, i);
    return l;
}
#endif /* LISP65_STRING_ARENA */
