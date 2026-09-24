"""Export publication card: command admission, then one Seed.

Derived like session_bank_alignment_producer.py (no product feature, no new
Session/decoder slices) rather than boot_name_index_producer.py's shape: the
predecessor world for THIS card is build/boot-name-index-product-r5, and r5's
own resolved profile and generated substitution linker script already carry
everything boot_name_index_producer.py had to admit by hand --

  - feature_defines= already lists LISP65_C2_BOOT_NAME_INDEX first (verified
    against build/boot-name-index-product-r5/wplto/resolved-profile.txt);
  - c2-substitution.ld already allocates .lisp65_rt_c2d_10a/10b (output
    sections, start/end/entry symbols, stack-safe-window ASSERTs and the
    paired NOCROSSREFS rows -- verified against
    build/boot-name-index-product-r5/wplto/c2-substitution.ld).

So this producer carries NO add_feature/bind_features/admit_feature_define
and NO register_slices/inject_slice_sections/SLOT_PINS/slot_pin_gate: adding
either again would raise 'feature already bound in the predecessor profile'
or duplicate slice records the predecessor script already has. The include
authority is likewise NOT rebased to a new successor closure: this card
touches no decoder file, so INC.CLOSURE stays bound to the SAME closure r5
itself resumed under, config/boot-name-index-native/include-closure.json,
at its current (unchanged) sha256 -- there is no successor closure of this
card's own to rebase onto, unlike native-diet-native/boot-name-index-native.

Source population: this card's own commissioned member is exactly
src/c2_product_runtime.c (SOURCES); it carries no HEADERS entry of its own
(HEADERS=()) and no carried/capacity members from an intermediate world --
r5 already folded the session-bank-alignment capacity predecessor's own
carried member (src/vm_runtime_overlay.c) and the guard commit's
src/symbol.c into ITS OWN source population, so this card's source_gate()
expects exactly {'src/c2_product_runtime.c'}, nothing else.

Verified: r5's generated-product-sources copy of c2_product_runtime.c is
byte-identical to the pre-index-card diet copy (git show 4e3bdafe, the
boot-name-index card's own DIFF_BASE) PLUS exactly the boot-name-index hunks
(c2_boot_name_index_read/head_get/head_put/invalidate and the phase-10
collect/resolve alternation) -- i.e. diet copy + index hunks, as required.
This card's own commissioned hunk (still uncommitted -- source authority
pending) projects onto THAT SAME r5 generated copy, not onto a fresh copy of
the live src/ tree, exactly as boot_name_index_producer.py projected its own
hunk onto the pre-index-card diet copy.

Linker scripts (REVISED after the first command-probe halt): a plain byte
copy of BASE's (r5's) four scripts is NOT what the storage-owner admission
gate compares against. storage_owner_consumption.Admission.__init__ derives
its OWN `self.expected` fresh, as
`storage_owner_linker.transform(OWNER_BASE/'wplto' files, facade)` --
purely a function of the FIXED storage-owner baseline (OWNER_BASE, i.e.
build/storage-owner-product-r2, never this card's own BASE) plus the live
symbol_layout_manifest -- with NO knowledge of any card's slice injection.
boot_name_index_producer.py's own admit_feature_define() patches exactly
that gate's `expected['c2-substitution.ld']` via inject_slice_sections()
before r5's own probe compares candidate vs. expected; because that patch
lives in a per-process, per-probe-run object, it does not carry over to
this card's own fresh gate instance, so this card must patch it again for
its own run even though it introduces no NEW feature or slice.
write_scripts() below therefore: (1) re-derives the fixed baseline itself,
the same way the admission does (`storage_owner_linker.transform` from
OWNER_BASE + facade); (2) proves that baseline has ZERO deviation from the
true pre-injection predecessor (build/session-bank-alignment-product-r1/
wplto, r5's own BASE) -- r5's own docstring already established the Bank-5
floor is "carried", not rebound, so nothing here should differ; (3) applies
the SAME inject_slice_sections() (imported from boot_name_index_producer,
fed anchor_record='13' -- the tail of C2_DECODER_SLICES at the time r5
registered the two records, NOT the '10' phase the records are named after;
verified empirically, see below -- and rows=('10a','10b'), the same section
names, unchanged) to the derived c2-substitution.ld; (4) asserts
the result is byte-identical to r5's OWN four wplto scripts (proving the
re-derivation reproduces r5 exactly); (5) writes that result to `out`; and
(6) patches this run's own STORAGE_OWNER_CONSUMER_GATE.expected the same
way admit_feature_define() does, so the admission's independent comparison
sees the same injected text this card actually writes. Recorded in
linker-scripts-derived-identical-to-r5.json; ANY textual difference at any
of these steps is a hard failure, not merely logged.

AUTH is now bound: '227e59e9' (source authority commit; DIFF_BASE='5d63537b'
is HEAD immediately before it, per the coordinator's binding message).
Historical note: this producer was originally written with
AUTH='AUTH_PENDING'/DIFF_BASE='d1ff87d1'; only py_compile and a dry-run
import were possible at that time. The first command-probe after binding
AUTH halted in storage_owner_linker.verify() for exactly the write_scripts
gap this revision fixes.

Merely running the command probe never consumes the Seed budget.
"""
import json
from pathlib import Path
import shutil
import subprocess
import sys

# The Seed's own slice injection for .lisp65_rt_c2d_10a/10b is the exact
# text transform boot_name_index_producer.py already proved correct (see
# its inject_slice_sections()); this card reuses that function rather than
# re-deriving the same four line families, per the coordinator's
# instruction. Importing the module executes no top-level side effect
# (constants and function/class definitions only).
import boot_name_index_producer as INDEX_PRODUCER

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT/'build/index-crc-r1/product-card.py'
HERE = ROOT/'build/export-publication-r1'
PREDECESSOR_PREFLIGHT = ROOT/'build/boot-name-index-product-r5-preflight'
# World history: r1 (build/export-publication-product-r1[-preflight]) halted
# after the real link at the section inventory gate: "final section
# inventory red: ['section-count','section-name-set']; additional=
# ['.lisp65_rt_c2d_10a','.lisp65_rt_c2d_10b', .rela...]". Cause: the two
# boot-name-index slices are a RUNTIME opt-in of the link tool itself
# (P.configure_boot_name_index_slices(), invoked via
# boot_name_index_producer.register_slices()) that sets
# P.SESSION_SLICE_SPECS/UNIQUE_SLICE_COUNT and therefore the expected
# section inventory and the Session pack -- NOT predecessor/world state the
# link tool inherits from r5's own files. r5's own producer opted in via
# this exact call; this producer originally did not, so the link tool's own
# fresh process (this card's own, independent of r5's) still expected the
# pre-index catalog (53 specs/61 unique) while the linker script (correctly
# derived+injected, see write_scripts) already carried the two records --
# hence "additional" sections the tool's own inventory didn't expect. r2
# (below) adds REGISTER_SLICES(P)/ADMIT_FEATURE(P) to this card's own
# configure() wrapper, exactly like boot_name_index_producer.py's own
# _configure_with_slices, so THIS process's P also opts in once, growing
# 53->55 session specs / 61->63 unique slices, matching r5's own recorded
# growth exactly (build/boot-name-index-r1/feature-wiring.json). r1 stays
# parked as the halt; r1's own build/export-publication-r1/*.json write-once
# receipts were cleared before r2's own command-probe run since they record
# the pre-fix (uninjected-in-the-tool) state.
OUT_PREFLIGHT = ROOT/'build/export-publication-product-r2-preflight'
BUILD = ROOT/'build/export-publication-product-r2'
AUTH = '227e59e9'
# HEAD immediately before the commissioned source authority at the time this
# producer was written (`git rev-parse --short HEAD`). The orchestrator sets
# this to the commit immediately before the real source authority once the
# concurrent Opus agent's commit lands; every hunk below is projected
# against this commit's copy of src/c2_product_runtime.c.
DIFF_BASE = '5d63537b'
# Compiled/hunk-tracked member: the .c file is copied into the world's
# generated-product-sources population (from r5's own copy, not a fresh copy
# of the live tree -- see module docstring) and drives profile()/allowed.
SOURCES = ('src/c2_product_runtime.c',)
# This file's predecessor digest, in r5's own resolved profile, is keyed to
# r5's OWN generated-product-sources copy of the file (verified:
# build/boot-name-index-product-r5/wplto/resolved-profile.txt records
# input_sha256=.../generated-product-sources/c2_product_runtime.c:25165a5...,
# not a plain src/ path), so the template's default predecessor-input-drift
# check is tautologically satisfied against that same generated copy without
# needing an override -- exactly the "no override needed" case
# boot_name_index_producer.py documents for its own generated-copy members.
# PRIOR_BASE is bound anyway, at the coordinator's instruction, so that if a
# future member of this card's population is ever profile()-keyed to a plain
# src/ path instead (unlike c2_product_runtime.c today), the same projection
# convention used by session_bank_alignment_producer.py is already wired in;
# with today's single generated-path-keyed member it has no observable
# effect. Left for the orchestrator to re-verify once AUTH is bound and the
# real predecessor profile row for this world exists.
PRIOR_BASE = {'src/c2_product_runtime.c': DIFF_BASE}
# No HEADERS entry: this card edits no header of its own (unlike
# boot_name_index's c2_product_runtime.h/symbol.h or session_bank_alignment's
# symbol.h) -- r5 already carries every header pin this world depends on.
HEADERS = ()
# Unchanged from r5: this card touches no decoder file, so there is no
# successor closure of its own to rebase INC.CLOSURE onto. r5 itself resumed
# under this same closure (see boot_name_index_producer.py SUCCESSOR_CLOSURE)
# and this card carries it forward at its current, unchanged sha256.
SUCCESSOR_CLOSURE = 'config/boot-name-index-native/include-closure.json'
SUCCESSOR_CLOSURE_SHA = '2681fb3e89deb5c70138e1cae6a7e5c00b575a211cf5b3e07d7bf5072debc572'
# No PROBES yet: this card's own impl/differential/admission/preflight
# receipts (build/export-publication-impl-r1/...) do not exist until the
# source authority lands -- unlike boot_name_index_producer.py/
# session_bank_alignment_producer.py, which were written after their own
# probes existed. The orchestrator populates this once
# build/export-publication-impl-r1/differential/receipt.json (and any
# sibling probes) exist, the same way the seal binds that receipt
# prospectively (see export_publication_seal.py).
PROBES = ()


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('producer template population drift: '+old)
    return text.replace(old, new, 1)


def bind(path):
    import hashlib
    data = path.read_bytes()
    return dict(path=str(path.relative_to(ROOT)), bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest())


def register_and_admit(P):
    """r2 fix: opt this card's own (fresh) link-tool process into the two
    boot-name-index Session/decoder slices exactly like r5 did, then admit
    the inherited feature past the storage-owner gate.

    r1 halted after the real link at the section inventory gate
    ('additional=[.lisp65_rt_c2d_10a,.lisp65_rt_c2d_10b,...]') because the
    two slices are a RUNTIME opt-in of the link tool
    (P.configure_boot_name_index_slices(), which sets P.SESSION_SLICE_SPECS/
    P.UNIQUE_SLICE_COUNT and therefore the section inventory the tool
    expects and the Session pack it builds) -- not predecessor/world state
    this card inherits automatically. r5's own producer called exactly this
    opt-in via boot_name_index_producer.register_slices(); this card's own
    process never had, so its own P still expected the pre-index catalog
    (53 specs/61 unique) while the linker script (correctly derived+
    injected by write_scripts) already carried the two records.

    boot_name_index_producer.register_slices(P) is reused directly (not
    re-implemented): it is a stateless function of P's own default catalog
    (this card's own fresh process, not r5's), so calling it here grows
    53->55 session specs / 61->63 unique slices exactly as r5's own
    feature-wiring receipt recorded
    (build/boot-name-index-r1/feature-wiring.json: before
    session_specs=53/unique_slices=61, after 55/63), not a second,
    duplicating growth on top of an inherited 55/63 -- there is no such
    inherited in-memory state to double.

    boot_name_index_producer.admit_feature_define(P) is then reused for
    both halves it performs: stripping the inherited -D flag before the
    storage-owner compile-flags check (needed because that gate is also a
    fresh, per-process object with no memory of r5's own admission), and
    patching gate.expected['c2-substitution.ld'] via the SAME
    inject_slice_sections() call using the WIRING['slices'] register_slices
    just populated. write_scripts() below independently re-derives and
    OVERWRITES that same key with its own from-scratch computation (not an
    incremental edit on top of admit_feature_define's patch), so calling
    both is not a double injection: both converge on the identical text,
    proven byte-identical to r5 either way.

    No BIND_FEATURES(): this card binds no new feature expectation of its
    own -- LISP65_C2_BOOT_NAME_INDEX is already the predecessor's own bound
    feature_defines row, and bind_features() itself refuses
    ('feature already bound in the predecessor profile') if called on an
    already-carrying profile, which r5's is."""
    INDEX_PRODUCER.register_slices(P)
    INDEX_PRODUCER.admit_feature_define(P)


def slice_registration_receipt():
    """Write-once proof, independent of any real command, that this card's
    own registration reproduces r5's slice wiring exactly: same slot pins
    (LISP65_C2_PHASE_10A_SLOT/_10B_SLOT == 53/54 in src/c2_product_runtime.h,
    checked against the DERIVED catalog tail by
    boot_name_index_producer.slot_pin_gate()), same catalog growth, same
    unique-slice count -- comparable line for line against
    build/boot-name-index-r1/feature-wiring.json's own 'catalog'/'slot_pins'
    checks."""
    slices = INDEX_PRODUCER.WIRING.get('slices')
    if not slices:
        raise ValueError('slice registration receipt missing: register_slices did not run')
    pins = INDEX_PRODUCER.slot_pin_gate()
    HERE.mkdir(parents=True, exist_ok=True)
    receipt = HERE/'slice-registration.json'
    r5_expected = dict(slot_base=53, session_specs_before=53, session_specs_after=55,
                       unique_slices_before=61, unique_slices_after=63, hard_max=64)
    matches_r5 = dict(slot_base=slices['slot_base'] == r5_expected['slot_base'],
                      session_specs_after=slices['after']['session_specs'] == r5_expected['session_specs_after'],
                      unique_slices_after=slices['after']['unique_slices'] == r5_expected['unique_slices_after'])
    text = json.dumps(dict(
        status=('PASS: SLICE REGISTRATION REPRODUCES THE BOOT-NAME-INDEX-PRODUCT-R5 '
               'CATALOG GROWTH' if all(matches_r5.values()) else
               'BLOCKED: SLICE REGISTRATION DIFFERS FROM THE R5 REFERENCE'),
        slot_base=slices['slot_base'], rows=slices['rows'],
        anchor_record=slices['anchor_record'], anchor_entry=slices['anchor_entry'],
        before=slices['before'], after=slices['after'], hard_max=slices['hard_max'],
        slot_pins=pins, r5_reference=r5_expected, matches_r5_reference=matches_r5,
        r5_feature_wiring=str((ROOT/'build/boot-name-index-r1/feature-wiring.json').relative_to(ROOT)),
        ), indent=2, sort_keys=True)+'\n'
    if receipt.exists() and receipt.read_text() != text:
        raise ValueError('slice registration receipt overwrite: '+str(receipt))
    if not receipt.exists():
        receipt.write_text(text)
    if not all(matches_r5.values()):
        raise ValueError('slice registration differs from the r5 reference: '+repr(matches_r5))


def composition():
    """The admitted member population and its off-product evidence."""
    return dict(
        status='PASS: EXPORT PUBLICATION SOURCE COMPOSITION, NOT NATIVE ACCEPTANCE',
        authority=AUTH, diff_base=DIFF_BASE,
        members=[
            dict(name='export-publication-hunk', source='src/c2_product_runtime.c',
                 projected_text=None)],
        feature=None, new_slices=0, manifest_floor_changed=False,
        linker_scripts='byte-identical to the boot-name-index-product-r5 predecessor',
        claim='paired non-LTO object projections; the Seed link decides',
        evidence=[bind(ROOT/p) for p in PROBES])


def main():
    if sys.argv[1:] not in (['command-probe'], ['seed']):
        raise SystemExit('command-probe | seed')
    if AUTH == 'AUTH_PENDING':
        raise SystemExit('bind AUTH to the commissioned source commit first')
    raw = TEMPLATE.read_text()
    # No decoder change here: keep INC.CLOSURE pointed at the exact closure r5
    # itself resumed under (see SUCCESSOR_CLOSURE above) -- this is a rebind
    # to the SAME closure, not a rebase to a new successor tree.
    raw = replace_once(raw, "INC=prior['INC']",
        "INC=prior['INC'];INC.CLOSURE=ROOT/"+repr(SUCCESSOR_CLOSURE)
        +";INC.CLOSURE_SHA="+repr(SUCCESSOR_CLOSURE_SHA))
    # r2 fix: opt this card's own fresh link-tool process into the two
    # boot-name-index slices (REGISTER_SLICES) and re-admit the inherited
    # feature past this run's own fresh storage-owner gate (ADMIT_FEATURE),
    # both reused from boot_name_index_producer.py -- see
    # register_and_admit() docstring for why r1 halted without this and why
    # neither call duplicates r5's own (separate-process, in-memory-only)
    # registration. No BIND_FEATURES here: this card binds no new feature
    # expectation of its own (see register_and_admit() docstring).
    raw = replace_once(raw,
        "ig['original_configure']=g['configure']\ng['configure']=prior['configure']",
        "ig['original_configure']=g['configure']\n"
        "_configure_without_slices=prior['configure']\n"
        "def _configure_with_slices(*args,**kwargs):\n"
        "    result=_configure_without_slices(*args,**kwargs)\n"
        "    REGISTER_AND_ADMIT(P)\n"
        "    SLICE_RECEIPT()\n"
        "    return result\n"
        "g['configure']=_configure_with_slices")
    changed_names = '{'+','.join(repr(Path(p).name) for p in SOURCES)+'}'
    for old, new in {
        'HERE=Path(__file__).resolve().parent':
            "HERE=ROOT/'build/export-publication-r1';HERE.mkdir(parents=True,exist_ok=True)",
        "BASE=ROOT/'build/storage-owner-product-r2'":
            "BASE=ROOT/'build/boot-name-index-product-r5'",
        "BASE_PREFLIGHT=ROOT/'build/storage-owner-product-r2-preflight'":
            "BASE_PREFLIGHT=ROOT/"+repr(str(PREDECESSOR_PREFLIGHT.relative_to(ROOT))),
        "OUT=ROOT/'build/index-crc-product-r1-preflight'":
            "OUT=ROOT/"+repr(str(OUT_PREFLIGHT.relative_to(ROOT))),
        "BUILD=ROOT/'build/index-crc-product-r1'":
            "BUILD=ROOT/"+repr(str(BUILD.relative_to(ROOT))),
        "AUTH='4cf5a2f9'": f"AUTH='{AUTH}'",
        "CHANGED=('src/vm.c',)": 'CHANGED='+repr(SOURCES),
        "name='index-crc-and-final-sector-length'": "name='export-publication-placement'",
        "allowed=set(proof['changed_members'])|{'vm.c'}":
            "allowed=set(proof['changed_members'])|"+changed_names,
    }.items():
        raw = replace_once(raw, old, new)
    # Re-derive the fixed storage-owner baseline exactly the way the
    # admission gate does (from OWNER_BASE + facade, not from this card's own
    # BASE), prove it matches the true pre-injection predecessor with zero
    # deviation, inject the two boot-name-index slice records the same way
    # r5 did, prove the result is byte-identical to r5's own scripts, write
    # it, and keep the admission gate's own expectation in sync -- see the
    # module docstring for why each step is necessary.
    raw = replace_once(raw,
        "def write_scripts(out,*args,**kwargs):\n"
        "    for name in g['LINK'].FILES:\n"
        "        target=out/name;target.parent.mkdir(parents=True,exist_ok=True)\n"
        "        target.write_bytes((BASE/'wplto'/name).read_bytes())\n",
        "def write_scripts(out,*args,**kwargs):\n"
        "    files=g['LINK'].FILES\n"
        "    owner_source={name:(OWNER_BASE/'wplto'/name).read_text() for name in files}\n"
        "    facade=g['LINK'].facade_fixed_price(OWNER_BASE/'wplto')\n"
        "    derived=g['LINK'].transform(owner_source,facade)\n"
        "    pre_injection_ancestor=ROOT/'build/session-bank-alignment-product-r1'\n"
        "    pre_injection={name:(pre_injection_ancestor/'wplto'/name).read_text() for name in files}\n"
        "    pre_injection_changed=[name for name in files if derived[name]!=pre_injection[name]]\n"
        "    if pre_injection_changed:\n"
        "        raise ValueError('derived storage baseline drifted from the pre-injection '\n"
        "            'predecessor ahead of slice injection: '+repr(pre_injection_changed))\n"
        "    if not INJECT_SLICES_WIRING.get('slices'):\n"
        "        raise ValueError('slice registration missing ahead of injection: '\n"
        "            'REGISTER_AND_ADMIT(P) did not run during configure()')\n"
        "    injected=dict(derived)\n"
        "    injected['c2-substitution.ld']=INJECT_SLICES(injected['c2-substitution.ld'])\n"
        "    predecessor={name:(BASE/'wplto'/name).read_text() for name in files}\n"
        "    mismatched=[name for name in files if injected[name]!=predecessor[name]]\n"
        "    if mismatched:\n"
        "        raise ValueError('derived-and-injected linker scripts are not byte-identical '\n"
        "            'to the boot-name-index-product-r5 predecessor: '+repr(mismatched))\n"
        "    for name in files:\n"
        "        target=out/name;target.parent.mkdir(parents=True,exist_ok=True)\n"
        "        target.write_text(injected[name])\n"
        "    gate=getattr(P,'STORAGE_OWNER_CONSUMER_GATE',None)\n"
        "    if gate is not None:\n"
        "        gate.expected=dict(gate.expected)\n"
        "        gate.expected['c2-substitution.ld']=injected['c2-substitution.ld']\n"
        "    HERE.mkdir(parents=True,exist_ok=True)\n"
        "    receipt=HERE/'linker-scripts-derived-identical-to-r5.json'\n"
        "    text=json.dumps(dict(\n"
        "        status='PASS: DERIVED-PLUS-INJECTED LINKER SCRIPTS BYTE-IDENTICAL TO THE '\n"
        "               'BOOT-NAME-INDEX-PRODUCT-R5 PREDECESSOR',\n"
        "        owner_base=str(OWNER_BASE.relative_to(ROOT)),\n"
        "        pre_injection_predecessor=str(pre_injection_ancestor.relative_to(ROOT)),\n"
        "        pre_injection_changed=pre_injection_changed,\n"
        "        predecessor=str(BASE.relative_to(ROOT)),\n"
        "        slice_rows=INJECT_SLICES_WIRING['slices']['rows'],\n"
        "        additions=INJECT_SLICES_WIRING.get('linker_additions',[]),\n"
        "        predecessor_sha256={name:hashlib.sha256(predecessor[name].encode()).hexdigest()\n"
        "                           for name in files},\n"
        "        candidate_sha256={name:hashlib.sha256(injected[name].encode()).hexdigest()\n"
        "                         for name in files}),indent=2,sort_keys=True)+'\\n'\n"
        "    if receipt.exists() and receipt.read_text()!=text:\n"
        "        raise ValueError('linker scripts receipt overwrite: '+str(receipt))\n"
        "    if not receipt.exists(): receipt.write_text(text)\n")
    start = raw.index('def source_gate():')
    end = raw.index('\ndef prepare_inputs()', start)
    raw = raw[:start]+f'''def source_gate():
    expected={set(SOURCES)!r}
    changed=set(subprocess.check_output(['git','diff','{DIFF_BASE}','--name-only',
        '--','src','lib'],cwd=ROOT,text=True).splitlines())
    if changed!=expected: raise ValueError('uncommissioned source population: '+repr(changed))
    comp=R.C.load(HERE/'composition.json')
    if comp['authority']!=AUTH or comp['diff_base']!='{DIFF_BASE}':
        raise ValueError('composition authority drift')
    for row in comp['evidence']:
        if R.bind(ROOT/row['path'])!=row: raise ValueError('probe evidence drift: '+row['path'])
    return dict(status='PASS: EXPORT PUBLICATION SOURCE COMPOSITION, NOT NATIVE ACCEPTANCE',
        sources=[R.bind(ROOT/p) for p in sorted(changed)],
        composition=R.bind(HERE/'composition.json'),
        plane=R.bind(PLANE/'set-a-plane-receipt.json'),
        producer_template=R.bind(ROOT/'build/index-crc-r1/product-card.py'))
'''+raw[end:]
    start = raw.index('    # Apply only the commissioned diff')
    end = raw.index('    derived,proof=', start)
    raw = raw[:start]+f'''    # Preserve every consumed producer adaptation of the accepted
    # boot-name-index world (r5); apply only this card's own commissioned
    # hunk, with exact context, since {DIFF_BASE}, projected onto r5's OWN
    # generated-product-sources copy (which already carries diet copy +
    # index hunks) -- not a fresh copy of the live src/ tree.
    import re
    for name,source in (('c2_product_runtime.c','src/c2_product_runtime.c'),):
        target=generated/name;text=target.read_text()
        diff=subprocess.check_output(['git','diff','{DIFF_BASE}','--',source],cwd=ROOT,text=True)
        (out/(name+'.export-publication.patch')).write_text(diff)
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
    # Native-only card: the Lisp plane is the accepted (unchanged) plane,
    # byte for byte -- same identical_plane() proof as native-diet-native/
    # boot_name_index_producer.py/session_bank_alignment_producer.py.
    raw = replace_once(raw,
        "    derived,proof=R.W.DATA.derive(BASE_PREFLIGHT/'setup-owned/static-plane/narrow-static',PLANE,\n"
        "        BASE/'wplto/generated-product-sources',out/'world-data-derivation',R.bind)",
        "    derived,proof=identical_plane(generated,out/'world-data-derivation')")
    raw = replace_once(raw, 'def materialize(out):', """def identical_plane(generated,work):
    base=BASE_PREFLIGHT/'setup-owned/static-plane/narrow-static'
    rows=[]
    left=sorted(p.relative_to(base) for p in base.rglob('*') if p.is_file())
    right=sorted(p.relative_to(PLANE) for p in PLANE.rglob('*') if p.is_file())
    if left!=right: raise ValueError('plane file population differs from the r5 predecessor plane')
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
    return {},dict(status='PASS: PLANE BYTE-IDENTICAL TO THE R5 PREDECESSOR; NO DATA DERIVATION',
        changed_members=[],files=len(rows),population=rows,
        tables=tables,mutations_rejected=mutations,
        generator=R.bind(Path(R.W.DATA.V6.__file__)),
        inputs=[R.bind(PLANE/p) for p in
                ('product/substitution-artifacts.json','product/product-shelf-v4-direct.bin',
                 'v6-semantics/initial.c2d-v6.bin')])

def materialize(out):""")
    # Profile inputs read directly from a plain src/ path (none exist for
    # this card's own member today -- see PRIOR_BASE note above) would be
    # commissioned members here, keyed against their content at DIFF_BASE
    # rather than the live tree; kept for parity with
    # session_bank_alignment_producer.py's own override shape.
    raw = replace_once(raw,
        "        if R.bind(before)['sha256']!=digest: raise ValueError('predecessor input drift')",
        "        prior=(subprocess.check_output(['git','show',"+repr(PRIOR_BASE)+"[name]+':'+name],cwd=ROOT)\n"
        "               if name in "+repr(PRIOR_BASE)+" else before.read_bytes())\n"
        "        if hashlib.sha256(prior).hexdigest()!=digest: raise ValueError('predecessor input drift')")
    raw = replace_once(raw, "        if name=='vm.c': raise ValueError('data derivation selected native code')",
        "        if name=='c2_product_runtime.c':\n"
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
              INJECT_SLICES=INDEX_PRODUCER.inject_slice_sections,
              INJECT_SLICES_WIRING=INDEX_PRODUCER.WIRING,
              REGISTER_AND_ADMIT=register_and_admit,
              SLICE_RECEIPT=slice_registration_receipt))


if __name__ == '__main__':
    main()
