#ifndef LISP65_C2_PLATFORM_DMA_H
#define LISP65_C2_PLATFORM_DMA_H

#include <stdint.h>

void vm_ext_write(const uint8_t *source, uint16_t length,
                  uint8_t bank, uint16_t offset);
#ifdef LISP65_CODE_WINDOW_CONVERGENCE
#define C2_DMA_CONTENT_TIMEOUT_FRAMES 64u
#endif

#endif
