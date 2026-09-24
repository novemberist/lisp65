"""Witness each lane GC through native entry/return PC and SP."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
p=ROOT/'build/resolver-owner-r1/lane-gc-charges.py'
raw=p.read_text()
anchor="source=source.replace(\"cycle-observer.json\", \"cycle-observer-r2.json\")"
assert raw.count(anchor)==1
extra="\n".join("source=source.replace("+repr(a)+","+repr(b)+")" for a,b in {
 'build/resolver-owner-r1/ready-instrument.json':'build/definition-set-a-r3/ready-instrument.json',
 'build/index-crc-final-medium-r1':'build/transient-retirement-final-medium-r1',
 'build/resolver-owner-seed-medium-r1':'build/definition-set-a-seed-medium-r2',
}.items())
extra += "\nsource=source.replace(\"raw=p.read_text()\", \"raw=p.read_text().replace('HERE=Path(__file__).resolve().parent', \\\"HERE=ROOT/'build/definition-set-a-r3'\\\")\")"
raw=raw.replace(anchor,anchor+'\n'+extra)
raw=raw.replace("'build/resolver-owner-lane-gc-charges-'", "'build/definition-set-a-auth-lane-gc-charges-'")
exec(compile(raw,str(p),'exec'),dict(__name__='__main__',__file__=str(p)))
