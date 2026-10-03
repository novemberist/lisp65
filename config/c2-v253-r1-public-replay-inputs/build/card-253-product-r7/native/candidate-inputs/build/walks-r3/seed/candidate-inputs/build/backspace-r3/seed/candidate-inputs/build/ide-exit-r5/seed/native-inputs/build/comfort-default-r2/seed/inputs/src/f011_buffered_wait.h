/* Buffered F011 completion, authority 566c2e23.
 * Core 03b24c6b9d0e456f762fdca0d2dd66ec3c3e1fc6, sdcardio.vhdl:
 * ReadingSector sets LOST without suppressing buffer writes and inhibits EQ.
 * Chipset reference printed pp.120,128-129: buffered access; status bits.
 * No diagnostic record. All failures return to the ordinary caller.
 */
#ifndef LISP65_F011_BUFFERED_WAIT_H
#define LISP65_F011_BUFFERED_WAIT_H
#include <stdint.h>
#ifndef F011_WAIT_FRAME8
#include "c2_kernal_runtime.h"
#define F011_WAIT_FRAME8(hi) ((hi) ? C2K_FRAME_HI : C2K_FRAME_LO)
#endif
#define F011_WAIT_CAP_FRAMES 600u
/* Finite observation fuel only: never interpreted as elapsed time. */
#define F011_WAIT_CLOCK_FUEL 65535u

static uint8_t f011_clock_verified;

static LISP65_C2_MAPPED_F011_COLD_FN uint8_t f011_wait_sample(uint16_t *out) {
    uint8_t tries=4;
    do {
        uint8_t a=F011_WAIT_FRAME8(1), lo=F011_WAIT_FRAME8(0), b=F011_WAIT_FRAME8(1);
        if(a==b) { *out=(uint16_t)lo|((uint16_t)a<<8); return 1; }
    } while(--tries);
    return 0;
}

/* Prove progress before the first READ; do not charge one frame per sector.
 * A later clock stall still has its own finite fail-closed escape below.
 */
static LISP65_C2_MAPPED_F011_COLD_FN uint8_t f011_wait_clock_ready(void) {
    uint16_t start, now, fuel=F011_WAIT_CLOCK_FUEL;
    if(f011_clock_verified) return 1;
    if(!f011_wait_sample(&start)) return 0;
    do {
        if(!f011_wait_sample(&now)) return 0;
        if(now!=start) { f011_clock_verified=1; return 1; }
    } while(--fuel);
    return 0;
}

static LISP65_C2_MAPPED_F011_COLD_FN uint8_t f011_wait_complete(uint16_t start) {
    uint16_t previous=start, now, fuel=F011_WAIT_CLOCK_FUEL;
    for(;;) {
        uint8_t status=LISP65_F011_READ8(0xd082u);
        if(!f011_wait_sample(&now)) return 0;
        if((uint16_t)(now-start)>=F011_WAIT_CAP_FRAMES) return 0;
        if(!(status&0x80u)) return (status&0xd8u)==0x40u;
        if(now!=previous) { previous=now; fuel=F011_WAIT_CLOCK_FUEL; }
        else if(!--fuel) return 0;
    }
}
#endif
