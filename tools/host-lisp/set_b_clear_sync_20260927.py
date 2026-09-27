"""One isolated synchronous publication / full CLEAR repair; bounded host qualification."""
import argparse
import ctypes as C
import difflib
import gzip
import hashlib
from pathlib import Path
import shutil
import subprocess
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import set_b_clear_gc_gate_20260926 as PREVIOUS
from set_b_fourth_halt_seal_20260926 import local_import_closure
from set_b_load_preflight_seal_20260926 import external_binding
ROOT=P.ROOT
HEAD='2a36aabe'
OUT=ROOT/'build/set-b-clear-sync-r1'
CANDIDATE=OUT/'candidate'
ARCH=ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks'
STEM='set-b-clear-sync-20260927'
SEAL=ARCH/(STEM+'.json')
REPORT=ROOT/'docs/planning/set-b-clear-sync-report.md'
SOURCES=PREVIOUS.SOURCES
AUTHORITIES=PREVIOUS.AUTHORITIES+[PREVIOUS.REPORT]

UNDO=r'''
/* The undo becomes a CPU-visible root before replacing its function cell.
 * Uses the same synchronous primitive as terminal backup scrubbing. */
static C2_KERNAL_RESIDENT uint8_t c2_export_undo_store(
        uint16_t at, const void *bytes, uint16_t length) {
    if (at < C2_EXPORT_JOURNAL_BASE || length != 4u
        || (uint32_t)at + length > C2_EXPORT_PLAN_LIMIT) return 0u;
    return c2_map_cpu_write(0x50000UL + at, bytes, length);
}
'''
SETTER=r'''void symfn_ext_set(uint16_t index, obj value) {
    uint16_t word = (uint16_t)value;
#ifdef LISP65_SET_B
    /* Finish canonical function-cell publication before another allocation.
     * There must be no older asynchronous store behind the synchronous one. */
    if (!c2_map_cpu_write(((uint32_t)SYMFN_EXT_BANK << 16)
            + SYMFN_EXT_OFF + (uint32_t)index * 2u,
            (const uint8_t *)&word, 2u))
        lisp_abort_static(LISP65_ERR_RUNTIME_OVERLAY_TIMEOUT,
                          "CPU content write failed");
#else
    c2_facade_c2_dma((uint16_t)(uintptr_t)&word, 0u,
                     (uint16_t)(SYMFN_EXT_OFF + index * 2u),
                     SYMFN_EXT_BANK, 2u);
#endif
}
'''


def prepare():
    PREVIOUS.check();authority=S.require_auth()
    assert subprocess.check_output(['git','rev-parse','--short=8','HEAD'],cwd=ROOT,text=True).strip()==HEAD
    OUT.mkdir(exist_ok=False);shutil.copytree(PREVIOUS.CANDIDATE,CANDIDATE)
    for name in ('src/c2_platform_dma.c','src/c2_platform_dma.h','src/optional/c2_map_cpu_read.s'):
        to=CANDIDATE/name;to.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,to)
    runtime=CANDIDATE/'src/c2_product_runtime.c';before=runtime.read_text()
    pub=PREVIOUS.extract(before,'uint8_t c2_append_publish_exports_phase(')
    assert pub.count('c2_stream_c2d_write(')==1
    after=before.replace(pub,pub.replace('c2_stream_c2d_write(','c2_export_undo_store(',1))
    at=after.index('#ifdef LISP65_C2_LITE_V6_CORESIDENT_DIET',after.index('uint8_t c2_append_publish_plan_resolve_phase'))
    runtime.write_text(after[:at]+UNDO+'\n'+after[at:])
    dma=CANDIDATE/'src/c2_platform_dma.c';before_dma=dma.read_text()
    old=PREVIOUS.extract(before_dma,'void symfn_ext_set(');dma.write_text(before_dma.replace(old,SETTER))
    header=CANDIDATE/'src/c2_platform_dma.h';text=header.read_text()
    header.write_text(text.replace('#include <stdint.h>', '#include <stdint.h>\n\n#ifdef LISP65_SET_B\nuint8_t c2_map_cpu_write(uint32_t destination, const uint8_t *source, uint16_t length);\n#endif',1))
    # Same MAP tuple, 8-KiB crossing and restoration as the existing CPU reader.
    # Private leaf uses its existing ABI with source/destination roles reversed.
    asm=(ROOT/'src/optional/c2_map_cpu_read.s').read_text()
    asm=asm[:asm.index('; Preserve the historical runtime-overlay vector')]
    asm=asm.replace('c2_map_cpu_read','c2_map_cpu_write').replace('.Lc2_cpu_', '.Lc2_store_')
    asm=asm.replace('__lisp65_c2_map_cpu_hot_', '__lisp65_c2_map_cpu_store_hot_')
    a=asm.index('\t; The ordinary product owns');b=asm.index('\tlda __rc7',a);asm=asm[:a]+asm[b:]
    a=asm.index('\t; Unexecuted placement prefix');b=asm.index('c2_map_cpu_write:',a);asm=asm[:a]+asm[b:]
    asm=asm.replace('\t.globl __lisp65_c2_fixed_bank0_runtime\n','')
    asm=asm.replace('\tlda (__rc12),y\n\tsta (__rc4),y','\tlda (__rc4),y\n\tsta (__rc12),y')
    a=asm.index('\t.section');asm='; Synchronous physical writer, derived from the bound CPU reader.\n; ABI: destination=A/X/rc2/rc3, CPU source=rc4/rc5, length=rc6/rc7.\n; Length <=255; source and this code must remain outside CPU $4000-$5fff.\n; No DMA submission. IRQ flags, MAPL and low-MB restored as by CPU reader.\n; All accepted callers must prove source span disjoint from mapped block.\n'+asm[a:]
    (CANDIDATE/'src/optional/c2_map_cpu_write.s').write_text(asm)
    patches=[]
    for path,original in ((runtime,before),(dma,before_dma),(header,text)):
        rel=path.relative_to(CANDIDATE)
        patches.append(''.join(difflib.unified_diff(original.splitlines(True),path.read_text().splitlines(True),fromfile='a/'+str(rel),tofile='b/'+str(rel))))
    patches.append(''.join(difflib.unified_diff([],asm.splitlines(True),fromfile='/dev/null',tofile='b/src/optional/c2_map_cpu_write.s')))
    (OUT/'authored.patch').write_text(''.join(patches))
    old=P.load(PREVIOUS.OUT/'receipt.json')
    P.write(OUT/'binding.json',dict(execution_head=HEAD,source_authority=authority,driver=P.bind(Path(__file__)),predecessor=P.bind(PREVIOUS.SEAL),
        compiler_authority=old['compiler_authority'],compiler_inputs=old['compiler_inputs'],before=old['candidate'],candidate=[P.bind(p) for p in sorted(CANDIDATE.rglob('*')) if p.is_file()],
        budget=dict(source_forms=1,host_compile_attempts=2,host_dependencies=1,native_objects=16,native_dependencies=8,assembler=2,product_builds=0,product_links=0,seeds=0,finals=0,guest=0,device=0),
        scope='One isolated repair, first synchronous publication root gate; terminal-controller portion follows only after this prerequisite. No maintained product source change or linked placement admitted.'))
    print('PREPARED isolated synchronous undo/function writes and MAP-store leaf; no compile')


def close():
    import set_b_clear_sync_roots_20260927 as R
    import set_b_clear_sync_native_20260927 as N
    root=OUT/'roots';command=P.load(root/'command.json')['command'][:]
    at=command.index('-o');del command[at:at+2];command+=['-M','-MT','fixture']
    assert not (root/'dependencies.json').exists()
    P.write(root/'dependencies.json',dict(command=command,status='host dependency1 charged before execution'))
    r=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
    (root/'dependencies.log').write_text(r.stdout+r.stderr);assert r.returncode==0,r.stderr
    internal,external=[],[]
    for name in r.stdout.replace('\\\n',' ').split(':',1)[1].split():
        path=(ROOT/name).resolve()
        (internal if path.is_relative_to(ROOT) else external).append(P.bind(path) if path.is_relative_to(ROOT) else external_binding(path))
    P.write(root/'dependencies.json',dict(command=command,exit=r.returncode,internal=internal,external=external,log=P.bind(root/'dependencies.log')))
    native=P.load(OUT/'native/receipt.json');assert native['status']=='HALT at prerequisite capacity'
    host=P.load(root/'result.json');assert host['candidate_rows']==240 and host['falling_controls']==3
    old=P.load(PREVIOUS.OUT/'receipt.json');binding=P.load(OUT/'binding.json')
    for row in old['compiler_inputs']+old['candidate']:assert P.bind(ROOT/row['path'])==row
    for row in binding['candidate']:assert P.bind(ROOT/row['path'])==row
    P.write(OUT/'receipt.json',dict(status='HALT: host-qualified synchronous publication exceeds ordinary/E000 floors',execution_head=HEAD,
        source_authority=S.require_auth(),driver=P.bind(Path(__file__)),predecessor=P.bind(PREVIOUS.SEAL),
        compiler_authority=old['compiler_authority'],compiler_inputs=old['compiler_inputs'],before=old['candidate'],candidate=binding['candidate'],verified_compiler_roots=74,
        root_tool=P.bind(Path(R.__file__)),native_tool=P.bind(Path(N.__file__)),host=P.bind(root/'result.json'),native=P.bind(OUT/'native/receipt.json'),
        artifacts=[P.bind(p) for p in sorted(OUT.rglob('*')) if p.is_file() and p!=OUT/'receipt.json'],
        toolchain=[external_binding((ROOT/'tools/llvm-mos/bin'/n).resolve()) for n in ('mos-mega65-clang','llvm-readobj','llvm-objdump')],
        this_commission=dict(host_compile_attempts=1,host_links=1,host_dependencies=1,native_object_calls=4,native_dependencies=4,assembler_calls=1,
            candidate_host_rows=240,falling_controls=3,root_observations=648,new_source_forms=1,terminal_controller_authored=0,
            product_builds=0,product_links=0,seeds=0,finals=0,guest_runs=0,device_contacts=0),
        remaining=dict(host_compile_attempts=1,host_dependencies=0,native_object_calls=12,native_dependencies=4,assembler_calls=1),
        consumed=old['consumed'],authorized_ceiling=old['authorized_ceiling'],product_admitted=False,
        next_recommendation='Placement and shared read/write MAP transport plan before another source form. Avoid duplicating169 ordinary bytes; name exact owners for193 ordinary and57 E000 delta, preserving floors and full CLEAR gates. Do not count unmeasured controller savings or enlarge region0.',
        limit='Synchronous publication prerequisite is tested and object-priced. Full terminal controller, integrated CLEAR, native execution and final linked placement remain unqualified; no product admission.'))
    print('CLOSED capacity halt: ordinary+193/margin-185;E000+57/margin-32;host240/3 pass; no terminal-controller extension')


def seal():
    PREVIOUS.check();S.require_auth()
    assert not SEAL.exists() and not (ARCH/STEM).exists()
    receipt=P.load(OUT/'receipt.json')
    selected={p for p in OUT.rglob('*') if p.is_file()}
    selected.update(SOURCES+AUTHORITIES+[REPORT,PREVIOUS.SEAL,PREVIOUS.REPORT])
    selected.update(local_import_closure([Path(__file__)]))
    external=[external_binding(Path(shutil.which(n)).resolve()) for n in ('python3','rg','git')]
    def bindings(value):
        if isinstance(value,dict):
            if {'path','bytes','sha256'}<=value.keys():
                row={k:value[k] for k in ('path','bytes','sha256')};path=ROOT/row['path']
                if Path(row['path']).is_absolute():assert external_binding(path)==row;external.append(row)
                else:assert P.bind(path)==row,row['path'];selected.add(path)
            else:
                for item in value.values():bindings(item)
        elif isinstance(value,list):
            for item in value:bindings(item)
    for path in OUT.rglob('*.json'):bindings(P.load(path))
    scope=ARCH/STEM/'design-scope.txt';scope.parent.mkdir(parents=True)
    scope.write_text('Owner: Dann bitte gemäß deiner Empfehlung fortfahren. Continue2a36aabe: one coherent synchronous publication/full CLEAR repair, renewed host2/dependency1, native16/dependencies8/assembler2 only after host success;0 product build/link/Seed/Final/emulator/device. Host prerequisite is qualified before native prerequisite pricing; first capacity failure stops controller extension. Full rollback and all floors unchanged.\n\n'+
        subprocess.check_output(['git','show',HEAD+':docs/planning/set-b-clear-gc-gate-report.md'],cwd=ROOT,text=True))
    inputs,copies=[],[]
    for path in sorted(selected):
        row=P.bind(path);inputs.append(row)
        if not path.is_relative_to(ROOT/'build'):continue
        raw=path.read_bytes();compressed=len(raw)>131072 or (path.is_relative_to(OUT) and path.suffix in ('.txt', '.patch', '.c', '.h', '.s'));dest=ARCH/STEM/path.relative_to(ROOT)
        if compressed:dest=dest.with_name(dest.name+'.gz')
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes(gzip.compress(raw,compresslevel=9,mtime=0) if compressed else raw)
        copies.append(dict(source=row,copy=P.bind(dest),encoding='gzip' if compressed else 'identity'))
    P.write(SEAL,dict(status=receipt['status'],execution_head=HEAD,source_authority=receipt['source_authority'],
        owner_scope=P.bind(scope),report=P.bind(REPORT),closure=P.bind(OUT/'receipt.json'),predecessor=P.bind(PREVIOUS.SEAL),
        inputs=inputs,receipt_copies=copies,external_tools=external,this_commission=receipt['this_commission'],
        consumed=receipt['consumed'],authorized_ceiling=receipt['authorized_ceiling'],accepted_world='Card L Final',public_release='2.4.0',product_admitted=False))
    print('SEALED',len(inputs),'inputs;',len(copies),'lossless copies')


def check():
    value=P.load(SEAL)
    for row in value['inputs']+[value['owner_scope']]:assert P.bind(ROOT/row['path'])==row,row['path']
    for row in value['external_tools']:assert external_binding(Path(row['path']))==row
    for row in value['receipt_copies']:
        path=ROOT/row['copy']['path'];assert P.bind(path)==row['copy'];raw=path.read_bytes()
        if row['encoding']=='gzip':raw=gzip.decompress(raw)
        assert len(raw)==row['source']['bytes'] and hashlib.sha256(raw).hexdigest()==row['source']['sha256']
    PREVIOUS.check();S.require_auth();print('PASS synchronous publication seal:74 roots, isolated form,240 root rows,3 controls,matched native price and lossless copies')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=('prepare','close','seal','check'))
    {'prepare':prepare,'close':close,'seal':seal,'check':check}[parser.parse_args().mode]()
