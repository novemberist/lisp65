/* Set B tenant: included once by c2_product_runtime.c to retain private state.
 * All functions use explicit overlay sections, as in card_l_stage.c. */
RCOMMIT static uint8_t rc_read(uint16_t at,uint8_t *p,uint8_t n) {
 return c2_map_cpu_read(0x50000UL+at,p,n);
}
RCOMMIT static uint8_t rc_write(uint16_t at,const uint8_t *p,uint8_t n) {
 uint8_t b[32],i,m;
 while(n){m=n>32u?32u:n;
  c2_facade_c2_dma((uint16_t)(uintptr_t)p,0,at,5u,m);
  if(!rc_read(at,b,m))return 0;
  for(i=0;i<m;++i)if(b[i]!=p[i])return 0;
  at+=m;p+=m;n-=m;
 }return 1;
}
RCOMMIT uint8_t c2_retire_commit_phase(void *opaque){
 c2r_ctx *x=RX; c2r_dispatch *d=opaque; uint8_t *j=JJ,i,k,b[32];
 /* Keep each synchronous MAP read within the admitted 64-byte bound. */
 if(!rc_read(RJ,j,64u) || !rc_read(RJ+64u,j+64u,8u))return C2_STREAM_ERR_C2D;
 if(j[0]){
  /* An append journal and retirement journal can never be active together. */
  for(k=0;k<2;++k){
   if(!c2_stream_c2d_read(C2D_UNWIND_BASE+(uint16_t)k*32u,b,32u))return C2_STREAM_ERR_C2D;
   for(i=0;i<32;++i)if(b[i])return C2_STREAM_ERR_STATE;
  }
  d->next=60u;return C2_STREAM_OK;
 }
 if(d->recovery || x->victim==255u){d->mode=d->recovery?4u:3u;d->next=d->recovery?0u:56u;return C2_STREAM_OK;}
 if(x->generation!=c2_runtime.generation || x->count!=c2_runtime.image_count || x->victim<x->first || x->victim>=x->count || (x->ref[x->victim>>3]&(1u<<(x->victim&7))))return C2_STREAM_ERR_STATE;
 for(i=0;i<72;++i)j[i]=0;
 j[1]=x->victim;j[2]=x->count;j[3]=254u;j[4]=(uint8_t)x->generation;j[5]=(uint8_t)(x->generation>>8);j[6]=x->first;
 if(!c2_stream_c2d_read(c2_runtime.images_offset+(uint16_t)x->victim*32u,j+8,32u) || j[8]!=1u || j[9] || c2_u16(j+12)!=x->generation || !rc_write(RJ+1u,j+1,71u))return C2_STREAM_ERR_C2D;
 j[0]=RMAGIC;
 if(!rc_write(RJ,j,1u))return C2_STREAM_ERR_C2D;
 d->next=60u;return C2_STREAM_OK;
}

