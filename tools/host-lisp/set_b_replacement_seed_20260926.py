"""Owner-authorized replacement: immutable predecessor admission, one Seed/link."""
import inspect
from pathlib import Path
import re
import subprocess
import traceback
import set_b_producer as P

ROOT=P.ROOT
OLD=ROOT/'build/set-b-r1/step4-r2'
OUT=ROOT/'build/set-b-r1/step4-r3'
PRODUCT=ROOT/'build/set-b-product-r2'
SEAL=ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks/set-b-seed-link-halt-20260926.json'
SCRIPT='config/set-b-native/linker/full-map-linker/c.ld'
PRODUCER='tools/host-lisp/set_b_producer.py'

def main():
    assert not OUT.exists() and not PRODUCT.exists(), 'No implicit replacement retry'
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=ROOT), 'Commit tools before execution'
    OUT.mkdir()
    try:
        authority=P.require_auth()
        assert authority.startswith('7bef0c2c')
        seal=P.load(SEAL)
        verified=[];changes=[]
        for row in seal['inputs']+seal['receipt_copies']:
            actual=P.bind(ROOT/row['path'])
            if actual!=row:
                assert row['path'] in (SCRIPT,PRODUCER), row['path']
                before=subprocess.check_output(['git','show','9e946c38:'+row['path']],cwd=ROOT)
                import hashlib
                assert hashlib.sha256(before).hexdigest()==row['sha256']
                after=(ROOT/row['path']).read_bytes()
                if row['path']==SCRIPT:
                    needle=b'"Set B 72-byte journal owner");'
                    assert before.count(needle)==1
                    assert after==before.replace(needle,needle[:-1],1)
                else:
                    norm=lambda b:re.sub(rb'^AUTH = [^\n]+',b'AUTH = POINTER',b,flags=re.M)
                    assert norm(before)==norm(after)
                changes.append(dict(before=row,after=actual))
            else:verified.append(actual)
        assert {r['after']['path'] for r in changes}=={SCRIPT,PRODUCER}
        ns=dict(vars(P));transforms=[]
        for name,old,new in [
            ('command_probe',"out=HERE/'step3/command-preview'","out=ROOT/'build/set-b-r1/step4-r3/command-preview'"),
            ('seed',"out=HERE/'seed'","out=ROOT/'build/set-b-product-r2'")]:
            source=inspect.getsource(getattr(P,name));assert source.count(old)==1
            source=source.replace(old,new,1)
            path=OUT/(name+'-executed.py');path.write_text(source)
            exec(compile(source,str(path),'exec'),ns)
            transforms.append(dict(function=name,before=old,after=new,executed=P.bind(path)))
        preview=ns['command_probe']()
        original=P.load(OLD/'command-preview/commands.json')
        replacement=P.load(preview/'commands.json')
        rebased=[[a.replace('build/set-b-r1/step4-r2/command-preview',
                            'build/set-b-r1/step4-r3/command-preview') for a in c] for c in original]
        assert rebased==replacement, 'Command drift beyond output paths'
        reused=[]
        for rel in ['link-preprobe/receipt.json','e000-preprobe/e000-low-edges-receipt.json',
                    'capacity-delivered/receipt.json']:
            assert P.load(OLD/rel)['status']=='PASS'
            reused.append(P.bind(OLD/rel))
        assert P.load(OLD/'link-syntax-attribution/receipt.json')['status'].startswith('PASS:')
        P.write(OUT/'admission.json',dict(status='PASS',authority=authority,
            predecessor_seal=P.bind(SEAL),verified_unchanged=verified,admitted_changes=changes,
            commands_before=P.bind(OLD/'command-preview/commands.json'),commands_after=P.bind(preview/'commands.json'),
            reused_probes=reused,reuse_basis='All sealed compiler inputs, object probes and delivered capacity inputs unchanged; only linker ASSERT punctuation and normalized AUTH pointer differ.',
            syntax_control=P.bind(OLD/'link-syntax-attribution/receipt.json'),
            linked_placement='PENDING: producer exact partition checks remain unchanged'))
        P.write(OUT/'seed-invocation.json',dict(authority=authority,
            source_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            driver=P.bind(Path(__file__)),producer=P.bind(Path(P.__file__)),transformations=transforms,
            admission=P.bind(OUT/'admission.json'),output=str(PRODUCT.relative_to(ROOT)),
            replacement_seed_invocations=1,cumulative_seed_ceiling=2,cumulative_product_link_ceiling=2,retry=False))
        print('PASS replacement admission; invoking the single authorized replacement Seed',flush=True)
        ns['seed']()
        P.write(OUT/'seed-result.json',dict(status='PASS: LINKED AND EXTRACTED; INVENTORY/MEDIA/GUEST GATES PENDING',retry=False))
    except Exception as e:
        P.write(OUT/'seed-result.json',dict(status='HALT',error=str(e),traceback=traceback.format_exc(),retry=False))
        raise

if __name__=='__main__':main()
