/* Structural R3 launcher probe.
 *
 * This is deliberately not the G6 media loader.  It proves that AUTOBOOT can
 * be represented by a separate target artifact with a closed phase descriptor
 * and without linking a byte into the Workbench PRG.  The product block may
 * replace the phase markers with real D81 reads only after contract review.
 */
#include <stdint.h>

#define R3_STAGER_MAGIC_0 'L'
#define R3_STAGER_MAGIC_1 '6'
#define R3_STAGER_MAGIC_2 '5'
#define R3_STAGER_MAGIC_3 'S'

enum r3_stager_phase {
    R3_PHASE_VALIDATE_DESCRIPTOR = 1,
    R3_PHASE_VALIDATE_CATALOG = 2,
    R3_PHASE_STAGE_BANK5 = 3,
    R3_PHASE_STAGE_ATTIC = 4,
    R3_PHASE_SELECT_PRODUCT = 5
};

static volatile const uint8_t r3_stager_probe_descriptor[] = {
    R3_STAGER_MAGIC_0, R3_STAGER_MAGIC_1, R3_STAGER_MAGIC_2,
    R3_STAGER_MAGIC_3, 1,
    R3_PHASE_VALIDATE_DESCRIPTOR,
    R3_PHASE_VALIDATE_CATALOG,
    R3_PHASE_STAGE_BANK5,
    R3_PHASE_STAGE_ATTIC,
    R3_PHASE_SELECT_PRODUCT,
    5, 'b', 'a', 'n', 'k', '5',
    5, 'a', 't', 't', 'i', 'c',
    7, 'p', 'r', 'o', 'd', 'u', 'c', 't'
};

int main(void) {
    uint8_t checksum = 0;
    uint16_t i;

    for (i = 0; i < sizeof(r3_stager_probe_descriptor); i++)
        checksum ^= r3_stager_probe_descriptor[i];

#ifdef __MEGA65__
    /* A visible probe marker only.  No media is read and no product is
     * entered, so this artifact cannot be mistaken for G3/G6 evidence. */
    *((volatile uint8_t *)0xd020) = (uint8_t)(checksum & 0x0f);
    for (;;) __asm__ volatile("nop");
#endif

    return checksum == 0xffu ? 1 : 0;
}
