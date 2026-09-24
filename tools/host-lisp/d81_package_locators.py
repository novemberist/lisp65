"""Final-media admission: bind each L65INDEX locator to its named file chain.

Use only on a complete medium, not an index placeholder during construction.
No-index media still receive the file/BAM ownership check.
"""
from pathlib import Path
import argparse,ast,json

def validate_visible(raw,files):
    """Common readback boundary; no recursive call to visible_files."""
    import d81_persistence_fault as D
    import c2_require_resolver_gate as L
    if b'L65INDEX' not in files:return []
    slots={D.entry_name(s.record):s.record for s in D.directory_slots(raw) if s.record[2]}
    checks=[]
    for row in L.decode_index(files[b'L65INDEX']):
        name=row['name'].upper().encode('ascii')
        if name not in files:raise ValueError('indexed file absent: '+name.decode())
        chain=D.file_chain(raw,slots[name]);start=(row['track'],row['sector'])
        if start!=chain[0]:raise ValueError('stale package locator: '+name.decode())
        if row['artifact_bytes']!=len(files[name]):raise ValueError('indexed file length: '+name.decode())
        checks.append(dict(name=name.decode(),start=list(start),sectors=len(chain),bytes=len(files[name])))
    return checks

def qualify(raw):
    import legacy_ide_delivery as D
    import c2_require_resolver_gate as L
    files=D.inventory(raw)
    checks=[]
    if 'L65INDEX' in files:
        for row in L.decode_index(files['L65INDEX']['data']):
            name=row['name'].upper()
            if name not in files:raise ValueError('indexed file absent: '+name)
            start=(row['track'],row['sector'])
            chain=files[name]['sectors']
            if not chain or start!=chain[0]:raise ValueError('stale package locator: '+name)
            if row['artifact_bytes']!=len(files[name]['data']):raise ValueError('indexed file length: '+name)
            checks.append(dict(name=name,start=list(start),sectors=len(chain),bytes=len(files[name]['data'])))
    return dict(status='PASS',files=len(files),locators=checks)

def publish(path,raw):
    """A complete-medium writer cannot release unresolved locators."""
    proof=qualify(raw)
    if path.exists():raise ValueError('qualified media output already exists')
    path.write_bytes(raw)
    if path.read_bytes()!=raw:raise ValueError('media write/readback mismatch')
    qualify(path.read_bytes())
    return proof

def audit_hooks(sources):
    for path,function,call in (
        ('tools/host-lisp/d81_persistence_fault.py','visible_files','validate_visible'),
        ('tools/host-lisp/c2_lite_media_product.py','close_packed_artifacts','qualify')):
        tree=ast.parse(sources[path]);fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==function)
        calls=[ast.unparse(n.func) for n in ast.walk(fn) if isinstance(n,ast.Call)]
        if call not in calls:raise ValueError('media admission hook absent: '+function)

def selftest():
    root=Path(__file__).resolve().parents[2]
    old=root/'build/definition-set-a-final-medium-r1/packed/hardware-sp-seed.d81'
    good=qualify(old.read_bytes());assert len(good['locators'])==5
    bad=root/'build/stager-crc32-r2/product.d81'
    import d81_persistence_fault as D
    rejected=[]
    for label,fn in [('qualified-admission',qualify),('common-readback',D.visible_files)]:
        try:fn(bad.read_bytes())
        except ValueError:rejected.append(label)
        else:raise AssertionError('stale index admitted: '+label)
    sources={p:(root/p).read_text() for p in ('tools/host-lisp/d81_persistence_fault.py','tools/host-lisp/c2_lite_media_product.py')}
    audit_hooks(sources)
    for p,call in [('tools/host-lisp/d81_persistence_fault.py','validate_visible(image, result)'),('tools/host-lisp/c2_lite_media_product.py','qualify(path.read_bytes())')]:
        assert sources[p].count(call)==1
        mutation=dict(sources);mutation[p]=sources[p].replace(call,'None')
        try:audit_hooks(mutation)
        except ValueError:rejected.append('drop-hook:'+call)
        else:raise AssertionError('missing hook accepted')
    print(json.dumps(dict(status='PASS',locators=good['locators'],negative_controls=rejected),indent=2))

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('medium',type=Path,nargs='?');ap.add_argument('--selftest',action='store_true')
    args=ap.parse_args()
    if args.selftest:selftest()
    else:
        if args.medium is None:ap.error('medium required')
        print(json.dumps(qualify(args.medium.read_bytes()),indent=2))

if __name__=='__main__':main()
