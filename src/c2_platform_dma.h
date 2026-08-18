#ifndef LISP65_C2_PLATFORM_DMA_H
#define LISP65_C2_PLATFORM_DMA_H

#include <stdint.h>

void vm_ext_write(const uint8_t *source, uint16_t length,
                  uint8_t bank, uint16_t offset);
#ifdef LISP65_C2_MUTABLE_CPU_READS
/* Synchronous 28-bit MAP transport.  Mutable content readers use this
 * directly: there is no DMA completion signal and therefore no convergence
 * oracle to trust. */
uint8_t c2_map_cpu_read(uint32_t source, uint8_t *destination,
                        uint16_t length);
#endif
#ifdef LISP65_CODE_WINDOW_CONVERGENCE
#define C2_DMA_CONTENT_TIMEOUT_FRAMES 64u
#endif

#endif
