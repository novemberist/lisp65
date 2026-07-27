/* Shared C/assembler addresses for the R3 cold-stager handoff. */
#ifndef LISP65_R3_COLD_STAGER_CONTRACT_H
#define LISP65_R3_COLD_STAGER_CONTRACT_H

#define R3_CHAIN_CODE_ADDR 0x1800u
#define R3_CHAIN_JOB_ADDR 0x1840u
#ifdef LISP65_C2_LITE_MEDIA_STAGER
#define R3_PRODUCT_ENTRY 0x2023u
#else
#define R3_PRODUCT_ENTRY 0x2026u
#endif
#define R3_PRODUCT_LOAD 0x2001u

#endif /* LISP65_R3_COLD_STAGER_CONTRACT_H */
