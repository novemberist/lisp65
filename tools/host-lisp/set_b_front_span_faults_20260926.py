"""Actual extracted decoder C: error-order controls and span helper qualification."""
from pathlib import Path
import ctypes as C
import subprocess
import set_b_producer as P
import set_b_front_relocation_faults_20260926 as OLD
import set_b_front_integration_r2_20260926 as I
import set_b_front_relocation_20260926 as EARLY
import set_b_front_span_20260926 as F
ROOT=P.ROOT
OUT=ROOT/'build/set-b-front-span-faults-r1'

SUFFIX=r'''
void tweak(uint8_t mode){
 if(mode==11)w24(plane+raw_at+18,0x10064u);
 if(mode==12)shelf[meta+24+2]=1;
 if(mode==13)w16(plane+entry_at+2,99);
 if(mode==14){w24(plane+raw_at+18,65534);w16(plane+entry_at+2,65534);w16(plane+entry_at+12,5);}
 if(mode==15){w24(plane+raw_at+18,60744);w16(plane+entry_at+2,60744);w16(plane+entry_at+12,60751);}
}
uint8_t run(uint8_t world,uint8_t direct){
 uint8_t (*phases[4][3])(void*)={{b_phase04,b_phase05a,b_phase05b},
   {p_phase04,p_phase05a,p_phase05b},{n_phase04,n_phase05a,n_phase05b},
   {e_phase04,e_phase05a,e_phase05b}};
 if(direct){c2aw.append.phase=5;c2aw.append.reserved=0x5a;}
 for(uint8_t i=direct?2:0;i<3;++i){
  uint8_t e=phases[world][i](&c2aw.append);
  if(e){result_stage=i;result_code=e;result_front=c2aw.append.entry_cursor;return e;}
 }
 result_stage=3;result_front=c2aw.append.entry_cursor;return 0;
}
uint8_t guard_probe(uint8_t mode){
 setup(0,0,0,0);c2aw.append.entry_cursor=29;
 if(mode==1)c2aw.staged=0;
 if(mode==2)c2aw.attic=65537;
 if(mode==3)c2_decode_active=&c2_runtime;
 uint8_t e=n_guard(&c2aw.append);result_front=c2aw.append.entry_cursor;return e;
}
uint8_t helper_probe(uint16_t start,uint16_t length,uint16_t pending){
 c2_stream_context c,before;memset(&c,0xa5,sizeof c);c.entry_cursor=pending;before=c;
 c2_front_pending_max(&c,start,length);result_front=c.entry_cursor;
 for(unsigned i=0;i<sizeof c;++i){
  if(i>=offsetof(c2_stream_context,entry_cursor)&&i<offsetof(c2_stream_context,entry_cursor)+2)continue;
  if(((uint8_t*)&c)[i]!=((uint8_t*)&before)[i])return 0;
 }
 return 1;
}
'''

def main():
    F.R.I.OLD.S.require_auth()
    gate=ROOT/'build/set-b-front-span-capacity-r1/receipt.json';assert P.load(gate)['status'].startswith('PASS')
    OUT.mkdir(exist_ok=False)
    source_paths=[ROOT/'src/c2_product_runtime.c',ROOT/'config/set-b-native/includes/c2-stream-decoder.c']
    worlds=[('b',*source_paths)]
    for name,root in (('p',I.OUT),('n',F.OUT),('e',EARLY.OUT)):
        worlds.append((name,root/'candidate/src/c2_product_runtime.c',root/'candidate/config/set-b-native/includes/c2-stream-decoder.c'))
    pre=OLD.PRE.replace('at==meta+24?','at==(uint32_t)meta+24u?')
    pre='#include <stddef.h>\n'+pre
    assert F.HELPER in (F.OUT/'candidate/src/c2_product_runtime.c').read_text()
    pieces=[F.HELPER];extracted=[];inputs=[]
    for prefix,rp,dp in worlds:
        runtime=rp.read_text();decoder=dp.read_text();inputs.extend((P.bind(rp),P.bind(dp)))
        block=[I.function(runtime,'c2_append_source_domain_guard').replace('c2_append_source_domain_guard',prefix+'_guard')]
        for name in ('04','05a','05b'):
            block.append(I.function(decoder,'c2_stream_phase_'+name).replace('c2_stream_phase_'+name,prefix+'_phase'+name)
                .replace('c2_append_source_domain_guard',prefix+'_guard'))
        p=OUT/(prefix+'-extracted.c');p.write_text('\n'.join(block));extracted.append(P.bind(p));pieces.extend(block)
    header=ROOT/'config/set-b-native/includes/c2-stream-decoder.h'
    (OUT/header.name).write_bytes(header.read_bytes())
    fixture=OUT/'fixture.c';fixture.write_text(pre+'\n'+'\n'.join(pieces)+SUFFIX)
    lib=OUT/'fixture.so';cmd=['cc','-std=c11','-O1','-g','-fPIC','-shared','-Wall','-Wextra','-Werror',
        '-Wno-misleading-indentation','-I'+str(OUT),str(fixture),'-o',str(lib)]
    r=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True);log=OUT/'compile.log';log.write_text(r.stdout+r.stderr)
    P.write(OUT/'command.json',dict(command=cmd,exit=r.returncode,log=P.bind(log)));assert r.returncode==0,r.stderr
    d=C.CDLL(str(lib));d.setup.argtypes=[C.c_uint8]*4;d.tweak.argtypes=[C.c_uint8]
    d.run.argtypes=[C.c_uint8]*2;d.run.restype=C.c_uint8
    d.helper_probe.argtypes=[C.c_uint16]*3;d.helper_probe.restype=C.c_uint8
    def execute(world,mutation=0,fault=0,partial=0,boot=0,direct=0):
        d.setup(mutation if mutation<=10 else 0,fault,partial,boot);d.tweak(mutation)
        status=d.run(world,direct)
        return dict(status=status,phase=['04','05a','05b','completed05b'][C.c_uint8.in_dll(d,'result_stage').value],
            pending=C.c_uint16.in_dll(d,'result_front').value,
            reads=list((C.c_uint8*64).in_dll(d,'read_classes'))[:C.c_uint32.in_dll(d,'read_count').value])
    rows=[];halt=None
    def add(row,ok):
        nonlocal halt
        rows.append(row)
        if not ok:halt=row
        return ok
    for mode in range(4):
        result=d.guard_probe(mode);pending=C.c_uint16.in_dll(d,'result_front').value
        assert add(dict(kind='guard',mode=mode,result=result,pending=pending),
            (result,pending)==((1,90) if mode==0 else (0,29)))
    # Identical complete result includes semantic read history and pending max.
    for mutation in range(16):
        if halt:break
        for boot in (0,1):
            if halt:break
            for fault in (0,1,2,3,5,6,7):
                if halt:break
                for partial in ((0,) if fault==0 else (0,1,2)):
                    a=execute(1,mutation,fault,partial,boot);b=execute(2,mutation,fault,partial,boot)
                    if not add(dict(kind='decoder-matrix',mutation=mutation,boot=boot,fault=fault,partial=partial,
                        previous=a,candidate=b),a==b):break
    if not halt:
        for mutation in range(16):
            for fault in (0,1,5,6,7):
                a=execute(1,mutation,fault,direct=1);b=execute(2,mutation,fault,direct=1)
                if not add(dict(kind='05b-isolated-late-metadata',mutation=mutation,fault=fault,previous=a,candidate=b),a==b):break
            if halt:break
    if not halt:
        for partial in (0,1,2):
            for mutation,fault,expected in ((4,3,(1,5)),(6,4,(5,1))):
                a=execute(1,mutation,fault,partial);b=execute(2,mutation,fault,partial);e=execute(3,mutation,fault,partial)
                if not add(dict(kind='falling-early05a-control',mutation=mutation,fault=fault,partial=partial,
                    previous=a,candidate=b,early=e),a==b and (b['status'],e['status'])==expected):break
            if halt:break
    if not halt:
        for start in (0,1,254,255,256,32767,60000,60744,60751,60757):
            for length in sorted({1,7,255,256,60758-start}):
                if start+length>60758:continue
                end=start+length
                for pending in sorted({0,1,end-1,end,min(65535,end+1),65535}):
                    guard=d.helper_probe(start,length,pending);value=C.c_uint16.in_dll(d,'result_front').value
                    if not add(dict(kind='exact-helper',start=start,length=length,pending=pending,
                        result=value,other_context_bytes_unchanged=bool(guard)),guard and value==max(pending,end)):break
                if halt:break
            if halt:break
    P.write(OUT/'rows.json',rows)
    if halt:P.write(OUT/'first-unbound-error.json',halt)
    status='HALT: UNBOUND C SUCCESSOR' if halt else 'PASS EXACT DECODER AND SPAN-HELPER C; LIFECYCLE STILL OPEN'
    P.write(OUT/'receipt.json',dict(status=status,driver=P.bind(Path(__file__)),gate=P.bind(gate),execution_head='09c7c983',
        inputs=inputs,extracted=extracted,helper_source=P.bind(Path(F.__file__)),fixture=P.bind(fixture),header=P.bind(OUT/header.name),
        library=P.bind(lib),compile=P.bind(OUT/'command.json'),rows=P.bind(OUT/'rows.json'),row_count=len(rows),
        passing_rows=len(rows)-(1 if halt else 0),halt=P.bind(OUT/'first-unbound-error.json') if halt else None,
        host_c_compiles=1,host_c_links=1,
        scope='Exact guards/phases04/05a/05b and helper, common copied header; synthetic image helper/transaction layout and semantic-class partial reads. Late-metadata rows deliberately bypass05a; no shipped reachability claim.',
        limits='No terminal publication, rollback/recovery, real transport, native code execution or whole-product exact error proof yet.',
        product_builds=0,product_links=0,seeds=0,device_contacts=0))
    print(status,'rows',len(rows),'passes',len(rows)-(1 if halt else 0))

if __name__=='__main__':main()
