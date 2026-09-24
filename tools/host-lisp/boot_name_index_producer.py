"""Boot-time name index card: command admission, then one Seed.

Derived like the native-diet/placement producer from the accepted producer
template. The predecessor world is the accepted native-diet product (ELF
a5c17af55dfb0a219d48550f135e0bf590d2f6beb6b6bc94733efaee3717ecfb), whose
generated sources are copied unchanged; only the commissioned hunks since the
native-diet closure are applied: the Bank-5 transient-owner static bounds
(c2_platform_dma.c), the resident driver dispatch and invalidation
(c2_product_runtime.c/.h), the boot-only decoder phases 10a/10b sharing one
owner in the v2 decoder body (scripts/c2-stream-v2-decoder.c/.h) and the
exported symbol constructor used by phase 10b (symbol.c/.h).

Shape C (two boot-only decoder phases, each its own translation unit, sharing
one Bank-5 transient owner declared in c2_platform_dma.c and driven/
invalidated from c2_product_runtime.c) is the only shape this card admits.
The manifest free floor is rebound from 8576 to 374 bytes after the owner is
carved out of the Bank-5 free tail. All of that analysis lives in the
impl/differential/batching/admission/preflight receipts bound below; this
producer only composes and admits the source population, it does not repeat
the analysis.

Unlike the v1 decoder (already rebased once, by the native-diet card, into
config/native-diet-native/), the v2 decoder is the file that changes here.
The v2 decoder's own predecessor content is NOT byte-identical to the pristine
2.3.0 public authority: it had already drifted between that authority and the
diet card's own AUTH by unrelated `v2_roots_offset` changes never pulled into
this product's materialized projection. That drift is irrelevant here because
the commissioned hunk is a pure append onto the end of the file (a new
`#if C2_STREAM_V2_PHASE == 16 || == 17` block); it projects cleanly onto the
pristine authority regardless, and it is that pristine-plus-hunk text -- not
the live tree's `scripts/c2-stream-v2-decoder.c` -- that is the successor
projection, exactly as the native-diet card treated the v1 decoder. The two
new phase wrapper translation units (10a, 10b) are two-line `#define
C2_STREAM_V2_PHASE n` / `#include "c2-stream-v2-decoder.c"` files, admitted
into the generated-product-sources population and closure the same way the
existing `c2-stream-v2-phase-11a.c` wrapper already is -- no hunk projection
of their own, since they are brand new files, not commissioned diffs of an
existing predecessor.

The Lisp plane is the accepted native-diet plane, copied byte for byte.
Merely running the command probe never consumes the Seed budget.

World history (this card was parked at the fourth Seed, Session overlay bank
full; see the r1-r4 note on OUT_PREFLIGHT below for the link/post-link
halts this card itself sealed). r5 resumes it on the accepted Session-bank
capacity world (build/session-bank-alignment-product-r1, budget 1/1/1,
docs/planning/session-bank-capacity-final-report.md) as predecessor instead
of the diet world: that world already carries this card's own Bank-5 floor
rebind (374, "linker-floor-carried") and, orthogonally, its own commissioned
payload-alignment narrowing (256 -> 32, src/vm_runtime_overlay.c) -- a
Runtime file this card never touches, carried through untouched. Rebinding
the predecessor changes three things from the r4 producer: (1) the Bank-5
floor is no longer rebound here -- the predecessor already carries it, so
write_scripts() only injects the two slice records into otherwise-identical
linker scripts (see the "predecessor already carries the floor" note below);
(2) src/symbol.c is no longer a hunk-tracked member -- the guard commit
0ed9e98d (source authority AUTH, below) committed the feature-conditional
`sym_create`/`new_symbol` split directly, and the capacity predecessor's own
resolved profile already records exactly that committed content as its
input, so the file compiles from the tree as is, with no projection and no
profile()-tracked "change"; only the -D flag differs, handled by
admit_feature_define() as before; (3) source_gate()'s expected population
gains src/vm_runtime_overlay.c -- the capacity card's own commissioned
member, carried through this world unchanged, not this card's.
"""
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT/'build/index-crc-r1/product-card.py'
HERE = ROOT/'build/boot-name-index-r1'
PREDECESSOR_PREFLIGHT = ROOT/'build/session-bank-alignment-product-r1-preflight'
# The r1 world was a null world: its profile never carried the feature define
# and its link never carried the two phase records, so nothing behind
# LISP65_C2_BOOT_NAME_INDEX or .lisp65_rt_c2d_10a/10b reached the ELF.  The
# r2 world halted at the link: the slices referenced the static mapped facade
# `c2_dma_read_or_abort` across translation units.  The r3 world linked and
# passed the price, then halted in the post-link chain: the resident head
# reader left the E000 window by `jmp` into the seam instead of a fixed
# vector.  r4 (authority 53148bea, head reader in ordinary text) fixed that
# but parked at the fourth Seed: the Session overlay bank was full on the
# diet world. r5 is r4's replacement, resumed on the accepted Session-bank
# capacity world (predecessor rebound, see PREDECESSOR_PREFLIGHT/BASE/
# BASE_PREFLIGHT below); r1, r2, r3 and r4 stay exactly as they were sealed.
OUT_PREFLIGHT = ROOT/'build/boot-name-index-product-r5-preflight'
BUILD = ROOT/'build/boot-name-index-product-r5'
FEATURE = 'LISP65_C2_BOOT_NAME_INDEX'
# Product-header slot pins the tool's dynamic slot base must reproduce.
SLOT_PINS = (('LISP65_C2_PHASE_10A_SLOT', 0), ('LISP65_C2_PHASE_10B_SLOT', 1))
# Filled by register_slices() and consumed by the feature-wiring receipt.
WIRING = {}
# The guard commit 0ed9e98d (below) is the last commit to touch any member of
# this card's own source population (it edited src/symbol.c/.h so that the
# feature-off object stays byte-identical to the diet card's private
# new_symbol); the index card's source authority therefore moved from
# 53148bea to 0ed9e98d, even though this card commissions no new hunk of its
# own here. DIFF_BASE is unaffected -- it is still the pre-index-card native
# diet commit that every hunk below is projected against.
AUTH = '0ed9e98d'
DIFF_BASE = '4e3bdafe'
# Compiled/hunk-tracked members: appear in the predecessor's resolved profile
# via their generated-product-sources copy and drive the profile()/allowed
# "changes" population. src/symbol.c is deliberately NOT one of these any
# more: the capacity predecessor's own resolved profile already records the
# guard commit's committed content (0ed9e98d) as its input for src/symbol.c
# directly (no generated copy), so the file is neither hunk-projected nor
# profile()-"changed" here -- only the -D flag differs (admit_feature_define).
SOURCES = ('src/c2_platform_dma.c', 'src/c2_product_runtime.c')
# Header-only commissioned members: part of the exact source_gate population,
# but never appear as resolved-profile.txt input_sha256 lines, so they never
# enter the profile() "changes" bookkeeping.
HEADERS = ('src/c2_product_runtime.h', 'src/symbol.h')
# Carried unchanged from the capacity predecessor: not this card's own
# member, but git diff DIFF_BASE reports it (the capacity card's own
# commissioned hunk), so source_gate()'s expected population must include it
# or the gate would read it as an uncommissioned source-population drift.
CAPACITY_CARRIED = ('src/vm_runtime_overlay.c',)
# src/symbol.c: reported by git diff DIFF_BASE (the guard commit touched it)
# and part of the exact source_gate population, but -- like HEADERS -- never
# tracked by profile() as a "changed" compiled member (see SOURCES comment).
CARRIED_SOURCE = ('src/symbol.c',)
DECODER = 'scripts/c2-stream-v2-decoder.c'
DECODER_H = 'scripts/c2-stream-v2-decoder.h'
WRAPPERS = ('scripts/c2-stream-v2-phase-10a.c', 'scripts/c2-stream-v2-phase-10b.c')
SUCCESSOR_CLOSURE = 'config/boot-name-index-native/include-closure.json'
SUCCESSOR_CLOSURE_SHA = '2681fb3e89deb5c70138e1cae6a7e5c00b575a211cf5b3e07d7bf5072debc572'
PREDECESSOR_DECODER = 'config/c2-v230-public-native/includes/c2-stream-v2-decoder.c'
SUCCESSOR_DECODER = 'config/boot-name-index-native/includes/c2-stream-v2-decoder.c'
PREDECESSOR_DECODER_H = 'config/c2-v230-public-native/includes/c2-stream-v2-decoder.h'
SUCCESSOR_DECODER_H = 'config/boot-name-index-native/includes/c2-stream-v2-decoder.h'
PROBES = ('build/boot-name-index-impl-r1/receipt.json',
          'build/boot-name-index-impl-r1/differential/receipt.json',
          'build/boot-name-index-impl-r1/batching-receipt.json',
          'build/boot-name-index-admission-r1/receipt.json',
          'build/boot-name-index-preflight-r1/replay.json')


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('producer template population drift: '+old)
    return text.replace(old, new, 1)


def add_feature(text):
    """Return a resolved profile whose single feature row also carries the
    card's one new product feature.

    The define is placed BEFORE the inherited sequence, never after it: the
    single-link producer re-derives its own argument list as "every feature
    that is not automatically folded, then the folded tail" (liveness, input
    capture/hybrid, recovery quiescence, the symbol22 latch, the F011 cold
    read).  A new explicit feature appended behind that tail would no longer
    close to the bound population and the producer's own feature gate would
    reject the world."""
    lines = text.splitlines()
    rows = [i for i, line in enumerate(lines) if line.startswith('feature_defines=')]
    if len(rows) != 1:
        raise ValueError('feature authority absent or ambiguous')
    index = rows[0]
    features = lines[index].split('=', 1)[1].split(',')
    if not features or '' in features or len(features) != len(set(features)):
        raise ValueError('inherited feature population is empty or duplicated')
    if FEATURE in features:
        raise ValueError('feature already bound in the predecessor profile')
    lines[index] = 'feature_defines='+','.join([FEATURE]+features)
    return '\n'.join(lines)+'\n'


def feature_row(text):
    """Return the single feature row of a resolved profile."""
    rows = [line for line in text.splitlines()
            if line.startswith('feature_defines=')]
    if len(rows) != 1:
        raise ValueError('feature authority absent or ambiguous')
    return rows[0]


add_feature.row = feature_row


def bind_features(R, predecessor):
    """Bind the successor feature expectation the whole chain reads back.

    R.A.bound_features() asserts the bound profile against
    R.A.expected_features(); the compiler-consumed parity gate then proves
    every one of those features occurs exactly once in the real command.  So
    the new define has to be installed in both places or neither."""
    inherited = R.A.features(predecessor)
    if 'feature' in WIRING and R.A.expected_features() == (FEATURE,)+tuple(inherited):
        return R.A.expected_features()
    if FEATURE in inherited:
        raise ValueError('feature already bound in the predecessor profile')
    expected = (FEATURE,)+tuple(inherited)
    # Only the reader the product link consults is rebound, and only after
    # configure() has finished installing the inherited chain's own readers:
    # nothing about the predecessor's feature activation decisions changes.
    R.A.expected_features = lambda: expected
    if R.A.expected_features() != expected:
        raise ValueError('successor feature expectation not installed')
    WIRING['feature'] = dict(name=FEATURE, inherited_count=len(inherited),
                             successor_count=len(expected), position=0)
    return expected


def header_slot_pins():
    """Read the two product-header slot pins the resident driver dispatches on."""
    header = (ROOT/'src/c2_product_runtime.h').read_text()
    pins = {}
    for name, offset in SLOT_PINS:
        found = re.search(r'^#define '+name+r' (\d+)u$', header, re.M)
        if not found:
            raise ValueError('product header slot pin absent: '+name)
        pins[name] = dict(value=int(found[1]), offset=offset)
    return pins


def slot_pin_gate():
    """The catalog slot the producer derived and the slot the resident driver
    compiles against must be the same number, otherwise c2_overlay_call()
    dispatches on some other record.  Fail closed."""
    slices = WIRING.get('slices')
    if not slices:
        raise ValueError('slice registration receipt missing')
    base = slices['slot_base']
    pins = header_slot_pins()
    rows = {name: dict(header=row['value'], derived=base+row['offset'])
            for name, row in pins.items()}
    mismatch = {name: row for name, row in rows.items()
                if row['header'] != row['derived']}
    slices['slot_pins'] = rows
    if mismatch:
        raise ValueError(
            'product header slot pins disagree with the derived catalog tail: '
            +repr(mismatch)+'; correct src/c2_product_runtime.h to '
            +', '.join(f'{name} {row["derived"]}u' for name, row in rows.items()))
    return rows


def inject_slice_sections(text):
    """Allocate the two boot-only decoder records in the derived substitution
    linker script.

    This card's world does not render c2-substitution.ld from the live tool
    generator: the storage-owner producer derives all four linker scripts as a
    text transform of the accepted predecessor's scripts, so a record added to
    C2_DECODER_SLICES never reaches the script by itself.  The four line
    families the generator would have produced for a decoder record (output
    section, start/end symbols, entry symbol, stack-safe window assertion) are
    therefore inserted here, in the generator's own order -- directly behind
    the last inherited decoder record -- plus the pairwise NOCROSSREFS row the
    private disk member carries for every other runtime section."""
    slices = WIRING.get('slices')
    if not slices:
        raise ValueError('slice registration receipt missing')
    anchor = slices['anchor_record']
    rows = slices['rows']
    added = []

    def insert_after(text, anchor_line, additions):
        if text.count(anchor_line) != 1:
            raise ValueError('derived linker script shape differs: '+anchor_line)
        added.extend(additions)
        return text.replace(anchor_line, anchor_line+''.join(additions), 1)

    text = insert_after(
        text, '        .lisp65_rt_c2d_'+anchor+' { KEEP(*(.lisp65_rt_c2d_'+anchor+')) }\n',
        ['        .lisp65_rt_c2d_'+name+' { KEEP(*(.lisp65_rt_c2d_'+name+')) }\n'
         for name, _entry in rows])
    text = insert_after(
        text, '__lisp65_rt_c2d_'+anchor+'_start = ADDR(.lisp65_rt_c2d_'+anchor
        + '); __lisp65_rt_c2d_'+anchor+'_end = ADDR(.lisp65_rt_c2d_'+anchor
        + ') + SIZEOF(.lisp65_rt_c2d_'+anchor+');\n',
        ['__lisp65_rt_c2d_'+name+'_start = ADDR(.lisp65_rt_c2d_'+name
         + '); __lisp65_rt_c2d_'+name+'_end = ADDR(.lisp65_rt_c2d_'+name
         + ') + SIZEOF(.lisp65_rt_c2d_'+name+');\n' for name, _entry in rows])
    text = insert_after(
        text, '__lisp65_rt_c2d_'+anchor+'_entry = '+slices['anchor_entry']+';\n',
        ['__lisp65_rt_c2d_'+name+'_entry = '+entry+';\n' for name, entry in rows])
    text = insert_after(
        text, 'ASSERT(SIZEOF(.lisp65_rt_c2d_'+anchor+') > 0 && SIZEOF(.lisp65_rt_c2d_'
        + anchor+') <= 1792 && __lisp65_rt_c2d_'+anchor+'_end <= '
        '__lisp65_workbench_runtime_overlay_limit, "C2 decoder phase '+anchor
        + ' exceeds its stack-safe window");\n',
        ['ASSERT(SIZEOF(.lisp65_rt_c2d_'+name+') > 0 && SIZEOF(.lisp65_rt_c2d_'
         + name+') <= 1792 && __lisp65_rt_c2d_'+name+'_end <= '
         '__lisp65_workbench_runtime_overlay_limit, "C2 decoder phase '+name
         + ' exceeds its stack-safe window");\n' for name, _entry in rows])
    # The private disk member's pairwise exclusion list is sorted by section
    # name, so 10a/10b belong directly behind the phase-10 row.
    exclusion = [line for line in text.splitlines(keepends=True)
                 if line.startswith('NOCROSSREFS(') and '.lisp65_rt_c2d_' in line]
    if exclusion:
        member = exclusion[0].split('(', 1)[1].split()[0]
        text = insert_after(
            text, 'NOCROSSREFS('+member+' .lisp65_rt_c2d_10)\n',
            ['NOCROSSREFS('+member+' .lisp65_rt_c2d_'+name+')\n'
             for name, _entry in rows])
    WIRING['linker_additions'] = [line.strip() for line in added]
    return text


def admit_feature_define(P):
    """Admit this card's one new feature define at the pre-compiler boundary.

    The storage-owner admission compares the complete -D population of the
    real command against the sealed public-2.3.0 definition list
    (config/c2-v230-public-native/manifest.json via
    symbol_layout_manifest.replace_definitions).  That list cannot know a
    product feature commissioned after 2.3.0, so a card that adds one has to
    admit it here -- exactly one name, with no value, proven present in the
    real command before it is taken out of the comparison.  The alternative is
    to extend the sealed manifest (and the sha256 pinned for it in
    config/storage-owner-manifest.json), which is an authority change, not a
    producer change."""
    gate = getattr(P, 'STORAGE_OWNER_CONSUMER_GATE', None)
    if gate is None:
        raise ValueError('storage-owner admission gate absent')
    original = gate.check
    if getattr(original, '_boot_name_index', False):
        return
    def check(*, target, compile_flags, link_flags, **rest):
        flag = '-D'+FEATURE
        if list(compile_flags).count(flag) != 1:
            raise ValueError('card feature define absent from the real command: '
                             +str(target))
        result = original(target=target,
                          compile_flags=[f for f in compile_flags if f != flag],
                          link_flags=link_flags, **rest)
        result['card_feature_definitions'] = [FEATURE]
        return result
    check._boot_name_index = True
    gate.check = check
    # The same admission re-derives the four expected linker scripts from the
    # owner base and compares the whole population byte for byte.  Its
    # expectation has to carry this card's two allocated records too, or the
    # script the card actually hands the linker would read as an
    # uncommissioned change.
    script = 'c2-substitution.ld'
    if script not in gate.expected:
        raise ValueError('storage admission expectation lacks the substitution script')
    gate.expected = dict(gate.expected)
    gate.expected[script] = inject_slice_sections(gate.expected[script])
    WIRING['admission'] = dict(admitted=[FEATURE],
                               authority='card-owned post-2.3.0 product feature',
                               linker_expectation=script)


def register_slices(P):
    """Opt into the two boot-only decoder records before any command, profile
    or linker script is constructed.

    The link tool's own opt-in does the whole selection: the two decoder rows
    (and therefore their linker output sections and start/end/entry symbols),
    the tail append onto the live Session catalog, and the slot base it
    exposes.  This producer only records the outcome and proves the invariants
    the card depends on: every inherited record keeps its slot, the catalog
    stays dense, and each population grows by exactly two."""
    if 'slices' in WIRING:
        return
    baseline = list(P.SESSION_SLICE_SPECS)
    anchor_record, anchor_entry = P.C2_DECODER_SLICES[-1]
    decoder_rows = [tuple(row) for row in P.BOOT_NAME_INDEX_ROWS]
    if [name for name, _entry in decoder_rows] != ['10a', '10b']:
        raise ValueError('boot-name-index decoder rows drifted: '+repr(decoder_rows))
    before = dict(decoder_slices=len(P.C2_DECODER_SLICES),
                  session_specs=len(baseline),
                  unique_slices=P.UNIQUE_SLICE_COUNT)
    P.configure_boot_name_index_slices()
    specs = list(P.SESSION_SLICE_SPECS)
    base = P.BOOT_NAME_INDEX_SLOT_BASE
    if not P.BOOT_NAME_INDEX_SLICES or base is None:
        raise ValueError('the tool did not register the two decoder records')
    if specs[:len(baseline)] != baseline:
        raise ValueError('the tail append moved or dropped an inherited record')
    if [spec.split(':')[1] for spec in specs[len(baseline):]] != \
            ['c2-decode-10a', 'c2-decode-10b']:
        raise ValueError('the catalog tail is not the two boot-name-index records')
    if [int(spec.split(':', 1)[0]) for spec in specs] != list(range(len(specs))):
        raise ValueError('catalog is not dense after the tail append')
    if base != len(baseline):
        raise ValueError('slot base is not the live catalog tail: '+repr(base))
    if len(specs) > P.LISP65_RUNTIME_OVERLAY_HARD_MAX_SLICES:
        raise ValueError('Session catalog exceeds its hard maximum')
    after = dict(decoder_slices=len(P.C2_DECODER_SLICES),
                 session_specs=len(specs),
                 unique_slices=P.UNIQUE_SLICE_COUNT)
    for key, value in after.items():
        if value != before[key]+2:
            raise ValueError('catalog population did not grow by exactly two: '
                             +key+' '+repr((before[key], value)))
    WIRING['slices'] = dict(slot_base=base, before=before, after=after,
                            specs=specs[-2:], rows=decoder_rows,
                            anchor_record=anchor_record, anchor_entry=anchor_entry,
                            hard_max=P.LISP65_RUNTIME_OVERLAY_HARD_MAX_SLICES)
    # A Seed must never be constructed against a driver that dispatches on a
    # different slot.  The command probe runs the same gate after the command
    # world exists, so a mismatch is recorded there before it halts.
    if sys.argv[1:] == ['seed']:
        slot_pin_gate()
    print('boot-name-index slices: slots', base, base+1, 'session',
          before['session_specs'], '->', after['session_specs'], 'unique',
          before['unique_slices'], '->', after['unique_slices'])


def bind(path):
    import hashlib
    data = path.read_bytes()
    return dict(path=str(path.relative_to(ROOT)), bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest())


def composition():
    """The admitted member population and its off-product evidence."""
    return dict(
        status='PASS: BOOT-TIME NAME INDEX SOURCE COMPOSITION, NOT NATIVE ACCEPTANCE',
        authority=AUTH, diff_base=DIFF_BASE,
        members=[
            dict(name='decoder-shape-c-shared-body', source=DECODER, projected_text=0),
            dict(name='phase-10a-queue-writer-v2-bnx-post', source=WRAPPERS[0],
                 projected_text=125),
            dict(name='phase-10b-index-probe-v2-bnx-find', source=WRAPPERS[1],
                 projected_text=348),
            dict(name='resident-driver-dispatch-and-invalidate',
                 source='src/c2_product_runtime.c', projected_text=226),
            dict(name='symbol-new-symbol-exported-sym-create', source='src/symbol.c',
                 projected_text=51),
            dict(name='bank5-transient-owner-static-bounds', source='src/c2_platform_dma.c',
                 projected_text=0)],
        projected_text_total=750,
        shape='C',
        bank5=dict(index_offset=56960, index_bytes=2048, queue_offset=59008,
                   queue_bytes=6144, header_offset=65152, header_bytes=10,
                   floor_after_rebinding=374,
                   floor_rebound_by='this card (r4), carried unchanged by the '
                                     'session-bank-alignment predecessor (r5)'),
        claim='paired non-LTO object projections; the Seed link decides',
        evidence=[bind(ROOT/p) for p in PROBES])


def successor_decoder_ok():
    """The successor v2 decoder is exactly the pristine 2.3.0 bytes plus the
    commissioned append hunk -- for both the body and its header. The v2
    decoder's live tree content is not used directly: it carries unrelated
    drift against the pristine authority that this product never consumed."""
    import re

    def project(predecessor_text_path, diff_path):
        text = (ROOT/predecessor_text_path).read_text()
        diff = subprocess.check_output(['git', 'diff', DIFF_BASE, '--', diff_path],
                                       cwd=ROOT, text=True)
        parts = re.split(r'(^@@[^\n]*\n)', diff, flags=re.M)
        if len(parts) < 3:
            raise ValueError('commissioned decoder member absent: '+diff_path)
        for i in range(2, len(parts), 2):
            lines = parts[i].splitlines(keepends=True)
            before = ''.join(l[1:] for l in lines if l[:1] in (' ', '-'))
            after = ''.join(l[1:] for l in lines if l[:1] in (' ', '+'))
            if text.count(before) != 1:
                raise ValueError('decoder hunk does not project onto the 2.3.0 authority: '
                                  +diff_path)
            text = text.replace(before, after, 1)
        return text

    if (ROOT/SUCCESSOR_DECODER).read_text() != project(PREDECESSOR_DECODER, DECODER):
        raise ValueError('successor decoder is not the commissioned projection')
    if (ROOT/SUCCESSOR_DECODER_H).read_text() != project(PREDECESSOR_DECODER_H, DECODER_H):
        raise ValueError('successor decoder header is not the commissioned projection')
    for wrapper in WRAPPERS:
        if not subprocess.check_output(['git', 'diff', DIFF_BASE, '--', wrapper],
                                       cwd=ROOT, text=True):
            raise ValueError('commissioned wrapper member absent: '+wrapper)
    if bind(ROOT/SUCCESSOR_CLOSURE)['sha256'] != SUCCESSOR_CLOSURE_SHA:
        raise ValueError('successor include authority drift')


def verify_wiring():
    """Prove, against the world the card just constructed, that the feature
    define and the two phase records are actually carried.  Four independent
    checks: the bound/resolved profile, every real compiler command, the
    generated substitution linker script, and the overlay catalog."""
    ready = json.loads((OUT_PREFLIGHT/'command-ready.json').read_text())
    proof_path = ROOT/ready['proof']['path']
    proof = json.loads(proof_path.read_text())
    world = Path(proof['output'])
    checks = {}

    # (a) The bound feature profile and the world's resolved profile both
    # carry the define in their single feature row.
    rows = {}
    for label, path in (('bound_feature_profile', OUT_PREFLIGHT/'bound-feature-profile.txt'),
                        ('resolved_profile', world/'resolved-profile.txt')):
        found = [line for line in path.read_text().splitlines()
                 if line.startswith('feature_defines=')]
        if len(found) != 1:
            raise ValueError('feature authority absent or ambiguous: '+label)
        features = found[0].split('=', 1)[1].split(',')
        if FEATURE not in features:
            raise ValueError('feature define absent from '+label)
        rows[label] = features
        checks[label] = dict(path=str(path.relative_to(ROOT)),
                             feature_count=len(features),
                             index=features.index(FEATURE))
    if rows['bound_feature_profile'] != rows['resolved_profile']:
        raise ValueError('bound and world profile feature populations differ')

    # (b) Every real compiler command carries the define exactly once.
    commands = [command for command in proof['commands'] if '-c' in command]
    if not commands:
        raise ValueError('command receipt carries no compiler command')
    for command in commands:
        if list(command).count('-D'+FEATURE) != 1:
            raise ValueError('feature define escaped a real compiler command: '
                             +command[command.index('-c')+1])
    wrappers = sorted(command[command.index('-c')+1] for command in commands
                      if Path(command[command.index('-c')+1]).name
                      in ('c2-stream-v2-phase-10a.c', 'c2-stream-v2-phase-10b.c'))
    if len(wrappers) != 2:
        raise ValueError('phase 10a/10b wrapper translation units not compiled')
    checks['compiler_commands'] = dict(
        total=len(proof['commands']), compiler=len(commands),
        carrying_define=len(commands), wrappers=wrappers,
        receipt=str(proof_path.relative_to(ROOT)))

    # (c) The generated substitution linker script allocates both records.
    script = world/'c2-substitution.ld'
    text = script.read_text()
    sections = {}
    for name in ('10a', '10b'):
        needed = ['.lisp65_rt_c2d_'+name,
                  '__lisp65_rt_c2d_'+name+'_start',
                  '__lisp65_rt_c2d_'+name+'_end',
                  '__lisp65_rt_c2d_'+name+'_entry']
        missing = [item for item in needed if item not in text]
        if missing:
            raise ValueError('linker script omits boot-name-index record '
                             +name+': '+repr(missing))
        sections[name] = {item: text.count(item) for item in needed}
    checks['linker_script'] = dict(path=str(script.relative_to(ROOT)),
                                  records=sections)

    # (d) The overlay catalog carries the two records and the world profile
    # reports the grown slice population.
    slices = WIRING.get('slices')
    if not slices:
        raise ValueError('slice registration receipt missing')
    profile_counts = {}
    for key in ('slice_count_unique', 'session_family_slice_count',
                'boot_family_slice_count'):
        found = [line.split('=', 1)[1] for line in
                 (world/'resolved-profile.txt').read_text().splitlines()
                 if line.startswith(key+'=')]
        if len(found) != 1:
            raise ValueError('catalog population row absent: '+key)
        profile_counts[key] = int(found[0])
    if profile_counts['slice_count_unique'] != slices['after']['unique_slices']:
        raise ValueError('world profile slice count differs from the catalog: '
                         +repr(profile_counts))
    checks['catalog'] = dict(slot_base=slices['slot_base'],
                             specs=slices['specs'],
                             before=slices['before'], after=slices['after'],
                             hard_max=slices['hard_max'],
                             profile_counts=profile_counts)

    pins = {name: dict(header=row['value'], derived=slices['slot_base']+row['offset'])
            for name, row in header_slot_pins().items()}
    blocked = [name for name, row in pins.items() if row['header'] != row['derived']]
    checks['slot_pins'] = dict(pins=pins, blocked=blocked,
                               header='src/c2_product_runtime.h')
    value = dict(status=('PASS: FEATURE DEFINE AND PHASE RECORDS CARRIED BY THE '
                         'CONSTRUCTED WORLD; NO COMPILER OR LINK EXECUTED')
                 if not blocked else
                 ('BLOCKED: WIRING CARRIED, PRODUCT-HEADER SLOT PINS STILL '
                  'DISAGREE WITH THE DERIVED CATALOG TAIL'),
                 feature=WIRING.get('feature'), authority=AUTH,
                 world=str(world.relative_to(ROOT)), checks=checks,
                 driver=bind(Path(__file__).resolve()))
    HERE.mkdir(parents=True, exist_ok=True)
    (HERE/'feature-wiring.json').write_text(
        json.dumps(value, indent=2, sort_keys=True)+'\n')
    print('feature-wiring proofs', FEATURE,
          'profile_features', checks['bound_feature_profile']['feature_count'],
          'compiler_commands', len(commands),
          'linker_records', len(sections),
          'catalog', profile_counts)
    # Recorded first, then fail closed: the four wiring proofs above are the
    # evidence this world needed, and the slot pin is the one prerequisite it
    # cannot satisfy by itself.
    slot_pin_gate()
    print('PASS: boot-name-index feature wiring and slot pins')


def main():
    if sys.argv[1:] not in (['command-probe'], ['seed']):
        raise SystemExit('command-probe | seed')
    if AUTH == 'AUTH_PENDING':
        raise SystemExit('bind AUTH to the commissioned source commit first')
    successor_decoder_ok()
    raw = TEMPLATE.read_text()
    # Rebind the include authority to the card's successor; the v1 decoder
    # rebasing done by native-diet-native stays as is.
    raw = replace_once(raw, "INC=prior['INC']",
        "INC=prior['INC'];INC.CLOSURE=ROOT/"+repr(SUCCESSOR_CLOSURE)
        +";INC.CLOSURE_SHA="+repr(SUCCESSOR_CLOSURE_SHA))
    # Opt into the two boot-only decoder records once the product's own append/
    # service ABI has been selected by configure() -- the slot base is derived
    # from that selection -- and still before any command, profile, catalog or
    # linker script is constructed by the command world.
    raw = replace_once(raw,
        "ig['original_configure']=g['configure']\ng['configure']=prior['configure']",
        "ig['original_configure']=g['configure']\n"
        "_configure_without_slices=prior['configure']\n"
        "def _configure_with_slices(*args,**kwargs):\n"
        "    result=_configure_without_slices(*args,**kwargs)\n"
        "    REGISTER_SLICES(P)\n"
        "    BIND_FEATURES(R,BASE/'wplto/resolved-profile.txt')\n"
        "    ADMIT_FEATURE(P)\n"
        "    return result\n"
        "g['configure']=_configure_with_slices")
    changed_names = '{'+','.join(repr(Path(p).name) for p in SOURCES)+'}'
    for old, new in {
        'HERE=Path(__file__).resolve().parent':
            "HERE=ROOT/'build/boot-name-index-r1';HERE.mkdir(parents=True,exist_ok=True)",
        "BASE=ROOT/'build/storage-owner-product-r2'":
            "BASE=ROOT/'build/session-bank-alignment-product-r1'",
        "BASE_PREFLIGHT=ROOT/'build/storage-owner-product-r2-preflight'":
            "BASE_PREFLIGHT=ROOT/'build/session-bank-alignment-product-r1-preflight'",
        "OUT=ROOT/'build/index-crc-product-r1-preflight'":
            "OUT=ROOT/"+repr(str(OUT_PREFLIGHT.relative_to(ROOT))),
        "BUILD=ROOT/'build/index-crc-product-r1'":
            "BUILD=ROOT/"+repr(str(BUILD.relative_to(ROOT))),
        "AUTH='4cf5a2f9'": f"AUTH='{AUTH}'",
        "CHANGED=('src/vm.c',)": 'CHANGED='+repr(SOURCES),
        "name='index-crc-and-final-sector-length'": "name='boot-name-index-placement'",
        "allowed=set(proof['changed_members'])|{'vm.c'}":
            "allowed=set(proof['changed_members'])|"+changed_names,
        # The card's one new product feature enters the bound profile here and
        # in profile(); BIND_FEATURES installs the matching successor
        # expectation that R.A.bound_features() and the compiler-consumed
        # parity gate both read back.
        "    target=OUT/'bound-feature-profile.txt'\n"
        "    if not target.exists(): shutil.copyfile(BASE/'wplto/resolved-profile.txt',target)\n":
            "    target=OUT/'bound-feature-profile.txt'\n"
            "    text=ADD_FEATURE((BASE/'wplto/resolved-profile.txt').read_text())\n"
            "    if not target.exists(): target.write_text(text)\n"
            # profile() rewrites this same file with the successor input
            # digests, so only the feature row is re-checked here.
            "    if ADD_FEATURE.row(target.read_text())!=ADD_FEATURE.row(text):\n"
            "        raise ValueError('bound feature profile drift')\n",
        "    R.C.BOUND_PROFILE.write_text('\\n'.join(lines)+'\\n')\n"
        "    return dict(changes=changes,successor=R.bind(R.C.BOUND_PROFILE))":
            "    R.C.BOUND_PROFILE.write_text(ADD_FEATURE('\\n'.join(lines)+'\\n'))\n"
            "    if R.A.features(R.C.BOUND_PROFILE)!=R.A.expected_features():\n"
            "        raise ValueError('bound successor feature population drift')\n"
            "    return dict(changes=changes,successor=R.bind(R.C.BOUND_PROFILE),\n"
            "                features=list(R.A.bound_features()))",
    }.items():
        raw = replace_once(raw, old, new)
    # The manifest's Bank-5 free floor (374) was rebound by this card's own
    # r4 commission and the capacity predecessor (BASE) already carries that
    # rebind in its own linker scripts (build/session-bank-alignment-r1/
    # linker-floor-carried.json): BASE/wplto's four scripts already assert
    # the 374 floor, not the diet card's 8576. So unlike r4 (which had to
    # re-derive the floor rebind against a stale-floor predecessor), r5's
    # write_scripts() only has to inject this card's own two boot-only
    # decoder slice records into the predecessor's otherwise-untouched
    # scripts -- no floor line is expected to change here.
    raw = replace_once(raw,
        "def write_scripts(out,*args,**kwargs):\n"
        "    for name in g['LINK'].FILES:\n"
        "        target=out/name;target.parent.mkdir(parents=True,exist_ok=True)\n"
        "        target.write_bytes((BASE/'wplto'/name).read_bytes())\n",
        "def write_scripts(out,*args,**kwargs):\n"
        "    files=g['LINK'].FILES\n"
        "    predecessor={name:(BASE/'wplto'/name).read_text() for name in files}\n"
        "    derived=dict(predecessor)\n"
        "    derived['c2-substitution.ld']=INJECT_SLICES(derived['c2-substitution.ld'])\n"
        "    changed=[name for name in files if derived[name]!=predecessor[name]]\n"
        "    if changed!=['c2-substitution.ld']:\n"
        "        raise ValueError('linker scripts differ from the capacity predecessor '\n"
        "            'outside the injected slice records: '+repr(changed))\n"
        "    for name in files:\n"
        "        target=out/name;target.parent.mkdir(parents=True,exist_ok=True)\n"
        "        target.write_text(derived[name])\n"
        "    HERE.mkdir(parents=True,exist_ok=True)\n"
        "    receipt=HERE/'linker-scripts-carried-slices-injected.json'\n"
        "    text=json.dumps(dict(\n"
        "        status='PASS: LINKER SCRIPTS IDENTICAL TO THE SESSION-BANK-ALIGNMENT '\n"
        "               'PREDECESSOR, ONLY THE TWO BOOT-NAME-INDEX SLICE RECORDS INJECTED',\n"
        "        predecessor=str(BASE.relative_to(ROOT)),changed_files=changed,\n"
        "        additions=WIRING.get('linker_additions',[]),\n"
        "        predecessor_sha256={name:hashlib.sha256(predecessor[name].encode()).hexdigest()\n"
        "                           for name in files},\n"
        "        candidate_sha256={name:hashlib.sha256(derived[name].encode()).hexdigest()\n"
        "                         for name in files}),indent=2,sort_keys=True)+'\\n'\n"
        "    if receipt.exists() and receipt.read_text()!=text:\n"
        "        raise ValueError('linker scripts receipt overwrite: '+str(receipt))\n"
        "    if not receipt.exists(): receipt.write_text(text)\n")
    start = raw.index('def source_gate():')
    end = raw.index('\ndef prepare_inputs()', start)
    raw = raw[:start]+f'''def source_gate():
    # expected = this card's own hunk-tracked/header members, plus symbol.c
    # (committed by the guard commit, carried as is -- see CARRIED_SOURCE)
    # and src/vm_runtime_overlay.c (the capacity predecessor's own
    # commissioned member, carried through this world unchanged -- see
    # CAPACITY_CARRIED). Both are reported by `git diff {DIFF_BASE}` but are
    # not this card's own compiled-object "changes"; only the population
    # here has to match, not the profile()/allowed accounting.
    expected={(set(SOURCES)|set(HEADERS)|set(CARRIED_SOURCE)|set(CAPACITY_CARRIED))!r}
    changed=set(subprocess.check_output(['git','diff','{DIFF_BASE}','--name-only',
        '--','src','lib'],cwd=ROOT,text=True).splitlines())
    if changed!=expected: raise ValueError('uncommissioned source population: '+repr(changed))
    if not subprocess.check_output(['git','diff','{DIFF_BASE}','--','{DECODER}'],cwd=ROOT,text=True):
        raise ValueError('commissioned decoder member absent')
    if not subprocess.check_output(['git','diff','{DIFF_BASE}','--','{DECODER_H}'],cwd=ROOT,text=True):
        raise ValueError('commissioned decoder header member absent')
    for wrapper in {WRAPPERS!r}:
        if not subprocess.check_output(['git','diff','{DIFF_BASE}','--',wrapper],cwd=ROOT,text=True):
            raise ValueError('commissioned wrapper member absent: '+wrapper)
    comp=R.C.load(HERE/'composition.json')
    if comp['authority']!=AUTH or comp['diff_base']!='{DIFF_BASE}':
        raise ValueError('composition authority drift')
    for row in comp['evidence']:
        if R.bind(ROOT/row['path'])!=row: raise ValueError('probe evidence drift: '+row['path'])
    return dict(status='PASS: BOOT-TIME NAME INDEX SOURCE COMPOSITION, NOT NATIVE ACCEPTANCE',
        sources=[R.bind(ROOT/p) for p in sorted(changed)]+[R.bind(ROOT/'{DECODER}'),
            R.bind(ROOT/'{DECODER_H}')]+[R.bind(ROOT/p) for p in {WRAPPERS!r}],
        composition=R.bind(HERE/'composition.json'),
        plane=R.bind(PLANE/'set-a-plane-receipt.json'),
        producer_template=R.bind(ROOT/'build/index-crc-r1/product-card.py'))
'''+raw[end:]
    start = raw.index('    # Apply only the commissioned diff')
    end = raw.index('    derived,proof=', start)
    raw = raw[:start]+f'''    # Preserve every consumed producer adaptation of the accepted native-diet
    # world; apply only the commissioned hunks, with exact context, since
    # {DIFF_BASE}. The v2 decoder body and header both carry pure-append hunks
    # onto their carried-forward (pristine) generated copies.
    import re
    for name,source in (('c2_platform_dma.c','src/c2_platform_dma.c'),
                        ('c2_product_runtime.c','src/c2_product_runtime.c'),
                        ('c2-stream-v2-decoder.c','{DECODER}'),
                        ('c2-stream-v2-decoder.h','{DECODER_H}')):
        target=generated/name;text=target.read_text()
        diff=subprocess.check_output(['git','diff','{DIFF_BASE}','--',source],cwd=ROOT,text=True)
        (out/(name+'.boot-name-index.patch')).write_text(diff)
        parts=re.split(r'(^@@[^\\n]*\\n)',diff,flags=re.M)
        if len(parts)<3: raise ValueError('commissioned hunk absent: '+source)
        for i in range(2,len(parts),2):
            lines=parts[i].splitlines(keepends=True)
            before=''.join(l[1:] for l in lines if l[:1] in (' ','-'))
            after=''.join(l[1:] for l in lines if l[:1] in (' ','+'))
            if text.count(before)!=1: raise ValueError('source projection hunk mismatch: '+name)
            text=text.replace(before,after,1)
        target.write_text(text)
        if source.startswith('src/'): mapping[(ROOT/source).resolve()]=target
'''+raw[end:]
    # Native-only card: the Lisp plane is the accepted native-diet plane, byte
    # for byte. Only the paired derivation's stale-table control needs a
    # changed plane; here identity of the whole plane tree is the proof that
    # the copied generated data is already the successor's data. Everything
    # else that derive() executes is reproduced below: the delivery CRC
    # tables and the twelve executable delivery-word mutations, so this
    # card's world-data-consumers receipt carries the same consumer contract
    # as the native-diet receipt (tables + mutations_rejected), minus that
    # one control.
    raw = replace_once(raw,
        "    derived,proof=R.W.DATA.derive(BASE_PREFLIGHT/'setup-owned/static-plane/narrow-static',PLANE,\n"
        "        BASE/'wplto/generated-product-sources',out/'world-data-derivation',R.bind)",
        "    derived,proof=identical_plane(generated,out/'world-data-derivation')")
    raw = replace_once(raw, 'def materialize(out):', """def identical_plane(generated,work):
    base=BASE_PREFLIGHT/'setup-owned/static-plane/narrow-static'
    rows=[]
    left=sorted(p.relative_to(base) for p in base.rglob('*') if p.is_file())
    right=sorted(p.relative_to(PLANE) for p in PLANE.rglob('*') if p.is_file())
    if left!=right: raise ValueError('plane file population differs from native-diet plane')
    for rel in left:
        if (base/rel).read_bytes()!=(PLANE/rel).read_bytes():
            raise ValueError('plane byte drift: '+str(rel))
        rows.append(R.bind(PLANE/rel))
    # Mandatory consumer contract, independent of any derived exception set:
    # every .short delivery word in the Phase-02a owner must be load bearing.
    # Flipping one bit of any of them has to make crc_tables() fall.
    import re
    work.mkdir(parents=True,exist_ok=True)
    owner=generated/'c2-stream-phase-02a.c'
    tables=R.W.DATA.crc_tables(owner,PLANE)
    pattern=r'(?<=\\.short )0x[0-9a-f]{4}'
    words=list(re.finditer(pattern,owner.read_text()))
    if len(words)!=sum(map(len,tables.values())):
        raise ValueError('delivery word population differs from the CRC tables')
    mutations=[];mutant=work/'mutant-owner.c'
    for index,word in enumerate(words):
        text=owner.read_text()
        mutant.write_text(text[:word.start()]+f'0x{int(word[0],16)^1:04x}'+text[word.end():])
        try:R.W.DATA.crc_tables(mutant,PLANE)
        except AssertionError:mutations.append(f'wrong-delivery-word-{index}')
        else:raise AssertionError('wrong CRC word survived')
    return {},dict(status='PASS: PLANE BYTE-IDENTICAL TO NATIVE-DIET; NO DATA DERIVATION',
        changed_members=[],files=len(rows),population=rows,
        tables=tables,mutations_rejected=mutations,
        generator=R.bind(Path(R.W.DATA.V6.__file__)),
        inputs=[R.bind(PLANE/p) for p in
                ('product/substitution-artifacts.json','product/product-shelf-v4-direct.bin',
                 'v6-semantics/initial.c2d-v6.bin')])

def materialize(out):""")
    # Unlike r4, no override of the default "predecessor input drift" check is
    # needed here: every profile() row this card's members touch is now
    # either a generated-product-sources path (tautologically checked against
    # its own recorded digest, same as any untouched compiled source) or, for
    # src/symbol.c, a plain src/ path whose recorded digest (in BASE's own
    # resolved profile) already IS the guard commit's committed content --
    # the same content the current tree carries -- so the template's default
    # `R.bind(before)['sha256']!=digest` check already passes unmodified.
    raw = replace_once(raw, "        if name=='vm.c': raise ValueError('data derivation selected native code')",
        "        if name in ('c2_platform_dma.c','c2_product_runtime.c',\n"
        "                    'c2-stream-v2-decoder.c','c2-stream-v2-decoder.h'):\n"
        "            raise ValueError('data derivation selected native code')")
    HERE.mkdir(parents=True, exist_ok=True)
    comp = HERE/'composition.json'
    text = json.dumps(composition(), indent=2, sort_keys=True)+'\n'
    if comp.exists() and comp.read_text() != text:
        raise ValueError('composition overwrite: '+str(comp))
    if not comp.exists():
        comp.write_text(text)
    plane_source = (PREDECESSOR_PREFLIGHT/'setup-owned/static-plane/narrow-static/'
                    'set-a-plane-receipt.json')
    plane = HERE/'plane.json'
    if plane.exists() and plane.read_bytes() != plane_source.read_bytes():
        raise ValueError('plane input overwrite: '+str(plane))
    if not plane.exists():
        plane.write_bytes(plane_source.read_bytes())
    # The Lisp plane is unchanged: copy the accepted configured setup whole.
    setup = OUT_PREFLIGHT/'setup-owned'
    if not setup.exists():
        OUT_PREFLIGHT.mkdir(parents=True, exist_ok=True)
        shutil.copytree(PREDECESSOR_PREFLIGHT/'setup-owned', setup)
    exec(compile(raw, str(Path(__file__).resolve()), 'exec'),
         dict(__name__='__main__', __file__=str(Path(__file__).resolve()),
              ADD_FEATURE=add_feature, BIND_FEATURES=bind_features,
              REGISTER_SLICES=register_slices, ADMIT_FEATURE=admit_feature_define,
              INJECT_SLICES=inject_slice_sections, WIRING=WIRING))
    # Fail-closed: the world just constructed must carry both halves of the
    # wiring.  A world that carries neither is the r1 null world again.  The
    # media, price and qualification adapters only capture the card code
    # through a replaced `exec` and construct no world; the proof belongs to
    # the run that does.
    import builtins
    if exec is builtins.exec:
        verify_wiring()


if __name__ == '__main__':
    main()
