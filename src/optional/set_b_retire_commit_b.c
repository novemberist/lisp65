/* Set B tenant: included once by c2_product_runtime.c to retain private state.
 * All functions use explicit overlay sections, as in card_l_stage.c. */
#undef RCOMMIT
#define RCOMMIT C2_APPEND_SECTION("retire_move")
RCOMMIT static uint8_t rm_read(uint16_t at,uint8_t *p,uint8_t n) {
 return c2_map_cpu_read(0x50000UL+at,p,n);
}
RCOMMIT static uint8_t rm_write(uint16_t at,const uint8_t *p,uint8_t n) {
 uint8_t b[32],i,m;
 while(n){m=n>32u?32u:n;
  c2_facade_c2_dma((uint16_t)(uintptr_t)p,0,at,5u,m);
  if(!rm_read(at,b,m))return 0;
  for(i=0;i<m;++i)if(b[i]!=p[i])return 0;
  at+=m;p+=m;n-=m;
 }return 1;
}
RCOMMIT static uint8_t rm_phase(uint8_t *j,uint8_t p){
 if(!rm_write(RJ+3u,&p,1u))return 0;j[3]=p;return 1;
}
RCOMMIT static uint8_t rm_own(uint8_t *r,uint8_t owner){
 uint16_t e=c2_u16(r+6),n=c2_u16(r+8);
 if(e>c2_runtime.entry_count || n>c2_runtime.entry_count-e)return 0;
 while(n--){if(!rm_write(c2_runtime.entries_offset+e*10u,&owner,1u))return 0;++e;}return 1;
}
RCOMMIT static uint8_t rm_finish(uint8_t *j){
 uint8_t c,r[32],i;
 if(j[0]!=RMAGIC || c2_u16(j+4)!=c2_runtime.generation || j[6]!=(c2r_boot_count&127u) || j[1]<j[6] || j[1]>=j[2] || j[2]>64u)return 0;
 if(j[3]==254u){
  if(!rm_own(j+8,255u) || !rm_phase(j,128u+j[1]+1u))return 0;
 }
 for(;;){
  if(j[3]==255u)break;
  c=j[3]&127u;
  if(c<=j[1] || c>j[2])return 0;
  if(j[3]&128u){
   if(c==j[2]){if(!rm_phase(j,255u))return 0;break;}
   if(!c2_stream_c2d_read(c2_runtime.images_offset+(uint16_t)c*32u,r,32u) || !rm_write(RJ+40u,r,32u))return 0;
   for(i=0;i<32;++i)j[40+i]=r[i];
   if(!rm_phase(j,c))return 0;
  }
  for(i=0;i<32;++i)r[i]=j[40+i];
  if(c2_u16(r+4)!=c2_runtime.generation || r[0]!=1u || r[1])return 0;
  r[2]=c-7u;
  if(!rm_write(c2_runtime.images_offset+(uint16_t)(c-1u)*32u,r,32u) || !rm_own(r,c-1u) || !rm_phase(j,128u+c+1u))return 0;
 }
 return 1;
}
RCOMMIT uint8_t c2_retire_move(void *opaque){
 c2r_dispatch *d=opaque; if(!rm_finish(JJ))return C2_STREAM_ERR_C2D;d->next=61u;return C2_STREAM_OK;
}

