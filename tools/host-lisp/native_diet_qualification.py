"""Reuse the established lane/GC instruments on the native-diet fourth Seed.

Predecessor: the Set-A Final medium (Runtime identical to the accepted world;
the stager does not affect prompt lanes or GC). Candidate: the r5 Seed medium.
"""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
kind=sys.argv.pop(1)
names={'instrument':'ready-instrument','lanes':'native-lanes','gc':'gc-equal','vm':'vm-lanes'}
assert kind in names
source=ROOT/f'build/index-crc-r1/{names[kind]}.py'
raw=source.read_text()
for old,new in {
    'build/storage-owner-r2/ready-instrument.json':'build/definition-set-a-r3/ready-instrument.json',
    'build/storage-owner-ready-instrument-r2b/xemu':'build/definition-set-a-auth-ready-instrument-r1/xemu',
    'build/index-crc-ready-instrument-r1b':'build/native-diet-ready-instrument-r2',
    'build/storage-owner-final-medium-r2':'build/definition-set-a-final-medium-r1',
    "'storage-owner-final-medium-r2'":"'definition-set-a-final-medium-r1'",
    'build/index-crc-seed-medium-r1':'build/native-diet-seed-medium-r5',
    "'index-crc-seed-medium-r1'":"'native-diet-seed-medium-r5'",
    'build/index-crc-r1/ready-instrument.json':'build/native-diet-r4/ready-instrument.json',
    'build/index-crc-native-':'build/native-diet-s4-native-',
    'build/index-crc-gc-equal-':'build/native-diet-s4-gc-equal-',
    'build/index-crc-seed-vm-lanes-r1':'build/native-diet-s4-vm-lanes-r1',
    'build/index-crc-product-r1-preflight':'build/native-diet-product-r4-preflight',
    "authority='4cf5a2f9'":"authority='4e3bdafe'",
}.items():raw=raw.replace(old,new)
raw=raw.replace('HERE=Path(__file__).resolve().parent',"HERE=ROOT/'build/native-diet-r4'")
if kind=='instrument':
    # The diet card changes nothing before _start/vm_callprim/input_take, so
    # the rebound observer source can equal its parent. Admit exactly that
    # case: an empty source delta only when cpu65.c is provably unchanged.
    # An empty delta is only admissible when the candidate world the observer
    # is bound to is the baseline world in every observed coordinate. Without
    # this, candidate-versus-baseline was never compared at all: the existing
    # assert above only relates baseline to its prior instrument.
    inner_old="assert sorted(p for p in changed_files if not p.startswith('build/objs/'))==['xemu/cpu65.c']"
    inner_new=("assert sorted(p for p in changed_files if not p.startswith('build/objs/'))=="
               "(['xemu/cpu65.c'] if changed!=cpu else [])\n"
               "if changed==cpu:\n"
               "    assert all(candidate[k]==baseline[k] for k in\n"
               "        ('entry','paused_pc','entry_code','main','signature','vm_callprim')), \\\n"
               "        'empty observer source delta with a drifted candidate world'")
    assert raw.count('changes={\n')==1
    raw=raw.replace('changes={\n','changes={\n '+repr(inner_old)+':'+repr(inner_new)+',\n',1)
needle="exec(compile(raw,str(source),'exec'),dict(__name__='__main__',__file__=__file__))"
if needle in raw:
    raw=raw.replace(needle,"raw=raw.replace('HERE=Path(__file__).resolve().parent',\"HERE=ROOT/'build/native-diet-r4'\")\n"+needle)
exec(compile(raw,str(source),'exec'),dict(__name__='__main__',__file__=__file__))
