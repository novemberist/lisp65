"""Reuse the established lane/GC instruments on the session-bank-alignment Seed.

Predecessor: the native-diet Final medium (Runtime identical to the
accepted world). Candidate: the session-bank-alignment Seed medium.
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
    'build/storage-owner-r2/ready-instrument.json':'build/native-diet-r4/ready-instrument.json',
    'build/storage-owner-ready-instrument-r2b/xemu':'build/native-diet-ready-instrument-r2/xemu',
    'build/index-crc-ready-instrument-r1b':'build/session-bank-alignment-ready-instrument-r1',
    'build/storage-owner-final-medium-r2':'build/native-diet-seed-medium-r5',
    "'storage-owner-final-medium-r2'":"'native-diet-seed-medium-r5'",
    'build/index-crc-seed-medium-r1':'build/session-bank-alignment-seed-medium-r1',
    "'index-crc-seed-medium-r1'":"'session-bank-alignment-seed-medium-r1'",
    'build/index-crc-r1/ready-instrument.json':'build/session-bank-alignment-r1/ready-instrument.json',
    'build/index-crc-native-':'build/session-bank-alignment-native-',
    'build/index-crc-gc-equal-':'build/session-bank-alignment-gc-equal-',
    'build/index-crc-seed-vm-lanes-r1':'build/session-bank-alignment-vm-lanes-r1',
    'build/index-crc-product-r1-preflight':'build/session-bank-alignment-product-r1-preflight',
    "authority='4cf5a2f9'":"authority='0ed9e98d'",
}.items():raw=raw.replace(old,new)
raw=raw.replace('HERE=Path(__file__).resolve().parent',"HERE=ROOT/'build/session-bank-alignment-r1'")
if kind=='instrument':
    # This card changes nothing before _start/vm_callprim/input_take, so the
    # rebound observer source can equal its parent -- same reasoning as the
    # native-diet card's own instrument adapter. Admit exactly that case: an
    # empty source delta only when cpu65.c is provably unchanged, and only
    # when the candidate world is the baseline world in every observed
    # coordinate; otherwise an empty observer delta with a drifted candidate
    # world would have compared nothing at all.
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
    raw=raw.replace(needle,"raw=raw.replace('HERE=Path(__file__).resolve().parent',\"HERE=ROOT/'build/session-bank-alignment-r1'\")\n"+needle)
exec(compile(raw,str(source),'exec'),dict(__name__='__main__',__file__=__file__))
