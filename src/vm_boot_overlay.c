/* Profile-bound EXT-RAM staging bootstrap. Entire unit is opt-in. */
#include "vm_boot_overlay.h"

#if defined(LISP65_VM) && defined(LISP65_STAGED_BOOT_OVERLAY)
#include "vm.h"
#include "interrupt.h"
#include "eval.h"
#include "mem.h"
#include "c2_lite_bank3_stage.h"
#include "error_codes.h"
#ifdef LISP65_C2_LITE_BANK3_STAGING
#include "c2_kernal_facade.h"
#endif

#if defined(LISP65_BOOT_OVERLAY_WIPE) && !defined(LISP65_BOOT_STACK_PROBE)
#error "LISP65_BOOT_OVERLAY_WIPE requires LISP65_BOOT_STACK_PROBE"
#endif

#ifndef LISP65_BOOT_OVERLAY_STAGE_BANK
#error "LISP65_BOOT_OVERLAY_STAGE_BANK is required"
#endif
#ifndef LISP65_BOOT_OVERLAY_STAGE_OFF
#error "LISP65_BOOT_OVERLAY_STAGE_OFF is required"
#endif
#ifndef LISP65_BOOT_OVERLAY_PROFILE_BUILD_ID
#error "LISP65_BOOT_OVERLAY_PROFILE_BUILD_ID is required"
#endif
#if LISP65_BOOT_OVERLAY_STAGE_BANK > 255
#error "boot-overlay stage bank must fit in uint8_t"
#endif
#if LISP65_BOOT_OVERLAY_STAGE_OFF > (0x10000UL - LISP65_BOOT_OVERLAY_HEADER_SIZE)
#error "boot-overlay descriptor exceeds its EXT bank"
#endif

#ifdef LISP65_BOOT_OVERLAY_HOST_TEST
/* Native smoke substitutes a host buffer for the 16-bit Bank-0 destination. */
extern uint8_t lisp65_boot_overlay_host_target[];
extern const uint16_t lisp65_boot_overlay_host_vma;
extern const uint16_t lisp65_boot_overlay_host_entry;
extern const uint16_t lisp65_boot_overlay_host_len;
#define OV_VMA    lisp65_boot_overlay_host_vma
#define OV_ENTRY  lisp65_boot_overlay_host_entry
#define OV_LEN    lisp65_boot_overlay_host_len
#define OV_TARGET lisp65_boot_overlay_host_target
#define OV_CALL() vm_workbench_boot_overlay_entry()
#else
/* Supplied and asserted by the Workbench overlay linker script. */
extern uint8_t __lisp65_workbench_overlay_start[];
extern uint8_t __lisp65_workbench_overlay_end[];
#define OV_VMA    ((uint16_t)(uintptr_t)__lisp65_workbench_overlay_start)
#define OV_ENTRY  ((uint16_t)(uintptr_t)vm_workbench_boot_overlay_entry)
#define OV_LEN    ((uint16_t)(__lisp65_workbench_overlay_end - \
                              __lisp65_workbench_overlay_start))
#define OV_TARGET __lisp65_workbench_overlay_start
#define OV_CALL() vm_workbench_boot_overlay_entry()
#endif

#if defined(LISP65_C2_LITE_BANK3_STAGING) && \
    !defined(LISP65_BOOT_OVERLAY_HOST_TEST)
extern uint8_t __lisp65_boot_bank3_stage_start[];
extern uint8_t __lisp65_boot_bank3_stage_end[];
void vm_bank3_boot_stage_entry(void);
#define B3_VMA ((uint16_t)(uintptr_t)__lisp65_boot_bank3_stage_start)
#define B3_ENTRY ((uint16_t)(uintptr_t)vm_bank3_boot_stage_entry)
#define B3_LEN ((uint16_t)(__lisp65_boot_bank3_stage_end - \
                           __lisp65_boot_bank3_stage_start))
#define B3_CALL() vm_bank3_boot_stage_entry()
#define B3_CHAIN_BANK 2u
#endif

#ifdef LISP65_BOOT_STACK_PROBE
#ifdef LISP65_BOOT_OVERLAY_HOST_TEST
/* The isolated native harness supplies logical Bank-0/Page-1 buffers. */
extern uint8_t lisp65_boot_probe_host_soft[];
extern uint16_t lisp65_boot_probe_host_soft_floor;
extern uint16_t lisp65_boot_probe_host_soft_sp;
extern uint8_t lisp65_boot_probe_host_page1[256];
extern uint8_t lisp65_boot_probe_host_hw_sp;
#define PROBE_SOFT_FLOOR()       lisp65_boot_probe_host_soft_floor
#define PROBE_SOFT_SP()          lisp65_boot_probe_host_soft_sp
#define PROBE_SOFT_READ(a)       lisp65_boot_probe_host_soft[(uint16_t)(a) - lisp65_boot_probe_host_soft_floor]
#define PROBE_SOFT_WRITE(a, v)   (lisp65_boot_probe_host_soft[(uint16_t)(a) - lisp65_boot_probe_host_soft_floor] = (v))
#define PROBE_PAGE_READ(i)       lisp65_boot_probe_host_page1[(uint8_t)(i)]
#define PROBE_PAGE_WRITE(i, v)   (lisp65_boot_probe_host_page1[(uint8_t)(i)] = (v))
#else
extern uint8_t __lisp65_workbench_runtime_overlay_limit[];
#define PROBE_SOFT_FLOOR()       ((uint16_t)(uintptr_t)__lisp65_workbench_runtime_overlay_limit)
#define PROBE_SOFT_SP()          (*(volatile uint16_t *)0x0002u)
#define PROBE_SOFT_READ(a)       (*(volatile uint8_t *)(uintptr_t)(uint16_t)(a))
#define PROBE_SOFT_WRITE(a, v)   (*(volatile uint8_t *)(uintptr_t)(uint16_t)(a) = (v))
#define PROBE_PAGE_READ(i)       (*(volatile uint8_t *)(uintptr_t)(0x0100u + (uint8_t)(i)))
#define PROBE_PAGE_WRITE(i, v)   (*(volatile uint8_t *)(uintptr_t)(0x0100u + (uint8_t)(i)) = (v))
#endif

__attribute__((used)) volatile uint8_t  lisp65_boot_probe_complete;
__attribute__((used)) volatile uint8_t  lisp65_boot_probe_flags;
__attribute__((used)) volatile uint16_t lisp65_boot_probe_soft_initial;
#ifdef LISP65_BOOT_OVERLAY_HOST_TEST
__attribute__((used)) volatile uint16_t lisp65_boot_probe_soft_low;
__attribute__((used)) volatile uint16_t lisp65_boot_probe_soft_margin;
#endif
__attribute__((used)) volatile uint8_t  lisp65_boot_probe_hw_initial;
#ifdef LISP65_BOOT_OVERLAY_HOST_TEST
__attribute__((used)) volatile uint8_t  lisp65_boot_probe_hw_low;
__attribute__((used)) volatile uint8_t  lisp65_boot_probe_hw_remaining;
#endif

#define PROBE_SOFT_CANARY 0xa5u
#define PROBE_HW_CANARY   0x5au

#ifdef LISP65_BOOT_OVERLAY_HOST_TEST
#define STACK_PROBE_CODE
#else
#define STACK_PROBE_CODE __attribute__((section(".lisp65_rt_boot_02")))
#endif

STACK_PROBE_CODE __attribute__((noinline, used))
void vm_boot_stack_probe_begin(void) {
    uint16_t address, floor = PROBE_SOFT_FLOOR();
    uint8_t page;

    lisp65_boot_probe_complete = 0;
    lisp65_boot_probe_flags = 0;
    lisp65_boot_probe_soft_initial = PROBE_SOFT_SP();
#ifdef LISP65_BOOT_OVERLAY_HOST_TEST
    lisp65_boot_probe_hw_initial = lisp65_boot_probe_host_hw_sp;
#else
    __asm__ volatile(
        "tsx\n\t"
        "stx lisp65_boot_probe_hw_initial"
        ::: "x", "memory");
#endif

    if (lisp65_boot_probe_soft_initial <= floor) {
        lisp65_boot_probe_flags |=
            LISP65_BOOT_PROBE_SOFT_RANGE_BAD | LISP65_BOOT_PROBE_SOFT_EXHAUSTED;
#ifdef LISP65_BOOT_OVERLAY_HOST_TEST
        lisp65_boot_probe_soft_low = floor;
        lisp65_boot_probe_soft_margin = 0;
#endif
    } else {
        for (address = floor; address < lisp65_boot_probe_soft_initial; address++)
            PROBE_SOFT_WRITE(address, PROBE_SOFT_CANARY);
    }

    page = 0;
    do {
        PROBE_PAGE_WRITE(page, PROBE_HW_CANARY);
    } while (page++ != lisp65_boot_probe_hw_initial);
#ifndef LISP65_BOOT_OVERLAY_HOST_TEST
    /* Target readback scans the armed ranges after runtime activity. */
    lisp65_boot_probe_complete = 1;
#endif
}

#ifdef LISP65_BOOT_OVERLAY_HOST_TEST
__attribute__((noinline, used)) void vm_boot_stack_probe_end(void) {
    uint16_t address, floor = PROBE_SOFT_FLOOR();
    uint8_t page;

    if (lisp65_boot_probe_soft_initial > floor) {
        lisp65_boot_probe_soft_low = lisp65_boot_probe_soft_initial;
        for (address = floor; address < lisp65_boot_probe_soft_initial; address++) {
            if (PROBE_SOFT_READ(address) != PROBE_SOFT_CANARY) {
                lisp65_boot_probe_soft_low = address;
                break;
            }
        }
        lisp65_boot_probe_soft_margin =
            (uint16_t)(lisp65_boot_probe_soft_low - floor);
        if (lisp65_boot_probe_soft_low == floor)
            lisp65_boot_probe_flags |= LISP65_BOOT_PROBE_SOFT_EXHAUSTED;
    }

    lisp65_boot_probe_hw_low = lisp65_boot_probe_hw_initial;
    page = 0;
    do {
        if (PROBE_PAGE_READ(page) != PROBE_HW_CANARY) {
            lisp65_boot_probe_hw_low = page;
            break;
        }
    } while (page++ != lisp65_boot_probe_hw_initial);
    /* Deliberately conservative: byte hw_low itself is not counted free. */
    lisp65_boot_probe_hw_remaining = lisp65_boot_probe_hw_low;
    if (lisp65_boot_probe_hw_low == 0)
        lisp65_boot_probe_flags |= LISP65_BOOT_PROBE_HW_EXHAUSTED;
    lisp65_boot_probe_complete = 1;
}
#endif
#undef STACK_PROBE_CODE
#endif /* LISP65_BOOT_STACK_PROBE */

#ifdef LISP65_BOOT_OVERLAY_WIPE
__attribute__((used)) volatile uint8_t lisp65_boot_overlay_wipe_ok;

__attribute__((noinline, used)) void vm_boot_overlay_wipe(void);
#endif

static uint8_t ov_wipe_target(void) {
    volatile uint8_t *target = (volatile uint8_t *)OV_TARGET;
    uint16_t i, length = OV_LEN;
#ifdef LISP65_BOOT_OVERLAY_WIPE
    lisp65_boot_overlay_wipe_ok = 0;
#endif
    for (i = 0; i < length; i++) {
        target[i] = 0;
        if (target[i]) return 0;
    }
#ifdef LISP65_BOOT_OVERLAY_WIPE
    lisp65_boot_overlay_wipe_ok = 1;
#endif
    return 1;
}

#if defined(LISP65_BOOT_OVERLAY_WIPE) && defined(LISP65_BOOT_OVERLAY_HOST_TEST)
__attribute__((noinline, used)) void vm_boot_overlay_wipe(void) {
    (void)ov_wipe_target();
}
#endif

uint8_t vm_boot_overlay_status;
static uint8_t ov_started;

#ifdef LISP65_BOOT_OVERLAY_HOST_TEST
void vm_boot_overlay_host_reset(void) { ov_started = 0; }
#endif

/* The non-LTO bootstrap commit leaf calls this ordinary resident helper.  Keep
 * it a sized ELF citizen instead of letting LTO clone the CRC into the seam. */
__attribute__((noinline, used))
uint16_t ov_crc16(const uint8_t *p, uint16_t n) {
    uint16_t crc = LISP65_BOOT_OVERLAY_CRC16_INIT;
    while (n--) {
        uint8_t bits = 8;
        crc ^= (uint16_t)*p++ << 8;
        while (bits--) {
            if (crc & 0x8000u)
                crc = (uint16_t)((crc << 1) ^ LISP65_BOOT_OVERLAY_CRC16_POLY);
            else
                crc = (uint16_t)(crc << 1);
        }
    }
    return crc;
}

static uint16_t ov_u16(const uint8_t *p) {
    return (uint16_t)(p[0] | ((uint16_t)p[1] << 8));
}

__attribute__((section(".lisp65_boot"), noinline, used))
void vm_workbench_boot_overlay_entry(void) {
    eval_init();
}

#ifdef LISP65_C2_LITE_BANK3_STAGING
/* The six-byte resident seam is emitted by c2_boot_chain_commit.s.  Keeping
 * the Workbench geometry outside both overlay records prevents an overlay
 * from owning a direct reference to its NOCROSSREFS sibling. */
extern const uint16_t vm_boot_overlay_chain_expected[3];

/* Record 1 has an 18-byte prefix reserved by the linker.  Once its code is
 * executing beyond that prefix, it may reuse the prefix as the descriptor
 * buffer for Record 2 without overwriting a live instruction. */
static __attribute__((noinline, used,
                      section(".lisp65_boot_bank3_stage")))
uint16_t ov_bank_crc16(uint8_t bank, uint16_t length) {
    uint8_t block[32];
    uint16_t crc = LISP65_BOOT_OVERLAY_CRC16_INIT;
    uint16_t offset = 0u;
    while (offset != length) {
        uint8_t i = 0u;
        uint8_t chunk = (uint16_t)(length - offset) > sizeof block
            ? sizeof block : (uint8_t)(length - offset);
        c2_facade_vm_code_load(bank, offset, chunk, block);
        while (i != chunk) {
            uint8_t bits = 8u;
            crc ^= (uint16_t)block[i++] << 8;
            do {
                crc = (crc & 0x8000u)
                    ? (uint16_t)((crc << 1) ^
                                 LISP65_BOOT_OVERLAY_CRC16_POLY)
                    : (uint16_t)(crc << 1);
            } while (--bits);
        }
        offset = (uint16_t)(offset + chunk);
    }
    return crc;
}

__attribute__((noinline, used, section(".lisp65_boot_bank3_stage")))
uint8_t vm_boot_overlay_chain_prepare(void) {
    uint8_t *header = __lisp65_boot_bank3_stage_start;
    uint16_t expected_vma = vm_boot_overlay_chain_expected[0];
    uint16_t expected_entry = vm_boot_overlay_chain_expected[1];
    uint16_t expected_length = vm_boot_overlay_chain_expected[2];
    uint16_t next = (uint16_t)(((uint32_t)LISP65_BOOT_OVERLAY_STAGE_OFF
        + LISP65_BOOT_OVERLAY_HEADER_SIZE + B3_LEN + 0xffu) & ~0xffu);
    uint16_t expected_crc;
    uint32_t end = (uint32_t)next + LISP65_BOOT_OVERLAY_HEADER_SIZE
        + expected_length;

    if (end > 0x10000UL) return 0;
    vm_boot_overlay_status = VM_BOOT_OVERLAY_ERR_MAGIC;
    c2_facade_vm_code_load((uint8_t)LISP65_BOOT_OVERLAY_STAGE_BANK,
                           next, LISP65_BOOT_OVERLAY_HEADER_SIZE, header);
    if (header[0] != LISP65_BOOT_OVERLAY_MAGIC_0 ||
        header[1] != LISP65_BOOT_OVERLAY_MAGIC_1 ||
        header[2] != LISP65_BOOT_OVERLAY_MAGIC_2 ||
        header[3] != LISP65_BOOT_OVERLAY_MAGIC_3) return 0;
    vm_boot_overlay_status = VM_BOOT_OVERLAY_ERR_VERSION;
    if (header[4] != LISP65_BOOT_OVERLAY_VERSION) return 0;
    vm_boot_overlay_status = VM_BOOT_OVERLAY_ERR_HEADER;
    if (header[5] != LISP65_BOOT_OVERLAY_HEADER_SIZE) return 0;
    vm_boot_overlay_status = VM_BOOT_OVERLAY_ERR_PROFILE;
    if (header[6] != (uint8_t)LISP65_BOOT_OVERLAY_PROFILE_BUILD_ID ||
        header[7] != (uint8_t)(LISP65_BOOT_OVERLAY_PROFILE_BUILD_ID >> 8) ||
        header[8] != (uint8_t)(LISP65_BOOT_OVERLAY_PROFILE_BUILD_ID >> 16) ||
        header[9] != (uint8_t)(LISP65_BOOT_OVERLAY_PROFILE_BUILD_ID >> 24))
        return 0;
    vm_boot_overlay_status = VM_BOOT_OVERLAY_ERR_VMA;
    if (ov_u16(header + 10) != expected_vma) return 0;
    vm_boot_overlay_status = VM_BOOT_OVERLAY_ERR_ENTRY;
    if (ov_u16(header + 12) != expected_entry) return 0;
    vm_boot_overlay_status = VM_BOOT_OVERLAY_ERR_LENGTH;
    if (ov_u16(header + 14) != expected_length) return 0;
    expected_crc = ov_u16(header + 16);

    /* Record 1 owns all parsing and source verification for Record 2.  Bank 2
     * is unpublished scratch here; the later C2-lite code stage replaces it
     * before READY. */
    c2_facade_c2_dma((uint16_t)(next + LISP65_BOOT_OVERLAY_HEADER_SIZE),
                     (uint8_t)LISP65_BOOT_OVERLAY_STAGE_BANK,
                     0u, B3_CHAIN_BANK, expected_length);
    vm_boot_overlay_status = VM_BOOT_OVERLAY_ERR_CRC;
    return ov_bank_crc16(B3_CHAIN_BANK, expected_length) == expected_crc;
}

__attribute__((section(".lisp65_boot_bank3_stage"), noinline, used))
void vm_bank3_boot_stage_fail(void) {
    lisp_abort_static(LISP65_ERR_RUNTIME_FAMILY_STAGE,
                      "runtime family staging failed; redeploy");
}

/* c2_boot_chain_commit.s owns the sole resident commit seam.  C deliberately
 * has no second implementation of that ABI. */
#endif

__attribute__((noinline)) uint8_t vm_install_staged_boot_overlay(void) {
    uint8_t *header = OV_TARGET;
    uint16_t expected_crc;
#if defined(LISP65_C2_LITE_BANK3_STAGING) && \
    !defined(LISP65_BOOT_OVERLAY_HOST_TEST)
#define FIRST_VMA B3_VMA
#define FIRST_ENTRY B3_ENTRY
#define FIRST_LEN B3_LEN
#define FIRST_CALL() B3_CALL()
#else
#define FIRST_VMA OV_VMA
#define FIRST_ENTRY OV_ENTRY
#define FIRST_LEN OV_LEN
#define FIRST_CALL() OV_CALL()
#endif

    if (ov_started) {
        vm_boot_overlay_status = VM_BOOT_OVERLAY_ERR_REENTRY;
        return VM_BOOT_OVERLAY_ERR_REENTRY;
    }
    ov_started = 1;
    vm_boot_overlay_status = VM_BOOT_OVERLAY_ERR_LENGTH;
    if (!FIRST_VMA || FIRST_LEN < LISP65_BOOT_OVERLAY_HEADER_SIZE) goto done;

    vm_boot_overlay_status = VM_BOOT_OVERLAY_ERR_MAGIC;
    vm_code_load((uint8_t)LISP65_BOOT_OVERLAY_STAGE_BANK,
                 (uint16_t)LISP65_BOOT_OVERLAY_STAGE_OFF,
                 LISP65_BOOT_OVERLAY_HEADER_SIZE, header);
    if (header[0] != LISP65_BOOT_OVERLAY_MAGIC_0 ||
        header[1] != LISP65_BOOT_OVERLAY_MAGIC_1 ||
        header[2] != LISP65_BOOT_OVERLAY_MAGIC_2 ||
        header[3] != LISP65_BOOT_OVERLAY_MAGIC_3) goto done;
    vm_boot_overlay_status = VM_BOOT_OVERLAY_ERR_VERSION;
    if (header[4] != LISP65_BOOT_OVERLAY_VERSION) goto done;
    vm_boot_overlay_status = VM_BOOT_OVERLAY_ERR_HEADER;
    if (header[5] != LISP65_BOOT_OVERLAY_HEADER_SIZE) goto done;
    vm_boot_overlay_status = VM_BOOT_OVERLAY_ERR_PROFILE;
    if (header[6] != (uint8_t)LISP65_BOOT_OVERLAY_PROFILE_BUILD_ID ||
        header[7] != (uint8_t)(LISP65_BOOT_OVERLAY_PROFILE_BUILD_ID >> 8) ||
        header[8] != (uint8_t)(LISP65_BOOT_OVERLAY_PROFILE_BUILD_ID >> 16) ||
        header[9] != (uint8_t)(LISP65_BOOT_OVERLAY_PROFILE_BUILD_ID >> 24)) goto done;
    vm_boot_overlay_status = VM_BOOT_OVERLAY_ERR_VMA;
    if (ov_u16(header + 10) != FIRST_VMA) goto done;
    vm_boot_overlay_status = VM_BOOT_OVERLAY_ERR_ENTRY;
    if (ov_u16(header + 12) != FIRST_ENTRY) goto done;
    vm_boot_overlay_status = VM_BOOT_OVERLAY_ERR_LENGTH;
    if (ov_u16(header + 14) != FIRST_LEN) goto done;
    expected_crc = ov_u16(header + 16);

    vm_code_load((uint8_t)LISP65_BOOT_OVERLAY_STAGE_BANK,
                 (uint16_t)(LISP65_BOOT_OVERLAY_STAGE_OFF +
                            LISP65_BOOT_OVERLAY_HEADER_SIZE),
                 FIRST_LEN, OV_TARGET);
    vm_boot_overlay_status = VM_BOOT_OVERLAY_ERR_CRC;
    if (ov_crc16(OV_TARGET, FIRST_LEN) != expected_crc) goto done;
    vm_boot_overlay_status = VM_BOOT_OVERLAY_ERR_ENTRY_RUN;
    if (lisp_error_msg || mem_oom) goto done;
    FIRST_CALL();
    if (lisp_error_msg || mem_oom) goto done;
#if defined(LISP65_C2_LITE_BANK3_STAGING) && \
    !defined(LISP65_BOOT_OVERLAY_HOST_TEST)
    /* The tail-chained cold record and minimal commit seam own Record 2. */
    if (vm_boot_overlay_status != VM_BOOT_OVERLAY_OK) goto done;
#else
    vm_boot_overlay_status = VM_BOOT_OVERLAY_ERR_WIPE;
    if (!ov_wipe_target()) goto done;
    vm_boot_overlay_status = VM_BOOT_OVERLAY_OK;
#endif
done:
#undef FIRST_VMA
#undef FIRST_ENTRY
#undef FIRST_LEN
#undef FIRST_CALL
    return vm_boot_overlay_status;
}
#endif /* LISP65_VM && LISP65_STAGED_BOOT_OVERLAY */
