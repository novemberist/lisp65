#!/usr/bin/env python3
"""Execute proposed clock/wait/record bodies; host semantics only."""
import json
import re
import subprocess
from f011_frame_instrument_pricing import ROOT, OUT, HEADER, sources
from f011_status_instrument_pricing import write, bind

def main():
    io=sources()['io.c']
    a=io.index('#endif\n    unsigned char b')+len('#endif\n')
    body=io[a:io.index('\n/* ==== Rule-B',a)]
    body=re.sub(r'\*\(\(volatile unsigned char \*\)0x(D08[1456])\) = ([^;]+);',r'wr(0x\1, \2);',body)
    body='unsigned int f011_read_at(unsigned char T,unsigned char S) {\n'+body
    header=HEADER.read_text()
    fixture=(ROOT/'tests/fixtures/f011-frame-witness-host.c').read_text()
    variants={'control':header,
              'omit-clock-validation':header.replace('if(!f011_frame_sample(&start)) return 0;','return 1;\n    if(!f011_frame_sample(&start)) return 0;'),
              'omit-stalled-clock-escape':header.replace('else if(!--fuel) break;','else (void)fuel;'),
              'ignore-torn-sample':header.replace('if(a==b)', 'if(1)'),
              'wrong-wrap-subtraction':header.replace('(uint16_t)(now-start)','(now>=start?(uint16_t)(now-start):0)'),
              'weaken-frame-cap':header.replace('600u','1200u'),
              'overwrite-first-failure':header.replace('lisp65_f011_status_state.tag>F011_FIRST_SUCCESS','0'),
              'wrong-spin-status':header.replace('=r->after_spin_d082;', '=0;'),
              'reinsert-spinup-poll':header}
    # Exact cap is the oracle, not merely any value above the configured cap.
    fixture=fixture.replace('frames>=600','frames==600')
    results={}
    for name,h in variants.items():
        assert name in ('control','reinsert-spinup-poll') or h!=header
        src=OUT/f'host-{name}.c'; exe=src.with_suffix('')
        variant_body=body
        if name=='reinsert-spinup-poll':
            variant_body=body.replace('record.after_spin_d082=LISP65_F011_READ8(0xd082u);',
                'record.after_spin_d082=LISP65_F011_READ8(0xd082u); (void)LISP65_F011_READ8(0xd082u);')
            assert variant_body!=body
        write(src,fixture.replace('/* PROTOTYPE_HEADER */',h).replace('/* PROTOTYPE_BODY */',variant_body))
        subprocess.run(['/usr/bin/cc','-std=c11','-O2','-fpack-struct=1',str(src),'-o',str(exe)],check=True)
        try:
            p=subprocess.run([str(exe)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=2)
            code=p.returncode
        except subprocess.TimeoutExpired:
            code='host-timeout: missing finite escape'
        assert (code==0)==(name=='control'), (name,code)
        results[name]=dict(exit_code=code,source=bind(src))
    receipt=dict(control_pass=True,normal_completion_statuses=128,exception_modes=4,
                 first_failure_preservation=True,mutations=results,
                 claim='executed extracted C prototype; not final ELF, DWX, physical timing or IRQ proof')
    write(OUT/'host-semantics-r2.json',json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({name:r['exit_code'] for name,r in results.items()},indent=2))
if __name__=='__main__': main()
