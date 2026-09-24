"""Fill real image slots, accept the last group, reject the next without publication."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
source = ROOT/'build/library-delivery-r8/load-five.py'
raw = source.read_text().replace('build/library-delivery-final-five-load-r6-',
    'build/definition-set-a-capacity-').replace('build/library-delivery-final-medium-r6',
    'build/definition-set-a-seed-medium-r1')
start = raw.index('    forms=')
end = raw.index('    for name,form,value in forms:', start)
raw = raw[:start]+'''    forms=[('package','(require "defstruct")','T')]
    # The measured boot has eight persistent images; the package is the ninth.
    assert rows[0]['values']['images']==dict(used=8,capacity=64)
    forms += [(f'fill-{i}',f'(defun capfill{i} () 7)',f'CAPFILL{i}') for i in range(54)]
    forms += [('last-group','(defstruct caplast a b c d e)','T'),
              ('last-use','(caplast-a (make-caplast 42 2 3 4 5))','42'),
              ('rejected-group','(defstruct capnext a b c d e)','OOM'),
              ('after-rejection','(+ 4 5)','9'),
              ('old-use','(caplast-a (make-caplast 42 2 3 4 5))','42')]
''' + raw[end:]
raw = raw.replace('run=None;error=None;rows=[];outputs=None', '''run=None;error=None;rows=[];outputs=None
import hashlib
from collections import Counter
last_objects=None
def objects(m):
    header=m.memory_range(0x50000,48)
    count=int.from_bytes(header[16:18],'little')
    offset=int.from_bytes(header[30:32],'little')
    directory=m.memory_range(0x50000+offset,count*10)
    bank=m.memory_range(0x20000,65536)
    result={}
    for i in range(count):
        row=directory[i*10:(i+1)*10]
        start=int.from_bytes(row[2:4],'little');size=int.from_bytes(row[4:6],'little')
        result[i]=(row.hex(),hashlib.sha256(bank[start:start+size]).hexdigest())
    return result
''')
raw = raw.replace('okay=C.fresh_result(before,screen,value)', '''okay=(
                    '*** VM: OUT OF MEMORY' in R.ROWS.decoded_framebuffer(screen)
                    and '*** VM: OUT OF MEMORY' not in R.ROWS.decoded_framebuffer(before)
                    if value=='OOM' else C.fresh_result(before,screen,value))''')
old = "if any(x in decoded for x in ('***','OUT OF MEMORY','CANNOT OPEN')):break"
assert raw.count(old) == 1
raw = raw.replace(old, "if Counter(line for line in decoded.splitlines() if '***' in line)-Counter(line for line in R.ROWS.decoded_framebuffer(before).splitlines() if '***' in line):break")
needle = "        assert okay, 'native load failed: '+name"
assert raw.count(needle) == 1
raw = raw.replace(needle, needle+'''
        if name=='fill-53':
            assert row['values']['images']['used']==63
            last_objects=objects(m)
        if name=='last-group':
            assert row['values']['images']['used']==64
            current=objects(m)
            assert len(current)-len(last_objects)==18
            assert all(current[i]==v for i,v in last_objects.items())
            last_objects=current
            (out/'before-rejection-objects.json').write_text(json.dumps(current,indent=2)+'\\n')
        if name in ('rejected-group','after-rejection','old-use'):
            assert row['values']['images']['used']==64
            current=objects(m)
            assert current==last_objects, 'rejected group changed foreign code or directory population'
            (out/(name+'-objects.json')).write_text(json.dumps(current,indent=2)+'\\n')
''')
raw = raw.replace("print(name,'PASS' if okay else 'RED',row['values'],flush=True)",
    "print(name,'PASS' if okay else 'RED',row['values']['images'],flush=True)")
raw = raw.replace('Fresh result after each require and stopped live counters; no device or wall-clock claim',
    'Natural image-capacity boundary: last group one image, next OOM, unchanged published code objects/directory, old accessor and live prompt; not an abort-injection proof')
exec(compile(raw, str(source), 'exec'), dict(__name__='__main__', __file__=__file__))
