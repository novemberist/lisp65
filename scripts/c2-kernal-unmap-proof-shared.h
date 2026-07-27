#ifndef LISP65_C2_KERNAL_UNMAP_PROOF_SHARED_H
#define LISP65_C2_KERNAL_UNMAP_PROOF_SHARED_H

/* Shared controller/window state occupies an explicit NOLOAD linker
 * reservation.  Merely choosing a page below the PRG load address proved
 * insufficient on hardware: firmware remained free to reuse that page. */
#define C2KU_CTL_BASE          0x3000u
#define C2KU_FRAME_LO          0x3000u
#define C2KU_FRAME_HI          0x3001u
#define C2KU_NMI_COUNT         0x3002u
#define C2KU_EVENT_CODE        0x3003u
#define C2KU_EVENT_MODIFIERS   0x3004u
#define C2KU_DEQUEUE_COUNT     0x3005u
#define C2KU_COMMAND           0x3006u
#define C2KU_RESPONSE          0x3007u
#define C2KU_UNEXPECTED_IRQ    0x3008u
#define C2KU_STATE             0x3009u
#define C2KU_MAP_GENERATION    0x300au
#define C2KU_ABORT_LATCHED     0x300bu
#define C2KU_OLD_IRQ_LO        0x300cu
#define C2KU_OLD_IRQ_HI        0x300du
#define C2KU_HANDOFF_FRAME_LO  0x300eu
#define C2KU_HANDOFF_FRAME_HI  0x300fu
#define C2KU_WINDOW_CRC_LO     0x3010u
#define C2KU_WINDOW_CRC_HI     0x3011u
#define C2KU_VIC_D01A_PRE_MAP  0x3012u
#define C2KU_VIC_D01A_POST_MAP 0x3013u
#define C2KU_VIC_D01A_REARMED  0x3014u
#define C2KU_UNOWNED_VIC_FLAGS 0x3015u

#define C2KU_MAP_SNAPSHOT      0x3100u

#define C2KU_STATE_FIRMWARE    1u
#define C2KU_STATE_ARMED       2u
#define C2KU_STATE_CLOSED      3u
#define C2KU_STATE_PRODUCT     4u

#define C2KU_CMD_VALIDATE      1u
#define C2KU_CMD_POLL_EVENT    2u
#define C2KU_RESPONSE_MAGIC    0x65u

#define C2KU_MOD_CTRL          0x04u
#define C2KU_MOD_ALT           0x10u
#define C2KU_PETSCII_CTRL_SPACE 0xffu
#define C2KU_PETSCII_META_X    0x58u
#define C2KU_PETSCII_RUN_STOP  0x03u

#endif
