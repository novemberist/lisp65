"""Reuse complete CPU/DMA/IRQ closure for the charged Set-A pair."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
source=ROOT/'build/transient-retirement-r2/gc-closure.py'
raw=source.read_text().replace('==29557','==13192')
raw=raw.replace('build/transient-retirement-gc-charges-{role}-1','build/definition-set-a-auth-gc-charges-{role}-0')
needle="exec(compile(raw,str(p),'exec'),dict(__name__='__main__',__file__=__file__))"
assert raw.count(needle)==1
raw=raw.replace(needle,"raw=raw.replace('H=Path(__file__).resolve().parent;ROOT=H.parents[1]',\"ROOT=Path.cwd();H=ROOT/'build/definition-set-a-r3'\")\n"+needle)
exec(compile(raw,str(source),'exec'),dict(__name__='__main__',__file__=str(source)))
