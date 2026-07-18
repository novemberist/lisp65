/* 1.1-A: reset-persistent library shelf staging.
 *
 * The parser and bulk copy execute from the profile-bound runtime overlay.
 * Only the small invocation seam remains resident in Bank 0. A verified
 * container is copied into the existing disk scratch, after which the proven
 * L65M preflight/commit path owns installation exactly as it does for D81.
 */
#include "attic_library_shelf.h"
#include "c1_phase_probe.h"
#include "mem.h"
#ifdef LISP65_C1_TRUST_FASTPATH_PROBE
#include "dialect-v2/libs/lcc-contract.h"
#endif

#ifdef LISP65_ATTIC_LIBRARY_SHELF
#include "io.h"
#include "mem.h"
#include "obj.h"
#include "vm_runtime_overlay.h"

#if defined(__mos__) && defined(LISP65_RUNTIME_OVERLAY)
#define L65S_FN __attribute__((section(".lisp65_rt_l65s"), noinline, used))
#define L65S_NAME_FN __attribute__((section(".lisp65_rt_l65s_name"), noinline, used))
#define L65S_DATA __attribute__((section(".lisp65_rt_l65s_data"), used))
#define L65S_RESIDENT __attribute__((section(".lisp65_resident_island"), noinline, used))
#else
#define L65S_FN
#define L65S_NAME_FN
#define L65S_DATA
#define L65S_RESIDENT
#endif

#ifdef LISP65_ATTIC_LIBRARY_SHELF_HOST_TEST
static const uint8_t *l65s_host_shelf;
static uint16_t l65s_host_shelf_length;
static uint8_t *l65s_host_scratch;
static uint16_t l65s_host_scratch_capacity;
static const char *l65s_host_name;

void l65s_host_bind(const uint8_t *shelf, uint16_t shelf_length,
                    uint8_t *scratch, uint16_t scratch_capacity,
                    const char *name) {
    l65s_host_shelf = shelf;
    l65s_host_shelf_length = shelf_length;
    l65s_host_scratch = scratch;
    l65s_host_scratch_capacity = scratch_capacity;
    l65s_host_name = name;
}
#endif

static L65S_FN uint16_t l65s_u16(const uint8_t *p) {
    return (uint16_t)p[0] | ((uint16_t)p[1] << 8);
}

static L65S_FN uint32_t l65s_u32(const uint8_t *p) {
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8)
        | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

#ifndef LISP65_ATTIC_LIBRARY_SHELF_HOST_TEST
static L65S_DATA uint8_t l65s_edma_job[20];

static L65S_FN void l65s_dma(l65s_stage_context *context, uint32_t source,
                             uint32_t target, uint16_t length) {
    uint8_t *job = l65s_edma_job;
    (void)context;
    job[0] = 0x0b; job[1] = 0x80; job[2] = (uint8_t)(source >> 20);
    job[3] = 0x81; job[4] = (uint8_t)(target >> 20);
    job[5] = 0x85; job[6] = 1; job[7] = 0; job[8] = 0;
    job[9] = (uint8_t)length; job[10] = (uint8_t)(length >> 8);
    job[11] = (uint8_t)source; job[12] = (uint8_t)(source >> 8);
    job[13] = (uint8_t)((source >> 16) & 0x0fu);
    job[14] = (uint8_t)target; job[15] = (uint8_t)(target >> 8);
    job[16] = (uint8_t)((target >> 16) & 0x0fu);
    job[17] = job[18] = job[19] = 0;
    __asm__ volatile(
        "lda #1\n\tsta $d703\n\tlda #0\n\tsta $d702\n\tsta $d704\n\t"
        "lda #mos16hi(l65s_edma_job)\n\tsta $d701\n\t"
        "lda #mos16lo(l65s_edma_job)\n\tsta $d705\n\t"
        ::: "a", "memory");
}
#endif

static L65S_FN uint8_t l65s_attic_read(l65s_stage_context *context,
                                       uint16_t offset, uint8_t *dst,
                                       uint16_t length) {
#ifdef LISP65_ATTIC_LIBRARY_SHELF_HOST_TEST
    uint16_t i;
    (void)context;
    if (!l65s_host_shelf || (uint32_t)offset + length > l65s_host_shelf_length)
        return 0;
    for (i = 0; i < length; i++) dst[i] = l65s_host_shelf[offset + i];
#else
    l65s_dma(context, L65S_ATTIC_BASE + offset,
             (uint32_t)(uintptr_t)dst, length);
#endif
    return 1;
}

static L65S_FN uint32_t l65s_crc32(l65s_stage_context *context,
                                   uint16_t offset, uint16_t length) {
    uint32_t crc = 0xfffffffful;
    uint16_t index;
    uint8_t bit, chunk;
    while (length) {
        chunk = length > sizeof context->buffer
                    ? sizeof context->buffer : (uint8_t)length;
        if (!l65s_attic_read(context, offset, context->buffer, chunk))
            return 0;
        for (index = 0; index < chunk; index++) {
            crc ^= context->buffer[index];
            bit = 8;
            do crc = (crc >> 1) ^
                (0xedb88320ul & (uint32_t)-(int32_t)(crc & 1u));
            while (--bit);
        }
        offset = (uint16_t)(offset + chunk);
        length = (uint16_t)(length - chunk);
    }
    return crc ^ 0xfffffffful;
}

static L65S_FN uint8_t l65s_stage_copy(l65s_stage_context *context,
                                       uint16_t offset, uint16_t length) {
#ifdef LISP65_ATTIC_LIBRARY_SHELF_HOST_TEST
    uint16_t i;
    (void)context;
    if (!l65s_host_shelf || !l65s_host_scratch ||
        (uint32_t)offset + length > l65s_host_shelf_length ||
        length > l65s_host_scratch_capacity)
        return 0;
    for (i = 0; i < length; i++) l65s_host_scratch[i] = l65s_host_shelf[offset + i];
#else
    l65s_dma(context, L65S_ATTIC_BASE + offset,
             LISP65_EXT_DISK_FILE_PHYSICAL, length);
#endif
    return 1;
}

L65S_NAME_FN uint8_t l65s_name_entry(void *opaque) {
    l65s_stage_context *context = (l65s_stage_context *)opaque;
    uint8_t length, a, b, c, d = 0, e = 0, f = 0, id = 0xffu;
    if (!context || context->abi_version != L65S_STAGE_ABI_VERSION ||
        context->context_size != sizeof *context)
        return L65S_STAGE_ERR_CONTEXT;
#ifndef LISP65_ATTIC_LIBRARY_SHELF_HOST_TEST
    if (!IS_PTR(context->name) || cell_type(context->name) != T_STR)
        return L65S_STAGE_ERR_NAME;
#endif
#ifdef LISP65_ATTIC_LIBRARY_SHELF_HOST_TEST
    if (!l65s_host_name) return L65S_STAGE_ERR_NAME;
    for (length = 0; l65s_host_name[length] && length < 7; length++) {}
    if (length != 3 && length != 4 && length != 6) return L65S_STAGE_ERR_NAME;
    a = (uint8_t)l65s_host_name[0]; b = (uint8_t)l65s_host_name[1];
    c = (uint8_t)l65s_host_name[2];
    if (length == 4) d = (uint8_t)l65s_host_name[3];
    if (length == 6) {
        d = (uint8_t)l65s_host_name[3]; e = (uint8_t)l65s_host_name[4];
        f = (uint8_t)l65s_host_name[5];
    }
#else
    length = (uint8_t)str_len(context->name);
    if (length != 3 && length != 4 && length != 6)
        return L65S_STAGE_ERR_NAME;
    a = str_byte(context->name, 0); b = str_byte(context->name, 1);
    c = str_byte(context->name, 2);
    if (length == 4) d = str_byte(context->name, 3);
    if (length == 6) {
        d = str_byte(context->name, 3); e = str_byte(context->name, 4);
        f = str_byte(context->name, 5);
    }
#endif
    if (a == 'i' && b == 'd' && c == 'e') {
        if (length == 3) id = 0;
        else if (d == 'x') id = 1;
    } else if (length == 4 && a == 'm' && b == '6' && c == '5' && d == 'd') {
        id = 2;
    } else if (length == 3 && a == 'l' && b == 'c' && c == 'c') {
        id = 4;
    } else if (length == 6 && a == 'b' && b == 'u' && c == 'f' &&
               d == 'f' && e == 'e' && f == 'r') {
        id = 3;
    }
    if (id == 0xffu) return L65S_STAGE_ERR_NAME;
    context->library_id = id;
#ifdef LISP65_C1_TRUST_FASTPATH_PROBE
    /* This is only a candidate bit in the private call context. It cannot
     * authorize anything until the stage overlay has verified and copied the
     * selected shelf record successfully. */
    context->reserved = (uint8_t)(
        id == LISP65_C1_COMPILER_SHELF_RECORD_ID &&
        IS_SYMI((obj)(uint16_t)(uintptr_t)lisp65_disk_lib_source.ctx));
#endif
    return L65S_STAGE_OK;
}

L65S_FN uint8_t l65s_stage_entry(void *opaque) {
    l65s_stage_context *context = (l65s_stage_context *)opaque;
    uint16_t record_offset, offset, length, total;
    uint32_t expected_crc;
    if (!context || context->abi_version != L65S_STAGE_ABI_VERSION ||
        context->context_size != sizeof *context) return L65S_STAGE_ERR_CONTEXT;
    lisp65_c1_phase_mark_for(LISP65_C1_PROBE_SHELF_TRANSFER,
                             LISP65_C1_PROBE_EDGE_BEGIN);
    context->length = 0;
#ifndef LISP65_C1_TRUST_FASTPATH_PROBE
    context->reserved = 0;
#endif
    if (context->library_id >= L65S_RECORDS ||
        !l65s_attic_read(context, 0, context->buffer, L65S_HEADER_BYTES))
        return context->status = L65S_STAGE_ERR_HEADER;
    if (context->buffer[0] != L65S_MAGIC_0 || context->buffer[1] != L65S_MAGIC_1 ||
        context->buffer[2] != L65S_MAGIC_2 || context->buffer[3] != L65S_MAGIC_3 ||
        context->buffer[4] != L65S_VERSION ||
        context->buffer[5] != L65S_HEADER_BYTES ||
        context->buffer[6] != L65S_RECORD_BYTES ||
        context->buffer[7] != L65S_RECORDS ||
        l65s_u16(context->buffer + 8) != L65S_HEADER_BYTES ||
        l65s_u16(context->buffer + 10) != L65S_PAYLOAD_OFF ||
        context->buffer[14] || context->buffer[15])
        return context->status = L65S_STAGE_ERR_HEADER;
    total = l65s_u16(context->buffer + 12);
    if (total < L65S_PAYLOAD_OFF)
        return context->status = L65S_STAGE_ERR_HEADER;
    expected_crc = l65s_u32(context->buffer + 20);
    if (l65s_crc32(context, L65S_HEADER_BYTES,
                   L65S_RECORD_BYTES * L65S_RECORDS) != expected_crc)
        return context->status = L65S_STAGE_ERR_CATALOG;
    record_offset = (uint16_t)(L65S_HEADER_BYTES +
        (uint16_t)context->library_id * L65S_RECORD_BYTES);
    if (!l65s_attic_read(context, record_offset, context->buffer,
                         L65S_RECORD_BYTES))
        return context->status = L65S_STAGE_ERR_CATALOG;
    offset = l65s_u16(context->buffer + 8);
    length = l65s_u16(context->buffer + 10);
    if (offset < L65S_PAYLOAD_OFF || length < 4u || length > DISK_EXT_FILE_MAX ||
        offset > total || length > (uint16_t)(total - offset))
        return context->status = L65S_STAGE_ERR_RANGE;
    /* The catalog CRC authenticates the selected descriptor. The copied L65M
     * container is then validated from scratch by the existing L65M CRC16
     * preflight before any directory entry is published. */
    if (!l65s_stage_copy(context, offset, length))
        return context->status = L65S_STAGE_ERR_COPY;
    context->length = length;
#if defined(LISP65_C1_TRUST_FASTPATH_PROBE) && \
    !defined(LISP65_ATTIC_LIBRARY_SHELF_HOST_TEST)
    /* Private one-shot attestation, created only after the catalog, selected
     * record and exact copy have all passed. Phase 00 consumes and clears the
     * tag synchronously before commit or C1 lifetime code can observe ctx. */
    if (context->reserved)
        lisp65_disk_lib_source.ctx = (void *)
            ((uintptr_t)lisp65_disk_lib_source.ctx | 1u);
#endif
    lisp65_c1_phase_mark_for(LISP65_C1_PROBE_SHELF_TRANSFER,
                             LISP65_C1_PROBE_EDGE_END);
    return context->status = L65S_STAGE_OK;
}

#if defined(LISP65_RUNTIME_OVERLAY) && !defined(LISP65_ATTIC_LIBRARY_SHELF_HOST_TEST)
L65S_RESIDENT unsigned char io_attic_load_lib(obj name) {
    l65s_stage_context context;
    vm_runtime_overlay_status transport;
    uint8_t result;
    if (!name) return 0;
    context.abi_version = L65S_STAGE_ABI_VERSION;
    context.context_size = sizeof context;
    context.length = 0; context.status = L65S_STAGE_ERR_CONTEXT;
    context.reserved = 0; context.reserved_name = 0;
    context.name = name; context.library_id = 0xffu;
    transport = vm_runtime_overlay_exec(L65S_NAME_SLOT, &context, &result);
    if (transport != VM_RUNTIME_OVERLAY_OK || result != L65S_STAGE_OK ||
        context.library_id >= L65S_RECORDS)
        return 0;
    transport = vm_runtime_overlay_exec(L65S_STAGE_SLOT, &context, &result);
    if (transport != VM_RUNTIME_OVERLAY_OK || result != L65S_STAGE_OK ||
        context.status != L65S_STAGE_OK || !context.length)
        return 0;
    result = io_disk_lib_staged(context.length);
    return result;
}

#endif
#endif /* LISP65_ATTIC_LIBRARY_SHELF */
