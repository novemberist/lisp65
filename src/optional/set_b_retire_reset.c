/* Set B tenant: included once by c2_product_runtime.c to retain private state.
 * All functions use explicit overlay sections, as in card_l_stage.c. */
C2_APPEND_SECTION("retire_reset") uint8_t c2_retire_reset(void *opaque){
 uint8_t z=0,seen=255u;
 c2r_boot_count=0; /* Every reset failure remains disarmed, never fatal. */
 if(c2_ready || opaque!=&c2_runtime)return C2_STREAM_ERR_STATE;
 c2_facade_c2_dma((uint16_t)(uintptr_t)&z,0u,RJ,5u,1u);
 if(!c2_map_cpu_read(0x50000UL+RJ,&seen,1u) || seen)return C2_STREAM_ERR_C2D;
 c2r_boot_count=(uint8_t)c2_runtime.image_count|128u;return C2_STREAM_OK;
}
