"""Reuse the established lane/GC instruments on the boot-name-index card.

Pure renaming derivation of native_diet_qualification.py.  As in
session_bank_alignment_qualification.py (the pattern this substitution table
follows), the four lane/GC/instrument baseline anchors stay pointed at the
native-diet world, not at whatever this card's own immediate producer
predecessor is: these instruments measure a boundary (VM entry/callprim/
input_take identity for 'instrument'; lane/GC equivalence otherwise) that
neither the boot-name-index card nor the session-bank-alignment card moves,
so native-diet stays the valid "Runtime identical" baseline for them even
though r5's own producer predecessor is now the accepted Session-bank
capacity world (build/session-bank-alignment-product-r1); the candidate is
still this card's own Seed medium.

The `old` (left-hand) side of every substitution below is unchanged from
native_diet_qualification.py: both scripts read the exact same immutable
template at `build/index-crc-r1/{name}.py`, so the anchors that template
provides do not move.  Only the `new` (right-hand) side changes, to the
boot-name-index card's own paths:

  HERE (Kartenverzeichnis)   build/boot-name-index-r1
  BUILD                      build/boot-name-index-product-r5
  Preflight                  build/boot-name-index-product-r5-preflight
  Medium (== Final-Medium)   build/boot-name-index-seed-medium-r3
  Instrument                 build/boot-name-index-ready-instrument-r1
  Lane/GC output prefix      build/boot-name-index-

The predecessor (native-diet) paths this substitution now points at --
unchanged from r4 (see the docstring note above for why these stay anchored
at native-diet rather than moving to the r5 producer predecessor):

  Kartenverzeichnis   build/native-diet-r4
  Preflight           build/native-diet-product-r4-preflight
  Final-Medium        build/native-diet-seed-medium-r5 (Seed-Medium doubles
                       as the diet card's Final-Medium; there is no separate
                       native-diet-final-medium directory)
  Instrument          build/native-diet-ready-instrument-r2

Authority: the producer's own source authority, 0ed9e98d at r5 (see
boot_name_index_producer.py AUTH for why it moved there from 53148bea).
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
kind = sys.argv.pop(1)
names = {'instrument': 'ready-instrument', 'lanes': 'native-lanes',
         'gc': 'gc-equal', 'vm': 'vm-lanes'}
assert kind in names
source = ROOT/f'build/index-crc-r1/{names[kind]}.py'
raw = source.read_text()
for old, new in {
    'build/storage-owner-r2/ready-instrument.json': 'build/native-diet-r4/ready-instrument.json',
    'build/storage-owner-ready-instrument-r2b/xemu': 'build/native-diet-ready-instrument-r2/xemu',
    'build/index-crc-ready-instrument-r1b': 'build/boot-name-index-ready-instrument-r1',
    'build/storage-owner-final-medium-r2': 'build/native-diet-seed-medium-r5',
    "'storage-owner-final-medium-r2'": "'native-diet-seed-medium-r5'",
    'build/index-crc-seed-medium-r1': 'build/boot-name-index-seed-medium-r3',
    "'index-crc-seed-medium-r1'": "'boot-name-index-seed-medium-r3'",
    'build/index-crc-r1/ready-instrument.json': 'build/boot-name-index-r1/ready-instrument.json',
    'build/index-crc-native-': 'build/boot-name-index-native-',
    'build/index-crc-gc-equal-': 'build/boot-name-index-gc-equal-',
    'build/index-crc-seed-vm-lanes-r1': 'build/boot-name-index-vm-lanes-r1',
    'build/index-crc-product-r1-preflight': 'build/boot-name-index-product-r5-preflight',
    "authority='4cf5a2f9'": "authority='0ed9e98d'",
}.items(): raw = raw.replace(old, new)
raw = raw.replace('HERE=Path(__file__).resolve().parent', "HERE=ROOT/'build/boot-name-index-r1'")
if kind == 'instrument':
    # The diet-card rebinding kept these five identity keys checked; the
    # boot-name-index card changes nothing before that same boundary either
    # (the split is a decoder phase 10/10b change and a Bank-5 transient
    # owner, not a VM entry/callprim/input_take rebind), so the same empty
    # observer-source-delta admission carries forward unchanged.
    inner_old = "assert sorted(p for p in changed_files if not p.startswith('build/objs/'))==['xemu/cpu65.c']"
    inner_new = ("assert sorted(p for p in changed_files if not p.startswith('build/objs/'))=="
                 "(['xemu/cpu65.c'] if changed!=cpu else [])\n"
                 "if changed==cpu:\n"
                 "    assert all(candidate[k]==baseline[k] for k in\n"
                 "        ('entry','paused_pc','entry_code','main','signature','vm_callprim')), \\\n"
                 "        'empty observer source delta with a drifted candidate world'")
    assert raw.count('changes={\n') == 1
    raw = raw.replace('changes={\n', 'changes={\n ' + repr(inner_old) + ':' + repr(inner_new) + ',\n', 1)
needle = "exec(compile(raw,str(source),'exec'),dict(__name__='__main__',__file__=__file__))"
if needle in raw:
    raw = raw.replace(needle, "raw=raw.replace('HERE=Path(__file__).resolve().parent',\"HERE=ROOT/'build/boot-name-index-r1'\")\n" + needle)
exec(compile(raw, str(source), 'exec'), dict(__name__='__main__', __file__=__file__))
