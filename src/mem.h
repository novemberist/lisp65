/* lisp65 — memory/allocator + GC (lane K) */
#ifndef LISP65_MEM_H
#define LISP65_MEM_H

#include "obj.h"
#include "c2_kernal_layout.h"

/* One layout contract owns the Bank-4 disk scratch used by F011, the L65M
 * validator, first-class Buffer staging and the Attic shelf DMA.  Profile
 * builds may move DISK_EXT_BASE, but no consumer may mirror its physical
 * address as a literal. */
#ifndef EXT_BANK
#define EXT_BANK 0x04u
#endif
#ifndef DISK_EXT_BASE
#define DISK_EXT_BASE 0x6c00u
#endif
#define LISP65_EXT_DISK_FILE_OFFSET 256u
#define LISP65_EXT_DISK_FILE_PHYSICAL \
    (((uint32_t)EXT_BANK << 16) + DISK_EXT_BASE + LISP65_EXT_DISK_FILE_OFFSET)

void mem_init(void);                /* Heap als Freelist initialisieren (vor allem!) */
obj  alloc(uint8_t type);           /* rohe Zelle; loest bei Bedarf GC aus           */
obj  cons(obj car, obj cdr);        /* (cons car cdr) — schuetzt car/cdr selbst      */
/* One mutation core is shared by Treewalk and CALLPRIM.  Callers retain
 * their route-specific arity and diagnostic contracts. */
obj  list_nreverse(obj list);
obj  list_rplaca(obj cell, obj value);
obj  list_rplacd(obj cell, obj value);
uint16_t mem_free_cells(void);      /* read-only: aktuelle Freelist-Laenge          */
#ifdef LISP65_EXT_HEAP
void ext_disk_read(uint16_t off, uint8_t *dst, uint16_t len); /* Scratch -> Bank 0, bulk */
#endif

/* ---- GC: mark-sweep with a precise shadow root stack ----
 * Every function that holds a live obj across an allocation MUST push it
 * (GC runs only inside alloc). cons() already protects both of its arguments. */
#ifndef GC_ROOTS
/* 512 is ample (the real peak is <100) and gives the tight mega65 bank 0 noticeably
 * more soft-stack room up to $D000. Overridable with -D. */
#define GC_ROOTS 512
#endif
extern obj      gc_rootstack[GC_ROOTS];
extern uint16_t gc_rootsp;
extern uint16_t gc_badobj;   /* diagnosis: corrupt objs rejected by gc_mark */
extern uint16_t gc_runs;    /* Statistik: Anzahl gc_collect-Laeufe */
#ifdef LISP65_GC_SCAN_PROBE
extern uint32_t gc_symbol_scan_visits;
#endif
#ifdef LISP65_GC_LANE_PROBE
/* Host-only collector-lane accounting.  The product build never enables
 * this: it exists to distinguish marking from sweep/freelist failures
 * without changing the collector being exercised. */
extern uint16_t gc_lane_last_marked;
extern uint16_t gc_lane_last_reclaimed;
extern uint16_t gc_lane_last_free_before;
extern uint16_t gc_lane_last_free_after;
extern uint16_t gc_lane_min_free_after;
extern uint16_t gc_lane_last_alloc_high;
extern uint16_t gc_lane_last_frozen;
#endif
#ifdef LISP65_GC_WORK_ATTRIBUTION_PROBE
/* Host-only work accounting for one collection.  These counters describe
 * logical collector work and modeled EXT transfers; they are not target
 * cycle or wall-clock measurements. */
enum {
    GC_ATTR_OUTSIDE = 0,
    GC_ATTR_ROOTS,
    GC_ATTR_SYMBOLS,
    GC_ATTR_TRACE,
    GC_ATTR_ARENA,
    GC_ATTR_SWEEP,
    GC_ATTR_PHASES
};
extern uint32_t gc_attr_dma_reads[GC_ATTR_PHASES];
extern uint32_t gc_attr_dma_writes[GC_ATTR_PHASES];
extern uint32_t gc_attr_dma_bytes[GC_ATTR_PHASES];
extern uint32_t gc_attr_total_dma_reads[GC_ATTR_PHASES];
extern uint32_t gc_attr_total_dma_writes[GC_ATTR_PHASES];
extern uint32_t gc_attr_total_dma_bytes[GC_ATTR_PHASES];
extern uint32_t gc_attr_mark_attempts[GC_ATTR_PHASES];
extern uint32_t gc_attr_new_marks[GC_ATTR_PHASES];
extern uint32_t gc_attr_mark_walk_visits[GC_ATTR_PHASES];
extern uint16_t gc_attr_shadow_roots;
extern uint16_t gc_attr_symbol_rows;
extern uint16_t gc_attr_symbol_value_reads;
extern uint16_t gc_attr_symbol_function_reads;
extern uint16_t gc_attr_trace_passes;
extern uint32_t gc_attr_trace_hot_visits;
extern uint32_t gc_attr_trace_ext_visits;
extern uint16_t gc_attr_arena_slots;
extern uint16_t gc_attr_arena_marked_slots;
extern uint16_t gc_attr_arena_copy_jobs;
extern uint32_t gc_attr_arena_copy_bytes;
extern uint16_t gc_attr_sweep_hot_visits;
extern uint16_t gc_attr_sweep_ext_visits;
extern uint16_t gc_attr_sweep_hot_reclaimed;
extern uint16_t gc_attr_sweep_ext_reclaimed;
#endif
#if !defined(__mos__) && defined(LISP65_EXT_HEAP_HOST_DMA_MODEL)
extern uint32_t ext_host_dma_read_jobs;
extern uint32_t ext_host_dma_write_jobs;
extern uint32_t ext_host_dma_bytes;
extern uint16_t ext_host_dma_faults;
#endif
extern uint8_t LISP65_C2_ZP mem_oom; /* 1 = alloc lief in OOM (REPL meldet + loescht) */
#define GC_PUSH(x)  (gc_rootstack[gc_rootsp++] = (obj)(x))
#define GC_SET(i,x) (gc_rootstack[(i)] = (obj)(x))   /* gepushten Slot aktualisieren */
#define GC_TOP      (gc_rootsp - 1)
#define GC_POPN(n)  (gc_rootsp = (uint16_t)(gc_rootsp - (n)))
#define GC_CAN_RESERVE(n) \
    (gc_rootsp <= GC_ROOTS && (uint16_t)(n) <= (uint16_t)(GC_ROOTS - gc_rootsp))

/* Soft-stack guard (F1, docs/vollprofil-stack-heap-collision.md): the C recursion (nested vm_run,
 * compile_expr, read_expr) grows on the mega65 DOWNWARD from $D000 towards the top of heap[].
 * lisp_stack_low() returns 1 as soon as the current frame reaches the heap cap plus margin
 * -> the caller aborts with VM_STACKOVER/err (an HONEST error instead of silent heap corruption).
 * Active only under -DLISP65_STACK_GUARD (the default product stays byte-identical). Host: the heap
 * is a global far from the native stack -> always 0 (no false alarm). */
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
void     str_arena_freeze(void);                               /* freeze the boot prefix */
uint16_t str_arena_used(void);                                 /* diagnosis: arena bytes in use */
uint16_t str_arena_capacity(void);                             /* build cap, read-only */
/* Streaming builder (no fixed buffer): open -> putc* -> close; do NOT allocate between open and close. */
obj      str_open(void);
uint8_t  str_putc(obj s, uint8_t c);                           /* 0 = arena full (mem_oom set) */
obj      str_close(obj s);

#ifdef LISP65_FIRST_CLASS_BUFFER
/* First-class byte buffers share the compacted byte arena with strings. The
 * object cell is stable; GC may relocate its contiguous byte span and update
 * the private offset. A buffer becomes immutable atomically by changing its
 * type to T_STR only after all writes have completed. */
obj      buf_make(uint16_t len);
obj      buf_from_string(obj string);
#if (defined(LISP65_C1_COMPILER_TIER) || defined(LISP65_C2_PRODUCT_CUT)) && defined(LISP65_EXT_HEAP)
obj      buf_from_stage(uint16_t len);
uint16_t buf_to_stage(obj buffer);
#endif
uint16_t buf_len(obj buffer);
uint8_t  buf_byte(obj buffer, uint16_t index);
void     buf_set(obj buffer, uint16_t index, uint8_t value);
obj      buf_freeze(obj buffer);
#endif

#endif

#endif /* LISP65_MEM_H */
