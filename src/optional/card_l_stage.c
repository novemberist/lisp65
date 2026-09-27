/* Bank-5 late-region staging, Session slot 55; Set B carries seven tenants. */
#include <stdint.h>
#include "vm_runtime_overlay.h"
#include "c2_kernal_facade.h"
#include "c2_kernal_runtime.h"
#include "c2_product_runtime.h"
#ifdef LISP65_SET_B
#include "../../config/set-b-native/set-b-placement.h"
#else
#include "../../config/card-l-native/card-l-placement.h"
#endif
#define C2_LITE_STAGE_BLOCK 32u

/* The tuple is inside the authenticated Session record, not ordinary rodata.
 * Zero refuses staging until the producer writes the sealed marker tuple
 * after link and refreshes the authenticated slot-55 record. */
typedef struct { uint16_t image_size, crc16; } c2_lite_family_stage_binding;
__attribute__((used, section(".lisp65_rt_card_l_binding")))
const volatile c2_lite_family_stage_binding rtov_late_stage_binding = {0u, 0u};
__attribute__((noinline, used, section(".lisp65_rt_card_l_stage")))
static uint8_t card_l_stage(void) {
    uint8_t block[C2_LITE_STAGE_BLOCK];
    uint16_t size, expected, start, offset, left, crc;
    size = rtov_late_stage_binding.image_size;
    expected = rtov_late_stage_binding.crc16;
    if (size != 8192u)
        return 0u;
    /* Called only after successful boot publication and header invalidation.
     * Durable Attic source is disjoint from the Session arena. */
    c2_product_physical_copy(
        CARD_L_MARKER_SOURCE,
        ((uint32_t)5u << 16)
            + 0xde80u,
        size);
    start = c2_kernal_frame_count_inline();
    do {
        crc = LISP65_RUNTIME_OVERLAY_CRC16_INIT;
        offset = 0u;
        left = size;
        while (left) {
            uint8_t i = 0u;
            uint8_t chunk = left > C2_LITE_STAGE_BLOCK
                ? C2_LITE_STAGE_BLOCK : (uint8_t)left;
            c2_facade_vm_code_load(
                5u,
                (uint16_t)(0xde80u + offset),
                chunk, block);
            while (i != chunk) {
                uint8_t bits = 8u;
                crc ^= (uint16_t)block[i++] << 8;
                do {
                    crc = (crc & 0x8000u)
                        ? (uint16_t)((crc << 1)
                            ^ LISP65_RUNTIME_OVERLAY_CRC16_POLY)
                        : (uint16_t)(crc << 1);
                } while (--bits);
            }
            offset = (uint16_t)(offset + chunk);
            left = (uint16_t)(left - chunk);
        }
        if (crc == expected) return 1u;
    } while ((uint16_t)(c2_kernal_frame_count_inline() - start) <
             LISP65_RTOV_COMPLETION_TIMEOUT_FRAMES);
    return 0u;
}

/* Stream success is zero; no state or owner is published on failure. */
__attribute__((noinline, used, section(".lisp65_rt_card_l_stage")))
uint8_t card_l_stage_entry(void *context) {
    (void)context;
    return card_l_stage() ? 0u : 1u;
}
