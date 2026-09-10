"""Build and execute the materialized product C on the host; not a product build."""
import binascii,hashlib,json,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'build/capacity/card2a-r1'
OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(ROOT/'tools/host-lisp'))
import c2_lite_v6_product_probe as P
base=ROOT/'build/v2.1/renderer-branch-product-r1/wplto'
meta=json.loads((base/'runtime-overlays-session-final.json').read_text())
image=base/meta['storage']['file'];extra=base/meta['overflow_storage']['file']
assert hashlib.sha256(image.read_bytes()).hexdigest()==meta['storage']['sha256']
count=meta['catalog']['slice_count']-2
assert [s['id'] for s in meta['slices']]==list(range(count+2)) and count>0
if len(sys.argv)==2:
    source=ROOT/sys.argv[1]
else:
    mapping=P.generated_product_sources(Path(tempfile.mkdtemp(prefix='integration-',dir=OUT)))
    source=mapping[ROOT/'src/vm_runtime_overlay.c']
defines=['LISP65_VM','LISP65_RUNTIME_OVERLAY_HOST_TEST','LISP65_RUNTIME_OVERLAY_LIFETIME_FAMILIES',
 'LISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH','LISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH_ISLAND',
 'LISP65_C2_LITE_BANK3_STAGING','LISP65_C2_LITE_CHIP_RAM','LISP65_RUNTIME_OVERLAY_FORMAT_V4',
 'LISP65_RTOV_SESSION_RECORD_CACHE']
header=''.join('#define '+d+' 1\n' for d in defines)
header+=f'#define LISP65_RTOV_SESSION_RECORD_COUNT {count}\n'
header+=f'#define TEST_IMAGE_SIZE {len(image.read_bytes())}\n#define TEST_IMAGE_CRC {binascii.crc_hqx(image.read_bytes(),65535)}\n'
header+=f'#define TEST_OVERFLOW_SIZE {len(extra.read_bytes())}\n'
header+='#include "'+str(base/'runtime-overlay-session-final.h')+'"\n'
header+='\n#include <stdint.h>\nuint16_t c2_kernal_frame_count_inline(void);\n'
(OUT/'integration-config.h').write_text(header)
cmd=['cc','-std=c11','-g','-O1','-fsanitize=address,undefined','-fno-pie','-no-pie',
 '-ffunction-sections','-fdata-sections','-Wl,--gc-sections','-I'+str(source.parent),'-I'+str(OUT),'-Isrc','-Iscripts',
 str(ROOT/'scripts/capacity-window-loader-test.c'),'-o',str(OUT/'integration-test')]
subprocess.run(cmd,cwd=ROOT,check=True)
subprocess.run([str(OUT/'integration-test'),str(image),str(extra)],check=True)
mutations={
 'record-comparison-removed':('if (rtov_crc_mem(record, LISP65_RUNTIME_OVERLAY_ENTRY_SIZE) !=\n            rtov_session_cache.record_crc[index])','if (0)'),
 'generation-comparison-removed':('rtov_session_cache.generation != rtov_family_generation ||','0 ||'),
 'size-comparison-removed':('rtov_session_cache.image_size != rtov_family_stage_bindings[1].image_size ||','0 ||'),
 'identity-comparison-removed':('rtov_session_cache.image_crc != rtov_family_stage_bindings[1].crc16)','0)'),
 'partial-authentication-published':('rtov_session_cache.count != LISP65_RTOV_SESSION_RECORD_COUNT) {','rtov_session_cache.count != 1u) {'),
 'append-invalidation-removed':('    RTOV_SESSION_INVALIDATE();\n#ifdef LISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH_ISLAND\n    rtov_transaction_payload_off = 0;','    /* dropped invalidation */\n#ifdef LISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH_ISLAND\n    rtov_transaction_payload_off = 0;'),
 'lifetime-invalidation-removed':('#define RTOV_SESSION_INVALIDATE() (rtov_session_cache.ready = 0u)','#define RTOV_SESSION_INVALIDATE() ((void)0)'),
}
rejected=[]
for name,(old,new) in mutations.items():
    original=source.read_text(); assert original.count(old)==1,(name,original.count(old))
    directory=Path(tempfile.mkdtemp(prefix='mutant-'+name+'-',dir=OUT))
    mutant=directory/source.name;mutant.write_text(original.replace(old,new))
    mc=[('-I'+str(directory)) if p=='-I'+str(source.parent) else p for p in cmd]
    mc[-1]=str(directory/'test')
    subprocess.run(mc,cwd=ROOT,check=True,capture_output=True)
    run=subprocess.run([mc[-1],str(image),str(extra)],capture_output=True)
    assert run.returncode!=0,name+' survived'
    (directory/'stderr.txt').write_bytes(run.stderr)
    rejected.append(dict(name=name,returncode=run.returncode))
def bind(p):return dict(path=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
(OUT/'integration-test.json').write_text(json.dumps(dict(status='HOST_MATERIALIZED_C_PASS',
 source=bind(source),authored=bind(ROOT/'src/vm_runtime_overlay.c'),harness=bind(ROOT/'scripts/capacity-window-loader-test.c'),
 image=bind(image),population=count,command=cmd,mutations=rejected,limits=['Host substitutes DMA and dispatch; no target layout, timing or assembly proof.',
 'Stage identity supplied by the harness; stage writer closure is a separate obligation.'],budget=[0,0,0]),indent=2)+'\n')
