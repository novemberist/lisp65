"""Park a resident certificate query using the unchanged existing scanner."""
from pathlib import Path
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import set_b_front_prototype_20260926 as OLD

ROOT=P.ROOT
OUT=ROOT/'build/set-b-shared-front-r1'
QUERY=r'''FC_FN obj c2_resolver_charged_front(void){
 uint8_t header[8],saved_trace,ok;
 uint16_t count,low;
 if(!c2_ready || (c2_front_certificate[2]&FC_BUSY))return NIL;
 if(!c2_stream_c2d_read(10u,header,8u))goto refuse;
 count=c2_u16(header+6);
 if(count>C2D_ENTRY_CAP || c2_u16(header)!=c2_runtime.generation
    || count!=c2_runtime.entry_count || c2_runtime.entries_offset!=2096u)
  goto refuse;
 if(c2_front_certificate[2]==FC_VALID){
  low=c2_u16(c2_front_certificate);
 }else{
  if(!c2_phase_scratch_acquire(LISP65_C2_PHASE_OWNER_APPEND))goto refuse;
  saved_trace=((volatile uint8_t *)lisp65_c2_phase_scratch)
      [LISP65_C2_INSTALL_LAST_SLOT_OFFSET];
  c2_record_u16(c2aw.record+2,C2D_ENTRY_CAP);
  C2AW_RESERVE_MARK(&c2aw)=C2_RESERVE_SCAN_REQUEST;
  ok=c2_overlay_call(LISP65_C2_APPEND_RESERVE_PERSISTENT_CODE_SLOT,&c2aw);
  ok=(uint8_t)(ok && C2AW_RESERVE_MARK(&c2aw)==C2_RESERVE_SCAN_DONE);
  low=c2_u16(c2aw.record+12);
  C2AW_RESERVE_MARK(&c2aw)=0u;
  ((volatile uint8_t *)lisp65_c2_phase_scratch)
      [LISP65_C2_INSTALL_LAST_SLOT_OFFSET]=saved_trace;
  if(!c2_phase_scratch_release(LISP65_C2_PHASE_OWNER_APPEND) || !ok)goto refuse;
  if(!(c2_front_certificate[2]&FC_TAINTED)){
   c2_front_certificate[0]=(uint8_t)low;
   c2_front_certificate[1]=(uint8_t)(low>>8);
   c2_front_certificate[2]=FC_VALID;
  }
 }
 return cons(MKFIX(low&255u),MKFIX(low>>8));
refuse:
 c2_front_abort();return NIL;
}
#undef FC_FN
'''
HELPER=OLD.HELPER[:OLD.HELPER.index('FC_FN obj c2_resolver_charged_front(void)')]+QUERY
HELPER=HELPER.replace(' * No scratch, decoder cursor, journal field or READY byte is borrowed.',
    ' * Refills exclusively acquire APPEND scratch; restore normal-return trace.\n * No decoder cursor, journal field or READY byte is borrowed.\n * Nonlocal recovery still requires an integrated certificate invalidation hook.')

def function(source,name):
    start=source.index(name+'(');start=source.rfind('\n',0,start)+1
    brace=source.index('{',start);depth=1;end=brace+1
    while depth:
        depth+=(source[end]=='{')-(source[end]=='}');end+=1
    return source[start:end]+'\n'

def main():
    S.require_auth();OUT.mkdir(exist_ok=False)
    (OUT/'certificate.inc').write_text(HELPER)
    source=ROOT/'src/c2_product_runtime.c';s=source.read_text()
    scan=function(s,'c2_lite_bank2_scan');phase=function(s,'c2_append_reserve_persistent_code_phase')
    (OUT/'existing-scan.inc').write_text(scan);(OUT/'existing-entry.inc').write_text(phase)
    P.write(OUT/'binding.json',dict(status='PARKED SHARED-SCANNER WRAPPER; NOT PRODUCT INTEGRATION',
        driver=P.bind(Path(__file__)),kernel=P.bind(OUT/'certificate.inc'),source=P.bind(source),
        scan=P.bind(OUT/'existing-scan.inc'),entry=P.bind(OUT/'existing-entry.inc'),
        authority=S.require_auth(),execution_head='9a8f04cf',
        contract='Actual header/base check, exclusive APPEND scratch, save/restore LAST_SLOT on normal returns, honor transport and DONE, release before cons; no latch reset or READY change.',
        limits='Raw/lifecycle hooks and decoder accumulator not installed. Host nonlocal recovery is an explicit proposed integration seam.',
        product_builds=0,product_links=0,seeds=0,device_contacts=0))
    print('PARKED shared-front wrapper and exact existing scan/entry source')

if __name__=='__main__':main()
