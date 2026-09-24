"""Apply the existing no-tolerance GC phase decomposition to this Seed pair."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
p=ROOT/'build/index-crc-r1/phase-decompose.py';raw=p.read_text()
raw=raw.replace('H=Path(__file__).resolve().parent',"H=ROOT/'build/definition-set-a-r3'")
raw=raw.replace('build/index-crc-phase-replay-seed-r1b','build/definition-set-a-auth-lane-gc-charges-r1')
raw=raw.replace('build/index-crc-native-natural-seed-r1','build/definition-set-a-auth-native-natural-r1')
exec(compile(raw,str(p),'exec'),dict(__name__='__main__',__file__=str(p)))
