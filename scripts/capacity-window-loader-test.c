/* Executes the producer-materialized implementation, not the cache model.
 * Host substitutes only transport, dispatch and the already-staged identity.
 * No target timing, stack or layout claim follows from this harness. */
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include "integration-config.h"
#include "vm_runtime_overlay.c"

uint8_t lisp65_runtime_overlay_host_target[4096];
const uint16_t lisp65_runtime_overlay_host_vma = 0xc356;
uint16_t lisp65_runtime_overlay_host_limit = 0xc356 + 1853;
uint16_t lisp65_runtime_overlay_host_soft_sp = 0xffff;
uint8_t lisp65_resident_island_host_target[LISP65_RUNTIME_ISLAND_CAPACITY];
const volatile c2_lite_family_stage_binding rtov_family_stage_bindings[2] = {
    {0,0}, {TEST_IMAGE_SIZE,TEST_IMAGE_CRC}
};
static uint8_t image[65536], pristine[65536], overflow[65536];
static unsigned catalog_calls, record_calls, payload_calls, reads;
static unsigned mutate_during_auth;
static unsigned corrupted_slot;

void vm_code_load(uint8_t bank, uint16_t off, uint16_t n, uint8_t *dst) {
    assert((unsigned)off+n <= 65536);
    assert(bank==3 || bank==5);
    memcpy(dst,(bank==3?image:overflow)+off,n);
    ++reads;
    if (mutate_during_auth && bank==3 && n==32 &&
        off==32+corrupted_slot*32) dst[12]^=1;
}
uint8_t vm_runtime_overlay_host_call(uint16_t entry, void *context) {
    if (rtov_loaded_len==LISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_FILE_SIZE &&
        !memcmp(RTOV_TARGET,image+LISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_FILE_OFF,rtov_loaded_len)) {
        assert(entry==RTOV_VMA+LISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_ENTRY_OFFSET);
        ++catalog_calls;
        return vm_runtime_overlay_catalog_verifier(context);
    }
    if (rtov_loaded_len==LISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_FILE_SIZE &&
        !memcmp(RTOV_TARGET,image+LISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_FILE_OFF,rtov_loaded_len)) {
        assert(entry==RTOV_VMA+LISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_ENTRY_OFFSET);
        ++record_calls;
        return vm_runtime_overlay_record_verifier(context);
    }
    ++payload_calls;
    return 17;
}
static void reset(void) {
    memcpy(image,pristine,sizeof image);
    vm_runtime_overlay_host_reset();
    rtov_family=LISP65_RUNTIME_OVERLAY_FAMILY_SESSION;
    rtov_family_generation=1;
    rtov_island_state=RTOV_ISLAND_READY;
    mutate_during_auth=0;
    catalog_calls=record_calls=payload_calls=reads=0;
}
static uint8_t run(unsigned slot) {
    uint8_t result=255;
    uint8_t status=vm_runtime_overlay_exec_family(2,1,slot,0,&result);
    if (!status) assert(result==17);
    else assert(result==255);
    return status;
}
static void authenticated(void) {
    assert(run(2)==VM_RUNTIME_OVERLAY_OK);
    assert(catalog_calls==1 && record_calls==1 && payload_calls==1);
    assert(rtov_session_cache.ready==1 && rtov_session_cache.count==LISP65_RTOV_SESSION_RECORD_COUNT);
    for (unsigned i=0;i<LISP65_RTOV_SESSION_RECORD_COUNT;++i)
        assert(rtov_session_cache.record_crc[i]==rtov_crc_mem(image+32+(i+2)*32,32));
}
int main(int argc,char **argv) {
    assert(argc==3);
    FILE *f=fopen(argv[1],"rb");assert(f);
    assert(fread(pristine,1,TEST_IMAGE_SIZE,f)==TEST_IMAGE_SIZE);fclose(f);
    f=fopen(argv[2],"rb");assert(f);
    assert(fread(overflow+LISP65_RUNTIME_OVERLAY_REGION1_ADDRESS,1,TEST_OVERFLOW_SIZE,f)==TEST_OVERFLOW_SIZE);fclose(f);
    assert(sizeof rtov_session_cache==2*LISP65_RTOV_SESSION_RECORD_COUNT+8);
    reset();authenticated();
    for(unsigned i=2;i<LISP65_RTOV_SESSION_RECORD_COUNT+2;++i) assert(!run(i));
    assert(catalog_calls==1 && record_calls==1);
    for(unsigned i=2;i<LISP65_RTOV_SESSION_RECORD_COUNT+2;++i) {
        reset();authenticated();
        image[32+i*32+12]^=1;
        unsigned before=payload_calls;
        assert(run(i)==VM_RUNTIME_OVERLAY_ERR_CRC);
        assert(payload_calls==before && !rtov_session_cache.ready);
        reset(); mutate_during_auth=1;corrupted_slot=i;
        assert(run(2)==VM_RUNTIME_OVERLAY_ERR_CRC);
        assert(!rtov_session_cache.ready && payload_calls==0);
    }
    reset();authenticated();rtov_session_cache.generation^=1;
    assert(run(2)==VM_RUNTIME_OVERLAY_ERR_FAMILY);
    reset();authenticated();rtov_session_cache.image_crc^=1;
    assert(run(2)==VM_RUNTIME_OVERLAY_ERR_FAMILY);
    reset();authenticated();rtov_session_cache.image_size^=1;
    assert(run(2)==VM_RUNTIME_OVERLAY_ERR_FAMILY);
    reset();authenticated();rtov_session_cache.count--;
    assert(run(2)==VM_RUNTIME_OVERLAY_ERR_SLOT);
    reset();authenticated();assert(run(1)==VM_RUNTIME_OVERLAY_ERR_SLOT);
    reset();authenticated();assert(!vm_runtime_overlay_transaction_begin(2,1));
    assert(!rtov_session_cache.ready);assert(!run(2));
    assert(!rtov_session_cache.ready);assert(!vm_runtime_overlay_transaction_end());
    assert(!rtov_session_cache.ready);assert(!run(2));assert(rtov_session_cache.ready);
    reset();authenticated();vm_runtime_overlay_abort_cleanup();assert(!rtov_session_cache.ready);
    reset();authenticated();vm_runtime_overlay_host_reset();assert(!rtov_session_cache.ready);
    reset();authenticated();image[32]^=1;RTOV_SESSION_INVALIDATE();
    assert(run(2)==VM_RUNTIME_OVERLAY_ERR_CRC);
    puts("PASS: materialized catalog/record/cache/append/fail/abort/reset paths");
}
