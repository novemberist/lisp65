"""Storage-owner admission at the actual compiler invocation boundary.

The callback consumes compiler/link flags, not a separately generated wish list.
It does not invoke a compiler. Historical product profiles are not opted in.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import symbol_layout_manifest as layout
import storage_owner_linker as linker

ROOT = layout.ROOT

def bind(path):
    raw=path.read_bytes()
    return dict(path=str(path.resolve().relative_to(ROOT)),bytes=len(raw),
                sha256=hashlib.sha256(raw).hexdigest())

def normalized(definitions):
    result={}
    for item in definitions:
        name,separator,value=item.partition('=')
        if name in result: raise ValueError('duplicate compiler definition: '+name)
        if separator:
            try: value=layout.number(value)
            except ValueError: pass
        else: value=None
        result[name]=value
    return result

def before_compile(product_definitions, callback, **invocation):
    consumed=normalized(product_definitions)
    wanted=layout.values()
    selected=(consumed.get('MAX_SYM')==wanted['MAX_SYM'] or
              consumed.get('NAMEPOOL')==wanted['NAMEPOOL'] or
              consumed.get('SYMPOOL_EXT_BANK')==wanted['SYMPOOL_EXT_BANK'])
    if selected or callback is not None:
        if not callable(callback):
            raise RuntimeError('selected storage layout lacks pre-compiler consumption admission')
        return callback(**invocation)
    return None

class Admission:
    def __init__(self, predecessor, artifacts):
        self.predecessor=predecessor.resolve()
        self.artifacts=artifacts.resolve()
        self.manifest_binding=bind(layout.MANIFEST)
        self.artifact_binding=bind(self.artifacts)
        self.before={name:(self.predecessor/name).read_text() for name in linker.FILES}
        self.before_bindings={name:bind(self.predecessor/name) for name in linker.FILES}
        self.expected=linker.transform(self.before,linker.facade_fixed_price(self.predecessor))

    def check(self, *, target, compile_flags, link_flags, **unused):
        if bind(layout.MANIFEST)!=self.manifest_binding: raise ValueError('manifest changed after admission')
        if bind(self.artifacts)!=self.artifact_binding: raise ValueError('artifact authority changed after admission')
        for name,expected in self.before_bindings.items():
            if bind(self.predecessor/name)!=expected: raise ValueError('predecessor linker changed')
        out=target.parent.resolve()
        actual={name:(out/name).read_text() for name in linker.FILES}
        linker.verify(actual,self.expected)
        selected=json.loads(self.artifacts.read_text())
        native=json.loads((ROOT/layout.load()['predecessor_manifest']['path']).read_text())
        expected=normalized(layout.replace_definitions(native['definitions']))
        expected['LISP65_C2_PRODUCT_BUILD_ID']=int(selected['product_build_id_hex'],0)
        expected['LISP65_C2_PRODUCT_SHELF_BYTES']=selected['artifacts']['shelf']['bytes']
        consumed=normalized([f[2:] for f in compile_flags if f.startswith('-D')])
        if consumed!=expected:
            delta={key:[expected.get(key),consumed.get(key)] for key in expected.keys()|consumed.keys()
                   if key not in expected or key not in consumed or expected[key]!=consumed[key]}
            raise ValueError('compiler definition drift: '+json.dumps(delta,sort_keys=True))
        # No late -U or force-defined competing storage values are admitted.
        if any(f.startswith('-U') for f in compile_flags): raise ValueError('compiler undefinition')
        scripts=[f.removeprefix('-Wl,-T,') for f in link_flags if f.startswith('-Wl,-T,')]
        dirs=[f.removeprefix('-Wl,-L,') for f in link_flags if f.startswith('-Wl,-L,')]
        if [Path(p).resolve() for p in scripts]!=[out/'c2-substitution.ld']:
            raise ValueError('wrong explicit linker script')
        if [Path(p).resolve() for p in dirs]!=[out/'full-map-linker']:
            raise ValueError('competing or absent owner script search path')
        toolchain=ROOT/'tools/llvm-mos/mos-platform'
        paths=[out/'full-map-linker']+[toolchain/name/'lib' for name in ('mega65','commodore','common')]
        closure={}
        def visit(path):
            path=path.resolve()
            if path in closure: return
            closure[path]=bind(path)
            text=re.sub(r'/\*.*?\*/','',path.read_text(),flags=re.S)
            for name in re.findall(r'\bINCLUDE\s+([^\s;]+)',text):
                matches=[root/name for root in paths if (root/name).is_file()]
                if not matches: raise ValueError('unresolved linker include: '+name)
                visit(matches[0])
        visit(out/'c2-substitution.ld')
        visit(toolchain/'mega65/lib/link.ld')
        if any((out/name) not in closure for name in linker.FILES):
            raise ValueError('derived script is not reached by selected linker roots')
        return dict(status='PASS: actual flags and reached linker inputs match storage authority',
                    manifest=self.manifest_binding,artifacts=self.artifact_binding,
                    predecessor_scripts=self.before_bindings,
                    definitions=consumed,linker_closure=list(closure.values()),
                    target=str(target.relative_to(ROOT)),compiler_started=False)

    def __call__(self, **kwargs):
        result=self.check(**kwargs)
        target=kwargs['target']
        Path(str(target)+'.storage-owner-admission.json').write_text(json.dumps(result,indent=2)+'\n')
        return result

def selftest(predecessor, artifacts, output):
    linker.derive(predecessor,output)
    gate=Admission(predecessor,artifacts)
    source=json.loads((ROOT/layout.load()['predecessor_manifest']['path']).read_text())
    artifact=json.loads(artifacts.read_text())
    definitions=layout.replace_definitions(source['definitions'])
    dynamic={'LISP65_C2_PRODUCT_BUILD_ID':artifact['product_build_id_hex'],
             'LISP65_C2_PRODUCT_SHELF_BYTES':str(artifact['artifacts']['shelf']['bytes'])}
    definitions=[d.split('=',1)[0]+'='+dynamic[d.split('=',1)[0]]
                 if d.split('=',1)[0] in dynamic else d for d in definitions]
    invocation=dict(target=output/'selftest.prg',compile_flags=['-D'+d for d in definitions],
        link_flags=['-Wl,-L,'+str(output/'full-map-linker'),'-Wl,-T,'+str(output/'c2-substitution.ld')])
    baseline=gate.check(**invocation)
    rejected=[]
    def reject(name,operation):
        try: operation()
        except (ValueError,RuntimeError,OSError): rejected.append(name)
        else: raise ValueError('surviving storage consumption mutation: '+name)
    for key,value in layout.values().items():
        mutant=dict(invocation)
        mutant['compile_flags']=[f'-D{key}={value+1}' if f.startswith('-D'+key+'=') else f
                                 for f in invocation['compile_flags']]
        reject('define:'+key,lambda:gate.check(**mutant))
    for name in linker.FILES:
        path=output/name;original=path.read_bytes()
        try:
            path.write_bytes(original+b'\n/* unbound change */\n')
            reject('script-drift:'+name,lambda:gate.check(**invocation))
            path.unlink()
            reject('script-absent:'+name,lambda:gate.check(**invocation))
        finally:path.write_bytes(original)
    for name,prefix in [('wrong-root','-Wl,-T,'),('wrong-search','-Wl,-L,')]:
        mutant=dict(invocation)
        mutant['link_flags']=[f+'-wrong' if f.startswith(prefix) else f for f in invocation['link_flags']]
        reject(name,lambda:gate.check(**mutant))
    mutant=dict(invocation);mutant['compile_flags']=invocation['compile_flags']+['-UMAX_SYM']
    reject('late-undefine',lambda:gate.check(**mutant))
    mutant=dict(invocation);mutant['compile_flags']=invocation['compile_flags']+['-DMAX_SYM=1008']
    reject('duplicate-definition',lambda:gate.check(**mutant))
    reject('missing-callback',lambda:before_compile(definitions,None,**invocation))
    alternate=[d.replace('MAX_SYM=1008','MAX_SYM=0x3f0u') for d in definitions]
    reject('hex-definition-missing-callback',lambda:before_compile(alternate,None,**invocation))
    # The frozen release definition set remains outside this card's opt-in.
    if before_compile(source['definitions'],None,**invocation) is not None:
        raise ValueError('historical compiler invocation was changed')
    result=dict(status='PASS: storage consumption selftest',controls=rejected,
                baseline=baseline,compiler_invocations=0,
                claim='Synthetic invocation controls; not full producer or candidate admission.')
    from check_result_receipt import report
    report(output/'selftest.json', result)
    print(result['status'],'controls',len(rejected))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--predecessor',type=Path,required=True)
    parser.add_argument('--artifacts',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    selftest(args.predecessor.resolve(),args.artifacts.resolve(),args.output.resolve())
