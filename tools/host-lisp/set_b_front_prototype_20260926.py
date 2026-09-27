"""Park an isolated certificate C kernel. No product sources are changed."""
from pathlib import Path
import set_b_producer as P
import set_b_fifth_seed_20260926 as S

ROOT=P.ROOT
OUT=ROOT/'build/set-b-front-prototype-r1'
HELPER=r'''/* Isolated proposed certificate kernel. Publication callers must prove
 * complete validation, physical completion and terminal transaction success.
 * A raw-write notification permanently disables reuse until trusted boot.
 * No scratch, decoder cursor, journal field or READY byte is borrowed. */
#define FC_VALID 1u
#define FC_BUSY 2u
#define FC_TAINTED 4u
static uint8_t c2_front_certificate[3]; /* front LE16, state byte */
_Static_assert(LISP65_C2_BANK2_CODE_LIMIT < 65536UL,
               "front certificate requires the bound sub-bank limit");
#define FC_FN __attribute__((noinline,used))
FC_FN void c2_front_boot_reset(void){c2_front_certificate[2]=0u;}
FC_FN uint8_t c2_front_begin(void){
 if(c2_front_certificate[2]&FC_BUSY)return 0u;
 c2_front_certificate[2]=(c2_front_certificate[2]&FC_TAINTED)|FC_BUSY;
 return 1u;
}
FC_FN void c2_front_abort(void){c2_front_certificate[2]&=FC_TAINTED;}
FC_FN void c2_front_raw_write(void){
 c2_front_certificate[2]=(c2_front_certificate[2]&FC_BUSY)|FC_TAINTED;
}
FC_FN uint8_t c2_front_publish(uint16_t checked_front){
 if(!(c2_front_certificate[2]&FC_BUSY)
    || checked_front>LISP65_C2_BANK2_CODE_LIMIT){
  c2_front_abort();return 0u;
 }
 if(c2_front_certificate[2]&FC_TAINTED){
  c2_front_certificate[2]=FC_TAINTED;return 1u;
 }
 c2_front_certificate[0]=(uint8_t)checked_front;
 c2_front_certificate[1]=(uint8_t)(checked_front>>8);
 c2_front_certificate[2]=FC_VALID;
 return 1u;
}
FC_FN obj c2_resolver_charged_front(void){
 uint8_t row[10];uint16_t generation,count,i,low=0,end,at,length;
 const uint16_t limit=(uint16_t)LISP65_C2_BANK2_CODE_LIMIT;
 if(!c2_ready || (c2_front_certificate[2]&FC_BUSY))return NIL;
 if(!c2_stream_c2d_read(10u,row,8u))goto refuse;
 generation=c2_u16(row);count=c2_u16(row+6);
 if(count>C2D_ENTRY_CAP || generation!=c2_runtime.generation
    || count!=c2_runtime.entry_count)goto refuse;
 if(c2_front_certificate[2]==FC_VALID){
  low=c2_u16(c2_front_certificate);
 }else{
  for(i=0;i<count;++i){
   if(!c2_stream_c2d_read((uint16_t)(2096u+i*10u),row,10u)
      || c2_u16(row+8)!=generation)goto refuse;
   at=c2_u16(row+2);length=c2_u16(row+4);
   if(!length || at>limit || length>(uint16_t)(limit-at))goto refuse;
   end=at+length;if(end>low)low=end;
  }
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

def main():
    S.require_auth();OUT.mkdir(exist_ok=False)
    p=OUT/'certificate.inc';p.write_text(HELPER)
    P.write(OUT/'binding.json',dict(status='PARKED ISOLATED HOST PROTOTYPE; NOT PRODUCT INTEGRATION',
        driver=P.bind(Path(__file__)),kernel=P.bind(p),source_authority=S.require_auth(),execution_head='117e925b',
        policy=dict(raw_write='All notified raw writes taint until trusted boot reset; no address exemptions',
            abort='Invalidate, never restore pending/cursor; next stable query fully refills',
            warm='One actual header read; no entry reads. Faults at eliminated entry reads are not executed',
            publication='Begin first; publish only caller-proven complete/terminal front. No certificate on intermediate failure'),
        limits='Caller integration, raw-I/O interception and real INIT trace not proved by this isolated kernel.',
        product_builds=0,product_links=0,seeds=0,device_contacts=0))
    print('PARKED kernel; three-byte owner; raw writes taint until boot; abort requires refill')

if __name__=='__main__':main()
