"""Price and prove Stager CRC32 forms without building a product or stager."""
from pathlib import Path
import argparse,ctypes,hashlib,json,subprocess,sys,zlib,re
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/host-lisp'))
from elf_truth import ElfTruth

def bind(p):
    b=p.read_bytes();return dict(path=str(p.relative_to(ROOT)),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def validate_package_locators(files):
    import c2_require_resolver_gate as L
    for row in L.decode_index(files['L65INDEX']['data']):
        name=row['name'].upper()
        assert name in files,('missing indexed package',name)
        assert (row['track'],row['sector'])==files[name]['sectors'][0],('stale package locator',name)
def table(bits):
    result=[]
    for n in range(1<<bits):
        for _ in range(bits):n=(n>>1)^(0xedb88320 if n&1 else 0)
        result.append(n)
    return result
def body(kind):
    if kind=='bitwise':return '''uint8_t bit; crc ^= value;
    for (bit=0;bit<8;bit++) crc=(crc>>1)^(0xedb88320ul & (uint32_t)-(int32_t)(crc&1u));
    return crc;'''
    values=table(4 if kind=='nibble' else 8)
    if kind=='planes':
        arrays='\n'.join('static const uint8_t t%d[256]={%s};'%(i,','.join(str((v>>(8*i))&255) for v in values)) for i in range(4))
        return arrays+'''\nuint8_t k=(uint8_t)(crc^value);
    return (crc>>8) ^ ((uint32_t)t0[k] | ((uint32_t)t1[k]<<8) | ((uint32_t)t2[k]<<16) | ((uint32_t)t3[k]<<24));'''
    array='static const uint32_t t[%d]={%s};\n'%(len(values),','.join('0x%08xUL'%v for v in values))
    if kind=='nibble':return array+'crc ^= value; crc=(crc>>4)^t[crc&15]; return (crc>>4)^t[crc&15];'
    assert kind=='byte'
    return array+'return (crc>>8)^t[(uint8_t)(crc^value)];'

def preflight(out):
    import legacy_ide_delivery as D
    out.mkdir(parents=True,exist_ok=False)
    base=ROOT/'build/definition-set-a-final-medium-r1/packed'
    old=(base/'delivery-stager-main.c').read_text()
    live=ROOT/'scripts/r3-cold-stager-main.c';source=live.read_text()
    raw=(base/'hardware-sp-seed.d81').read_bytes();files=D.inventory(raw)
    descriptor=files['BOOT.ID']['data'];assert len(descriptor)==336
    constants=dict(R3_DESCRIPTOR_BYTES=len(descriptor),R3_DESCRIPTOR_RECORDS=descriptor[6],
        R3_ROLE_LAST=descriptor[6],R3_ROLE_MASK=(1<<descriptor[6])-1)
    begin=source.index('#ifdef LISP65_C2_LITE_MEDIA_STAGER\n');end=source.index('#elif defined(LISP65_SHIP_MEDIA_STAGER)',begin)
    block=source[begin:end]
    for key in constants:
        block,n=re.subn(r'(?m)^#define '+key+r' [^\n]+$','#define '+key+' LISP65_DELIVERY_'+key,block);assert n==1
    source=source[:begin]+block+source[end:]
    current_crc=D.c_function(source,'crc32_step');old_crc=D.c_function(old,'crc32_step')
    assert source.replace(current_crc,old_crc)==old,'unexpected whole-stager source change'
    # Canonical product body must be exactly the priced four-plane algorithm.
    normalized=lambda s:re.sub(r'\s+','',re.sub(r'/\*.*?\*/','',s,flags=re.S))
    assert normalized(current_crc.split('{',1)[1].rsplit('}',1)[0])==normalized(body('planes'))
    (out/'stager-main.c').write_text(source)
    (out/'delivery-roles.h').write_text(''.join('#define LISP65_DELIVERY_'+k+' '+str(v)+'u\n' for k,v in constants.items()))
    (out/'boot.id').write_bytes(descriptor)
    # Actual C descriptor and file validators: same errors on both CRC forms.
    prefix='#include <stdint.h>\n#include <stdio.h>\n#include <string.h>\n'
    for k,v in dict(constants,R3_DESCRIPTOR_HEADER_BYTES=16,R3_DESCRIPTOR_RECORD_BYTES=32,R3_DESCRIPTOR_VERSION=2,
        R3_RESTAGE_LIMIT=2,R3_EXPECTED_PRODUCT_BUILD_ID=int.from_bytes(descriptor[8:12],'little'),R3_FLAG_STAGE=1).items():prefix+='#define '+k+' '+str(v)+'u\n'
    prefix+='static uint8_t descriptor[R3_DESCRIPTOR_BYTES];\nstatic const char *directory,*missing;\n'
    main=r'''
static uint8_t scan_file(const char *name,uint32_t dest,uint8_t stage,uint32_t len,uint32_t crc) {
 char path[4096];(void)dest;(void)stage;if(!strcmp(name,missing))return 0;
 snprintf(path,sizeof path,"%s/%s",directory,name);FILE *f=fopen(path,"rb");if(!f)return 0;
 uint32_t c=0xffffffffu,n=0;int b;while((b=fgetc(f))!=EOF){c=crc32_step(c,(uint8_t)b);n++;}fclose(f);
 return n==len && (c^0xffffffffu)==crc;
}
'''
    tail=r'''
int main(int argc,char **argv){
 if(argc!=4)return 3;FILE *f=fopen(argv[1],"rb");if(!f)return 3;
 size_t n=fread(descriptor,1,sizeof descriptor,f);int extra=fgetc(f);fclose(f);
 if(n!=sizeof descriptor||extra!=EOF||!validate_descriptor())return 2;
 directory=argv[2];missing=argv[3];
 for(uint8_t i=0;i<R3_DESCRIPTOR_RECORDS;i++){const uint8_t *r=record_at(i);if(!disk_record(r,!!(r[1]&1)))return 2;}return 0;
}
'''
    executables=[]
    for label,text in [('before',old),('candidate',source)]:
        code=prefix+'\n'.join(D.c_function(text,n) for n in ('rd32','crc32_step','record_at','record_name','validate_descriptor'))
        code+=main+D.c_function(text,'disk_record')+tail
        p=out/(label+'.c');p.write_text(code);exe=p.with_suffix('')
        subprocess.run(['cc','-std=c99','-O2','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',str(p),'-o',str(exe)],check=True)
        executables.append(exe)
    folder=out/'files';folder.mkdir()
    for i in range(descriptor[6]):
        r=descriptor[16+i*32:48+i*32];name=r[16:].split(b'\0')[0].decode();(folder/name).write_bytes(files[name.upper()]['data'])
    cases=[]
    def check(label,path,missing='',expected=2):
        codes=[subprocess.run([str(e),str(path),str(folder),missing]).returncode for e in executables]
        assert codes==[expected,expected],(label,codes);cases.append(dict(name=label,results=codes))
    check('original',out/'boot.id',expected=0)
    for f in sorted(folder.iterdir()):
        original=f.read_bytes();check('missing-'+f.name,out/'boot.id',missing=f.name)
        for label,data in [('truncated',original[:-1]),('extra',original+b'\0'),('wrong-crc',bytes([original[0]^1])+original[1:])]:
            f.write_bytes(data);check(label+'-'+f.name,out/'boot.id')
        f.write_bytes(original)
    for i in (0,4,5,6,7,8,12,16,28,335):
        b=bytearray(descriptor);b[i]^=1;p=out/('descriptor-%d.id'%i);p.write_bytes(b)
        # Byte 12 is the legacy profile hint, explicitly unused by verified
        # restage. Payload records retain their bound CRC/build identity.
        check('descriptor-byte-%d'%i,p,expected=0 if i==12 else 2)
    check('restored',out/'boot.id',expected=0)
    price=json.loads((ROOT/'build/stager-crc32-price-r2/price.json').read_text())
    chosen=next(r for r in price['rows'] if r['kind']=='planes')
    assert chosen['function_bytes']==36 and sum(v for k,v in chosen['sections'].items() if k.startswith('.rodata'))==1024
    result=dict(status='PASS: PREFLIGHT; STAGER BUILD UNCONSUMED',authority='29839748',
        source=bind(live),generated_source=bind(out/'stager-main.c'),header=bind(out/'delivery-roles.h'),
        predecessor_source=bind(base/'delivery-stager-main.c'),predecessor_medium=bind(base/'hardware-sp-seed.d81'),
        descriptor=bind(out/'boot.id'),descriptor_unchanged=True,source_delta='only crc32_step',
        price=bind(ROOT/'build/stager-crc32-price-r2/price.json'),host_cases=cases,
        projection=dict(function=36,table=1024,net_stager_bytes=976,runtime_text=0,runtime_rodata=0,bss=0),
        budget=dict(stager_builds=0,media_links=0,runtime_seeds=0))
    (out/'preflight.json').write_text(json.dumps(result,indent=2)+'\n');print(result['status'],len(cases),'host cases')

def build(out):
    import c2_lite_media_product as M
    import legacy_ide_delivery as D
    pre=json.loads((out/'preflight.json').read_text())
    assert pre['status'].startswith('PASS')
    for name in ('source','generated_source','header','predecessor_medium','descriptor','price'):
        r=pre[name];assert bind(ROOT/r['path'])['sha256']==r['sha256'],name
    # Projection: branch-free 36-byte function and four 256-byte tables.
    obj=ROOT/'build/stager-crc32-price-r2/planes.o'
    t=ElfTruth.read(obj,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',include_section_data=True)
    code=t.section_bytes('.text.crc32_step');width={0x86:2,0x45:2,0xa8:1,0xbe:3,0xa5:2,0x59:3,0x85:2,0xa6:2,0x60:1}
    at=0;ops=[]
    while at<len(code):op=code[at];assert op in width;ops.append(op);at+=width[op]
    assert at==36 and ops[-1]==0x60
    timing=ROOT/'build/boot-ledger-r1/observer/xemu/cpu65.c'
    maps=[list(map(int,m.split(','))) for m in re.findall(r'^#define TIMINGS_\w+\s+\{([^}]+)\}',timing.read_text(),re.M)]
    assert maps and all(len(m)==256 for m in maps)
    worst=sum(max(m[op] for m in maps) for op in ops)+4
    assert worst<=128
    before=json.loads((ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks/boot-ledger-set-a.json').read_text())
    oldcrc=before['pc_attribution']['disk_record']['crc32_step']
    base=ROOT/'build/definition-set-a-final-medium-r1/packed';oldtruth=ElfTruth.read(base/'autoboot.c65.elf',llvm_readobj=M.CANONICAL.COMPILER.parent/'llvm-readobj')
    assert oldtruth.symbol('__heap_start').value+1024+256 < oldtruth.symbol('__stack').value
    descriptor=(out/'boot.id').read_bytes()
    bytes_scanned=sum(int.from_bytes(descriptor[16+i*32+8:16+i*32+12],'little') for i in range(descriptor[6]))
    gain=(oldcrc-bytes_scanned*worst)/40500000;assert gain>=5
    projection=dict(status='PASS: SINGLE-OBJECT WORST-CASE PROJECTION; NOT MEASURED STAGER',
        object=bind(obj),timing_source=bind(timing),worst_function_cycles=worst,bytes_scanned=bytes_scanned,
        projected_gain_seconds_at_least=gain,stager_heap_before=oldtruth.symbol('__heap_start').value,
        stager_stack=oldtruth.symbol('__stack').value,table_bytes=1024,projected_body_delta=-48,
        runtime_text=0,runtime_rodata=0,runtime_bss=0)
    (out/'projection.json').write_text(json.dumps(projection,indent=2)+'\n')
    marker=out/'build-started.json';assert not marker.exists(),'stager budget consumed'
    marker.write_text(json.dumps(dict(authority='29839748',stager_builds=1,media_links_reserved=1,runtime_seeds=0))+'\n')
    old=json.loads((base.parent/'packed-receipt.json').read_text());rows=[]
    for r in old['descriptor']:r=dict(r);r['crc32']=int(r['crc32'],16);rows.append(r)
    M.STAGER_C=out/'stager-main.c'
    gate=M.compile_stager(int.from_bytes(descriptor[8:12],'little'),rows,build_dir=out,
        stager=out/'autoboot.c65',stager_map=out/'autoboot.c65.map',
        compile_defines=('-DLISP65_STARTUP_REQUIRE_EXPERIENCE','-Iscripts','-include',str(out/'delivery-roles.h')))
    (out/'stager-gates.json').write_text(json.dumps(gate,indent=2)+'\n')
    newtruth=ElfTruth.read(out/'autoboot.c65.elf',llvm_readobj=M.CANONICAL.COMPILER.parent/'llvm-readobj')
    assert newtruth.symbol('__heap_start').value < newtruth.symbol('__stack').value
    runtime=ROOT/old['elf']['path'];assert bind(runtime)['sha256']==old['elf']['sha256']
    raw=(base/'hardware-sp-seed.d81').read_bytes();files=D.inventory(raw)
    files['AUTOBOOT.C65']['data']=(out/'autoboot.c65').read_bytes()
    entries=[];folder=out/'packed-files';folder.mkdir()
    for name,row in files.items():p=folder/name.lower();p.write_bytes(row['data']);entries.append((p,name.lower()))
    assert not (out/'product.d81').exists()
    (out/'media-link-started.json').write_text('{"media_links":1,"runtime_links":0}\n')
    log=M.build_d81(out/'product.d81','l65sys,65',entries);(out/'pack.log').write_text(log)
    resultfiles=D.inventory((out/'product.d81').read_bytes())
    assert set(resultfiles)==set(files) and len(files)==19
    for name in files:assert resultfiles[name]['data']==files[name]['data'],name
    validate_package_locators(resultfiles)
    receipt=dict(status='STAGER BUILT AND MEDIUM PACKED; NATIVE BOOT QUALIFICATION PENDING',authority='29839748',
        medium=bind(out/'product.d81'),elf=old['elf'],stager_elf=bind(out/'autoboot.c65.elf'),
        stager=gate,predecessor_medium=pre['predecessor_medium'],preflight=bind(out/'preflight.json'),projection=bind(out/'projection.json'),
        descriptor_unchanged=True,runtime_unchanged=True,retained_files=18,
        stager_price=dict(old_bytes=(base/'autoboot.c65').stat().st_size,new_bytes=(out/'autoboot.c65').stat().st_size,
            old_heap=oldtruth.symbol('__heap_start').value,new_heap=newtruth.symbol('__heap_start').value),
        budget=dict(stager_builds=1,media_links=1,runtime_seeds=0,runtime_finales=0,runtime_links=0),device_contacts=0)
    (out/'packed-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(receipt['status'])
def price(out):
    out.mkdir(parents=True,exist_ok=False)
    cc=ROOT/'tools/llvm-mos/bin/mos-mega65-clang';readobj=cc.with_name('llvm-readobj')
    rows=[]
    for kind in ('bitwise','nibble','byte','planes'):
        source=out/(kind+'.c');source.write_text('#include <stdint.h>\nuint32_t crc32_step(uint32_t crc,uint8_t value) {\n'+body(kind)+'\n}\n')
        obj=source.with_suffix('.o');cmd=[str(cc),'-std=c99','-Oz','-fno-lto','-Wall','-Wextra','-Werror','-c',str(source),'-o',str(obj)]
        subprocess.run(cmd,check=True)
        asm=subprocess.check_output([str(cc.with_name('llvm-objdump')),'-dr',str(obj)],text=True)
        source.with_suffix('.disasm.txt').write_text(asm)
        t=ElfTruth.read(obj,llvm_readobj=readobj)
        sizes={s.name:s.bytes for s in t.sections if s.bytes and 'SHF_ALLOC' in s.flags}
        row=dict(kind=kind,source=bind(source),object=bind(obj),command=cmd,sections=sizes,
                 function_bytes=t.symbol('crc32_step').bytes)
        so=source.with_suffix('.so');subprocess.run(['cc','-std=c99','-O2','-shared','-fPIC',str(source),'-o',str(so)],check=True)
        fn=ctypes.CDLL(str(so)).crc32_step;fn.argtypes=[ctypes.c_uint32,ctypes.c_uint8];fn.restype=ctypes.c_uint32
        def ref(c,b):
            c^=b
            for _ in range(8):c=(c>>1)^(0xedb88320 if c&1 else 0)
            return c
        count=0
        for c in [0,0xffffffff]+[1<<i for i in range(32)]:
            for b in range(256):assert fn(c,b)==ref(c,b);count+=1
        # Every actual descriptor and delivered file, not just synthetic CRC vectors.
        import d81_persistence_fault as D
        packed=ROOT/'build/definition-set-a-final-medium-r1/packed/hardware-sp-seed.d81'
        population=D.visible_files(packed.read_bytes());crcs={}
        for name,data in population.items():
            c=0xffffffff
            for b in data:c=fn(c,b)
            assert c^0xffffffff==zlib.crc32(data)
            crcs[name.decode()]=dict(bytes=len(data),crc32='%08x'%(c^0xffffffff))
        row.update(transitions_checked=count,files=crcs,host_binary=bind(so));rows.append(row)
    # A corrupt lookup entry must not inherit a PASS from the reference vectors.
    mutant=body('byte').replace('0x00000000UL','0x00000001UL',1)
    p=out/'mutant.c';p.write_text('#include <stdint.h>\nuint32_t crc32_step(uint32_t crc,uint8_t value){'+mutant+'}\n')
    so=p.with_suffix('.so');subprocess.run(['cc','-shared','-fPIC',str(p),'-o',str(so)],check=True)
    f=ctypes.CDLL(str(so)).crc32_step;f.restype=ctypes.c_uint32
    assert f(0,0)!=0
    result=dict(status='HOST CRC PARITY AND SINGLE-OBJECT PRICES; NO STAGER BUILD',authority='29839748',
      compiler=bind(cc),rows=rows,falling_controls=['corrupt table entry'],runtime_builds=0,stager_builds=0,media_links=0)
    (out/'price.json').write_text(json.dumps(result,indent=2)+'\n')
    for r in rows:print(r['kind'],r['function_bytes'],r['sections'])
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['price','preflight','build']);p.add_argument('out',type=Path)
    a=p.parse_args();globals()[a.action](a.out.resolve())
