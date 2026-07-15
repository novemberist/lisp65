/* lisp65 — Objektmodell (zentraler Vertrag, Lane K)
 * obj ist eine 16-Bit-getaggte Referenz:
 *   NIL    = 0
 *   Fixnum = (n << 1) | 1     (15-Bit-signed Immediate)
 *   Zeiger = gerade, != 0     (Zellindex << 1; Zelltyp steht in der Zelle)
 *
 * ACHTUNG: Dies ist ein Interface-Header. Änderungen rippeln in alle Module —
 * vor Änderung in docs/collaboration.md ankündigen (Interface-Vertrag).
 */
#ifndef LISP65_OBJ_H
#define LISP65_OBJ_H

#include <stdint.h>

typedef int16_t obj;

#define NIL        ((obj)0)
#define MKFIX(n)   ((obj)(uint16_t)((((uint16_t)(int16_t)(n)) << 1) | 1u))
#define IS_FIX(o)  ((o) & 1)
#define FIXVAL(o)  ((int16_t)((o) >> 1))
/* Heap-Zell-Zeiger: gerade, != 0, Index < 0x4000. Gerade Werte mit Index >= 0x4000 sind
 * getaggte IMMEDIATES (kein Heap, kein GC) — aktuell BCODE (kompilierte Fn: traegt den
 * Code-Directory-Index direkt im obj; spart je Funktion eine permanente Heap-Zelle, bei
 * 121 Stdlib-Funktionen ~1/3 des Boot-Heap-Verbrauchs). */
/* Encoding-Trick: Heap-Index < 0x4000 <=> obj POSITIV; Immediates (BCODE ab Basis 0x6000)
 * <=> obj NEGATIV (als int16). IS_PTR ist damit ein Vorzeichen+Paritaets-Test — BILLIGER
 * als die alte Maske+NIL-Pruefung (NIL=0 faellt durch >0 automatisch raus). */
#define IS_PTR(o)  ((o) > 0 && ((o) & 1) == 0)

/* Immediate-Raum (negativ+gerade), aufgeteilt nach Roh-uint16 des obj:
 *   $C000..$DFFE = BCODE (Basis 0x6000): kompilierte Fn, traegt den Code-Directory-Index
 *   $E000..$FFFE = SYMI  (Basis 0x7000): INTERNIERTES Symbol, traegt den symtab-Index
 * SYMI (Stufe 2b): internierte Symbole kosten keine Heap-Zelle mehr (~174 Boot-Zellen frei);
 * eq bleibt exakt (intern liefert denselben Index). gensyms bleiben T_SYM-Heap-Zellen —
 * ihre eq-Identitaet IST die Zelle, der GC sammelt sie normal ein. "Ist Symbol?" heisst
 * jetzt IS_SYMI(o) || (IS_PTR(o) && cell_type(o)==T_SYM) (Helfer in eval.c/vm.c). */
#define BCODE_IMM_BASE 0x6000u
#define MK_BCODE(d)    ((obj)(uint16_t)((BCODE_IMM_BASE + (uint16_t)(d)) << 1))
#define IS_BCODE(o)    ((o) < 0 && ((o) & 1) == 0 && (uint16_t)(o) < 0xE000u)
#define BCODE_IDX(o)   ((uint16_t)((((uint16_t)(o)) >> 1) - BCODE_IMM_BASE))

#define SYMI_BASE      0x7000u
#define MK_SYMI(i)     ((obj)(uint16_t)((SYMI_BASE + (uint16_t)(i)) << 1))
#define IS_SYMI(o)     ((o) < 0 && ((uint16_t)(o) & 1) == 0 && (uint16_t)(o) >= 0xE000u)
#define SYMI_IDX(o)    ((uint16_t)((((uint16_t)(o)) >> 1) - SYMI_BASE))

enum { T_CONS, T_SYM, T_PRIM, T_CLOSURE, T_MACRO, T_STR, T_BCODE };

/* Zell-Layout je Typ:
 *   CONS:    a=car                   b=cdr
 *   SYM:     a=Symboltabellen-Index  b=ungenutzt (Wert/Funktion: symbol.c)
 *   PRIM:    a=Primitiv-ID (Fixnum)  b=ungenutzt
 *   CLOSURE: a=(params . body)       b=captured env   (lambda)
 *   MACRO:   a=(params . body)       b=captured env   (defmacro)
 *   STR:     a=Zeichenliste(Fixnums) b=ungenutzt      ("…"; GC traversiert a wie CONS)
 *   BCODE:   a=Code-Directory-Index  b=ungenutzt      (kompilierte Fn; apply -> VM; GC: nicht traversieren) */
typedef struct {
    uint8_t type;
    obj a;
    obj b;
} Cell;

#ifndef HEAP_CELLS
/* Mark-Sweep-Heap (Zelle 0 = NIL reserviert); -D überschreibbar.
 * Default 1536 für Host/c64/Smokes. Der mega65-Deploy baut mit -DHEAP_CELLS=1200, weil
 * Bank 0 (~44 KB) für REPL+Prelude+Strings+load-Puffer eng ist und ~1,7 KB Soft-Stack
 * bleiben müssen (sonst Crash beim Prelude-Laden). Echtes Wachstum kommt mit dem flachen
 * 8-MB-Modell (§4.3, post-MVP). */
#define HEAP_CELLS 1536
#endif
extern Cell heap[HEAP_CELLS];      /* Hot-Bereich: Bank-0-Pool (Zelle 0..HEAP_CELLS-1) */

#define CELL(o)    heap[(uint16_t)(o) >> 1]

/* --- Hybrid-Heap-Dimensionierung ------------------------------------------------
 * HEAP_CELLS = Hot-Bereich (Bank 0, direkt/inline). Mit -DLISP65_EXT_HEAP kommt ein
 * Ueberlauf ins erweiterte RAM (Bank 4 flach $40000, F018-DMA; Bank 5 = Blob+Namepool) dazu; MAX_CELLS = Hot+Erw.
 * obj-Zeiger (index<<1, int16) tragen bis 32767 Zellen ohne Encoding-Aenderung.
 * Symbole werden frueh (Prelude) alloziert und landen dadurch immer im Hot-Bereich —
 * symbol.c greift direkt via CELL()/heap[] zu (unangetastet). */
#ifdef LISP65_EXT_HEAP
  #ifndef EXT_CELLS
  /* Mark-Bits sind bei EXT eine Bitmap (kompakt), daher sind grosse Werte tragbar. Obergrenze:
   * die erweiterten Zellen liegen flach ab $40000 (Bank 4, 64 KB) = max ~8192 Zellen a 8 Byte.
   * Ueber -DEXT_CELLS fuer den Deploy-Build feinjustierbar. */
  #define EXT_CELLS 4096
  #endif
#else
  #define EXT_CELLS 0
#endif
#define MAX_CELLS (HEAP_CELLS + EXT_CELLS)
#if MAX_CELLS > 0x4000
#error "MAX_CELLS kollidiert mit dem Immediate-Bereich (obj-Encoding: Heap-Index < 0x4000)"
#endif

/* Bank-4-Disk-Scratch-Dateifenster hinter dem 256-B-Directory-Sektor.
 * Default-Layout: EXT-Zellen $40000-$41fff, String-Arena $42000-$46bff,
 * Disk-Scratch ab $46c00. Workbench darf STR_ARENA_SIZE/DISK_EXT_BASE/
 * DISK_EXT_FILE_MAX enger pinnen, damit die ladbare IDE-Lib ins Diskfenster passt. */
#ifndef DISK_EXT_FILE_MAX
#define DISK_EXT_FILE_MAX 0x9300u
#endif

/* Zell-Accessor-Naht. **static inline Pflicht**: der 6502-HW-Stack (256 B) ist knapp;
 * out-of-line-Accessoren legen pro Zellzugriff ein JSR in die tiefe eval-Rekursion →
 * Stack-Overflow (im String-Pfad reproduziert). Der heisse Bank-0-Zweig bleibt daher inline;
 * nur der KALTE erweiterte Zweig (o>>1 >= HEAP_CELLS) ruft die out-of-line-DMA-Helfer. */
#ifdef LISP65_EXT_HEAP
uint8_t ext_type(uint16_t i);
obj     ext_a(uint16_t i);
obj     ext_b(uint16_t i);
void    ext_set_type(uint16_t i, uint8_t t);
void    ext_set_a(uint16_t i, obj v);
void    ext_set_b(uint16_t i, obj v);
/* Disk-EXT-Scratch (Regel-B-LOAD): byteweiser Zugriff auf eine EXT-Region oberhalb des
 * Zell-Heaps — io.c legt Dir-Sektor + Datei dort ab statt in einen grossen Bank-0-Puffer. */
void    ext_disk_put(uint16_t off, uint8_t v);
uint8_t ext_disk_get(uint16_t off);
#ifdef LISP65_DISK_LIBS
/* Stufe 2: Blob+Trailer aus dem Disk-Scratch (EXT_BANK) in EINEM DMA nach (dbank,doff) kopieren. */
void    ext_disk_stage(uint16_t scratch_off, uint8_t dbank, uint16_t doff, uint16_t n);
#endif
static inline uint8_t cell_type(obj o){ uint16_t i=(uint16_t)o>>1; return i<HEAP_CELLS ? heap[i].type : ext_type(i); }
static inline obj     cell_a(obj o)   { uint16_t i=(uint16_t)o>>1; return i<HEAP_CELLS ? heap[i].a    : ext_a(i); }
static inline obj     cell_b(obj o)   { uint16_t i=(uint16_t)o>>1; return i<HEAP_CELLS ? heap[i].b    : ext_b(i); }
static inline void    cell_set_type(obj o,uint8_t t){ uint16_t i=(uint16_t)o>>1; if(i<HEAP_CELLS) heap[i].type=t; else ext_set_type(i,t); }
static inline void    cell_set_a(obj o,obj v){ uint16_t i=(uint16_t)o>>1; if(i<HEAP_CELLS) heap[i].a=v; else ext_set_a(i,v); }
static inline void    cell_set_b(obj o,obj v){ uint16_t i=(uint16_t)o>>1; if(i<HEAP_CELLS) heap[i].b=v; else ext_set_b(i,v); }
#else
static inline uint8_t cell_type(obj o)                { return CELL(o).type; }
static inline obj     cell_a(obj o)                   { return CELL(o).a; }
static inline obj     cell_b(obj o)                   { return CELL(o).b; }
static inline void    cell_set_type(obj o, uint8_t t) { CELL(o).type = t; }
static inline void    cell_set_a(obj o, obj v)        { CELL(o).a = v; }
static inline void    cell_set_b(obj o, obj v)        { CELL(o).b = v; }
#endif

#endif /* LISP65_OBJ_H */
