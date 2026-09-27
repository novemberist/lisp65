/* Set B tenant: included once by c2_product_runtime.c to retain private state.
 * All functions use explicit overlay sections, as in card_l_stage.c. */
C2_APPEND_SECTION("retire_control") uint8_t c2_retire_control(void *opaque){
 c2r_dispatch *d=opaque; c2r_ctx *x=RX;uint8_t b[64],i,ok=1;
 if(d->mode==4u || d->mode==3u){
  if(d->mode==4u)c2r_boot_count=0;
  if(d->owned && !c2_phase_scratch_release(LISP65_C2_PHASE_OWNER_APPEND))ok=0;
  d->owned=0;
  d->next=0;return ok?C2_STREAM_OK:C2_STREAM_ERR_STATE;
 }
 if(d->mode<2u){
  if(d->recovery){
   (void)c2_phase_scratch_release(LISP65_C2_PHASE_OWNER_APPEND);
   (void)c2_phase_scratch_release(LISP65_C2_PHASE_OWNER_EMITTER);
  }
  if(!c2_phase_scratch_acquire(LISP65_C2_PHASE_OWNER_APPEND))return C2_STREAM_ERR_STATE;
  d->owned=1u;
  if(d->recovery){d->next=59u;return C2_STREAM_OK;}
  if(!vm_retire_prompt_quiescent() || gc_rootsp || c2_journal_count || c2_runtime.entry_first!=C2D_HANDLE_CAP || c2_pending_roots!=c2_committed_roots)return C2_STREAM_ERR_STATE;
  if(!c2_stream_c2d_read(C2D_UNWIND_BASE,b,64u))return C2_STREAM_ERR_C2D;
  for(i=0;i<64;++i)if(b[i])return C2_STREAM_ERR_STATE;
 }
 x->first=c2r_boot_count&127u;x->count=(uint8_t)c2_runtime.image_count;x->generation=c2_runtime.generation;
 gc_collect();if(c2r_gc_failed)return C2_STREAM_ERR_C2D;
 d->next=57u;return C2_STREAM_OK;
}
