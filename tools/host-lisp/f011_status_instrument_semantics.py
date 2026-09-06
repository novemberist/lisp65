#!/usr/bin/env python3
"""Execute pricing bodies on a host MMIO trace; not device qualification."""
import json
import re
from f011_status_instrument_pricing import ROOT, OUT, HEADER, io_successor, run, bind

def bodies(s):
    wait=s[s.index('static LISP65_C2_MAPPED_F011_COLD_FN unsigned char f011_wait_not_busy('):]
    wait=wait[:wait.index('/* F011 read of ONE')]
    body=s[s.index('#endif\n    unsigned char b'):]
    body=body[len('#endif\n'):body.index('\n/* ==== Rule-B')]
    body=re.sub(r'\*\(\(volatile unsigned char \*\)0x(D08[1456])\) = ([^;]+);',r'wr(0x\1, \2);',body)
    return wait+'\nunsigned int f011_read_at(unsigned char T,unsigned char S) {\n'+body

PRE=r'''
#include <stdint.h>
#include <assert.h>
#include <string.h>
#define LISP65_C2_MAPPED_F011_COLD_FN
static unsigned trace[200000], used, phase, polls, mode, final_status, aux, aux_reads;
static void event(unsigned v){ assert(used<200000); trace[used++]=v; }
static unsigned char rd(unsigned a){
 if(a==0xd083){ aux_reads++; return aux; }
 assert(a==0xd082);
 unsigned v;
 if((mode==1 && phase==0x20)||(mode==2 && phase==0x40)) v=0x81;
 else if(polls++<2) v=0x80;
 else if(polls==3) v=0;
 else v=final_status;
 event(0x10000|v); return v;
}
static void wr(unsigned a,unsigned v){event((a<<8)|v);if(a==0xd081){phase=v;polls=0;}}
static void m65_io_enable(void){event(1);}
static void lisp65_f011_take_context(void){event(2);}
static void lisp65_f011_map_buffer(void){event(3);}
#define LISP65_F011_READ8(a) rd(a)
enum{LISP65_F011_STATUS_BUSY=0x80,LISP65_F011_STATUS_READ_COMPLETE=0x60,LISP65_F011_STATUS_READ_MASK=0x7c};
#define LISP65_F011_READ_FAILED 0xffffu
'''
POST=r'''
static void reset_io(unsigned m,unsigned s){used=phase=polls=aux_reads=0;mode=m;final_status=s;aux=0x59;}
static unsigned saved[200000];
int main(void){
 unsigned cases=0;
 for(unsigned m=0;m<3;m++)for(unsigned s=0;s<256;s++)for(unsigned half=0;half<2;half++){
  reset_io(m,s); unsigned a=base_read(1,half), n=used; memcpy(saved,trace,n*sizeof(unsigned));
  reset_io(m,s); lisp65_f011_status_state.tag=0;
  unsigned b=f011_read_at(1,half);
  assert(a==b && n==used && !memcmp(saved,trace,n*sizeof(unsigned)));
  unsigned tag=m?m+2:((s&0x7c)==0x60?1:2);
  assert(lisp65_f011_status_state.tag==tag);
  assert(lisp65_f011_status_state.d082==(m?0x81:s));
  assert(lisp65_f011_status_state.d083==0x59 && aux_reads==1);
  cases++;
 }
 for(unsigned failure=2;failure<=4;failure++){
  lisp65_f011_status_state.tag=0; aux_reads=0; aux=7;
  f011_status_observe(1,0x63); assert(lisp65_f011_status_state.tag==1);
  aux=8; f011_status_observe(1,0x60);
  assert(lisp65_f011_status_state.d082==0x63 && aux_reads==1);
  f011_status_observe(failure,0x81);
  assert(lisp65_f011_status_state.tag==failure && lisp65_f011_status_state.d083==8);
  aux=9; f011_status_observe(2,0x40); f011_status_observe(1,0x60);
  assert(lisp65_f011_status_state.tag==failure && lisp65_f011_status_state.d082==0x81 && aux_reads==2);
 }
 return cases==1536?0:1;
}
'''

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    source=run(['git','show','f0c467cd:src/io.c']).decode()
    base=bodies(source).replace('f011_wait_not_busy','base_wait').replace('f011_read_at','base_read')
    header=(ROOT/'src/f011_status_witness.h').read_text()
    # This proof belongs to the retired three-byte instrument world, not
    # the witness-free buffered successor. Its executed mutations stay live.
    from evidence_era import era_blob
    assert bodies(era_blob('bbbaed02','src/io.c').decode()) == bodies(io_successor(source)), 'sealed read body differs from priced successor'
    variants={'control':header,
      'omit-success':header.replace('    if (lisp65_f011_status_state.tag >', '    if (tag == F011_FIRST_SUCCESS) return;\n    if (lisp65_f011_status_state.tag >'),
      'overwrite-first-failure':header.replace('lisp65_f011_status_state.tag > F011_FIRST_SUCCESS','0'),
      'resample-d082':header.replace('= consumed_status;', '= LISP65_F011_READ8(0xd082u);'),
      'wrong-payload':header.replace('= consumed_status;', '= 0;')}
    import subprocess
    results={}
    for name,h in variants.items():
        src=OUT/('semantics-'+name+'.c'); exe=src.with_suffix('')
        src.write_text(PRE+base+'\n#define LISP65_F011_INSTRUMENT_BODY\n'+h+'\n'+bodies(io_successor(source))+POST)
        run(['/usr/bin/cc','-std=c11','-O2',src,'-o',exe])
        p=subprocess.run([str(exe)],stdout=subprocess.PIPE,stderr=subprocess.PIPE, start_new_session=True)
        results[name]={'exit_code':p.returncode,'source':bind(src)}
        assert (p.returncode==0)==(name=='control'),name
    receipt={'cases':1536,'checks':['return value and original MMIO trace unchanged','exact consumed D082','both timeout phases','first success then immutable first failure','no D087 access','D083 reads only on record publication'], 'mutations':results,'claim':'host extracted C bodies, not final ELF or hardware; D083 read semantics remain device-bound'}
    (OUT/'semantics-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2))
if __name__=='__main__': main()
