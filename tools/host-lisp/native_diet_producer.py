"""Native diet/placement card: command admission, then one Seed.

Derived like the Set-A producer from the accepted producer template. The
predecessor world is the accepted Set-A product (ELF 526e88b0...), whose
generated sources are copied unchanged; only the commissioned hunks since the
Set-A closure are applied: the CRC helper byte domain (vm.c), the byte-wide
resolver owner table (c2_product_runtime.c) and the phase-local CRC32 nibble
form (the generated copy of scripts/c2-stream-decoder.c). The KERNAL window
CRC (c2_kernal_runtime.c, a profile input read from src/) is an argumentless
c2k_crc16 reaching the proven rtov_crc_mem leaf by a direct JSR; its caller,
the linker-patched compare site, is unchanged.

Fourth Seed (owner word, budget 4/1/1). Seed 1 (r1) failed the assembler-leaf
ABI gate (tail JMP to rtov_crc_mem); Seed 2 (r2) failed the KERNAL window
binding (compare moved out of take_ownership); Seed 3 (r3) was red in
check-source (byte owner table cannot hold the 65536 bank-end control).
All stay as evidence. This run writes the r4 directories.
The Lisp plane is the accepted Set-A plane, copied byte for byte.
Merely running the command probe never consumes the Seed budget.
"""
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT/'build/index-crc-r1/product-card.py'
HERE = ROOT/'build/native-diet-r4'
PREDECESSOR_PREFLIGHT = ROOT/'build/definition-set-a-product-r3-preflight'
OUT_PREFLIGHT = ROOT/'build/native-diet-product-r4-preflight'
AUTH = '4e3bdafe'
DIFF_BASE = '81d321d2'
SOURCES = ('src/vm.c', 'src/c2_product_runtime.c', 'src/c2_kernal_runtime.c')
DECODER = 'scripts/c2-stream-decoder.c'
SUCCESSOR_CLOSURE = 'config/native-diet-native/include-closure.json'
SUCCESSOR_CLOSURE_SHA = '91c824b84ade60e1d431d37306da6eb326704385c874561410bec3db1bc23bd8'
PREDECESSOR_DECODER = 'config/c2-v230-public-native/includes/c2-stream-decoder.c'
SUCCESSOR_DECODER = 'config/native-diet-native/includes/c2-stream-decoder.c'
PROBES = ('build/native-diet-object-probe-r2/receipt.json',
          'build/native-diet-bounds-probe-r3/receipt.json',
          'build/native-diet-boot-crc-probe-r3/receipt.json',
          'build/native-diet-crc32-differential-r1/receipt.json',
          'build/native-diet-shared-crc16-probe-r2/receipt.json',
          'build/native-diet-shared-crc16-probe-r2/accepted-leaf-gate.json')


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('producer template population drift: '+old)
    return text.replace(old, new, 1)


def bind(path):
    import hashlib
    data = path.read_bytes()
    return dict(path=str(path.relative_to(ROOT)), bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest())


def composition():
    """The admitted member population and its off-product evidence."""
    return dict(
        status='PASS: NATIVE DIET SOURCE COMPOSITION, NOT NATIVE ACCEPTANCE',
        authority=AUTH, diff_base=DIFF_BASE,
        members=[
            dict(name='crc32-nibble-phase-local', source=DECODER, projected_text=375),
            dict(name='kernal-window-crc-jsr-leaf', source='src/c2_kernal_runtime.c',
                 projected_text=93),
            dict(name='resolver-bytewise-header-check', source='src/c2_product_runtime.c',
                 projected_text=66),
            dict(name='crc-helper-byte-domain', source='src/vm.c', projected_text=56)],
        projected_text_total=590,
        seed_3=dict(path='build/native-diet-product-r3', text_delta=-622,
            halt='check-source resolver-owner-check: byte table cannot hold 65536'),
        seed_2=dict(path='build/native-diet-product-r2', text_delta=-609,
            halt='KERNAL CRC binding callee c2k_crc16 is absent'),
        seed_1=dict(path='build/native-diet-product-r1', text_delta=-698,
            halt='rtov_crc_mem edge is not JSR (assembler-leaf ABI gate)'),
        claim='paired non-LTO object projections; the Seed link decides',
        split_out='boot-time intern index: own card (owner word 2026-09-19)',
        evidence=[bind(ROOT/p) for p in PROBES])


def successor_decoder_ok():
    """The successor decoder is exactly the 2.3.0 bytes plus the commissioned hunks."""
    import re
    text = (ROOT/PREDECESSOR_DECODER).read_text()
    diff = subprocess.check_output(['git', 'diff', DIFF_BASE, '--', DECODER],
                                   cwd=ROOT, text=True)
    parts = re.split(r'(^@@[^\n]*\n)', diff, flags=re.M)
    for i in range(2, len(parts), 2):
        lines = parts[i].splitlines(keepends=True)
        before = ''.join(l[1:] for l in lines if l[:1] in (' ', '-'))
        after = ''.join(l[1:] for l in lines if l[:1] in (' ', '+'))
        if text.count(before) != 1:
            raise ValueError('decoder hunk does not project onto the 2.3.0 authority')
        text = text.replace(before, after, 1)
    if (ROOT/SUCCESSOR_DECODER).read_text() != text:
        raise ValueError('successor decoder is not the commissioned projection')
    if bind(ROOT/SUCCESSOR_CLOSURE)['sha256'] != SUCCESSOR_CLOSURE_SHA:
        raise ValueError('successor include authority drift')


def main():
    if sys.argv[1:] not in (['command-probe'], ['seed']):
        raise SystemExit('command-probe | seed')
    if AUTH == 'AUTH_PENDING':
        raise SystemExit('bind AUTH to the commissioned source commit first')
    successor_decoder_ok()
    raw = TEMPLATE.read_text()
    # Rebind the include authority to the card's successor; 2.3.0 stays as is.
    raw = replace_once(raw, "INC=prior['INC']",
        "INC=prior['INC'];INC.CLOSURE=ROOT/"+repr(SUCCESSOR_CLOSURE)
        +";INC.CLOSURE_SHA="+repr(SUCCESSOR_CLOSURE_SHA))
    changed_names = '{'+','.join(repr(Path(p).name) for p in SOURCES)+'}'
    for old, new in {
        'HERE=Path(__file__).resolve().parent':
            "HERE=ROOT/'build/native-diet-r4';HERE.mkdir(parents=True,exist_ok=True)",
        "BASE=ROOT/'build/storage-owner-product-r2'":
            "BASE=ROOT/'build/definition-set-a-product-r2'",
        "BASE_PREFLIGHT=ROOT/'build/storage-owner-product-r2-preflight'":
            "BASE_PREFLIGHT=ROOT/'build/definition-set-a-product-r3-preflight'",
        "OUT=ROOT/'build/index-crc-product-r1-preflight'":
            "OUT=ROOT/'build/native-diet-product-r4-preflight'",
        "BUILD=ROOT/'build/index-crc-product-r1'":
            "BUILD=ROOT/'build/native-diet-product-r4'",
        "AUTH='4cf5a2f9'": f"AUTH='{AUTH}'",
        "CHANGED=('src/vm.c',)": 'CHANGED='+repr(SOURCES),
        "name='index-crc-and-final-sector-length'": "name='native-diet-placement'",
        "allowed=set(proof['changed_members'])|{'vm.c'}":
            "allowed=set(proof['changed_members'])|"+changed_names,
    }.items():
        raw = replace_once(raw, old, new)
    start = raw.index('def source_gate():')
    end = raw.index('\ndef prepare_inputs()', start)
    raw = raw[:start]+f'''def source_gate():
    expected={set(SOURCES)!r}
    changed=set(subprocess.check_output(['git','diff','{DIFF_BASE}','--name-only',
        '--','src','lib'],cwd=ROOT,text=True).splitlines())
    if changed!=expected: raise ValueError('uncommissioned source population: '+repr(changed))
    if not subprocess.check_output(['git','diff','{DIFF_BASE}','--','{DECODER}'],cwd=ROOT,text=True):
        raise ValueError('commissioned decoder member absent')
    comp=R.C.load(HERE/'composition.json')
    if comp['authority']!=AUTH or comp['diff_base']!='{DIFF_BASE}':
        raise ValueError('composition authority drift')
    for row in comp['evidence']:
        if R.bind(ROOT/row['path'])!=row: raise ValueError('probe evidence drift: '+row['path'])
    gate=R.C.load(ROOT/'build/native-diet-shared-crc16-probe-r2/accepted-leaf-gate.json')
    if gate['status']!='passed-linked-assembler-leaf-crc-equivalence':
        raise ValueError('CRC16 leaf not proven on the predecessor ELF')
    return dict(status='PASS: NATIVE DIET SOURCE COMPOSITION, NOT NATIVE ACCEPTANCE',
        sources=[R.bind(ROOT/p) for p in sorted(changed)]+[R.bind(ROOT/'{DECODER}')],
        composition=R.bind(HERE/'composition.json'),
        plane=R.bind(PLANE/'set-a-plane-receipt.json'),
        producer_template=R.bind(ROOT/'build/index-crc-r1/product-card.py'))
'''+raw[end:]
    start = raw.index('    # Apply only the commissioned diff')
    end = raw.index('    derived,proof=', start)
    raw = raw[:start]+f'''    # Preserve every consumed producer adaptation of the accepted Set-A world;
    # apply only the commissioned hunks, with exact context, since {DIFF_BASE}.
    import re
    for name,source in (('vm.c','src/vm.c'),('c2_product_runtime.c','src/c2_product_runtime.c'),
                        ('c2-stream-decoder.c','{DECODER}')):
        target=generated/name;text=target.read_text()
        diff=subprocess.check_output(['git','diff','{DIFF_BASE}','--',source],cwd=ROOT,text=True)
        (out/(name+'.native-diet.patch')).write_text(diff)
        parts=re.split(r'(^@@[^\\n]*\\n)',diff,flags=re.M)
        if len(parts)<3: raise ValueError('commissioned hunk absent: '+source)
        for i in range(2,len(parts),2):
            lines=parts[i].splitlines(keepends=True)
            before=''.join(l[1:] for l in lines if l[:1] in (' ','-'))
            after=''.join(l[1:] for l in lines if l[:1] in (' ','+'))
            if text.count(before)!=1: raise ValueError('source projection hunk mismatch: '+name)
            text=text.replace(before,after,1)
        target.write_text(text)
        if source.startswith('src/'): mapping[(ROOT/source).resolve()]=target
'''+raw[end:]
    # Native-only card: the Lisp plane is the accepted Set-A plane, byte for
    # byte. Only the paired derivation's stale-table control needs a changed
    # plane; here identity of the whole plane tree is the proof that the copied
    # generated data is already the successor's data. Everything else that
    # derive() executes is reproduced below: the delivery CRC tables and the
    # twelve executable delivery-word mutations, so this card's
    # world-data-consumers receipt carries the same consumer contract as the
    # Set-A receipt (tables + mutations_rejected), minus that one control.
    raw = replace_once(raw,
        "    derived,proof=R.W.DATA.derive(BASE_PREFLIGHT/'setup-owned/static-plane/narrow-static',PLANE,\n"
        "        BASE/'wplto/generated-product-sources',out/'world-data-derivation',R.bind)",
        "    derived,proof=identical_plane(generated,out/'world-data-derivation')")
    raw = replace_once(raw, 'def materialize(out):', """def identical_plane(generated,work):
    base=BASE_PREFLIGHT/'setup-owned/static-plane/narrow-static'
    rows=[]
    left=sorted(p.relative_to(base) for p in base.rglob('*') if p.is_file())
    right=sorted(p.relative_to(PLANE) for p in PLANE.rglob('*') if p.is_file())
    if left!=right: raise ValueError('plane file population differs from Set-A plane')
    for rel in left:
        if (base/rel).read_bytes()!=(PLANE/rel).read_bytes():
            raise ValueError('plane byte drift: '+str(rel))
        rows.append(R.bind(PLANE/rel))
    # Mandatory consumer contract, independent of any derived exception set:
    # every .short delivery word in the Phase-02a owner must be load bearing.
    # Flipping one bit of any of them has to make crc_tables() fall.
    import re
    work.mkdir(parents=True,exist_ok=True)
    owner=generated/'c2-stream-phase-02a.c'
    tables=R.W.DATA.crc_tables(owner,PLANE)
    pattern=r'(?<=\\.short )0x[0-9a-f]{4}'
    words=list(re.finditer(pattern,owner.read_text()))
    if len(words)!=sum(map(len,tables.values())):
        raise ValueError('delivery word population differs from the CRC tables')
    mutations=[];mutant=work/'mutant-owner.c'
    for index,word in enumerate(words):
        text=owner.read_text()
        mutant.write_text(text[:word.start()]+f'0x{int(word[0],16)^1:04x}'+text[word.end():])
        try:R.W.DATA.crc_tables(mutant,PLANE)
        except AssertionError:mutations.append(f'wrong-delivery-word-{index}')
        else:raise AssertionError('wrong CRC word survived')
    return {},dict(status='PASS: PLANE BYTE-IDENTICAL TO SET-A; NO DATA DERIVATION',
        changed_members=[],files=len(rows),population=rows,
        tables=tables,mutations_rejected=mutations,
        generator=R.bind(Path(R.W.DATA.V6.__file__)),
        inputs=[R.bind(PLANE/p) for p in
                ('product/substitution-artifacts.json','product/product-shelf-v4-direct.bin',
                 'v6-semantics/initial.c2d-v6.bin')])

def materialize(out):""")
    # Profile inputs read directly from src/ are commissioned members here:
    # their predecessor digest is the source at the diff base, not the tree.
    raw = replace_once(raw,
        "        if R.bind(before)['sha256']!=digest: raise ValueError('predecessor input drift')",
        "        prior=(subprocess.check_output(['git','show','"+DIFF_BASE+":'+name],cwd=ROOT)\n"
        "               if name in "+repr(SOURCES)+" else before.read_bytes())\n"
        "        if hashlib.sha256(prior).hexdigest()!=digest: raise ValueError('predecessor input drift')")
    raw = replace_once(raw, "        if name=='vm.c': raise ValueError('data derivation selected native code')",
        "        if name in ('vm.c','c2_product_runtime.c','c2-stream-decoder.c'):\n"
        "            raise ValueError('data derivation selected native code')")
    HERE.mkdir(parents=True, exist_ok=True)
    comp = HERE/'composition.json'
    text = json.dumps(composition(), indent=2, sort_keys=True)+'\n'
    if comp.exists() and comp.read_text() != text:
        raise ValueError('composition overwrite: '+str(comp))
    if not comp.exists():
        comp.write_text(text)
    plane_source = (PREDECESSOR_PREFLIGHT/'setup-owned/static-plane/narrow-static/'
                    'set-a-plane-receipt.json')
    plane = HERE/'plane.json'
    if plane.exists() and plane.read_bytes() != plane_source.read_bytes():
        raise ValueError('plane input overwrite: '+str(plane))
    if not plane.exists():
        plane.write_bytes(plane_source.read_bytes())
    # The Lisp plane is unchanged: copy the accepted configured setup whole.
    setup = OUT_PREFLIGHT/'setup-owned'
    if not setup.exists():
        OUT_PREFLIGHT.mkdir(parents=True, exist_ok=True)
        shutil.copytree(PREDECESSOR_PREFLIGHT/'setup-owned', setup)
    exec(compile(raw, str(Path(__file__).resolve()), 'exec'),
         dict(__name__='__main__', __file__=str(Path(__file__).resolve())))


if __name__ == '__main__':
    main()
