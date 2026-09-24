"""Decode marked Cons survivors, preserving values and a separate shape view."""
from pathlib import Path
from collections import Counter
import hashlib, json
from elf_truth import ElfTruth

ROOT=Path(__file__).resolve().parents[2];HERE=ROOT/'build/definition-set-a-r3'
result={}
for role in ('baseline','candidate'):
    receipt=ROOT/f'build/definition-set-a-auth-gc-charges-{role}-0/receipt.json'
    r=json.loads(receipt.read_text());raw=(ROOT/r['outputs']['memory']['path']).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==r['outputs']['memory']['sha256']
    t=ElfTruth.read(ROOT/r['ELF']['path'],llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj')
    def word(at):return int.from_bytes(raw[at:at+2],'little')
    pool=t.symbol('__storage_symbol_names_start').value;off=t.symbol('__storage_nameoff_start').value
    hot=t.symbol('heap').value;cur=word(t.symbol('str_cur_off').value)
    def show(o,seen=(),shape=False):
        if o==0:return None
        if o&1:return ['int'] if shape else ['int',(o if o<32768 else o-65536)//2]
        if o>=0xe000:
            at=pool+word(off+((o-0xe000)//2)*2)
            return ['sym',raw[at:raw.index(b'\0',at)].decode('ascii')]
        if o>=0x8000:return ['immediate',o]
        i=o//2
        if i in seen:return ['cycle',seen.index(i)]
        at=hot+i*5 if i<48 else 0x40000+(i-48)*8
        kind=raw[at];a=word(at+(1 if i<48 else 2));b=word(at+(3 if i<48 else 4))
        if kind in (0,3,4):return [kind,show(a,seen+(i,),shape),show(b,seen+(i,),shape)]
        if kind==5:return ['string',raw[0x40000+cur+(b>>1):0x40000+cur+(b>>1)+(a>>1)].hex()]
        return [kind,a,b]
    h=json.loads((HERE/'gc-heap.json').read_text())['worlds'][role]
    rows=[dict(cell=x['cell'],value=show(x['cell']*2),shape=show(x['cell']*2,shape=True)) for x in h['cells'] if x['type']==0]
    result[role]=dict(rows=rows,memory=r['outputs']['memory'],ELF=r['ELF'])
def population(role,key):return Counter(json.dumps(x[key],sort_keys=True) for x in result[role]['rows'])
a,b=(population(role,'shape') for role in ('baseline','candidate'))
assert not a-b
extra=b-a
expected=[ [0,['sym','%c2-definition-group'],None],
    [0,['sym','quote'],[0,['sym','%c2-definition-group'],None]] ]
assert extra==Counter(json.dumps(x,sort_keys=True) for x in expected)
result['extra_cons']=expected
result['limits']=['Shape comparison ignores integer payloads only; exact decoded values are retained.',
    'This identifies the additional marked group-marker literal, not all timing effects or the cause of the fourteenth definition collection.']
(HERE/'gc-root-difference.json').write_text(json.dumps(result,indent=2)+'\n')
print('Two additional Cons: (quote %c2-definition-group); all other Cons shapes preserved.')
