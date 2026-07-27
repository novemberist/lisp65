/* Product-only transport split for the proven C2I-v2/C2D-v3 decoder.
 *
 * The format truth remains scripts/c2-stream-*.  These entries only divide
 * the same checks at persistent cursor boundaries so no overlay resident has
 * to exceed the 1792-byte transport window.
 */
#ifndef LISP65_C2_PRODUCT_DECODER_H
#define LISP65_C2_PRODUCT_DECODER_H

#include <stdint.h>

uint8_t c2_product_decode_02a(void *context);
uint8_t c2_product_decode_02b(void *context);
uint8_t c2_product_decode_05a(void *context);
uint8_t c2_product_decode_05b(void *context);
uint8_t c2_product_decode_06a(void *context);
uint8_t c2_product_decode_06b(void *context);
uint8_t c2_product_decode_06c(void *context);
uint8_t c2_product_decode_09a(void *context);
uint8_t c2_product_decode_09b(void *context);
uint8_t c2_product_decode_10a(void *context);
uint8_t c2_product_decode_10b(void *context);
uint8_t c2_product_decode_11a(void *context);
uint8_t c2_product_decode_11b(void *context);
uint8_t c2_product_decode_11c(void *context);
uint8_t c2_product_decode_11d(void *context);
uint8_t c2_product_decode_13a(void *context);
uint8_t c2_product_decode_13b(void *context);

#endif
