#include <stdio.h>
#include <assert.h>
#include "vm.h"
Cell heap[HEAP_CELLS];
uint8_t vm_status;
static Cell remote;
uint8_t ext_type(uint16_t i){assert(i==HEAP_CELLS);return remote.type;}
obj ext_a(uint16_t i){assert(i==HEAP_CELLS);return remote.a;}
obj ext_b(uint16_t i){assert(i==HEAP_CELLS);return remote.b;}
void ext_set_a(uint16_t i,obj x){assert(i==HEAP_CELLS);remote.a=x;}
void ext_set_b(uint16_t i,obj x){assert(i==HEAP_CELLS);remote.b=x;}
#include "crc-bridge.h"
uint32_t crc_bridge_value(uint16_t crc,uint8_t byte){
    heap[1].type=T_CONS;heap[1].a=MKFIX(crc&255);heap[1].b=MKFIX(crc>>8);vm_status=VM_OK;
    vm_index_crc_step(2,MKFIX(byte));
    return (uint32_t)FIXVAL(heap[1].a)|((uint32_t)FIXVAL(heap[1].b)<<8)|((uint32_t)vm_status<<16);
}
static uint16_t reference(uint16_t crc,uint8_t byte){
    static const uint16_t nibble[16]={0,0x1021,0x2042,0x3063,0x4084,0x50a5,0x60c6,0x70e7,
        0x8108,0x9129,0xa14a,0xb16b,0xc18c,0xd1ad,0xe1ce,0xf1ef};
    crc^=(uint16_t)byte<<8;
    crc=(uint16_t)((crc<<4)^nibble[crc>>12]);
    return (uint16_t)((crc<<4)^nibble[crc>>12]);
}
int main(void){
    for(unsigned external=0;external<2;external++){
        obj state=(external?HEAP_CELLS:1)*2;
        Cell *c=external?&remote:&heap[1];c->type=T_CONS;
        for(unsigned crc=0;crc<65536;crc++)for(unsigned byte=0;byte<256;byte++){
            c->a=MKFIX(crc&255);c->b=MKFIX(crc>>8);vm_status=VM_OK;
            assert(vm_index_crc_step(state,MKFIX(byte))==MKFIX(byte));
            assert(vm_status==VM_OK);
            assert(((uint16_t)FIXVAL(c->a)|((uint16_t)FIXVAL(c->b)<<8))==reference(crc,byte));
        }
        c->a=MKFIX(255);c->b=MKFIX(255);
        const char *p="123456789";
        while(*p)vm_index_crc_step(state,MKFIX(*p++));
        assert(FIXVAL(c->a)==0xb1&&FIXVAL(c->b)==0x29);
        obj invalid[]={NIL,MKFIX(-1),MKFIX(256),MK_BCODE(0)};
        for(unsigned i=0;i<4;i++){
            obj a=c->a,b=c->b;vm_status=VM_OK;
            assert(vm_index_crc_step(state,invalid[i])==NIL&&vm_status==VM_TYPEERROR);
            assert(c->a==a&&c->b==b);
        }
        c->a=NIL;vm_status=VM_OK;
        assert(vm_index_crc_step(state,MKFIX(0))==NIL&&vm_status==VM_TYPEERROR);
        c->type=T_STR;vm_status=VM_OK;
        assert(vm_index_crc_step(state,MKFIX(0))==NIL&&vm_status==VM_TYPEERROR);
    }
    vm_status=VM_OK;assert(vm_index_crc_step(NIL,MKFIX(0))==NIL&&vm_status==VM_TYPEERROR);
    puts("PASS: all 65536 CRC states x 256 bytes, local and EXT state; 0x29b1 vector; domain rejection preserves state");
}
