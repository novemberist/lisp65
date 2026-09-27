"""Isolated shared-query successor with abort-owned provenance cleanup."""
from pathlib import Path
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import set_b_shared_front_20260926 as OLD
ROOT=P.ROOT
OUT=ROOT/'build/set-b-shared-front-r2'
HELPER=OLD.HELPER.replace('#define FC_TAINTED 4u','#define FC_TAINTED 4u\n#define FC_REFILL 8u')
HELPER=HELPER.replace('c2_front_certificate[3]; /* front LE16, state byte */','c2_front_certificate[4]; /* front LE16, state, saved LAST_SLOT */')
HELPER=HELPER.replace('FC_FN void c2_front_abort(void){c2_front_certificate[2]&=FC_TAINTED;}',r'''FC_FN uint8_t c2_front_refill_release(void){
 uint8_t ok=1u;
 if(c2_front_certificate[2]&FC_REFILL){
  C2AW_RESERVE_MARK(&c2aw)=0u;
  ((volatile uint8_t *)lisp65_c2_phase_scratch)
      [LISP65_C2_INSTALL_LAST_SLOT_OFFSET]=c2_front_certificate[3];
  ok=c2_phase_scratch_release(LISP65_C2_PHASE_OWNER_APPEND);
  c2_front_certificate[2]&=FC_TAINTED;
 }
 return ok;
}
FC_FN void c2_front_abort(void){
 (void)c2_front_refill_release();c2_front_certificate[2]&=FC_TAINTED;
}''')
HELPER=HELPER.replace('(c2_front_certificate[2]&FC_BUSY)|FC_TAINTED;',
 '(c2_front_certificate[2]&(FC_BUSY|FC_REFILL))|FC_TAINTED;')
HELPER=HELPER.replace('FC_FN uint8_t c2_front_publish(uint16_t checked_front){',
 'FC_FN uint8_t c2_front_publish(uint16_t checked_front){\n if(c2_front_certificate[2]&FC_REFILL)return 0u;')
HELPER=HELPER.replace('uint8_t header[8],saved_trace,ok;','uint8_t header[8],ok;')
HELPER=HELPER.replace('saved_trace=((volatile uint8_t *)lisp65_c2_phase_scratch)',
 'c2_front_certificate[3]=((volatile uint8_t *)lisp65_c2_phase_scratch)')
HELPER=HELPER.replace('  c2_record_u16(c2aw.record+2,C2D_ENTRY_CAP);',
 '  c2_front_certificate[2]=(c2_front_certificate[2]&FC_TAINTED)|FC_BUSY|FC_REFILL;\n  c2_record_u16(c2aw.record+2,C2D_ENTRY_CAP);')
HELPER=HELPER.replace('''  C2AW_RESERVE_MARK(&c2aw)=0u;
  ((volatile uint8_t *)lisp65_c2_phase_scratch)
      [LISP65_C2_INSTALL_LAST_SLOT_OFFSET]=saved_trace;
  if(!c2_phase_scratch_release(LISP65_C2_PHASE_OWNER_APPEND) || !ok)goto refuse;''',
 '  if(!c2_front_refill_release() || !ok)goto refuse;')
HELPER=HELPER.replace(' * Nonlocal recovery still requires an integrated certificate invalidation hook.',
 ' * Proposed nonlocal recovery calls c2_front_abort BEFORE its existing\n * forced scratch releases; this ordering is tested in the host fixture only.')
assert 'saved_trace' not in HELPER

def main():
    S.require_auth();OUT.mkdir(exist_ok=False);(OUT/'certificate.inc').write_text(HELPER)
    for name in ('existing-scan.inc','existing-entry.inc'):
        (OUT/name).write_bytes((OLD.OUT/name).read_bytes())
    P.write(OUT/'binding.json',dict(status='PARKED ABORT-CLEANUP SUCCESSOR; NO PRODUCT HOOK INSTALLED',
        driver=P.bind(Path(__file__)),kernel=P.bind(OUT/'certificate.inc'),predecessor=P.bind(OLD.OUT/'binding.json'),
        source_authority=S.require_auth(),execution_head='9a8f04cf',
        ordering='Call c2_front_abort before existing nonlocal recovery releases scratch or starts a later owner. Trusted boot starts quiescent.',
        storage='Four certificate bytes; fourth stores LAST_SLOT only while REFILL bit owns APPEND scratch.',
        product_builds=0,product_links=0,seeds=0,device_contacts=0))
    print('PARKED r2 four-byte certificate with abort-owned trace and scratch cleanup')

if __name__=='__main__':main()
