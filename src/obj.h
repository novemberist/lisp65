/* lisp65 — object model (the central contract, lane K)
 * obj is a 16-bit tagged reference:
 *   NIL     = 0
 *   fixnum  = (n << 1) | 1     (15-bit signed immediate)
 *   pointer = even, != 0       (cell index << 1; the cell type lives in the cell)
 *
 * CAUTION: this is an interface header. Changes ripple into every module —
 * announce them in docs/collaboration.md before changing (interface contract).
 */
#ifndef LISP65_OBJ_H
#define LISP65_OBJ_H

#include <stdint.h>

typedef int16_t obj;

#define NIL        ((obj)0)
#define MKFIX(n)   ((obj)(uint16_t)((((uint16_t)(int16_t)(n)) << 1) | 1u))
#define IS_FIX(o)  ((o) & 1)
#define FIXVAL(o)  ((int16_t)((o) >> 1))
/* Heap cell pointer: even, != 0, index < 0x4000. Even values with index >= 0x4000 are
 * tagged IMMEDIATES (no heap, no GC) — currently BCODE (a compiled fn: it carries the
 * code directory index in the obj itself; this saves one permanent heap cell per function,
 * about a third of the boot heap consumption across 121 stdlib functions). */
/* Encoding trick: heap index < 0x4000 <=> obj POSITIVE; immediates (BCODE from base 0x6000)
 * <=> obj NEGATIVE (as int16). IS_PTR is therefore a sign plus parity test — CHEAPER than
 * the old mask plus NIL check (NIL=0 drops out of > 0 automatically). */
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
/* Existing enum range is optimizer-sensitive under LLVM-MOS LTO. Keep the
 * historical enum intact and allocate the next ABI value explicitly. */
#define T_BUF 7u

/* Zell-Layout je Typ:
 *   CONS:    a=car                   b=cdr
 *   SYM:     a=Symboltabellen-Index  b=ungenutzt (Wert/Funktion: symbol.c)
 *   PRIM:    a=Primitiv-ID (Fixnum)  b=ungenutzt
 *   CLOSURE: a=(params . body)       b=captured env   (lambda)
 *   MACRO:   a=(params . body)       b=captured env   (defmacro)
 *   STR:     a=Zeichenliste(Fixnums) b=ungenutzt      ("…"; GC traversiert a wie CONS)
 *   BCODE:   a=Code-Directory-Index  b=ungenutzt      (kompilierte Fn; apply -> VM; GC: nicht traversieren)
 *   BUF:     a=byte length            b=arena offset   (mutable contiguous bytes; GC leaf) */
typedef struct {
    uint8_t type;
    obj a;
    obj b;
} Cell;

#ifndef HEAP_CELLS
/* Mark-sweep heap (cell 0 = NIL, reserved); overridable with -D.
 * Default 1536 for host/c64/smokes. The mega65 deploy builds with -DHEAP_CELLS=1200 because
 * bank 0 (~44 KB) is tight for REPL + prelude + strings + load buffer and about 1.7 KB of
 * soft stack must remain (otherwise it crashes while loading the prelude). Real growth comes
 * with the flat 8 MB model (§4.3, post-MVP). */
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
  /* For EXT the mark bits are a bitmap (compact), so large values are affordable. Upper bound:
   * the extended cells sit flat from $40000 (bank 4, 64 KB) = at most ~8192 cells of 8 bytes.
   * Fine-tunable for the deploy build via -DEXT_CELLS. */
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
