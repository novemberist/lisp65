/* Set B shared types; only the two latches below allocate persistent BSS. */
extern uint8_t vm_retire_prompt_quiescent(void);
extern uint8_t gc_cell_marked(uint16_t);
extern uint16_t gc_scan_high(void), gc_scan_frozen(void);
typedef struct { uint8_t ref[8], first, count, bad, victim; uint16_t generation; } c2r_ctx;
/* High bit admits retirement; low seven bits protect the boot prefix.
 * Zero is persistent session disarm, including untrusted boot media. */
static uint8_t c2r_boot_count;
#define RSCAN C2_APPEND_SECTION("retire_scan_a")
#define RCOMMIT C2_APPEND_SECTION("retire_prepare")
/* Durable record at Bank 5 DE20..DE67 (24 gap bytes remain unassigned):
 * 0 magic (A7 armed, published last); 1 victim; 2 old count; 3 phase/cursor;
 * 4..5 generation LE; 6 boot protection prefix; 7 reserved zero;
 * 8..39 victim before-image; 40..71 current source before-image.
 * FE invalidates, 80+c loads, c moves, FF publishes count then disarms.
 * Scratch 0..15 holds the scan; 16..87 is a disposable journal readback.
 * Root/code/entry/resolution high-water marks are never reclaimed. */
#define RJ 0xde20u
#define RMAGIC 0xa7u

static uint8_t c2r_gc_failed;
typedef struct { uint8_t next, mode, recovery, owned, auth; } c2r_dispatch;
#define RX ((c2r_ctx *)(void *)lisp65_c2_phase_scratch)
#define JJ (lisp65_c2_phase_scratch+16u)
_Static_assert(sizeof(c2r_ctx)<=16u,"context overlap");
_Static_assert(16u+72u<LISP65_C2_INSTALL_TRACE_OFFSET,"trace overlap");
uint8_t c2_retire_run(uint8_t mode);

