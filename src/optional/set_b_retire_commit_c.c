/* Set B tenant: included once by c2_product_runtime.c to retain private state.
 * All functions use explicit overlay sections, as in card_l_stage.c. */
#undef RCOMMIT
#define RCOMMIT C2_APPEND_SECTION("retire_final")
RCOMMIT static uint8_t rf_read(uint16_t at,uint8_t *p,uint8_t n) {
 return c2_map_cpu_read(0x50000UL+at,p,n);
}
RCOMMIT static uint8_t rf_write(uint16_t at,const uint8_t *p,uint8_t n) {
 uint8_t b[32],i,m;
 while(n){m=n>32u?32u:n;
  c2_facade_c2_dma((uint16_t)(uintptr_t)p,0,at,5u,m);
  if(!rf_read(at,b,m))return 0;
  for(i=0;i<m;++i)if(b[i]!=p[i])return 0;
  at+=m;p+=m;n-=m;
 }return 1;
}
RCOMMIT uint8_t c2_retire_final(void *opaque){
 c2r_dispatch *d=opaque;uint8_t *j=JJ,r[32],i,z=0;
 for(i=0;i<32;++i)r[i]=0;
 if(!rf_write(c2_runtime.images_offset+(uint16_t)(j[2]-1u)*32u,r,32u))return C2_STREAM_ERR_C2D;
 r[0]=j[2]-1u;
 if(!rf_write(12u,r,2u))return C2_STREAM_ERR_C2D;
 /* Publish the cached count before clearing magic: even a successful clear
    with failed readback must leave the empty-journal replay consistent. */
 c2_runtime.image_count=r[0];
 /* All caches hold ordinal/physical code, not persistent image-row pointers.
    no live activation or append snapshot survives this prompt-only operation. */
 if(!rf_write(RJ,&z,1u))return C2_STREAM_ERR_C2D;
 /* Recovery completes publication before mode 4 disarms the session. */
 d->mode=d->recovery?4u:2u;d->next=d->recovery?0u:56u;return C2_STREAM_OK;
}

