/* Profile-bound EXT-RAM staging bootstrap. Entire unit is opt-in. */
#include "vm_boot_overlay.h"

#if defined(LISP65_VM) && defined(LISP65_STAGED_BOOT_OVERLAY)
#include "vm.h"
#include "interrupt.h"
#include "eval.h"
#include "mem.h"

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

static uint16_t ov_crc16(const uint8_t *p, uint16_t n) {
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

__attribute__((noinline)) uint8_t vm_install_staged_boot_overlay(void) {
    uint8_t *header = OV_TARGET;
    uint16_t expected_crc;

    if (ov_started) {
        vm_boot_overlay_status = VM_BOOT_OVERLAY_ERR_REENTRY;
        return VM_BOOT_OVERLAY_ERR_REENTRY;
    }
    ov_started = 1;
    vm_boot_overlay_status = VM_BOOT_OVERLAY_ERR_LENGTH;
    if (!OV_VMA || OV_LEN < LISP65_BOOT_OVERLAY_HEADER_SIZE) goto done;

    /* The execution window is dead until the verified payload replaces this
     * descriptor. Only its expected CRC must survive that DMA (two bytes). */
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
    if (ov_u16(header + 10) != OV_VMA) goto done;
    vm_boot_overlay_status = VM_BOOT_OVERLAY_ERR_ENTRY;
    if (ov_u16(header + 12) != OV_ENTRY) goto done;
    vm_boot_overlay_status = VM_BOOT_OVERLAY_ERR_LENGTH;
    if (ov_u16(header + 14) != OV_LEN) goto done;

    expected_crc = ov_u16(header + 16);

    vm_code_load((uint8_t)LISP65_BOOT_OVERLAY_STAGE_BANK,
                 (uint16_t)(LISP65_BOOT_OVERLAY_STAGE_OFF +
                            LISP65_BOOT_OVERLAY_HEADER_SIZE),
                 OV_LEN, OV_TARGET);
    vm_boot_overlay_status = VM_BOOT_OVERLAY_ERR_CRC;
    if (ov_crc16(OV_TARGET, OV_LEN) != expected_crc) goto done;

    vm_boot_overlay_status = VM_BOOT_OVERLAY_ERR_ENTRY_RUN;
    if (lisp_error_msg || mem_oom) goto done;
    OV_CALL();
    if (lisp_error_msg || mem_oom) goto done;
    vm_boot_overlay_status = VM_BOOT_OVERLAY_ERR_WIPE;
    if (!ov_wipe_target()) goto done;
    vm_boot_overlay_status = VM_BOOT_OVERLAY_OK;
done:
    return vm_boot_overlay_status;
}
#endif /* LISP65_VM && LISP65_STAGED_BOOT_OVERLAY */
