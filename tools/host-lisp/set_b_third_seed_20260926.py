"""One owner-authorized third Seed; fresh object admission, no implicit retry."""
import inspect
from pathlib import Path
import re
import shutil
import subprocess
import traceback
import set_b_producer as P
import boot_name_index_link_preprobe as L

ROOT=P.ROOT
OUT=ROOT/'build/set-b-r1/step4-r4'
PRODUCT=ROOT/'build/set-b-product-r3'
SEAL=ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks/set-b-placement-revision-20260926.json'

def main():
    assert not OUT.exists() and not PRODUCT.exists(), 'No implicit Seed retry'
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=ROOT), 'Commit before execution'
    OUT.mkdir()
    try:
        authority=P.require_auth();assert authority.startswith('7a4e43fa')
        verified=[];changes=[]
        for row in P.load(SEAL)['inputs']+P.load(SEAL)['receipt_copies']:
            actual=P.bind(ROOT/row['path'])
            if actual!=row:
                assert row['path']=='tools/host-lisp/set_b_producer.py',row['path']
                old=subprocess.check_output(['git','show','7a4e43fa:'+row['path']],cwd=ROOT)
                norm=lambda b:re.sub(rb'^AUTH = [^\n]+',b'AUTH = POINTER',b,flags=re.M)
                assert norm(old)==norm((ROOT/row['path']).read_bytes())
                changes.append(dict(before=row,after=actual))
            else:verified.append(actual)
        ns=dict(vars(P));transforms=[]
        for name,old,new in [
            ('command_probe',"out=HERE/'step3/command-preview'","out=ROOT/'build/set-b-r1/step4-r4/command-preview'"),
            ('seed',"out=HERE/'seed'","out=ROOT/'build/set-b-product-r3'")]:
            source=inspect.getsource(getattr(P,name));assert source.count(old)==1
            source=source.replace(old,new,1);path=OUT/(name+'-executed.py');path.write_text(source)
            exec(compile(source,str(path),'exec'),ns)
            transforms.append(dict(function=name,before=old,after=new,executed=P.bind(path)))
        preview=ns['command_probe']()
        commands=P.load(preview/'commands.json');normalized=[]
        for cmd in commands:
            cmd=list(cmd)
            if '-c' in cmd:
                assert cmd[-1]=='-DLISP65_SET_B'
                define=cmd.pop();cmd.insert(cmd.index('-c'),define)
            normalized.append(cmd)
        proof=preview/'wplto/command-proof.json';P.write(proof,dict(commands=normalized))
        baseline=OUT/'baseline-proof';baseline.mkdir()
        P.write(baseline/'command-proof.json',P.load(P.BASE/'final-command-consumption.json'))
        shutil.copyfile(P.BASE/'wplto/c2-substitution.ld',baseline/'c2-substitution.ld')
        shutil.copytree(P.BASE/'wplto/full-map-linker',baseline/'full-map-linker')
        print('Fresh undefined-symbol and E000 preprobes',flush=True)
        link=L.run_preprobe(proof,OUT/'link-preprobe',baseline/'command-proof.json')
        assert link['status']=='PASS',link['new_findings']
        edge=L.e000_low_edges_receipt([ROOT/p for p in link['objects']],
            sorted((OUT/'link-preprobe/baseline/objects').glob('*.o')))
        P.write(OUT/'e000-edges.json',edge);assert edge['status']=='PASS',edge['new_findings_keys']
        # Parser evidence and scripts are unchanged since the preceding link
        # parsed them successfully; layout is still checked at the actual link.
        scripts=[]
        for source in (ROOT/'config/set-b-native/linker').rglob('*'):
            if source.is_file():
                previous=ROOT/'build/set-b-product-r2/wplto'/source.relative_to(ROOT/'config/set-b-native/linker')
                assert source.read_bytes()==previous.read_bytes()
                scripts.append(dict(current=P.bind(source),previous=P.bind(previous)))
        extent,tenants=P.late_partition();assert extent==6720 and len(tenants)==7
        host=ROOT/'build/set-b-placement-r1/validation-r2/receipt.json'
        assert P.load(host)['status'].startswith('PASS:')
        P.write(OUT/'admission.json',dict(status='PASS',authority=authority,seal=P.bind(SEAL),
            verified_unchanged=verified,normalized_auth_changes=changes,scripts=scripts,
            commands=P.bind(preview/'commands.json'),probe_commands=P.bind(proof),
            probe_flag_normalization='Move unchanged trailing -DLISP65_SET_B before -c for the era parser',
            symbol_probe=P.bind(OUT/'link-preprobe/receipt.json'),e000_probe=P.bind(OUT/'e000-edges.json'),
            capacity_pack_fixture=P.bind(host),actual_linked_placement='PENDING'))
        P.write(OUT/'seed-invocation.json',dict(authority=authority,
            head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            driver=P.bind(Path(__file__)),producer=P.bind(Path(P.__file__)),transformations=transforms,
            admission=P.bind(OUT/'admission.json'),output=str(PRODUCT.relative_to(ROOT)),
            attempt=3,cumulative_seed_ceiling=3,cumulative_product_link_ceiling=3,retry=False))
        print('PASS preflight; starting the one authorized third Seed',flush=True)
        ns['seed']()
        P.write(OUT/'seed-result.json',dict(status='PASS: LINKED AND EXTRACTED; INVENTORY/MEDIA/GUEST GATES PENDING',retry=False))
        print('PASS linked and extracted; actual inventory pending',flush=True)
    except Exception as e:
        P.write(OUT/'seed-result.json',dict(status='HALT',error=str(e),traceback=traceback.format_exc(),retry=False))
        raise

if __name__=='__main__':main()
