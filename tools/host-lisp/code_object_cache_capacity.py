"""Current-medium native capacity prefilter; no product build or device contact."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/host-lisp'))
source=ROOT/'tools/host-lisp/definition_set_a_capacity_native.py'
script=source.read_text().replace('build/definition-set-a-capacity-', 'build/code-object-cache-capacity-').replace('build/definition-set-a-seed-medium-r1','build/code-object-cache-seed-medium-r1')
marker="exec(compile(raw, str(source), 'exec'), dict(__name__='__main__', __file__=__file__))"
assert script.count(marker)==1
replacement='''
a=raw.index('fork=json.loads')
b=raw.index('truth=ElfTruth.read',a)
raw=raw[:a]+"""S.FORK=ROOT/'build/code-object-cache-card-r3/ready-instrument.json'
instrument=json.loads(S.FORK.read_text())
world=next(w for w in instrument['worlds'] if w['role']=='candidate')
binary=ROOT/world['binary']['path']
assert R.bind(binary)['sha256']==world['binary']['sha256']
assert R.bind(medium)['sha256']=='97c29c4d5c766d9c44d83e9616dcf3c59bae52693c3af2c5cad630d4ac7f2577'
"""+raw[b:]
exec(compile(raw, str(source), 'exec'), dict(__name__='__main__', __file__=__file__))
'''
script=script.replace(marker,replacement)
exec(compile(script,str(source),'exec'),dict(__name__='__main__',__file__=__file__))
