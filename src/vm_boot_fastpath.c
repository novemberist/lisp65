/* Profile-bound boot fastpath. Semantic validity is proved by the ship gate. */
#include "vm_boot_fastpath.h"
#ifdef LISP65_BOOT_STACK_PROBE
#include "vm_boot_overlay.h"
#endif

#if defined(LISP65_VM) && defined(LISP65_STAGED_BOOT_OVERLAY) && \
    defined(LISP65_RUNTIME_OVERLAY) && defined(LISP65_STDLIB_EXT_METADATA)

#include "mem.h"
#include "interrupt.h"
#include "symbol.h"
#include "vm.h"
#include "vm_embed.h"

#ifndef LISP65_BOOT_STDLIB_PROFILE_BUILD_ID
#error "generated boot stdlib profile binding is required"
#endif
#ifndef LISP65_BOOT_STDLIB_IMAGE_CRC16
#error "generated boot stdlib CRC binding is required"
#endif
#ifndef LISP65_BOOT_STDLIB_LIT_FIX_COUNT
#error "generated boot stdlib literal-kind binding is required"
#endif
#ifndef LISP65_BOOT_STDLIB_LIT_NIL_COUNT
#error "generated boot stdlib literal-kind binding is required"
#endif
#ifndef LISP65_BOOT_STDLIB_LIT_T_COUNT
#error "generated boot stdlib literal-kind binding is required"
#endif
#ifndef LISP65_BOOT_STDLIB_LIT_SYMBOL_COUNT
#error "generated boot stdlib literal-kind binding is required"
#endif
#ifndef LISP65_BOOT_STDLIB_LIT_STRING_COUNT
#error "generated boot stdlib literal-kind binding is required"
#endif
#ifndef LISP65_BOOT_STDLIB_LIT_CONS_COUNT
#error "generated boot stdlib literal-kind binding is required"
#endif
#ifndef LISP65_BOOT_STDLIB_LIT_LIST_COUNT
#error "generated boot stdlib literal-kind binding is required"
#endif

#if LISP65_BOOT_STDLIB_PROFILE_BUILD_ID != LISP65_BOOT_OVERLAY_PROFILE_BUILD_ID
#error "boot overlay and stdlib must share one profile build ID"
#endif
#if LISP65_BOOT_STDLIB_BANK != 5u || LISP65_BOOT_STDLIB_OFF != 0u
#error "profile-bound boot stdlib must start at Bank 5 offset zero"
#endif
#if LISP65_BOOT_STDLIB_IMAGE_BYTES != \
        (LISP65_BOOT_STDLIB_BLOB_BYTES + LISP65_BOOT_STDLIB_METADATA_BYTES)
#error "boot stdlib image span is inconsistent"
#endif
#if LISP65_BOOT_STDLIB_LIT_NIL_COUNT != 0u || \
        LISP65_BOOT_STDLIB_LIT_T_COUNT != 0u || \
        LISP65_BOOT_STDLIB_LIT_CONS_COUNT != 0u || \
        LISP65_BOOT_STDLIB_LIT_LIST_COUNT != 0u
#error "profiled boot fastpath only accepts fix, symbol, and string literals"
#endif
#if LISP65_BOOT_STDLIB_LIT_FIX_COUNT + \
        LISP65_BOOT_STDLIB_LIT_SYMBOL_COUNT + \
        LISP65_BOOT_STDLIB_LIT_STRING_COUNT != \
        LISP65_BOOT_STDLIB_PATCH_COUNT || \
        LISP65_BOOT_STDLIB_PATCH_COUNT != LISP65_BOOT_STDLIB_NODE_COUNT
#error "profiled boot fastpath literal-kind counts do not cover all patches"
#endif

#define BF_INLINE static __attribute__((always_inline)) inline
#define BF_SLICE(name) \
    __attribute__((section(".lisp65_rt_boot_" name), noinline, used))
#define BF_HELP(name) \
    static __attribute__((section(".lisp65_rt_boot_" name), noinline))

#define BF_NAME_MAX 34u
#define BF_CRC_POLY 0x1021u
#define BF_CRC_INIT 0xffffu

enum { BF_LIT_FIX=1, BF_LIT_NIL, BF_LIT_T, BF_LIT_SYMBOL,
       BF_LIT_CONS, BF_LIT_LIST, BF_LIT_STRING };

BF_INLINE uint16_t bf_u16(const uint8_t *p) {
    return (uint16_t)(p[0] | ((uint16_t)p[1] << 8));
}

BF_INLINE uint16_t bf_cookie(uint8_t phase) {
    return (uint16_t)(VM_BOOT_FASTPATH_COOKIE_BASE ^ phase);
}

BF_INLINE uint8_t bf_enter(vm_boot_fastpath_work *work, uint8_t phase) {
    if (!work) return 0;
    if (work->abi_version != VM_BOOT_FASTPATH_ABI_VERSION) {
        work->status = VM_BOOT_FASTPATH_ERR_ABI; return 0;
    }
    if (work->busy) {
        work->status = VM_BOOT_FASTPATH_ERR_REENTRY; return 0;
    }
    if (work->expected_phase != phase) {
        work->status = VM_BOOT_FASTPATH_ERR_PHASE; return 0;
    }
    if (work->cookie != bf_cookie(phase)) {
        work->status = VM_BOOT_FASTPATH_ERR_COOKIE; return 0;
    }
    work->busy = 1;
    work->overlay_calls++;
    return 1;
}

BF_INLINE uint8_t bf_leave(vm_boot_fastpath_work *work, uint8_t status,
                           uint8_t next) {
    work->busy = 0;
    work->status = status;
    if (status != VM_BOOT_FASTPATH_OK) next = VM_BOOT_FASTPATH_PHASE_COUNT;
    work->expected_phase = next;
    work->cookie = bf_cookie(next);
    work->finished = (uint8_t)(next == VM_BOOT_FASTPATH_PHASE_COUNT);
    return status;
}

BF_INLINE void bf_read_image(uint16_t off, uint8_t *dst, uint16_t length) {
    vm_code_load((uint8_t)LISP65_BOOT_STDLIB_BANK,
                 (uint16_t)(LISP65_BOOT_STDLIB_OFF + off), length, dst);
}

BF_INLINE void bf_read_metadata(uint16_t off, uint8_t *dst, uint16_t length) {
    bf_read_image((uint16_t)(LISP65_BOOT_STDLIB_BLOB_BYTES + off), dst, length);
}

void vm_boot_fastpath_prepare(vm_boot_fastpath_work *work) {
    uint8_t *bytes = (uint8_t *)work;
    uint16_t i;
    if (!work) return;
    for (i = 0; i < sizeof *work; i++) bytes[i] = 0;
    work->abi_version = VM_BOOT_FASTPATH_ABI_VERSION;
    work->cookie = bf_cookie(VM_BOOT_FASTPATH_PHASE_VERIFY);
}

BF_SLICE("00") uint8_t vm_boot_fastpath_phase_verify(void *context) {
    vm_boot_fastpath_work *work = context;
    uint8_t bytes[16], patch[4], node[10], word[2], count, i, x, ch;
    uint16_t off = 0, crc = BF_CRC_INIT, cursor, string_off;
    obj value, keep = NIL, link;
    uint8_t status = VM_BOOT_FASTPATH_OK;
    if (!bf_enter(work, VM_BOOT_FASTPATH_PHASE_VERIFY)) return work
        ? work->status : VM_BOOT_FASTPATH_ERR_CONTEXT;
    if (lisp65_stdlib_bank != LISP65_BOOT_STDLIB_BANK
        || lisp65_stdlib_off != LISP65_BOOT_STDLIB_OFF
        || lisp65_stdlib_blob_len != LISP65_BOOT_STDLIB_BLOB_BYTES
        || vm_dir_count() != 0u
        || vm_ext_code_watermark() != LISP65_BOOT_STDLIB_BLOB_BYTES
        || lisp_error_msg || mem_oom)
        status = VM_BOOT_FASTPATH_ERR_STATE;
    while (status == VM_BOOT_FASTPATH_OK
           && off < LISP65_BOOT_STDLIB_IMAGE_BYTES) {
        count = (uint8_t)((uint16_t)(LISP65_BOOT_STDLIB_IMAGE_BYTES - off)
                          > sizeof bytes ? sizeof bytes
                          : (uint16_t)(LISP65_BOOT_STDLIB_IMAGE_BYTES - off));
        bf_read_image(off, bytes, count);
        for (i = 0; i < count; i++) {
            x = (uint8_t)(bytes[i] ^ (uint8_t)(crc >> 8));
            x ^= (uint8_t)(x >> 4);
            crc = (uint16_t)((crc << 8) ^ ((uint16_t)x << 12)
                             ^ ((uint16_t)x << 5) ^ x);
        }
        off = (uint16_t)(off + count);
    }
    work->crc_bytes = off;
    work->crc_passes = 1;
    if (status == VM_BOOT_FASTPATH_OK
        && crc != LISP65_BOOT_STDLIB_IMAGE_CRC16)
        status = VM_BOOT_FASTPATH_ERR_CRC;
    if (status == VM_BOOT_FASTPATH_OK
        && LISP65_BOOT_STDLIB_LIT_STRING_COUNT != 0u) {
        keep = intern("%lit-keep");
        if (!keep || mem_oom || lisp_error_msg)
            status = VM_BOOT_FASTPATH_ERR_HEAP;
    }
    for (cursor = 0; status == VM_BOOT_FASTPATH_OK
                     && cursor < LISP65_BOOT_STDLIB_PATCH_COUNT; cursor++) {
        bf_read_metadata(
            (uint16_t)(LISP65_BOOT_STDLIB_PATCHES_OFF + cursor * 4u),
            patch, sizeof patch);
        bf_read_metadata((uint16_t)(LISP65_BOOT_STDLIB_NODES_OFF
                                    + bf_u16(patch + 2) * 10u),
                         node, sizeof node);
        if (node[0] == BF_LIT_SYMBOL) continue;
        if (node[0] == BF_LIT_FIX) {
            value = MKFIX((int16_t)bf_u16(node + 2));
            work->fix_literals++;
        } else if (node[0] == BF_LIT_STRING) {
            string_off = bf_u16(node + 8);
#ifdef LISP65_STRING_ARENA
            value = str_open();
            if (value == NIL) { status = VM_BOOT_FASTPATH_ERR_HEAP; break; }
            for (i = 0;; i++) {
                bf_read_metadata((uint16_t)(LISP65_BOOT_STDLIB_STRINGS_OFF
                                            + string_off + i), &ch, 1);
                if (!ch) break;
                if (!str_putc(value, ch)) {
                    status = VM_BOOT_FASTPATH_ERR_HEAP; break;
                }
            }
            value = str_close(value);
#else
            value = NIL;
            for (i = 0;; i++) {
                bf_read_metadata((uint16_t)(LISP65_BOOT_STDLIB_STRINGS_OFF
                                            + string_off + i), &ch, 1);
                if (!ch) break;
            }
            GC_PUSH(value);
            while (i) {
                i--;
                bf_read_metadata((uint16_t)(LISP65_BOOT_STDLIB_STRINGS_OFF
                                            + string_off + i), &ch, 1);
                value = cons(MKFIX(ch), gc_rootstack[GC_TOP]);
                GC_SET(GC_TOP, value);
            }
            value = alloc(T_STR);
            if (value != NIL) {
                cell_set_a(value, gc_rootstack[GC_TOP]);
                cell_set_b(value, NIL);
            }
            GC_POPN(1);
#endif
            if (value == NIL || mem_oom) {
                status = VM_BOOT_FASTPATH_ERR_HEAP; break;
            }
            GC_PUSH(value);
            link = cons(gc_rootstack[GC_TOP], sym_value(keep));
            if (link != NIL && !mem_oom) set_sym_value(keep, link);
            GC_POPN(1);
            if (link == NIL || mem_oom) {
                status = VM_BOOT_FASTPATH_ERR_HEAP; break;
            }
            work->string_literals++;
        } else {
            status = VM_BOOT_FASTPATH_ERR_PROFILE;
            break;
        }
        word[0] = (uint8_t)value;
        word[1] = (uint8_t)((uint16_t)value >> 8);
        vm_ext_write(word, 2, (uint8_t)LISP65_BOOT_STDLIB_BANK,
                     (uint16_t)(LISP65_BOOT_STDLIB_OFF + bf_u16(patch)));
    }
    if (status == VM_BOOT_FASTPATH_OK
        && (work->fix_literals != LISP65_BOOT_STDLIB_LIT_FIX_COUNT
            || work->string_literals != LISP65_BOOT_STDLIB_LIT_STRING_COUNT))
        status = VM_BOOT_FASTPATH_ERR_PROFILE;
    return bf_leave(work, status, VM_BOOT_FASTPATH_PHASE_PATCHES);
}

BF_HELP("01") void bf_name_01(uint16_t off, char *dst) {
    uint16_t i;
    for (i = 0; i < BF_NAME_MAX - 1u; i++) {
        bf_read_metadata((uint16_t)(LISP65_BOOT_STDLIB_STRINGS_OFF + off + i),
                         (uint8_t *)dst + i, 1);
        if (!dst[i]) return;
    }
    dst[BF_NAME_MAX - 1u] = 0;
}

BF_SLICE("01") uint8_t vm_boot_fastpath_phase_patches(void *context) {
    vm_boot_fastpath_work *work = context;
    uint8_t patch[4], node[10], word[2];
    obj value;
    uint8_t status = VM_BOOT_FASTPATH_OK;
    if (!bf_enter(work, VM_BOOT_FASTPATH_PHASE_PATCHES)) return work
        ? work->status : VM_BOOT_FASTPATH_ERR_CONTEXT;
    if (work->fix_literals != LISP65_BOOT_STDLIB_LIT_FIX_COUNT
        || work->string_literals != LISP65_BOOT_STDLIB_LIT_STRING_COUNT)
        status = VM_BOOT_FASTPATH_ERR_PROFILE;
    while (status == VM_BOOT_FASTPATH_OK
           && work->cursor < LISP65_BOOT_STDLIB_PATCH_COUNT) {
        bf_read_metadata(
            (uint16_t)(LISP65_BOOT_STDLIB_PATCHES_OFF + work->cursor * 4u),
            patch, sizeof patch);
        bf_read_metadata((uint16_t)(LISP65_BOOT_STDLIB_NODES_OFF
                                    + bf_u16(patch + 2) * 10u),
                         node, sizeof node);
        if (node[0] == BF_LIT_SYMBOL) {
            char name[BF_NAME_MAX];
            bf_name_01(bf_u16(node + 8), name);
            value = intern(name);
            if (mem_oom || lisp_error_msg) {
                status = VM_BOOT_FASTPATH_ERR_HEAP; break;
            }
            word[0] = (uint8_t)value;
            word[1] = (uint8_t)((uint16_t)value >> 8);
            vm_ext_write(word, 2, (uint8_t)LISP65_BOOT_STDLIB_BANK,
                         (uint16_t)(LISP65_BOOT_STDLIB_OFF + bf_u16(patch)));
            work->symbol_literals++;
        } else if (node[0] != BF_LIT_FIX && node[0] != BF_LIT_STRING) {
            status = VM_BOOT_FASTPATH_ERR_PROFILE;
            break;
        }
        work->cursor++;
    }
    if (status == VM_BOOT_FASTPATH_OK
        && work->symbol_literals != LISP65_BOOT_STDLIB_LIT_SYMBOL_COUNT)
        status = VM_BOOT_FASTPATH_ERR_PROFILE;
    if (status == VM_BOOT_FASTPATH_OK) work->cursor = 0;
    return bf_leave(work, status, VM_BOOT_FASTPATH_PHASE_ENTRIES);
}

BF_HELP("02") void bf_name_02(uint16_t off, char *dst) {
    uint16_t i;
    for (i = 0; i < BF_NAME_MAX - 1u; i++) {
        bf_read_metadata((uint16_t)(LISP65_BOOT_STDLIB_STRINGS_OFF + off + i),
                         (uint8_t *)dst + i, 1);
        if (!dst[i]) return;
    }
    dst[BF_NAME_MAX - 1u] = 0;
}

BF_HELP("02") uint8_t bf_register_02(const char *name, uint8_t flags,
                                      uint16_t off, uint16_t length) {
    obj symbol;
    int directory_index;
    if (flags & (uint8_t)~1u) return 0;
    symbol = intern(name);
    if (mem_oom || lisp_error_msg) return 0;
    directory_index = vm_dir_add(symbol, (uint8_t)LISP65_BOOT_STDLIB_BANK,
                                 off, length);
    if (directory_index < 0) return 0;
    if (flags & 1u) {
        obj macro = alloc(T_MACRO);
        if (macro == NIL || mem_oom) return 0;
        cell_set_a(macro, MK_BCODE(directory_index)); cell_set_b(macro, NIL);
        set_sym_function(symbol, macro);
    } else {
        set_sym_function(symbol, MK_BCODE(directory_index));
    }
    return 1;
}

BF_SLICE("02") uint8_t vm_boot_fastpath_phase_entries(void *context) {
    vm_boot_fastpath_work *work = context;
    uint8_t entry[8], status = VM_BOOT_FASTPATH_OK;
    char name[BF_NAME_MAX];
    uint16_t off, length;
    if (!bf_enter(work, VM_BOOT_FASTPATH_PHASE_ENTRIES)) return work
        ? work->status : VM_BOOT_FASTPATH_ERR_CONTEXT;
    while (status == VM_BOOT_FASTPATH_OK
           && work->cursor < LISP65_BOOT_STDLIB_ENTRY_COUNT) {
        bf_read_metadata(
            (uint16_t)(LISP65_BOOT_STDLIB_ENTRIES_OFF + work->cursor * 8u),
            entry, sizeof entry);
        bf_name_02(bf_u16(entry), name);
        off = bf_u16(entry + 4); length = bf_u16(entry + 6);
        if (off > LISP65_BOOT_STDLIB_BLOB_BYTES
            || length > (uint16_t)(LISP65_BOOT_STDLIB_BLOB_BYTES - off)
            || !bf_register_02(name, entry[3],
                               (uint16_t)(LISP65_BOOT_STDLIB_OFF + off), length))
            status = VM_BOOT_FASTPATH_ERR_DIRECTORY;
        else
            work->cursor++;
    }
    if (status == VM_BOOT_FASTPATH_OK) {
        work->cursor = 0;
        if (work->crc_passes != VM_BOOT_FASTPATH_CRC_PASSES
            || work->crc_bytes != LISP65_BOOT_STDLIB_IMAGE_BYTES
            || work->overlay_calls != VM_BOOT_FASTPATH_OVERLAY_CALLS
            || work->fix_literals != LISP65_BOOT_STDLIB_LIT_FIX_COUNT
            || work->symbol_literals != LISP65_BOOT_STDLIB_LIT_SYMBOL_COUNT
            || work->string_literals != LISP65_BOOT_STDLIB_LIT_STRING_COUNT)
            status = VM_BOOT_FASTPATH_ERR_STATE;
        else {
            gc_freeze_boot();
#ifdef LISP65_BOOT_STACK_PROBE
            /* No later boot slice may overwrite the runtime watermark. */
            vm_boot_stack_probe_begin();
#endif
        }
    }
    return bf_leave(work, status, VM_BOOT_FASTPATH_PHASE_COUNT);
}

#endif
