"""Set-A command admission over the accepted Retirement producer.

Seed entry is explicit and requires the admitted command transcript,
conservative pack projection and group-route controls. Merely running the
command probe never consumes the Seed budget.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT/'build/index-crc-r1/product-card.py'


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('producer template population drift: '+old)
    return text.replace(old, new, 1)


def main():
    if sys.argv[1:] not in (['command-probe'], ['seed']):
        raise SystemExit('command-probe | seed')
    raw = TEMPLATE.read_text()
    for old, new in {
        'HERE=Path(__file__).resolve().parent':
            "HERE=ROOT/'build/definition-set-a-r2';HERE.mkdir(parents=True,exist_ok=True)",
        "BASE=ROOT/'build/storage-owner-product-r2'":
            "BASE=ROOT/'build/transient-retirement-product-r1'",
        "BASE_PREFLIGHT=ROOT/'build/storage-owner-product-r2-preflight'":
            "BASE_PREFLIGHT=ROOT/'build/transient-retirement-product-r1-preflight'",
        "OUT=ROOT/'build/index-crc-product-r1-preflight'":
            "OUT=ROOT/'build/definition-set-a-product-r2-preflight'",
        "BUILD=ROOT/'build/index-crc-product-r1'":
            "BUILD=ROOT/'build/definition-set-a-product-r1'",
        "AUTH='4cf5a2f9'": "AUTH='c97a8e60'",
        "CHANGED=('src/vm.c',)":
            "CHANGED=('src/vm.c','src/c2_product_runtime.c','src/c2_session_emitter.c')",
        "name='index-crc-and-final-sector-length'": "name='definitions-set-a'",
        "allowed=set(proof['changed_members'])|{'vm.c'}":
            "allowed=set(proof['changed_members'])|{'vm.c','c2_product_runtime.c','c2_session_emitter.c'}",
    }.items():
        raw = replace_once(raw, old, new)
    start = raw.index('def source_gate():')
    end = raw.index('\ndef prepare_inputs()', start)
    raw = raw[:start]+'''def source_gate():
    expected={'src/vm.c','src/vm.h','src/c2_product_runtime.c',
        'src/c2_product_runtime.h','src/c2_session_emitter.c',
        'lib/defstruct.lisp','lib/dialect-v2/eval-runtime.lisp'}
    changed=set(subprocess.check_output(['git','diff','21453532','--name-only',
        '--','src','lib'],cwd=ROOT,text=True).splitlines())
    if changed!=expected: raise ValueError('uncommissioned source population: '+repr(changed))
    comp=R.C.load(HERE/'composition.json')
    if not comp['baseline_relocation_equivalent'] or comp['total_bank2_delta']!=160:
        raise ValueError('Set-A composition not admitted')
    for row in [comp['manifest'],comp['authored'],comp['projection'],
                comp['package']['candidate']]:
        if R.bind(ROOT/row['path'])!=row: raise ValueError('composition drift')
    checks=[]
    for path in ('build/definition-group-route-r3/receipt.json',
                 'build/definition-set-a-pack-r2/receipt.json',
                 'build/definition-group-capacity-r2/receipt.json'):
        receipt=R.C.load(ROOT/path)
        if not receipt['status'].startswith('PASS'): raise ValueError('failed preflight: '+path)
        for row in receipt.get('inputs',[]):
            if R.bind(ROOT/row['path'])!=row: raise ValueError('preflight input drift: '+row['path'])
        checks.append(R.bind(ROOT/path))
    return dict(status='PASS: SET-A SOURCE COMPOSITION, NOT NATIVE ACCEPTANCE',
        sources=[R.bind(ROOT/p) for p in sorted(changed)],
        composition=R.bind(HERE/'composition.json'),
        checks=checks,
        plane=R.bind(PLANE/'set-a-plane-receipt.json'),
        producer_template=R.bind(ROOT/'build/index-crc-r1/product-card.py'))
''' + raw[end:]
    start = raw.index('    # Apply only the commissioned diff')
    end = raw.index('    derived,proof=', start)
    raw = raw[:start]+'''    # Preserve every consumed producer adaptation; only apply the seven
    # commissioned source hunks, with exact context, from the accepted world.
    import re
    for name in ('vm.c','c2_product_runtime.c','c2_session_emitter.c'):
        target=generated/name;text=target.read_text()
        diff=subprocess.check_output(['git','diff','21453532','--','src/'+name],cwd=ROOT,text=True)
        (out/(name+'.set-a.patch')).write_text(diff)
        if name=='vm.c':
            # The consumed VM has the older disk adapter between this seam
            # and vm_callprim. Bind the complete unchanged tail of the actual
            # Buffer transport, not the unrelated following function.
            authored=(ROOT/'src/vm.c').read_text()
            begin=authored.index('#ifdef LISP65_C2_PRODUCT_CUT\\nobj vm_buffer_from_stage(')
            end=authored.index('\\n#endif',begin)+len('\\n#endif')
            addition=authored[begin:end]
            before='    return context->result;\\n}\\n\\n#endif'
            if text.count(before)!=1 or authored.count(addition)!=1:
                raise ValueError('Buffer transport owner is not unique')
            text=text.replace(before,before[:-len('#endif')]+addition+'\\n\\n#endif',1)
            target.write_text(text);mapping[(ROOT/'src'/name).resolve()]=target
            continue
        parts=re.split(r'(^@@[^\\n]*\\n)',diff,flags=re.M)
        for i in range(2,len(parts),2):
            lines=parts[i].splitlines(keepends=True)
            before=''.join(l[1:] for l in lines if l[:1] in (' ','-'))
            after=''.join(l[1:] for l in lines if l[:1] in (' ','+'))
            if text.count(before)!=1: raise ValueError('source projection hunk mismatch: '+name)
            text=text.replace(before,after,1)
        target.write_text(text);mapping[(ROOT/'src'/name).resolve()]=target
''' + raw[end:]
    # Source-header changes are explicitly commissioned inputs, not arbitrary
    # differences against the historical public include closure.
    # The existing closure already checks source headers against SOURCE_BASE;
    # AUTH contains the two header changes and source_gate limits the population.
    here = ROOT/'build/definition-set-a-r2'
    here.mkdir(exist_ok=True)
    for target, source in (
        ('composition.json', ROOT/'build/definition-group-composition-r6/receipt.json'),
        ('plane.json', ROOT/'build/definition-set-a-product-r2-preflight/setup-owned/static-plane/narrow-static/set-a-plane-receipt.json'),
    ):
        path = here/target
        if path.exists() and path.read_bytes() != source.read_bytes():
            raise ValueError('preflight input overwrite: '+str(path))
        if not path.exists():
            path.write_bytes(source.read_bytes())
    exec(compile(raw, str(Path(__file__).resolve()), 'exec'),
         dict(__name__='__main__', __file__=str(Path(__file__).resolve())))


if __name__ == '__main__':
    main()
