/* lisp65 — Bytecode-VM (Lane K). Vertrag: docs/bytecode-abi.md (P0).
 *
 * EINHEITLICHES Streaming-Modell: Code-Objekte liegen an einem "Code-Ort" (bank/offset/len);
 * vm_run laedt das Objekt per vm_code_load() in EINEN hot-Puffer und fuehrt es dort aus. CALL laedt
 * den Callee (ueberschreibt den Puffer), der Aufrufer laedt sein Objekt nach der Rueckkehr neu
 * (Reload-on-return, EIN Puffer). vm_code_load ist die einzige Plattform-Naht:
 *   - Host-Test: memcpy aus einem simulierten erw.-RAM-Array.
 *   - mega65:    F018-Bulk-DMA aus dem erweiterten RAM (HW-bewiesen, seicht).
 * Wert-Stack + Frame liegen auf gc_rootstack (automatisch GC-gerootet).
 */
#ifndef LISP65_VM_H
#define LISP65_VM_H

#include "obj.h"
#include "error_codes.h"

/* CP4 is an atomic product-profile cut, never a permissive feature toggle. */
#ifdef LISP65_V2_CARRIER_CUT
#ifndef LISP65_DIALECT_V2
#error "LISP65_V2_CARRIER_CUT requires LISP65_DIALECT_V2"
#endif
#ifndef LISP65_TREEWALK_STRIP
#error "LISP65_V2_CARRIER_CUT requires LISP65_TREEWALK_STRIP"
#endif
#ifndef LISP65_VM_NATIVE_APPLY
#error "LISP65_V2_CARRIER_CUT requires LISP65_VM_NATIVE_APPLY"
#endif
#ifndef LISP65_V2_NATIVE_CAPABILITIES
#error "LISP65_V2_CARRIER_CUT requires LISP65_V2_NATIVE_CAPABILITIES"
#endif
#ifndef LISP65_V2_NATIVE_STRING_CODECS
#error "LISP65_V2_CARRIER_CUT requires LISP65_V2_NATIVE_STRING_CODECS"
#endif
#ifndef LISP65_V2_SERVICE_REGISTRY_CLOSED
#error "LISP65_V2_CARRIER_CUT requires LISP65_V2_SERVICE_REGISTRY_CLOSED"
#endif
#endif

/* Opcodes — eingefrorener P0-Vertrag (docs/bytecode-abi.md §4). */
enum {
    OP_HALT=0, OP_PUSHI8=1, OP_ADD=2, OP_RET=5, OP_PUSHLIT=6,
    OP_PUSHARG0=11, OP_PUSHARG1=12, OP_PUSHARG2=13,
    OP_SUB=14, OP_MUL=15, OP_DIV=16, OP_MOD=17, OP_LESS=18, OP_GREATER=19, OP_REMAINDER=24,
    OP_JMPREL=28, OP_JFALSEREL=29, OP_EQ=30, OP_NOT=42, OP_PUSHNIL=43, OP_PUSHT=44,
    OP_CONS=51, OP_CAR=52, OP_CDR=53, OP_CONSP=54, OP_EQL=55, OP_PUSHARGN=56,
    OP_LOADL=57, OP_STOREL=58, OP_DROP=59, OP_CALL=60, OP_CALLPRIM=61, OP_TAILCALL=62,
    OP_CLOSURE=63, OP_UPVAL=64, OP_SETUPVAL=65
};

/* Code-Objekt-Header (docs/bytecode-abi.md §2). */
#define CO_MAGIC 0xB5
#define CO_OFF_MAGIC 0
#define CO_OFF_NARGS 1
#define CO_OFF_NLOCS 2
#define CO_OFF_FLAGS 3
#define CO_OFF_CLEN  4
#define CO_OFF_NLITS 6
#define CO_OFF_LITTAB 7

/* CodeObject flags. v1 emitted only REST. v2 adds artifact-bound arity:
 * required = nargs - OPTIONAL_COUNT; REST removes only the upper bound. */
#define CO_FLAG_REST              0x01u
#define CO_FLAG_STRICT_ARITY      0x02u
#define CO_FLAG_OPTIONAL_SHIFT    2u
#define CO_FLAG_OPTIONAL_MASK     0xfcu
#define CO_OPTIONAL_COUNT(flags)  ((uint8_t)((flags) >> CO_FLAG_OPTIONAL_SHIFT))
#define CO_ARITY_FLAGS(optional_count, rest) \
    ((uint8_t)(CO_FLAG_STRICT_ARITY | \
               ((rest) ? CO_FLAG_REST : 0u) | \
               ((uint8_t)(optional_count) << CO_FLAG_OPTIONAL_SHIFT)))

#ifdef LISP65_DIALECT_V2
#define LISP65_V2_CODE_FLAGS_CHECK(nargs, nlocals, flags) do { \
    if (!((flags) & CO_FLAG_STRICT_ARITY) || \
        CO_OPTIONAL_COUNT(flags) > (nargs) || \
        (((flags) & CO_FLAG_REST) && !(nlocals))) { \
        vm_status = VM_BADOPCODE; goto done; \
    } \
} while (0)
#else
#define LISP65_V2_CODE_FLAGS_CHECK(nargs, nlocals, flags) ((void)0)
#endif

/* VM-Status. */
enum {
    VM_OK=0, VM_HALT, VM_BADOPCODE, VM_TYPEERROR, VM_STACKOVER, VM_HEAPOOM,
    VM_DIRMISS, VM_STEPLIMIT, VM_ARITY, VM_NOTDESIGNATOR
};
extern uint8_t vm_status;
const char *vm_status_message(void);   /* kurz; mit LISP65_VM_DIAGNOSTICS inkl. PC/Opcode/Stack/Funktion */
lisp65_error_code vm_status_error_code(uint8_t status);

/* Plattform-Naht: laedt len Bytes vom Code-Ort (bank:off im erw. RAM) nach dst (hot).
 * MUSS vom Build bereitgestellt werden (Host: memcpy; mega65: Bulk-DMA). */
void vm_code_load(uint8_t bank, uint16_t off, uint16_t len, uint8_t *dst);

void vm_init(void);   /* internt t; einmal vor vm_run */
#if defined(LISP65_DIALECT_FAMILY_HARNESS) && defined(LISP65_DIALECT_V2)
/* Treewalk-only semantic oracle bridge for direct internal codec forms.
 * The symbols remain deliberately absent from function-designator dispatch. */
obj vm_family_internal_primitive(uint8_t pid, obj *args, uint8_t nargs);
#endif

/* Code-Directory (docs/bytecode-abi.md §5): Symbol -> Code-Ort. CALL/TAILCALL lösen den Callee
 * (littab[idx] = Symbol) hierüber auf. */
#ifndef VM_MAXARGS
/* 8 -> 12 (2026-07-02): lib/ide-buffer.lisp baut den 9-Feld-Buffer via (list ...9 Args) —
 * mit 8 warf die ECHTE VM VM_BADOPCODE, waehrend das Host-Oracle es durchliess (Drift!).
 * Kosten: +4 Rootstack-Slots je VM-Frame (Frame-Check nutzt VM_MAXARGS als Reserve). */
#define VM_MAXARGS 12
#endif
void vm_dir_reset(void);
uint16_t vm_dir_count(void);
uint16_t vm_dir_capacity(void);
#ifdef LISP65_C1_COMPILER_TIER
uint8_t vm_dir_truncate(uint16_t count);
#endif
int  vm_dir_add(obj name_sym, uint8_t bank, uint16_t off, uint16_t len);  /* Index oder -1 */
/* dir_n auf die naechste 8er-Block-Grenze padden (Disk-Bytecode-Libs; s. vm.c/docs). */
void vm_dir_align8(void);

/* Fuehrt das Code-Objekt am Ort (bank/off/len) mit nargs Argumenten aus. Ergebnis = TOS bei
 * HALT/RET; setzt vm_status. */
obj vm_run(uint8_t bank, uint16_t off, uint16_t len, const obj *args, uint8_t nargs);

/* K3-Bruecken. vm_run_dir: Lauf per Directory-Index (Tree-Walker -> VM, aus apply).
 * vm_treewalk_call: von eval.c gesetzter Hook (VM -> Tree-Walker bei CALL-Fehltreffer).
 * CP4 entfernt die Hook-ABI aus dem v2-Cut-Produkt; v1 behaelt sie bytegleich. */
obj vm_run_dir(int di, const obj *args, uint8_t n);
#ifndef LISP65_V2_CARRIER_CUT
extern obj (*vm_treewalk_call)(obj sym, const obj *args, uint8_t n);
extern obj (*vm_treewalk_apply)(obj fn, obj arglist);   /* fuer CALLPRIM apply/funcall (Prim 7/8) */
#endif

/* VM-Closure aus OP_CLOSURE: T_CLOSURE{a=MK_BCODE(di), b=upvals}. Wird im optionalen
 * lcc-install-Closure-Profil vom Treewalker-apply benutzt; compile-repl nutzt denselben
 * Closure-State nativ. */
#if defined(LISP65_COMPILE_REPL) || defined(LISP65_VM_NATIVE_APPLY) || defined(LISP65_LCC_INSTALL_CLOSURES)
obj vm_apply_bcode_closure(obj fn, obj arglist);
#endif

/* M7: VM-native Aufrufe. vm_native_call nimmt ein flaches argv; vm_native_apply
 * adaptiert eine Lisp-Liste und behaelt nur im v1-Profil den Treewalk-Fallback. */
#if defined(LISP65_COMPILE_REPL) || defined(LISP65_VM_NATIVE_APPLY)
obj vm_native_apply(obj fn, obj arglist);
#endif
#ifdef LISP65_DIRECTORY_ONLY_HARNESS
obj vm_directory_only_test_callprim(uint8_t pid, obj *args, uint8_t nargs);
#endif

#endif /* LISP65_VM_H */
