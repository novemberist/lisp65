"""Refresh stale descriptive source hashes and validate in a fresh receipt tree."""
import inspect
from pathlib import Path
import set_b_producer as P
import set_b_placement_validate_20260926 as V

ROOT=P.ROOT
OUT=ROOT/'build/set-b-placement-r1/source-census-r2'

def main():
    OUT.mkdir(exist_ok=False)
    snapshot=OUT/'inputs-before-metadata-refresh.json'
    snapshot.write_bytes(P.INPUTS.read_bytes())
    inputs=P.load(P.INPUTS);updated=[]
    for row in inputs['sources']:
        current=P.bind(ROOT/row['path'])
        if row!=current:
            updated.append(dict(before=dict(row),after=current));row.update(current)
    assert {r['after']['path'] for r in updated}=={
        'src/optional/set_b_retire_commit_a.c','src/optional/set_b_retire_commit_b.c',
        'src/optional/set_b_retire_commit_c.c','src/optional/set_b_retire_common.h',
        'src/optional/set_b_retire_control.c','src/optional/set_b_retire_reset.c'}
    P.write(P.INPUTS,inputs)
    P.write(OUT/'metadata-refresh.json',dict(status='PASS',driver=P.bind(Path(__file__)),
        historical_inputs=P.bind(snapshot),current_inputs=P.bind(P.INPUTS),updated=updated,
        note='Descriptive sources[] hashes predated step 3b. Source files themselves unchanged in this revision.',
        source_content_changes=0,product_links=0))
    source=inspect.getsource(V.main)
    before='build/set-b-placement-r1/validation-r1/command-preview'
    after='build/set-b-placement-r1/validation-r2/command-preview'
    assert source.count(before)==1;source=source.replace(before,after,1)
    executed=OUT/'validation-executed.py';executed.write_text(source)
    ns=dict(vars(V));ns['OUT']=V.BASE/'validation-r2'
    exec(compile(source,str(executed),'exec'),ns)
    P.write(OUT/'invocation.json',dict(driver=P.bind(Path(__file__)),base_driver=P.bind(Path(V.__file__)),
        executed=P.bind(executed),changes=[dict(before=before,after=after),dict(global_name='OUT',after=str(ns['OUT'].relative_to(ROOT)))],
        input_refresh=P.bind(OUT/'metadata-refresh.json'),product_links=0,object_compiles=0))
    ns['main']()

if __name__=='__main__':main()
