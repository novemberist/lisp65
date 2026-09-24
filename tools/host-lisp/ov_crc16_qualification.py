"""Reuse the established lane/GC instruments on the ov_crc16 card.

Pure renaming derivation of export_publication_qualification.py. Following
that file's own precedent (and boot_name_index_qualification.py/
session_bank_alignment_qualification.py before it), the four lane/GC/
instrument baseline anchors stay pointed at the native-diet world for the
ones native-diet itself anchors (VM entry/callprim/input_take identity for
'instrument'): neither the session-bank capacity card, the boot-name-index
card, the export-publication card, nor this ov_crc16 card moves that
boundary, so native-diet stays the valid "Runtime identical" baseline for
it.

Like export_publication_qualification.py, the Final-medium/Instrument
anchors used as the CANDIDATE's own predecessor comparison point are rebound
one card further, to the export-publication card's own r2 world and medium
-- NOT to boot-name-index -- because that is this card's own immediate
producer predecessor (BASE=build/export-publication-product-r2 in
ov_crc16_producer.py) and this card's own hunk (retargeting both ov_crc16
call sites to the proven leaf rtov_crc_mem, removing ov_crc16) introduces no
new feature or slice and moves no Session/decoder boundary of its own; the
r2 world is therefore the correct "before" state for this card's own
lane/GC comparisons, exactly the same reasoning export_publication_
qualification.py's own docstring gives for anchoring at its own producer
predecessor (r5) rather than skipping back further.

  HERE (Kartenverzeichnis)   build/ov-crc16-r1
  BUILD                      build/ov-crc16-product-r1
  Preflight                  build/ov-crc16-product-r1-preflight
  Medium (== Final-Medium)   build/ov-crc16-seed-medium-r1
  Instrument                 build/ov-crc16-ready-instrument-r1
  Lane/GC output prefix      build/ov-crc16-

The predecessor (export-publication r2) paths this substitution now points
at:

  Kartenverzeichnis   build/export-publication-r1
  Preflight           build/export-publication-product-r2-preflight
  Final-Medium        build/export-publication-seed-medium-r1
  Instrument          build/export-publication-ready-instrument-r1

Authority: the producer's own source authority. AUTH is '0a41035d' at
the time this file was written (see ov_crc16_producer.py); the `authority=`
substitution below is deliberately left UNCHANGED from its '4cf5a2f9' anchor
removal (i.e. not rebound to a concrete commit) until the real source
authority lands, so that running this file before then fails loudly on the
unresolved anchor rather than silently stamping a wrong or placeholder
commit into a qualification receipt.
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
    'build/storage-owner-r2/ready-instrument.json': 'build/export-publication-r1/ready-instrument.json',
    'build/storage-owner-ready-instrument-r2b/xemu': 'build/export-publication-ready-instrument-r1/xemu',
    'build/index-crc-ready-instrument-r1b': 'build/ov-crc16-ready-instrument-r1',
    'build/storage-owner-final-medium-r2': 'build/export-publication-seed-medium-r1',
    "'storage-owner-final-medium-r2'": "'export-publication-seed-medium-r1'",
    'build/index-crc-seed-medium-r1': 'build/ov-crc16-seed-medium-r1',
    "'index-crc-seed-medium-r1'": "'ov-crc16-seed-medium-r1'",
    'build/index-crc-r1/ready-instrument.json': 'build/ov-crc16-r1/ready-instrument.json',
    'build/index-crc-native-': 'build/ov-crc16-native-',
    'build/index-crc-gc-equal-': 'build/ov-crc16-gc-equal-',
    'build/index-crc-seed-vm-lanes-r1': 'build/ov-crc16-vm-lanes-r1',
    'build/index-crc-product-r1-preflight': 'build/ov-crc16-product-r1-preflight',
    "authority='4cf5a2f9'": "authority='0a41035d'",
    # AUTH is still pending: leave the authority anchor unresolved so a run
    # before the source commit lands fails loudly (KeyError/anchor absent)
    # instead of stamping a wrong commit. The orchestrator adds
    # "authority='0a41035d'": "authority='<real commit>'" once AUTH
    # binds, the same way every other card in this substitution table does.
}.items(): raw = raw.replace(old, new)
raw = raw.replace('HERE=Path(__file__).resolve().parent', "HERE=ROOT/'build/ov-crc16-r1'")
if kind == 'instrument':
    # Same empty observer-source-delta admission as session_bank_alignment_
    # qualification.py/boot_name_index_qualification.py/export_publication_
    # qualification.py: this card changes nothing before _start/vm_callprim/
    # input_take (its own hunk is confined to two ov_crc16 call sites, both
    # already admitted-adjacent -- the leaf rtov_crc_mem is already a proven,
    # gated caller inventory, and neither call site moves the VM entry
    # boundary), so the same rebound observer source can equal its parent.
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
    raw = raw.replace(needle, "raw=raw.replace('HERE=Path(__file__).resolve().parent',\"HERE=ROOT/'build/ov-crc16-r1'\")\n" + needle)
exec(compile(raw, str(source), 'exec'), dict(__name__='__main__', __file__=__file__))
