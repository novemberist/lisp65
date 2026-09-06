/* Extracted-prototype test driver; no claim about physical F011 behaviour. */
#include <assert.h>
#include <stdint.h>
#include <string.h>
static uint16_t clock_value;
static unsigned mode, phase, reads, completed_status, spin_reads, aux_reads;
static unsigned sequence[16], sequence_used;
static uint8_t tick(unsigned high) {
    if(mode==3 && high) return (uint8_t)++reads; /* every high read tears */
    if(!high && mode!=1 && !(mode==2 && phase==0x40)) ++clock_value;
    return high?(uint8_t)(clock_value>>8):(uint8_t)clock_value;
}
static uint8_t rd(unsigned a) {
    if(a==0xd083) { aux_reads++; return 0xaa; }
    assert(a==0xd082); /* no data-register access */
    if(phase==0x20) { spin_reads++; return 0xd0; }
    assert(phase==0x40);
    return (++reads<=10 || mode==2 || mode==4)?0xd0:completed_status;
}
static void wr(unsigned a,unsigned v) {
    assert(sequence_used<16);
    if(a==0xd081) { sequence[sequence_used++]=v; phase=v; }
}
static void m65_io_enable(void) {}
static void lisp65_f011_take_context(void) { assert(phase==0); }
static void lisp65_f011_map_buffer(void) { sequence[sequence_used++]=0x81; }
#define F011_FRAME_READ8(high) tick(high)
#define LISP65_F011_READ8(a) rd(a)
#define LISP65_C2_MAPPED_F011_COLD_FN
#define LISP65_F011_INSTRUMENT_BODY
#define LISP65_F011_READ_FAILED 0xffffu
/* PROTOTYPE_HEADER */
/* PROTOTYPE_BODY */
static void reset(unsigned m, unsigned status, uint16_t clock) {
    mode=m; phase=reads=spin_reads=aux_reads=sequence_used=0;
    completed_status=status; clock_value=clock;
    memset((void *)&lisp65_f011_status_state,0,sizeof(lisp65_f011_status_state));
}
int main(void) {
    for(unsigned status=0;status<128;status++) {
        reset(0,status,0xfff8);
        unsigned r=f011_read_at(1,1);
        unsigned success=(status&0x7c)==0x60;
        assert(r==(success?256:0xffff));
        assert(sequence[0]==0x20 && sequence[1]==0x40 && spin_reads==1);
        assert(sequence_used==(success?3:2));
        assert(lisp65_f011_status_state.tag==(success?1:2));
        assert(lisp65_f011_status_state.after_spin_d082==0xd0);
        assert(lisp65_f011_status_state.d082==status && lisp65_f011_status_state.d083==0xaa);
        assert(lisp65_f011_status_state.frames>=11 && lisp65_f011_status_state.frames<=13);
        assert(lisp65_f011_status_state.validity==7 && aux_reads==1);
    }
    for(unsigned m=1;m<=4;m++) {
        reset(m,0x62,0);
        assert(f011_read_at(1,0)==0xffff);
        assert(lisp65_f011_status_state.tag==(m==4?4:5));
        if(m==1 || m==3) assert(sequence_used==0 && lisp65_f011_status_state.validity==0);
        if(m==2) assert(sequence_used==2 && !(lisp65_f011_status_state.validity&4));
        if(m==4) assert(lisp65_f011_status_state.frames>=600 && (lisp65_f011_status_state.validity&8));
    }
    reset(0,0x62,0);
    f011_status_record r={1,0xd0,0x62,0xaa,11,7};
    f011_frame_publish(&r);
    r.frames=25; f011_frame_publish(&r);
    assert(lisp65_f011_status_state.frames==11);
    r.tag=2; r.d082=0x52; f011_frame_publish(&r);
    r.tag=4; r.frames=600; f011_frame_publish(&r);
    assert(lisp65_f011_status_state.tag==2 && lisp65_f011_status_state.frames==25);
    return 0;
}
