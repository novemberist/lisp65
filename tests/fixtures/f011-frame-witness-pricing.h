/* Pricing prototype only. NOT a product header or qualified instrument.
 * Authority a78f6d78: historical command ordering, bounded completion wait.
 * Poll fuel is ONLY a finite no-clock escape, never elapsed time evidence.
 */
#ifndef F011_FRAME_WITNESS_PRICING_H
#define F011_FRAME_WITNESS_PRICING_H
#include <stdint.h>
#ifndef F011_FRAME_READ8
#include "c2_kernal_runtime.h"
#define F011_FRAME_READ8(hi) ((hi) ? C2K_FRAME_HI : C2K_FRAME_LO)
#endif
#define F011_MEASURE_CAP_FRAMES 600u
#define F011_CLOCK_OBSERVATION_FUEL 65535u
enum { F011_UNSEEN=0, F011_FIRST_SUCCESS=1, F011_MASK_FAILURE=2,
       F011_READ_TIMEOUT=4, F011_CLOCK_UNOBSERVED=5 };
enum { F011_CLOCK_INITIAL_VALID=1, F011_READ_ISSUED=2,
       F011_TIME_VALID=4, F011_FRAME_CAP_REACHED=8 };
typedef struct {
    uint8_t tag, after_spin_d082, d082, d083;
    uint16_t frames;
    uint8_t validity;
} f011_status_record;
_Static_assert(sizeof(f011_status_record)==7, "packed seven-byte target record");
extern volatile f011_status_record lisp65_f011_status_state;
#ifdef LISP65_F011_INSTRUMENT_BODY
volatile f011_status_record lisp65_f011_status_state
    __attribute__((section(".noinit.lisp65_f011_status"),used));

static LISP65_C2_MAPPED_F011_COLD_FN uint8_t f011_frame_sample(uint16_t *out) {
    uint8_t tries=4;
    do {
        uint8_t a=F011_FRAME_READ8(1), low=F011_FRAME_READ8(0), b=F011_FRAME_READ8(1);
        if(a==b) { *out=(uint16_t)low|((uint16_t)a<<8); return 1; }
    } while(--tries);
    return 0;
}
static LISP65_C2_MAPPED_F011_COLD_FN uint8_t f011_frame_live(void) {
    uint16_t start, now, fuel=F011_CLOCK_OBSERVATION_FUEL;
    if(!f011_frame_sample(&start)) return 0;
    do {
        if(!f011_frame_sample(&now)) return 0;
        if(now!=start) return 1;
    } while(--fuel);
    return 0;
}
static LISP65_C2_MAPPED_F011_COLD_FN void f011_frame_publish(const f011_status_record *r) {
    if(lisp65_f011_status_state.tag>F011_FIRST_SUCCESS ||
       (lisp65_f011_status_state.tag==F011_FIRST_SUCCESS && r->tag==F011_FIRST_SUCCESS)) return;
    lisp65_f011_status_state.after_spin_d082=r->after_spin_d082;
    lisp65_f011_status_state.d082=r->d082;
    lisp65_f011_status_state.d083=LISP65_F011_READ8(0xd083u);
    lisp65_f011_status_state.frames=r->frames;
    lisp65_f011_status_state.validity=r->validity;
    __asm__ volatile("" ::: "memory");
    lisp65_f011_status_state.tag=r->tag;
}
static LISP65_C2_MAPPED_F011_COLD_FN void f011_frame_wait(f011_status_record *r, uint16_t start) {
    uint16_t now, previous=start, fuel=F011_CLOCK_OBSERVATION_FUEL;
    for(;;) {
        r->d082=LISP65_F011_READ8(0xd082u);
        if(!f011_frame_sample(&now)) break;
        r->frames=(uint16_t)(now-start);
        r->validity|=F011_TIME_VALID;
        if(!(r->d082&0x80u)) {
            r->tag=((r->d082&0x7cu)==0x60u)?F011_FIRST_SUCCESS:F011_MASK_FAILURE;
            return;
        }
        if(r->frames>=F011_MEASURE_CAP_FRAMES) {
            r->validity|=F011_FRAME_CAP_REACHED;
            r->tag=F011_READ_TIMEOUT;
            return;
        }
        if(now!=previous) { previous=now; fuel=F011_CLOCK_OBSERVATION_FUEL; }
        else if(!--fuel) break;
    }
    r->validity &= (uint8_t)~F011_TIME_VALID;
    r->tag=F011_CLOCK_UNOBSERVED;
}
#endif
#endif
