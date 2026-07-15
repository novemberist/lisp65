/* lisp65 — Speicher/Allocator + GC (Lane K) */
#ifndef LISP65_MEM_H
#define LISP65_MEM_H

#include "obj.h"

void mem_init(void);                /* Heap als Freelist initialisieren (vor allem!) */
obj  alloc(uint8_t type);           /* rohe Zelle; loest bei Bedarf GC aus           */
obj  cons(obj car, obj cdr);        /* (cons car cdr) — schuetzt car/cdr selbst      */
uint16_t mem_free_cells(void);      /* read-only: aktuelle Freelist-Laenge          */
#ifdef LISP65_EXT_HEAP
void ext_disk_read(uint16_t off, uint8_t *dst, uint16_t len); /* Scratch -> Bank 0, bulk */
#endif

/* ---- GC: Mark-Sweep mit präzisem Shadow-Root-Stack ----
 * Jede Funktion, die einen lebenden obj ueber eine Allokation hinweg haelt, MUSS ihn
 * pushen (GC laeuft nur in alloc). cons() schuetzt seine beiden Argumente bereits. */
#ifndef GC_ROOTS
/* 512 reicht reichlich (realer Peak <100) und gibt dem engen mega65-Bank-0 spuerbar
 * mehr Soft-Stack-Raum bis $D000. -D ueberschreibbar. */
#define GC_ROOTS 512
#endif
extern obj      gc_rootstack[GC_ROOTS];
extern uint16_t gc_rootsp;
extern uint16_t gc_badobj;   /* Diagnose: von gc_mark verworfene korrupte objs */
extern uint16_t gc_runs;    /* Statistik: Anzahl gc_collect-Laeufe */
#ifdef LISP65_GC_SCAN_PROBE
extern uint32_t gc_symbol_scan_visits;
#endif
extern uint8_t mem_oom;          /* 1 = alloc lief in OOM (REPL meldet + loescht) */
#define GC_PUSH(x)  (gc_rootstack[gc_rootsp++] = (obj)(x))
#define GC_SET(i,x) (gc_rootstack[(i)] = (obj)(x))   /* gepushten Slot aktualisieren */
#define GC_TOP      (gc_rootsp - 1)
#define GC_POPN(n)  (gc_rootsp = (uint16_t)(gc_rootsp - (n)))
#define GC_CAN_RESERVE(n) \
    (gc_rootsp <= GC_ROOTS && (uint16_t)(n) <= (uint16_t)(GC_ROOTS - gc_rootsp))

/* Soft-Stack-Guard (F1, docs/vollprofil-stack-heap-collision.md): die C-Rekursion (vm_run-
 * Verschachtelung, compile_expr, read_expr) waechst auf dem mega65 von $D000 nach UNTEN Richtung
 * heap[]-Top. lisp_stack_low() meldet 1, sobald der aktuelle Frame den heap-Deckel + Marge erreicht
 * -> der Aufrufer bricht mit VM_STACKOVER/err ab (EHRLICHER Fehler statt stiller heap-Korruption).
 * Nur unter -DLISP65_STACK_GUARD aktiv (Default-Produkt byte-identisch). Host: heap ist ein Global
 * fern vom nativen Stack -> immer 0 (kein Fehlalarm). */
#ifdef LISP65_STACK_GUARD
uint8_t lisp_stack_low(void);
#endif

void gc_mark(obj o);
void gc_collect(void);
#ifdef LISP65_EXT_HEAP
void gc_freeze_boot(void);   /* Boot-Permanents einfrieren (nach vm_load_embedded_stdlib) */
#endif

#ifdef LISP65_STRING_ARENA
/* PACKED-BYTE-STRINGS (Prototyp, docs/ide-oom-packed-strings-design.md).
 * Ein T_STR ist EINE Zelle: a = Laenge (Fixnum), b = Byte-Offset in die String-Arena.
 * Der Text lebt als rohe Bytes in einer contiguous Arena; GC = mark-compact (Strings sind
 * immutable + singulaer besessen -> fragmentierungsfrei). Ersetzt die char-listen-Repraesentation
 * (1 Zelle/Zeichen, ~10x Overhead). Nur unter -DLISP65_STRING_ARENA; Default byte-identisch. */
obj      str_from_bytes(const uint8_t *bytes, uint16_t len);  /* Arena-Alloc + T_STR-Zelle */
obj      str_from_charlist(obj list);                          /* Fixnum-Liste -> Arena-String */
uint16_t str_len(obj s);                                       /* Laenge (= FIXVAL(cell_a)) */
uint8_t  str_byte(obj s, uint16_t i);                          /* Byte i aus der Arena */
uint16_t str_copy_out(obj s, char *dst, uint16_t max);         /* Bytes -> C-Puffer (min(len,max)) */
void     str_arena_freeze(void);                               /* Boot-Praefix einfrieren */
uint16_t str_arena_used(void);                                 /* Diagnose: belegte Arena-Bytes */
uint16_t str_arena_capacity(void);                             /* Build-Cap, read-only */
/* Streaming-Builder (kein Festpuffer): open -> putc* -> close; zwischen open/close NICHT allozieren. */
obj      str_open(void);
uint8_t  str_putc(obj s, uint8_t c);                           /* 0 = Arena voll (mem_oom gesetzt) */
obj      str_close(obj s);

#endif

#endif /* LISP65_MEM_H */
