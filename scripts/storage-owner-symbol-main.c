/* Host allocator proof with physical Bank-1/5 owners. This is not a MAP or
 * native timing substitute; the allocator is the unmodified src/symbol.c. */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "symbol.h"
#include "interrupt.h"

static uint8_t bank1[65536], bank5[65536];
Cell heap[HEAP_CELLS];
static unsigned errors;
void lisp_abort_code(lisp65_error_code c) { assert(c == LISP65_ERR_TOO_MANY_SYMBOLS); ++errors; }
void lisp_abort_symbol(lisp65_error_code c, obj s) { (void)s; lisp_abort_code(c); }
static uint16_t get(uint16_t at) { return bank5[at] | ((uint16_t)bank5[at+1] << 8); }
static void put(uint16_t at,uint16_t v) { bank5[at]=(uint8_t)v;bank5[at+1]=(uint8_t)(v>>8); }
uint16_t nameoff_get(uint16_t i) { assert(i<MAX_SYM);return get(NAMEOFF_EXT_OFF+i*2u); }
void nameoff_set(uint16_t i,uint16_t v) { assert(i<MAX_SYM);put(NAMEOFF_EXT_OFF+i*2u,v); }
obj symval_get(uint16_t i) { assert(i<MAX_SYM);return get(SYMVAL_EXT_OFF+i*2u); }
void symval_set(uint16_t i,obj v) { assert(i<MAX_SYM);put(SYMVAL_EXT_OFF+i*2u,v); }
obj symfn_ext_get(uint16_t i) { assert(i<MAX_SYM);return get(SYMFN_EXT_OFF+i*2u); }
void symfn_ext_set(uint16_t i,obj v) { assert(i<MAX_SYM);put(SYMFN_EXT_OFF+i*2u,v); }
void sympool_read(uint16_t off,char *dst,uint16_t n) {
    assert(off<NAMEPOOL && (uint32_t)SYMPOOL_EXT_OFF+off+n<=sizeof bank1);
    memcpy(dst,bank1+SYMPOOL_EXT_OFF+off,n);
}
void sympool_write(uint16_t off,const char *src,uint16_t n) {
    assert((uint32_t)off+n<=NAMEPOOL);
    memcpy(bank1+SYMPOOL_EXT_OFF+off,src,n);
}
static void owners_unchanged(void) {
    uint32_t i;
    for(i=0;i<SYMPOOL_EXT_OFF;++i) assert(bank1[i]==0xa7);
    for(i=SYMPOOL_EXT_OFF+NAMEPOOL;i<65536;++i) assert(bank1[i]==0xa7);
    for(i=0;i<SYMVAL_EXT_OFF;++i) assert(bank5[i]==0xb7);
    for(i=SYMFN_EXT_OFF+MAX_SYM*2u;i<65536;++i) assert(bank5[i]==0xb7);
}
int main(int argc,char **argv) {
    char name[34];unsigned i;obj s,out;
    assert(argc==2 && MAX_SYM==1008 && NAMEPOOL==16351);
    memset(bank1,0xa7,sizeof bank1);memset(bank5,0xb7,sizeof bank5);
    if(!strcmp(argv[1],"slots")) {
        for(i=0;i<MAX_SYM;++i) {
            snprintf(name,sizeof name,"s%04u",i);s=intern(name);assert(s!=NIL);
            if(i>=763 && i<963) {
                set_sym_value(s,MKFIX(37));set_sym_function(s,MKFIX(23));
                assert(sym_value(s)==MKFIX(37) && sym_function(s)==MKFIX(23));
            }
        }
        for(i=763;i<963;++i) {
            snprintf(name,sizeof name,"s%04u",i);
            assert(sym_lookup(name,&out) && sym_value(out)==MKFIX(37));
            assert(!strcmp(symname(out),name));
        }
        assert(sym_count()==MAX_SYM && intern("one-more")==NIL && errors==1);
        puts("PASS: 200 further symbols above 763 resolve; 1008 full; 1009 rejected");
    } else {
        unsigned remain=NAMEPOOL-1;
        for(i=0;remain;++i) {
            unsigned bytes=remain>34?34:remain;
            assert(bytes>5);
            snprintf(name,sizeof name,"n%032u",i);name[bytes-1]=0;
            assert(intern(name)!=NIL);remain-=bytes;
        }
        assert(sym_pool_used()==NAMEPOOL-1);
        s=intern("");assert(s!=NIL && !strcmp(symname(s),""));
        assert(sym_pool_used()==NAMEPOOL && sym_lookup("",&out) && out==s);
        assert(intern("overflow")==NIL && errors==1);
        puts("PASS: last usable pool byte, 34-byte tail read, first excess rejected");
    }
    owners_unchanged();puts("PASS: Bank-1 user area and guards, Bank-5 prefix and tail unchanged");
    return 0;
}
