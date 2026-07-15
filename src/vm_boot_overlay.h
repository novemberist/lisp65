/* lisp65 -- fail-closed loader for a profile-bound boot overlay staged in EXT RAM. */
#ifndef LISP65_VM_BOOT_OVERLAY_H
#define LISP65_VM_BOOT_OVERLAY_H

#include <stdint.h>

#define LISP65_BOOT_OVERLAY_MAGIC_0       'L'
#define LISP65_BOOT_OVERLAY_MAGIC_1       '6'
#define LISP65_BOOT_OVERLAY_MAGIC_2       '5'
#define LISP65_BOOT_OVERLAY_MAGIC_3       'O'
#define LISP65_BOOT_OVERLAY_VERSION       1u
#define LISP65_BOOT_OVERLAY_HEADER_SIZE   18u

/* CRC-16/CCITT-FALSE over the raw payload only:
 * poly=0x1021, init=0xffff, refin=false, refout=false, xorout=0. */
#define LISP65_BOOT_OVERLAY_CRC16_POLY    0x1021u
#define LISP65_BOOT_OVERLAY_CRC16_INIT    0xffffu

/* Opt-in AP4.4 stack-probe flags. Results are exported as fixed ELF symbols
 * so a hardware runner can read them without a Lisp-visible diagnostic API. */
#define LISP65_BOOT_PROBE_SOFT_EXHAUSTED   0x01u
#define LISP65_BOOT_PROBE_HW_EXHAUSTED     0x02u
#define LISP65_BOOT_PROBE_SOFT_RANGE_BAD   0x04u

enum {
    VM_BOOT_OVERLAY_OK = 0,
    VM_BOOT_OVERLAY_ERR_MAGIC,
    VM_BOOT_OVERLAY_ERR_VERSION,
    VM_BOOT_OVERLAY_ERR_HEADER,
    VM_BOOT_OVERLAY_ERR_PROFILE,
    VM_BOOT_OVERLAY_ERR_VMA,
    VM_BOOT_OVERLAY_ERR_ENTRY,
    VM_BOOT_OVERLAY_ERR_LENGTH,
    VM_BOOT_OVERLAY_ERR_CRC,
    VM_BOOT_OVERLAY_ERR_ENTRY_RUN,
    VM_BOOT_OVERLAY_ERR_WIPE,
    VM_BOOT_OVERLAY_ERR_REENTRY
};

#if defined(LISP65_VM) && defined(LISP65_STAGED_BOOT_OVERLAY)
/* Last completed bootstrap status remains inspectable after a failed boot. */
extern uint8_t vm_boot_overlay_status;

/* Validate descriptor, copy payload to its linked VMA, verify CRC, call the
 * linked init entry, then wipe the dead execution window before returning. */
uint8_t vm_install_staged_boot_overlay(void);

/* First Workbench boot stage. It initializes the evaluator and returns before
 * the resident coordinator starts any Bank-3 boot-commit slice. */
void vm_workbench_boot_overlay_entry(void);

#ifdef LISP65_BOOT_STACK_PROBE
extern volatile uint8_t  lisp65_boot_probe_complete;
extern volatile uint8_t  lisp65_boot_probe_flags;
extern volatile uint16_t lisp65_boot_probe_soft_initial;
#ifdef LISP65_BOOT_OVERLAY_HOST_TEST
extern volatile uint16_t lisp65_boot_probe_soft_low;
extern volatile uint16_t lisp65_boot_probe_soft_margin;
#endif
extern volatile uint8_t  lisp65_boot_probe_hw_initial;
#ifdef LISP65_BOOT_OVERLAY_HOST_TEST
extern volatile uint8_t  lisp65_boot_probe_hw_low;
extern volatile uint8_t  lisp65_boot_probe_hw_remaining;
#endif

/* The target arms the runtime watermark at the end of boot-fastpath phase 02,
 * after every larger boot slice has run. Stopped-target readback derives the
 * low-water mark without resident probe code. The host seam invokes begin/end
 * directly to exercise the scanner. */
void vm_boot_stack_probe_begin(void);
#ifdef LISP65_BOOT_OVERLAY_HOST_TEST
void vm_boot_stack_probe_end(void);
#endif
#endif

#ifdef LISP65_BOOT_OVERLAY_WIPE
extern volatile uint8_t lisp65_boot_overlay_wipe_ok;
/* Host-only seam for the reclaim proof; target install already wipes/verifies. */
#ifdef LISP65_BOOT_OVERLAY_HOST_TEST
void vm_boot_overlay_wipe(void);
#endif
#endif
#ifdef LISP65_BOOT_OVERLAY_HOST_TEST
void vm_boot_overlay_host_reset(void);
#endif
#endif

#endif /* LISP65_VM_BOOT_OVERLAY_H */
