#include <stdint.h>
#include <assert.h>
#define LISP65_C2_MAPPED_F011_COLD_FN
static unsigned ticks, mode, status, reads, samples;
static uint16_t initial;
static uint8_t frame(unsigned hi) {
    ++samples;
    if(mode==3) return hi ? (uint8_t)++ticks : 0;
    if(!hi && mode!=1) ++ticks;
    uint16_t value=(uint16_t)(initial+ticks/8);
    return (uint8_t)(value>>(hi?8:0));
}
static uint8_t reg(unsigned a) { assert(a==0xd082); ++reads; return (uint8_t)status; }
#define F011_WAIT_FRAME8(hi) frame(hi)
#define LISP65_F011_READ8(a) reg(a)
#include "f011_buffered_wait.h"
static void reset(unsigned m, unsigned s, uint16_t start) {
    ticks=reads=samples=0; mode=m; status=s; initial=start; f011_clock_verified=0;
}
int main(void) {
    for(unsigned s=0;s<256;s++) {
        reset(0,s,0);
        assert(f011_wait_clock_ready());
        unsigned before=samples;
        assert(f011_wait_clock_ready() && samples==before);
        uint16_t start; assert(f011_wait_sample(&start));
        unsigned expected=!(s&0x80) && (s&0x40) && !(s&0x18);
        assert(f011_wait_complete(start)==expected);
    }
    reset(1,0x44,0); assert(!f011_wait_clock_ready());
    reset(3,0x44,0); assert(!f011_wait_clock_ready());
    reset(0,0x44,65534); assert(f011_wait_clock_ready());
    uint16_t start; assert(f011_wait_sample(&start));
    assert(f011_wait_complete(start));
    reset(0,0xd0,65534); assert(f011_wait_clock_ready());
    assert(f011_wait_sample(&start)); assert(!f011_wait_complete(start));
    assert((uint16_t)((uint16_t)(initial+ticks/8)-start)>=600);
    assert((uint16_t)((uint16_t)(initial+ticks/8)-start)<=601);
    reset(1,0xd0,0); f011_clock_verified=1;
    assert(!f011_wait_complete(0)); assert(reads==65535);
    reset(0,0x44,600); assert(!f011_wait_complete(0));
    return 0;
}
