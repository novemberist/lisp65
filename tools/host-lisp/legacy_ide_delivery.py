"""Compose the current disk-role projection without rebuilding the runtime.

One selected population binds the descriptor and the generated stager source.
Historical media constructors and their 13-role claims are not rewritten.
"""
from pathlib import Path
import argparse, copy, hashlib, json, math, re, struct, subprocess, zlib
import c2_lite_media_product as M
import c2_require_resolver_gate as L
import d81_bam_sanity as BAM
MEDIA=M  # Canonical producer call spelling used by structural enumeration.

ROOT=Path(__file__).resolve().parents[2]
CONFIG=ROOT/'config/legacy-ide-delivery.json'
def require(ok,msg):
    if not ok:raise ValueError(msg)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def bind(p):return dict(path=str(p.resolve()),bytes=p.stat().st_size,sha256=sha(p.read_bytes()))
def checked(b):
    if 'commit' in b:
        raw=subprocess.check_output(['git','show',b['commit']+':'+b['path']],cwd=ROOT)
        require(sha(raw)==b['sha256'],'historical source identity: '+b['path'])
        p=ROOT/'build/legacy-ide-era-inputs'/b['commit']/b['path']
        if p.exists():require(p.read_bytes()==raw,'historical materialization drift')
        else:p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
        return p
    p=ROOT/b['path'];require(sha(p.read_bytes())==b['sha256'],str(p)+' identity');return p
def write(p,value):p.write_text(json.dumps(value,indent=2)+'\n')
def off(t,s):
    require(1<=t<=80 and 0<=s<40,'D81 sector');return ((t-1)*40+s)*256
def inventory(raw):
    require(len(raw)==819200,'D81 length')
    _,errors=BAM.bam_free_counts(raw);require(not errors,str(errors))
    t,s=raw[off(40,0):off(40,0)+2];seen=set();owned=set();out={}
    while t:
        require(t==40 and (t,s) not in seen,'directory chain');seen.add((t,s));at=off(t,s)
        for i in range(8):
            e=at+32*i
            if not raw[e+2]:continue
            name=raw[e+5:e+21].rstrip(b'\xa0').decode('ascii')
            require(name not in out,'duplicate filename')
            ft,fs=raw[e+3:e+5];chain=[];data=bytearray()
            while ft:
                require(ft!=40 and (ft,fs) not in owned,'shared/cyclic file sector')
                owned.add((ft,fs));chain.append((ft,fs));p=off(ft,fs);nt,ns=raw[p:p+2]
                require(nt or 1<=ns<=255,'file terminator')
                _,bitmap=BAM.bam_entry(raw,ft)
                require(not bitmap[fs//8]&(1<<(fs%8)),'allocated file sector is free')
                data.extend(raw[p+2:p+256 if nt else p+1+ns]);ft,fs=nt,ns
            require(len(chain)==int.from_bytes(raw[e+30:e+32],'little'),'block count')
            out[name]=dict(entry=e,sectors=chain,data=bytes(data))
        t,s=raw[at:at+2]
    require({n.encode():r['data'] for n,r in out.items()}==L.D81.visible_files(raw),'independent D81 readback')
    return out
def free(raw,t,s):
    b=off(40,1 if t<=40 else 2)+16+6*((t-1)%40)
    require(not raw[b+1+s//8]&(1<<(s%8)),'double free')
    raw[b]+=1;raw[b+1+s//8]|=1<<(s%8)
def compose(raw,retired,replacements):
    rows=inventory(raw);out=bytearray(raw)
    require('BUFFER' not in retired,'BUFFER must remain')
    for name in retired:
        row=rows[name];out[row['entry']+2]=0
        for t,s in row['sectors']:free(out,t,s)
    for name,data in replacements.items():
        row=rows[name];used=math.ceil(len(data)/254);chain=row['sectors']
        require(0<used<=len(chain),'replacement exceeds its paid sectors: '+name)
        for t,s in chain[used:]:free(out,t,s)
        out[row['entry']+30:row['entry']+32]=used.to_bytes(2,'little')
        for i,(t,s) in enumerate(chain[:used]):
            p=off(t,s);chunk=data[i*254:(i+1)*254]
            out[p:p+2]=bytes(chain[i+1]) if i+1<used else bytes((0,len(chunk)+1))
            out[p+2:p+2+len(chunk)]=chunk
    actual=inventory(bytes(out))
    require(set(actual)==set(rows)-set(retired),'file population')
    for name,row in actual.items():
        if name in replacements:require(row['data']==replacements[name],'replacement readback')
        else:require(row==rows[name],'retained payload/locator: '+name)
    return bytes(out)
def derive():
    cfg=json.loads(CONFIG.read_text());receipt_path=checked(cfg['predecessor_receipt'])
    old=json.loads(receipt_path.read_text());medium=checked(old['medium']);raw=medium.read_bytes();files=inventory(raw)
    source=checked(cfg['source']).read_text()
    require(len(cfg['static_only'])==len(set(cfg['static_only'])),'duplicate delivery policy')
    retired={n.upper() for n in cfg['static_only']}
    require(retired=={'IDE','IDEX','M65D'} and 'BUFFER' not in retired,'authority population')
    oldrows=[]
    for row in old['descriptor']:
        row=dict(row);row['crc32']=int(row['crc32'],16)
        data=files[row['name'].upper()]['data']
        require(len(data)==row['bytes'] and zlib.crc32(data)==row['crc32'],'predecessor descriptor payload')
        oldrows.append(row)
    rows=[r for r in oldrows if r['name'].upper() not in retired]
    require(len(oldrows)-len(rows)==len(retired),'retired role coverage')
    for n in cfg['required_disk_packages']:
        # L65I names and physical filenames need not be the same (DEFSTRUCT).
        require(n not in cfg['static_only'],'package retired')
    require(files['BUFFER']['data'][:4]==b'L65S','BUFFER package')
    roles=[r['role_id'] for r in rows]
    require(roles==list(range(1,len(rows)+1)),'non-contiguous projected role population')
    profile=int.from_bytes(files['BOOT.ID']['data'][12:16],'little')
    saved=M.RECORDS,M.DESCRIPTOR_BYTES
    try:
        M.RECORDS=len(rows);M.DESCRIPTOR_BYTES=M.HEADER_BYTES+M.RECORD_BYTES*len(rows)
        descriptor,build_id=M.make_descriptor(rows,profile)
    finally:M.RECORDS,M.DESCRIPTOR_BYTES=saved
    constants={'R3_DESCRIPTOR_BYTES':len(descriptor),'R3_DESCRIPTOR_RECORDS':len(rows),
               'R3_ROLE_LAST':max(roles),'R3_ROLE_MASK':sum(1<<(r-1) for r in roles)}
    begin=source.index('#ifdef LISP65_C2_LITE_MEDIA_STAGER\n')
    end=source.index('#elif defined(LISP65_SHIP_MEDIA_STAGER)',begin)
    block=source[begin:end]
    for name,value in constants.items():
        pattern=r'(?m)^#define '+name+r' [^\n]+$'
        block,n=re.subn(pattern,'#define '+name+' LISP65_DELIVERY_'+name,block)
        require(n==1,'stager constant source population: '+name)
    generated=source[:begin]+block+source[end:]
    header='/* Derived from config/legacy-ide-delivery.json and consumed descriptor. */\n'
    header+=''.join('#define LISP65_DELIVERY_'+n+' '+str(v)+'u\n' for n,v in constants.items())
    return dict(cfg=cfg,old=old,raw=raw,files=files,rows=rows,descriptor=descriptor,
                build_id=build_id,constants=constants,source=generated,header=header,retired=retired)
def validate(data,rows,build_id):
    saved=M.RECORDS,M.DESCRIPTOR_BYTES
    try:
        M.RECORDS=len(rows);M.DESCRIPTOR_BYTES=M.HEADER_BYTES+M.RECORD_BYTES*len(rows)
        return M.parse_descriptor(data,build_id,rows)
    finally:M.RECORDS,M.DESCRIPTOR_BYTES=saved
def c_function(source,name):
    start=re.search(r'(?m)^static [^\n]*\b'+name+r'\([^\n]*',source).start()
    brace=source.index('{',start);depth=0
    for end in range(brace,len(source)):
        depth+=(source[end]=='{')-(source[end]=='}')
        if not depth:return source[start:end+1]
    raise ValueError('C function boundary: '+name)
def host_gate(d,out):
    """Execute the consumed C descriptor predicate and disk_record branches.

    Host stdio is the transport seam, not a claimed F011 emulator. Xemu and
    the physical cold start retain their separate acceptance obligations.
    """
    out.mkdir(parents=True,exist_ok=True);source=checked(d['cfg']['source']).read_text()
    header='#include <stdint.h>\n#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n'
    header+='#define LISP65_VERIFIED_MEDIA_STAGER 1\n#define R3_FLAG_STAGE 1\n'
    for n,v in dict(d['constants'],R3_DESCRIPTOR_HEADER_BYTES=16,R3_DESCRIPTOR_RECORD_BYTES=32,
                   R3_DESCRIPTOR_VERSION=2,R3_RESTAGE_LIMIT=2,R3_EXPECTED_PRODUCT_BUILD_ID=d['build_id']).items():
        header+='#define '+n+' '+str(v)+'u\n'
    header+='static uint8_t descriptor[R3_DESCRIPTOR_BYTES];\nstatic const char *directory,*missing;\n'
    code=header+'\n'.join(c_function(source,n) for n in ('rd32','crc32_step','record_at','record_name','validate_descriptor'))
    code+=r'''
static uint8_t scan_file(const char *name,uint32_t destination,uint8_t stage,uint32_t expected_length,uint32_t expected_crc) {
    char path[4096]; uint32_t length=0,crc=0xffffffffu; int c;
    (void)destination; (void)stage;
    if (!strcmp(name,missing)) return 0;
    snprintf(path,sizeof path,"%s/%s",directory,name);
    FILE *f=fopen(path,"rb"); if(!f)return 0;
    while((c=fgetc(f))!=EOF){length++;crc=crc32_step(crc,(uint8_t)c);}
    fclose(f);return length==expected_length && (crc^0xffffffffu)==expected_crc;
}
'''
    code+=c_function(source,'disk_record')
    code+=r'''
int main(int argc,char **argv){
    if(argc!=4)return 3;
    FILE *f=fopen(argv[1],"rb");if(!f)return 3;
    size_t n=fread(descriptor,1,sizeof descriptor,f);int extra=fgetc(f);fclose(f);
    if(n!=sizeof descriptor || extra!=EOF || !validate_descriptor())return 2;
    directory=argv[2];missing=argv[3];
    for(uint8_t i=0;i<R3_DESCRIPTOR_RECORDS;i++){
        const uint8_t *r=record_at(i);
        if(!disk_record(r,!!(r[1]&R3_FLAG_STAGE)))return 2;
    }
    return 0;
}
'''
    p=out/'validator.c';p.write_text(code)
    exe=out/'validator';subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',str(p),'-o',str(exe)],check=True)
    files=out/'files';files.mkdir(exist_ok=True)
    for row in d['rows']:(files/row['name']).write_bytes(d['files'][row['name'].upper()]['data'])
    descriptor=out/'current.id';descriptor.write_bytes(d['descriptor'])
    def execute(path,missing=''):
        return subprocess.run([str(exe),str(path),str(files),missing]).returncode
    require(execute(descriptor)==0,'consumed C validator positive')
    cases=[]
    for row in d['rows']:
        require(execute(descriptor,row['name'])==2,'missing mandatory file accepted: '+row['name'])
        cases.append('missing-file-'+row['name'])
    old=out/'old.id';old.write_bytes(d['files']['BOOT.ID']['data'])
    require(execute(old)==2,'old descriptor accepted');cases.append('old-descriptor-new-stager')
    bad=bytearray(d['descriptor']);bad[28]^=1;(out/'bad-crc.id').write_bytes(bad)
    require(execute(out/'bad-crc.id')==2,'bad CRC accepted');cases.append('bad-crc')
    # The old compiled predicate is built for its own descriptor identity.
    oldcode=code
    oldbytes=old.read_bytes()
    oldvalues=dict(R3_DESCRIPTOR_BYTES=len(oldbytes),R3_DESCRIPTOR_RECORDS=oldbytes[6],
                   R3_ROLE_LAST=oldbytes[6],R3_ROLE_MASK=(1<<oldbytes[6])-1,
                   R3_EXPECTED_PRODUCT_BUILD_ID=int.from_bytes(oldbytes[8:12],'little'))
    for name,value in oldvalues.items():
        oldcode,n=re.subn(r'(?m)^#define '+name+r' \d+u$', '#define '+name+' '+str(value)+'u',oldcode)
        require(n==1,'old constant binding')
    pold=out/'old-validator.c';pold.write_text(oldcode);eold=out/'old-validator'
    subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',str(pold),'-o',str(eold)],check=True)
    for row in d['old']['descriptor']:(files/row['name']).write_bytes(d['files'][row['name'].upper()]['data'])
    require(subprocess.run([str(eold),str(old),str(files),'']).returncode==0,'old predicate positive')
    require(subprocess.run([str(eold),str(descriptor),str(files),'']).returncode==2,'new descriptor old stager')
    cases.append('new-descriptor-old-stager')
    write(out/'receipt.json',dict(status='PASS',source=bind(checked(d['cfg']['source'])),harness=bind(p),old_harness=bind(pold),
        cases=cases,claim='Consumed C predicates with stdio transport; no native hardware timing claim'))
    return cases
def selftest(d):
    data=d['descriptor'];rows=d['rows'];bid=d['build_id'];cases={}
    validate(data,rows,bid)
    for row in rows:
        r=bytearray(data);at=16+(row['role_id']-1)*32;r[at]=0
        cases['missing-required-role-'+row['name']]=bytes(r)
    for name,pos in [('wrong-crc',28),('wrong-profile',12)]:
        r=bytearray(data);r[pos]^=1;cases[name]=bytes(r)
    cases['old-descriptor-new-stager']=d['files']['BOOT.ID']['data']
    r=bytearray(data);r[6]+=1;r.extend(d['files']['BOOT.ID']['data'][-32:]);cases['stale-extra-role']=bytes(r)
    for name,raw in cases.items():
        try:
            validate(raw,rows,bid)
            require(raw[12:16]==data[12:16],'profile identity')
        except (ValueError,M.MediaError):continue
        raise AssertionError('mutation accepted: '+name)
    old=d['files']['BOOT.ID']['data']
    require(data[6]!=old[6] and len(data)!=len(old) and data[8:12]!=old[8:12],'new-descriptor-old-stager')
    extra=[]
    if 'commit' in d['cfg']['source']:
        live=dict(d['cfg']['source']);live.pop('commit')
        try:checked(live)
        except ValueError:extra.append('historical-gate-fed-live-stager')
        else:raise AssertionError('historical gate accepted live stager')
    return list(cases)+['new-descriptor-old-stager']+extra
def prepare(d,out):
    require(not (out/'stager-build-started.json').exists(),'stager budget already started')
    out.mkdir(parents=True,exist_ok=True)
    (out/'stager-main.c').write_text(d['source']);(out/'delivery-roles.h').write_text(d['header'])
    (out/'boot.id').write_bytes(d['descriptor'])
    write(out/'projection.json',dict(authority=d['cfg']['authority'],source=bind(checked(d['cfg']['source'])),
        predecessor=bind(checked(d['cfg']['predecessor_receipt'])),policy=bind(CONFIG),
        rows=d['rows'],constants=d['constants'],build_id=d['build_id'],
        descriptor=bind(out/'boot.id'),generated_source=bind(out/'stager-main.c'),header=bind(out/'delivery-roles.h'),
        mutations_rejected=selftest(d),static_only=d['cfg']['static_only'],retained_packages=d['cfg']['required_disk_packages']))
def build(d,out):
    prepare(d,out)
    host_gate(d,out/'host-gate')
    write(out/'stager-build-started.json',dict(authority=d['cfg']['authority'],stager_builds=1,runtime_builds=0))
    M.STAGER_C=out/'stager-main.c'
    # The generated source retains original relative includes; scripts is
    # their original include root. The one derived header supplies all four
    # changed constants, before any code generation.
    gate=MEDIA.compile_stager(d['build_id'],d['rows'],build_dir=out,stager=out/'autoboot.c65',
        stager_map=out/'autoboot.c65.map',compile_defines=('-DLISP65_STARTUP_REQUIRE_EXPERIENCE',
            '-Iscripts','-include',str(out/'delivery-roles.h')))
    write(out/'stager-gates.json',gate)
    require(not (out/'product.d81').exists(),'media budget already consumed')
    candidate=compose(d['raw'],d['retired'],{'AUTOBOOT.C65':(out/'autoboot.c65').read_bytes(),'BOOT.ID':d['descriptor']})
    (out/'product.d81').write_bytes(candidate)
    require((out/'product.d81').read_bytes()==candidate,'medium readback')
    files=inventory(candidate)
    for r in d['rows']:
        data=files[r['name'].upper()]['data']
        require(len(data)==r['bytes'] and zlib.crc32(data)==r['crc32'],'packed descriptor CRC')
    receipt=copy.deepcopy(d['old']);receipt['descriptor']=validate(d['descriptor'],d['rows'],d['build_id'])
    receipt['medium']=bind(out/'product.d81');receipt['stager']=gate
    for n in d['cfg']['static_only']:receipt['artifacts'].pop('library-'+n)
    receipt['status']='COMPOSED THREE-ROLE RETIREMENT; PENDING XEMU AND DEVICE'
    receipt['authority']={'commit':d['cfg']['authority'],'runtime_seeds':0,'runtime_finales':0,'stager_builds':1,'media_links':1,'device_contacts':0}
    receipt['predecessor_receipt']=d['cfg']['predecessor_receipt']
    receipt['projection']=bind(out/'projection.json')
    receipt['retained_files']={n:dict(bytes=len(r['data']),sha256=sha(r['data']),sectors=r['sectors']) for n,r in files.items()}
    receipt['freed_blocks']=sum(BAM.bam_free_counts(candidate)[0])-sum(BAM.bam_free_counts(d['raw'])[0])
    write(out/'packed-receipt.json',receipt)
    packed_gates(d,out)
def packed_gates(d,out):
    import shutil
    import c2_packed_medium_transitive_closure as C
    import c2_packed_object_generation_coherence as G
    import c2_v200_interactive_delivery_chain_pricing as P
    receipt=json.loads((out/'packed-receipt.json').read_text())
    medium=checked(receipt['medium']);files=inventory(medium.read_bytes())
    base=checked(d['cfg']['predecessor_receipt']).parent/'packed/readback-product'
    projection=out/'readback-product'
    if not projection.exists():shutil.copytree(base,projection)
    code=files['CODE.BIN']['data'];offset=0
    for key in C.PRODUCT_KEYS:
        original=base/(key+'.code.bin');n=original.stat().st_size
        part=code[offset:offset+n];require(part==original.read_bytes(),'readback code projection: '+key)
        (projection/(key+'.code.bin')).write_bytes(part);offset+=n
    closure=C.derive(projection/'substitution-artifacts.json');C.require_closed(closure)
    manifest=json.loads((projection/'substitution-artifacts.json').read_text())
    coherence=G.derive(checked(manifest['manifests'][0]),base/'stdlib-p0.code.bin',P.STDLIB_SUITE,
                       (projection/'stdlib-p0.code.bin').read_bytes())
    G.require_coherent(coherence)
    replacements={'AUTOBOOT.C65':(out/'autoboot.c65').read_bytes(),'BOOT.ID':d['descriptor']}
    expected=compose(d['raw'],d['retired'],replacements)
    require(medium.read_bytes()==expected,'packed medium composition')
    materialized=out/'readback-files';materialized.mkdir(exist_ok=True)
    artifacts={};gates={}
    def same(path,want):
        require(path.read_bytes()==want,'packed-artifact byte identity: '+str(path))
        return dict(status='PASS',sha256=sha(want),bytes=len(want))
    for name,row in files.items():
        p=materialized/name;p.write_bytes(row['data']);artifacts[name]=p
        want=replacements.get(name,d['files'][name]['data'])
        gates[name]=lambda path,want=want:same(path,want)
    artifacts['medium']=medium;gates['medium']=lambda path:same(path,expected)
    for name,b in [('runtime-elf',receipt['elf']),('stager-elf',receipt['stager']['linked_transport']['elf'])]:
        p=checked(b);artifacts[name]=p;want=p.read_bytes()
        gates[name]=lambda path,want=want:same(path,want)
    registry=MEDIA.close_packed_artifacts(artifacts,gates)
    require('BUFFER' in registry['executed'],'BUFFER closure omitted')
    result=dict(status='PASS',medium=bind(medium),registry=registry,closure=closure,coherence=coherence,
                runtime_byteidentical=True,readback_files=len(files),descriptor_roles=len(d['rows']))
    write(out/'producer-packed-gates.json',result)
    return result
def main():
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['prepare','selftest','host-gate','build','check']);args=ap.parse_args()
    d=derive();out=ROOT/d['cfg']['output']
    if args.action=='prepare':prepare(d,out)
    elif args.action=='build':build(d,out)
    elif args.action=='host-gate':host_gate(d,out/'host-gate')
    elif args.action=='check':
        receipt=json.loads((out/'packed-receipt.json').read_text());p=checked(receipt['medium'])
        projection=json.loads((out/'projection.json').read_text())
        require(projection['rows']==d['rows'] and projection['constants']==d['constants'],'projection drift')
        require((out/'stager-main.c').read_text()==d['source'],'hand-edited stager source')
        require((out/'delivery-roles.h').read_text()==d['header'],'hand-edited stager constants')
        checked(projection['descriptor']);checked(projection['generated_source']);checked(projection['header'])
        checked(receipt['stager']['linked_transport']['elf'])
        for b in receipt['artifacts'].values():checked(b)
        expected=compose(d['raw'],d['retired'],{'AUTOBOOT.C65':(out/'autoboot.c65').read_bytes(),'BOOT.ID':d['descriptor']})
        require(p.read_bytes()==expected,'exact composed medium')
        files=inventory(expected)
        require(set(files)==set(receipt['retained_files']),'receipt population')
        for name,row in files.items():
            bound=receipt['retained_files'][name]
            require(sha(row['data'])==bound['sha256'] and len(row['data'])==bound['bytes'],'receipt payload')
            require([list(s) for s in row['sectors']]==bound['sectors'],'receipt locator')
        packed_gates(d,out)
    print(json.dumps(dict(status='PASS',action=args.action,constants=d['constants'],mutations=selftest(d)),indent=2))
if __name__=='__main__':main()
