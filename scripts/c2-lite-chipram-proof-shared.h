#ifndef LISP65_C2_LITE_CHIPRAM_PROOF_SHARED_H
#define LISP65_C2_LITE_CHIPRAM_PROOF_SHARED_H

/* Explicit NOLOAD mailbox shared by the low controller and the owned test
 * window.  The proof linker reserves the complete page; it is not product
 * state and creates no product capacity claim. */
#define C2LT_CTL_BASE             0x7000u
#define C2LT_FRAME_LO             0x7000u
#define C2LT_FRAME_HI             0x7001u
#define C2LT_NMI_COUNT            0x7002u
#define C2LT_EVENT_CODE           0x7003u
#define C2LT_EVENT_MODIFIERS      0x7004u
#define C2LT_DEQUEUE_COUNT        0x7005u
#define C2LT_COMMAND              0x7006u
#define C2LT_RESPONSE             0x7007u
#define C2LT_UNEXPECTED_IRQ       0x7008u
#define C2LT_STATE                0x7009u
#define C2LT_NATIVE_GENERATION    0x700au
#define C2LT_NATIVE_FAMILY        0x700bu
#define C2LT_FREEZER_RETURNED     0x700cu
#define C2LT_FAIL_CASE            0x700du
#define C2LT_FAIL_CODE            0x700eu
#define C2LT_UNOWNED_VIC_FLAGS    0x700fu
#define C2LT_BANK2_CRC_LO         0x7010u
#define C2LT_BANK2_CRC_HI         0x7011u
#define C2LT_BANK3_BOOT_CRC_LO    0x7012u
#define C2LT_BANK3_BOOT_CRC_HI    0x7013u
#define C2LT_BANK3_SESSION_CRC_LO 0x7014u
#define C2LT_BANK3_SESSION_CRC_HI 0x7015u
#define C2LT_WINDOW_CRC_LO        0x7016u
#define C2LT_WINDOW_CRC_HI        0x7017u
#define C2LT_CASE_COUNT_DONE      0x7018u
#define C2LT_FREEZER_BANKS_OK     0x7019u
#define C2LT_WRITEBACK_OK         0x701au
#define C2LT_LATENCY_BASE         0x7020u

#define C2LT_STATE_INSTALLING     1u
#define C2LT_STATE_OWNED          2u
#define C2LT_STATE_PASS           3u

#define C2LT_FAMILY_INVALID       0u
#define C2LT_FAMILY_BOOT          1u
#define C2LT_FAMILY_SESSION       2u

#define C2LT_CMD_POLL_EVENT       1u

#endif
