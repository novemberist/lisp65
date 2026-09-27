/* Set B tenant: included once by c2_product_runtime.c to retain private state.
 * All functions use explicit overlay sections, as in card_l_stage.c. */
RSCAN static uint8_t rs_img(uint8_t k,uint8_t *r) {
 return c2_stream_c2d_read(c2_runtime.images_offset+(uint16_t)k*32u,r,32u);
}
RSCAN static void rs_note(c2r_ctx *x,obj v,uint8_t self) {
 uint8_t e[10],r[32],k; uint16_t n,first;
 if (!IS_BCODE(v) || x->bad) return;
 n=BCODE_IDX(v);
 if(n>=c2_runtime.entry_count) {x->bad=1;return;}
 if(!c2_stream_c2d_read(c2_runtime.entries_offset+n*10u,e,10u)) {x->bad=1;return;}
 k=e[0];
 /* A stale reachable handle is an error, not permission to forget its owner. */
 if(k>=x->count || c2_u16(e+8)!=x->generation || !rs_img(k,r)) {x->bad=1;return;}
 first=c2_u16(r+6);
 if(r[0]>1u || r[1] || c2_u16(r+4)!=x->generation || n<first || n-first>=c2_u16(r+8)) {x->bad=1;return;}
 if(k!=self) x->ref[k>>3]|=(uint8_t)(1u<<(k&7));
}
RSCAN static void rs_cell(c2r_ctx *x,uint8_t t,obj a,obj b) {
 if(t==T_BCODE) rs_note(x,MK_BCODE((uint16_t)a),255u);
 else if(t==T_CONS || t==T_CLOSURE || t==T_MACRO) {
  rs_note(x,a,255u);rs_note(x,b,255u);
 }
}
RSCAN uint8_t c2_retire_scan_phase(void *opaque) {
 c2r_ctx *x=RX; c2r_dispatch *d=opaque; uint16_t i,hi,fr,n; uint8_t k;
 if(!x || !c2_ready || x->generation!=c2_runtime.generation || x->count!=c2_runtime.image_count) return C2_STREAM_ERR_STATE;
 x->bad=0;x->victim=255u;
 for(k=0;k<8;++k)x->ref[k]=0;
 /* Collection was done by control tenant immediately before loading this slice. */
 hi=gc_scan_high();fr=gc_scan_frozen();
 for(i=1;i<=hi;++i) {
  if(!(i>=HEAP_CELLS && i<=fr) && !gc_cell_marked(i))continue;
  if(i<HEAP_CELLS)rs_cell(x,heap[i].type,heap[i].a,heap[i].b);
  else rs_cell(x,ext_type(i),ext_a(i),ext_b(i));
 }
 for(i=0;i<gc_rootsp;++i)rs_note(x,gc_rootstack[i],255u);
 n=sym_count();
 for(i=0;i<n;++i){obj s=sym_nth(i);rs_note(x,sym_value(s),255u);rs_note(x,sym_function(s),255u);}
 /* Read root plane explicitly as well: a transport error must veto this scan,
    even though the existing collector's root walker breaks on read failure. */
 if(x->bad)return C2_STREAM_ERR_C2D;
 d->next=58u;return C2_STREAM_OK;
}

