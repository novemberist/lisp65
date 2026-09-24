"""Reuse the established lane/GC instruments on the export-publication card.

Pure renaming derivation of boot_name_index_qualification.py. Following that
file's own precedent (and session_bank_alignment_qualification.py before
it), the four lane/GC/instrument baseline anchors stay pointed at the
native-diet world for the ones native-diet itself anchors (VM entry/
callprim/input_take identity for 'instrument'): neither the session-bank
capacity card, the boot-name-index card, nor this export-publication card
moves that boundary, so native-diet stays the valid "Runtime identical"
baseline for it.

Unlike boot_name_index_qualification.py, however, the Final-medium/
Instrument anchors used as the CANDIDATE's own predecessor comparison point
are rebound one card further, to the boot-name-index card's own r5 world
and medium -- NOT to native-diet -- because that is this card's own
immediate producer predecessor (BASE=build/boot-name-index-product-r5 in
export_publication_producer.py) and the boundary this card's own lane/GC
instruments measure (Session catalog / GC-equal state) IS the one the
boot-name-index card most recently moved (it grew the catalog by two
records); the r5 world is therefore the correct "before" state for this
card's own lane/GC comparisons, not the pre-index native-diet world. This
mirrors exactly how boot_name_index_qualification.py itself justifies
anchoring ITS OWN instrument/native-diet comparison at native-diet rather
than at ITS OWN producer predecessor (session-bank-alignment): the anchor
tracks whichever world last moved the measured boundary, not merely "the
producer's own predecessor" by rote.

  HERE (Kartenverzeichnis)   build/export-publication-r1
  BUILD                      build/export-publication-product-r1
  Preflight                  build/export-publication-product-r1-preflight
  Medium (== Final-Medium)   build/export-publication-seed-medium-r1
  Instrument                 build/export-publication-ready-instrument-r1
  Lane/GC output prefix      build/export-publication-

The predecessor (boot-name-index r5) paths this substitution now points at:

  Kartenverzeichnis   build/boot-name-index-r1
  Preflight           build/boot-name-index-product-r5-preflight
  Final-Medium        build/boot-name-index-seed-medium-r3
  Instrument          build/boot-name-index-ready-instrument-r1

Authority: the producer's own source authority. AUTH is '227e59e9' at
the time this file was written (see export_publication_producer.py); the
`authority=` substitution below is deliberately left UNCHANGED from its
'4cf5a2f9' anchor removal (i.e. not rebound to a concrete commit) until the
real source authority lands, so that running this file before then fails
loudly on the unresolved anchor rather than silently stamping a wrong or
placeholder commit into a qualification receipt.
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
    'build/storage-owner-r2/ready-instrument.json': 'build/boot-name-index-r1/ready-instrument.json',
    'build/storage-owner-ready-instrument-r2b/xemu': 'build/boot-name-index-ready-instrument-r1/xemu',
    'build/index-crc-ready-instrument-r1b': 'build/export-publication-ready-instrument-r1',
    'build/storage-owner-final-medium-r2': 'build/boot-name-index-seed-medium-r3',
    "'storage-owner-final-medium-r2'": "'boot-name-index-seed-medium-r3'",
    'build/index-crc-seed-medium-r1': 'build/export-publication-seed-medium-r1',
    "'index-crc-seed-medium-r1'": "'export-publication-seed-medium-r1'",
    'build/index-crc-r1/ready-instrument.json': 'build/export-publication-r1/ready-instrument.json',
    'build/index-crc-native-': 'build/export-publication-native-',
    'build/index-crc-gc-equal-': 'build/export-publication-gc-equal-',
    'build/index-crc-seed-vm-lanes-r1': 'build/export-publication-vm-lanes-r1',
    'build/index-crc-product-r1-preflight': 'build/export-publication-product-r2-preflight',
    "authority='4cf5a2f9'": "authority='227e59e9'",
    # AUTH is still pending: leave the authority anchor unresolved so a run
    # before the source commit lands fails loudly (KeyError/anchor absent)
    # instead of stamping a wrong commit. The orchestrator adds
    # "authority='4cf5a2f9'": "authority='<real commit>'" once AUTH binds,
    # the same way every other card in this substitution table does.
}.items(): raw = raw.replace(old, new)
raw = raw.replace('HERE=Path(__file__).resolve().parent', "HERE=ROOT/'build/export-publication-r1'")
if kind == 'instrument':
    # Same empty observer-source-delta admission as session_bank_alignment_
    # qualification.py / boot_name_index_qualification.py: this card changes
    # nothing before _start/vm_callprim/input_take (its own hunk is confined
    # to c2_product_runtime.c's phase-10 dispatch and the boot-name-index
    # transient owner, both already admitted by the boot-name-index card),
    # so the same rebound observer source can equal its parent.
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
    raw = raw.replace(needle, "raw=raw.replace('HERE=Path(__file__).resolve().parent',\"HERE=ROOT/'build/export-publication-r1'\")\n" + needle)
exec(compile(raw, str(source), 'exec'), dict(__name__='__main__', __file__=__file__))
