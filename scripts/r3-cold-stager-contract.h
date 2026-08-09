/* Shared C/assembler addresses for the R3 cold-stager handoff. */
#ifndef LISP65_R3_COLD_STAGER_CONTRACT_H
#define LISP65_R3_COLD_STAGER_CONTRACT_H

#define R3_CHAIN_CODE_ADDR 0x1800u
#define R3_CHAIN_JOB_ADDR 0x1900u
#define R3_CHAIN_STATE_ADDR 0x1920u
#define R3_CHAIN_CRC_ATTEMPTS 64u
/* CRC32 state after consuming the little-endian $2001 PRG load address.
 * The handoff trampoline continues this state over the copied payload, so its
 * final comparison is against the manifest CRC of the complete PRG. */
#define R3_PRODUCT_CRC_INIT_0 0x89u
#define R3_PRODUCT_CRC_INIT_1 0xfcu
#define R3_PRODUCT_CRC_INIT_2 0x53u
#define R3_PRODUCT_CRC_INIT_3 0x9cu
#ifndef R3_PRODUCT_ENTRY
#ifdef LISP65_C2_LITE_MEDIA_STAGER
#define R3_PRODUCT_ENTRY 0x2023u
#else
#define R3_PRODUCT_ENTRY 0x2026u
#endif
#endif
#define R3_PRODUCT_LOAD 0x2001u

#endif /* LISP65_R3_COLD_STAGER_CONTRACT_H */
