"""ov_crc16 card: command admission, then one Seed. Never implicit final.

Derived directly from export_publication_producer.py (itself derived from
session_bank_alignment_producer.py's shape rather than
boot_name_index_producer.py's): the predecessor world for THIS card is
build/export-publication-product-r2, and r2's own resolved profile and
generated substitution linker script already carry everything
boot_name_index_producer.py had to admit by hand --

  - feature_defines= already lists LISP65_C2_BOOT_NAME_INDEX first (r2 is a
    direct descendant of build/boot-name-index-product-r5, which admitted
    it; export_publication_producer.py carried it forward unchanged);
  - c2-substitution.ld already allocates .lisp65_rt_c2d_10a/10b (output
    sections, start/end/entry symbols, stack-safe-window ASSERTs and the
    paired NOCROSSREFS rows -- verified against
    build/export-publication-product-r2/wplto/c2-substitution.ld, which is
    byte-identical to r5's own script per
    build/export-publication-r1/linker-scripts-derived-identical-to-r5.json).

So this producer carries NO add_feature/bind_features/admit_feature_define
of its own and NO new register_slices/inject_slice_sections rows: this card
adds no product feature and no new Session/decoder slice (per the owner's
"read-only preflight" recommendation, build/ov-crc16-preflight-r1/
report-draft.md -- form (b) retargets both ov_crc16 callers to the already-
proven leaf rtov_crc_mem and removes ov_crc16; it is pure text/E000
recovery, not a feature). The include authority is likewise NOT rebased to
a new successor closure: this card touches no decoder file, so INC.CLOSURE
stays bound to the SAME closure export-publication itself resumed under,
config/boot-name-index-native/include-closure.json, at its current
(unchanged) sha256 -- there is no successor closure of this card's own to
rebase onto.

Slice registration is STILL required, even though this card introduces no
feature or slice of its own: .lisp65_rt_c2d_10a/10b are a RUNTIME opt-in of
the link tool (P.configure_boot_name_index_slices(), invoked via
boot_name_index_producer.register_slices()), not predecessor/world state a
fresh process inherits from r2's own files. export_publication_producer.py
already documents why (its own r1 world halted at the final section
inventory gate without this call); this card's own process is equally
fresh, so it must call REGISTER_AND_ADMIT(P) again for exactly the same
reason, reusing boot_name_index_producer.py's register_slices()/
admit_feature_define() the same way export_publication_producer.py does --
see register_and_admit() below, unchanged in shape from that card's own.

Source population: this card's own commissioned members are exactly
src/vm_boot_overlay.c and src/c2_boot_chain_commit.s (SOURCES); it carries
no HEADERS entry of its own (HEADERS=()) -- grep across src/*.h found no
header declaring ov_crc16 (it is defined and called only within
src/vm_boot_overlay.c, plus the one JSR from the hand-written ASM leaf
src/c2_boot_chain_commit.s; see build/ov-crc16-preflight-r1/receipt.json).

Profile keying (verified against
build/export-publication-product-r2/wplto/resolved-profile.txt, NOT
assumed): the two members are NOT keyed the same way.
  - src/vm_boot_overlay.c is keyed as a PLAIN src/ path
    (`input_sha256=src/vm_boot_overlay.c:...`), and it is absent from
    build/export-publication-product-r2/wplto/generated-product-sources/ --
    i.e. it compiles straight from the live tree today, with no generated
    copy of its own anywhere in this world's ancestry. This is the OPPOSITE
    of the coordinator's working assumption ("prüfe, ob die Vorgängerwelt
    für vm_boot_overlay.c eine generated-Kopie führt"); the check came back
    negative, so materialize() below must MANUFACTURE a generated copy for
    this member from `git show {DIFF_BASE}:src/vm_boot_overlay.c` before it
    can apply this card's own commissioned hunk to it (see materialize()
    override), rather than reading a pre-existing generated copy in place.
  - src/c2_boot_chain_commit.s IS already present in that same
    generated-product-sources population and is keyed to that generated
    path (`input_sha256=build/export-publication-product-r2/wplto/
    generated-product-sources/c2_boot_chain_commit.s:...`) -- i.e. it is
    "src-direct" only in the sense that it is assembled outside the C LTO
    unit, but its generated copy already exists in r2's own population and
    this card's hunk projects onto THAT copy, exactly like every other
    generated-copy member in this family of producers (c2_product_runtime.c
    for boot_name_index/export_publication, the v2 decoder pair, etc).
  Because vm_boot_overlay.c's default predecessor-input-drift check in the
  template reads `ROOT/name` (i.e. the LIVE working tree) and the
  concurrent Opus agent's edit to that file is uncommitted while AUTH is
  pending, PRIOR_BASE overrides exactly that one member with a `git show
  {DIFF_BASE}:...` read, the same projection convention
  session_bank_alignment_producer.py/export_publication_producer.py use.
  c2_boot_chain_commit.s needs no such override: its profile key already
  points at a generated copy of the (currently still identical) r2
  predecessor's own file on disk, tautologically satisfied exactly as
  export_publication_producer.py's own PRIOR_BASE note describes for a
  generated-path-keyed member.

Linker scripts: unchanged mechanism from export_publication_producer.py's
own REVISED write_scripts() (after its own first command-probe halt) --
this card introduces no NEW feature or slice, but its own fresh admission
gate object still has no memory of any predecessor's in-process admission,
so write_scripts() below: (1) re-derives the fixed storage-owner baseline
itself (`storage_owner_linker.transform` from OWNER_BASE + facade); (2)
proves that baseline has ZERO deviation from the true pre-injection
predecessor (build/session-bank-alignment-product-r1/wplto, unchanged
across every card in this family so far); (3) applies the SAME
inject_slice_sections() (imported from boot_name_index_producer, same
anchor_record='13', rows=('10a','10b')) to the derived c2-substitution.ld;
(4) asserts the result is byte-identical to THIS CARD's OWN predecessor's
four wplto scripts -- build/export-publication-product-r2/wplto, not r5,
since r2 is this card's own immediate BASE and r2's own scripts were
already proven byte-identical to r5's; (5) writes the result to `out`; and
(6) patches this run's own STORAGE_OWNER_CONSUMER_GATE.expected the same
way admit_feature_define() does. Recorded in
linker-scripts-derived-identical-to-r2.json; any textual difference at any
step is a hard failure, not merely logged.

AUTH is still 'AUTH_PENDING': this file was written before the
commissioned source authority (the concurrent Opus agent's edit to
src/vm_boot_overlay.c and src/c2_boot_chain_commit.s implementing form (b))
lands. DIFF_BASE='40e919d4' is `git rev-parse --short HEAD` at the time
this producer was written; the orchestrator is expected to set it to the
commit immediately before the real source authority once that commit
lands (per the coordinator's instruction), the same convention every prior
card in this family documents. Only py_compile and a dry-run import are
possible before AUTH binds; the dry-run import is expected to fail exactly
at `if AUTH == 'AUTH_PENDING': raise SystemExit(...)` in main(), the same
gate every predecessor producer in this family fails at before its own
source authority lands.

Merely running the command probe never consumes the Seed budget.
"""
import json
from pathlib import Path
import shutil
import subprocess
import sys

# The Seed's own slice re-registration for .lisp65_rt_c2d_10a/10b is the
# exact text transform boot_name_index_producer.py already proved correct
# (see its inject_slice_sections()); this card reuses that function rather
# than re-deriving the same four line families, per the coordinator's
# instruction (the same reuse export_publication_producer.py already made).
# Importing the module executes no top-level side effect (constants and
# function/class definitions only).
import boot_name_index_producer as INDEX_PRODUCER

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT/'build/index-crc-r1/product-card.py'
HERE = ROOT/'build/ov-crc16-r1'
PREDECESSOR_PREFLIGHT = ROOT/'build/export-publication-product-r2-preflight'
OUT_PREFLIGHT = ROOT/'build/ov-crc16-product-r1-preflight'
BUILD = ROOT/'build/ov-crc16-product-r1'
AUTH = '0a41035d'
# HEAD immediately before the commissioned source authority at the time this
# producer was written (`git rev-parse --short HEAD`). The orchestrator sets
# this to the commit immediately before the real source authority once the
# concurrent Opus agent's commit lands; every hunk below is projected
# against this commit's copy of the two SOURCES.
DIFF_BASE = '40e919d4'
# Compiled/hunk-tracked members: both call sites this card retargets from
# ov_crc16 to the proven leaf rtov_crc_mem (see build/ov-crc16-preflight-r1/
# report-draft.md form (b)) -- the ASM commit leaf's own six-instruction
# register setup (src/c2_boot_chain_commit.s) and the one C caller
# (src/vm_boot_overlay.c). No HEADERS entry: ov_crc16 is declared and used
# only within these two files; grep across src/*.h found no header
# declaring it.
SOURCES = ('src/vm_boot_overlay.c', 'src/c2_boot_chain_commit.s')
HEADERS = ()
# Predecessor digest override: needed ONLY for src/vm_boot_overlay.c, which
# is profile()-keyed to a PLAIN src/ path in
# build/export-publication-product-r2/wplto/resolved-profile.txt (verified;
# see module docstring) and is therefore read from the LIVE working tree by
# the template's default predecessor-input-drift check -- which would see
# the concurrent Opus agent's uncommitted edit while AUTH is pending.
# src/c2_boot_chain_commit.s needs no such entry: its own profile key already
# points at its generated-product-sources copy under BASE, which is a
# stored predecessor artifact untouched by any live edit (the "no override
# needed" case export_publication_producer.py documents for its own
# generated-path-keyed member).
PRIOR_BASE = {'src/vm_boot_overlay.c': DIFF_BASE}
# Unchanged from export_publication_producer.py: this card touches no
# decoder file, so there is no successor closure of its own to rebase
# INC.CLOSURE onto.
SUCCESSOR_CLOSURE = 'config/boot-name-index-native/include-closure.json'
SUCCESSOR_CLOSURE_SHA = '2681fb3e89deb5c70138e1cae6a7e5c00b575a211cf5b3e07d7bf5072debc572'
# No PROBES yet: this card's own impl/differential/admission/preflight
# receipts (build/ov-crc16-impl-r1/...) do not exist until the source
# authority lands -- the orchestrator populates this once
# build/ov-crc16-impl-r1/differential.json (and the leaf-gate receipt) exist,
# the same way the seal binds those receipts prospectively (see
# ov_crc16_seal.py).
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
    """Opt this card's own (fresh) link-tool process into the two
    boot-name-index Session/decoder slices exactly like every predecessor
    process in this family did, then admit the inherited feature past the
    storage-owner gate.

    Reused directly from export_publication_producer.py's own function of
    the same name (which reuses boot_name_index_producer.py's own
    register_slices()/admit_feature_define(), stateless functions of P's
    own default catalog): this card's own process is a fresh Python process
    with no memory of any predecessor's in-process slice registration, so
    without this call the link tool's own section inventory would still
    expect the pre-index catalog while the linker script (correctly
    derived+injected by write_scripts) already carries the two records --
    the exact halt export_publication_producer.py's own r1 world hit and
    documented.

    No BIND_FEATURES(): this card binds no new feature expectation of its
    own -- LISP65_C2_BOOT_NAME_INDEX is already the predecessor's own bound
    feature_defines row, and bind_features() itself refuses on an
    already-carrying profile."""
    INDEX_PRODUCER.register_slices(P)
    INDEX_PRODUCER.admit_feature_define(P)


def slice_registration_receipt():
    """Write-once proof, independent of any real command, that this card's
    own registration reproduces the predecessor's slice wiring exactly --
    same slot pins, same catalog growth, same unique-slice count -- the same
    shape as export_publication_producer.py's own function of this name,
    compared against the same r5 feature-wiring reference (this card adds
    no slice of its own, so the reference growth is unchanged)."""
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
        status='PASS: OV_CRC16 SOURCE COMPOSITION, NOT NATIVE ACCEPTANCE',
        authority=AUTH, diff_base=DIFF_BASE,
        members=[
            dict(name='ov-crc16-hunk', source='src/vm_boot_overlay.c', projected_text=None),
            dict(name='ov-crc16-hunk', source='src/c2_boot_chain_commit.s', projected_text=None)],
        feature=None, new_slices=0, manifest_floor_changed=False,
        linker_scripts='byte-identical to the export-publication-product-r2 predecessor',
        claim='both ov_crc16 call sites retargeted to the proven leaf rtov_crc_mem; the Seed link decides',
        evidence=[bind(ROOT/p) for p in PROBES])


def main():
    if sys.argv[1:] not in (['command-probe'], ['seed']):
        raise SystemExit('command-probe | seed')
    if AUTH == 'AUTH_PENDING':
        raise SystemExit('bind AUTH to the commissioned source commit first')
    raw = TEMPLATE.read_text()
    # No decoder change here: keep INC.CLOSURE pointed at the exact closure
    # export-publication itself resumed under (see SUCCESSOR_CLOSURE above)
    # -- this is a rebind to the SAME closure, not a rebase to a new
    # successor tree.
    raw = replace_once(raw, "INC=prior['INC']",
        "INC=prior['INC'];INC.CLOSURE=ROOT/"+repr(SUCCESSOR_CLOSURE)
        +";INC.CLOSURE_SHA="+repr(SUCCESSOR_CLOSURE_SHA))
    # Opt this card's own fresh link-tool process into the two
    # boot-name-index slices (REGISTER_SLICES) and re-admit the inherited
    # feature past this run's own fresh storage-owner gate (ADMIT_FEATURE),
    # both reused from boot_name_index_producer.py -- see
    # register_and_admit() docstring. No BIND_FEATURES here: this card binds
    # no new feature expectation of its own.
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
            "HERE=ROOT/'build/ov-crc16-r1';HERE.mkdir(parents=True,exist_ok=True)",
        "BASE=ROOT/'build/storage-owner-product-r2'":
            "BASE=ROOT/'build/export-publication-product-r2'",
        "BASE_PREFLIGHT=ROOT/'build/storage-owner-product-r2-preflight'":
            "BASE_PREFLIGHT=ROOT/"+repr(str(PREDECESSOR_PREFLIGHT.relative_to(ROOT))),
        "OUT=ROOT/'build/index-crc-product-r1-preflight'":
            "OUT=ROOT/"+repr(str(OUT_PREFLIGHT.relative_to(ROOT))),
        "BUILD=ROOT/'build/index-crc-product-r1'":
            "BUILD=ROOT/"+repr(str(BUILD.relative_to(ROOT))),
        "AUTH='4cf5a2f9'": f"AUTH='{AUTH}'",
        "CHANGED=('src/vm.c',)": 'CHANGED='+repr(SOURCES),
        "name='index-crc-and-final-sector-length'": "name='ov-crc16-leaf-retarget'",
        "allowed=set(proof['changed_members'])|{'vm.c'}":
            "allowed=set(proof['changed_members'])|"+changed_names,
    }.items():
        raw = replace_once(raw, old, new)
    # Re-derive the fixed storage-owner baseline exactly the way the
    # admission gate does (from OWNER_BASE + facade, not from this card's
    # own BASE), prove it matches the true pre-injection predecessor with
    # zero deviation, inject the two boot-name-index slice records the same
    # way every predecessor in this family did, prove the result is
    # byte-identical to THIS card's own predecessor (export-publication-
    # product-r2, not r5 -- r2 already proved byte-identical to r5), write
    # it, and keep the admission gate's own expectation in sync.
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
        "            'to the export-publication-product-r2 predecessor: '+repr(mismatched))\n"
        "    for name in files:\n"
        "        target=out/name;target.parent.mkdir(parents=True,exist_ok=True)\n"
        "        target.write_text(injected[name])\n"
        "    gate=getattr(P,'STORAGE_OWNER_CONSUMER_GATE',None)\n"
        "    if gate is not None:\n"
        "        gate.expected=dict(gate.expected)\n"
        "        gate.expected['c2-substitution.ld']=injected['c2-substitution.ld']\n"
        "    HERE.mkdir(parents=True,exist_ok=True)\n"
        "    receipt=HERE/'linker-scripts-derived-identical-to-r2.json'\n"
        "    text=json.dumps(dict(\n"
        "        status='PASS: DERIVED-PLUS-INJECTED LINKER SCRIPTS BYTE-IDENTICAL TO THE '\n"
        "               'EXPORT-PUBLICATION-PRODUCT-R2 PREDECESSOR',\n"
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
    return dict(status='PASS: OV_CRC16 SOURCE COMPOSITION, NOT NATIVE ACCEPTANCE',
        sources=[R.bind(ROOT/p) for p in sorted(changed)],
        composition=R.bind(HERE/'composition.json'),
        plane=R.bind(PLANE/'set-a-plane-receipt.json'),
        producer_template=R.bind(ROOT/'build/index-crc-r1/product-card.py'))
'''+raw[end:]
    start = raw.index('    # Apply only the commissioned diff')
    end = raw.index('    derived,proof=', start)
    raw = raw[:start]+f'''    # Preserve every consumed producer adaptation of the accepted
    # export-publication world (r2); apply only this card's own commissioned
    # hunks, with exact context, since {DIFF_BASE}.
    #
    # src/c2_boot_chain_commit.s already has a generated copy under r2's own
    # generated-product-sources population (copied above); this card's hunk
    # projects onto THAT SAME copy, like every other generated-copy member
    # in this family.
    #
    # src/vm_boot_overlay.c has NO generated copy anywhere in this world's
    # ancestry (verified: absent from
    # build/export-publication-product-r2/wplto/generated-product-sources/,
    # and its own resolved-profile.txt row is keyed to the plain src/ path
    # -- see module docstring). Its generated copy is therefore MANUFACTURED
    # here first, from the DIFF_BASE content (`git show`), before this
    # card's own hunk is applied to it -- not read from a pre-existing file.
    import re
    (generated/'vm_boot_overlay.c').write_bytes(
        subprocess.check_output(['git','show','{DIFF_BASE}:src/vm_boot_overlay.c'],cwd=ROOT))
    for name,source in (('vm_boot_overlay.c','src/vm_boot_overlay.c'),
                        ('c2_boot_chain_commit.s','src/c2_boot_chain_commit.s')):
        target=generated/name;text=target.read_text()
        diff=subprocess.check_output(['git','diff','{DIFF_BASE}','--',source],cwd=ROOT,text=True)
        (out/(name+'.ov-crc16.patch')).write_text(diff)
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
    # boot_name_index_producer.py/export_publication_producer.py.
    raw = replace_once(raw,
        "    derived,proof=R.W.DATA.derive(BASE_PREFLIGHT/'setup-owned/static-plane/narrow-static',PLANE,\n"
        "        BASE/'wplto/generated-product-sources',out/'world-data-derivation',R.bind)",
        "    derived,proof=identical_plane(generated,out/'world-data-derivation')")
    raw = replace_once(raw, 'def materialize(out):', """def identical_plane(generated,work):
    base=BASE_PREFLIGHT/'setup-owned/static-plane/narrow-static'
    rows=[]
    left=sorted(p.relative_to(base) for p in base.rglob('*') if p.is_file())
    right=sorted(p.relative_to(PLANE) for p in PLANE.rglob('*') if p.is_file())
    if left!=right: raise ValueError('plane file population differs from the r2 predecessor plane')
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
    return {},dict(status='PASS: PLANE BYTE-IDENTICAL TO THE R2 PREDECESSOR; NO DATA DERIVATION',
        changed_members=[],files=len(rows),population=rows,
        tables=tables,mutations_rejected=mutations,
        generator=R.bind(Path(R.W.DATA.V6.__file__)),
        inputs=[R.bind(PLANE/p) for p in
                ('product/substitution-artifacts.json','product/product-shelf-v4-direct.bin',
                 'v6-semantics/initial.c2d-v6.bin')])

def materialize(out):""")
    # Profile inputs read directly from a plain src/ path are commissioned
    # members here, keyed against their content at DIFF_BASE rather than the
    # live tree -- see PRIOR_BASE note above. Only src/vm_boot_overlay.c is
    # in PRIOR_BASE today; src/c2_boot_chain_commit.s falls through to the
    # unmodified `before.read_bytes()` branch (its generated copy is a
    # stored predecessor artifact, not the live tree).
    raw = replace_once(raw,
        "        if R.bind(before)['sha256']!=digest: raise ValueError('predecessor input drift')",
        "        prior=(subprocess.check_output(['git','show',"+repr(PRIOR_BASE)+"[name]+':'+name],cwd=ROOT)\n"
        "               if name in "+repr(PRIOR_BASE)+" else before.read_bytes())\n"
        "        if hashlib.sha256(prior).hexdigest()!=digest: raise ValueError('predecessor input drift')")
    raw = replace_once(raw, "        if name=='vm.c': raise ValueError('data derivation selected native code')",
        "        if name in ('vm_boot_overlay.c','c2_boot_chain_commit.s'):\n"
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
