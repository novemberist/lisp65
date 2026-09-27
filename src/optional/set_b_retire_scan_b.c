/* Set B tenant: included once by c2_product_runtime.c to retain private state.
 * All functions use explicit overlay sections, as in card_l_stage.c. */
#undef RSCAN
#define RSCAN C2_APPEND_SECTION("retire_scan_b")
RSCAN static uint8_t rb_img(uint8_t k,uint8_t *r) {
 return c2_stream_c2d_read(c2_runtime.images_offset+(uint16_t)k*32u,r,32u);
}
RSCAN static void rb_note(c2r_ctx *x,obj v,uint8_t self) {
 uint8_t e[10],r[32],k; uint16_t n,first;
 if (!IS_BCODE(v) || x->bad) return;
 n=BCODE_IDX(v);
 if(n>=c2_runtime.entry_count) {x->bad=1;return;}
 if(!c2_stream_c2d_read(c2_runtime.entries_offset+n*10u,e,10u)) {x->bad=1;return;}
 k=e[0];
 /* A stale reachable handle is an error, not permission to forget its owner. */
 if(k>=x->count || c2_u16(e+8)!=x->generation || !rb_img(k,r)) {x->bad=1;return;}
 first=c2_u16(r+6);
 if(r[0]>1u || r[1] || c2_u16(r+4)!=x->generation || n<first || n-first>=c2_u16(r+8)) {x->bad=1;return;}
 if(k!=self) x->ref[k>>3]|=(uint8_t)(1u<<(k&7));
}
RSCAN uint8_t c2_retire_scan_b(void *opaque) {
 c2r_ctx *x=RX; c2r_dispatch *d=opaque;
 uint16_t i,n,first;uint8_t r[32],w[2],k;
 for(i=0;i<c2_committed_roots;++i){
  if(!c2_stream_c2d_read(c2_runtime.roots_offset+i*2u,w,2u))return C2_STREAM_ERR_C2D;
  rb_note(x,(obj)c2_u16(w),255u);
 }
 for(k=0;k<x->count;++k){
  if(!rb_img(k,r))return C2_STREAM_ERR_C2D;
  first=c2_u16(r+10);n=c2_u16(r+12);
  if(r[0]>1u || r[1] || c2_u16(r+4)!=x->generation || first>c2_runtime.resolution_count || n>c2_runtime.resolution_count-first)return C2_STREAM_ERR_C2D;
  for(i=0;i<n;++i){
   if(!c2_stream_c2d_read(c2_runtime.resolutions_offset+(first+i)*2u,w,2u))return C2_STREAM_ERR_C2D;
   rb_note(x,(obj)c2_u16(w),k);
  }
 }
 if(x->bad)return C2_STREAM_ERR_C2D;
 for(k=x->first;k<x->count;++k)if(!(x->ref[k>>3]&(1u<<(k&7))))x->victim=k;
 d->next=59u;return C2_STREAM_OK;
}
