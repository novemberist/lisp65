"""Dated successor producer for the authorized boot-only PRG carrier.

Reuse the accepted producer's input projection, not its historical output
directories. Explicitly derive a successor profile, linker and section owner.
Seed execution remains blocked until the complete preflight admission exists.
"""
import builtins
import hashlib
import json
from pathlib import Path
import re
import sys

import boot_only_carrier_linker as LINKER

ROOT = Path(__file__).resolve().parents[2]
FEATURE = 'LISP65_BOOT_ONLY_CARRIER'
AUTH = '4cd7eac3'
DIFF_BASE = '523c31e0'
BASE = ROOT/'build/ov-crc16-product-r1'
HERE = ROOT/'build/boot-only-carrier-r1'
TEMPLATE = ROOT/'tools/host-lisp/ov_crc16_producer.py'


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('producer seam drift: '+old)
    return text.replace(old,new,1)


def add_feature(text):
    rows = text.splitlines()
    indices = [i for i,r in enumerate(rows) if r.startswith('feature_defines=')]
    if len(indices)!=1:
        raise ValueError('profile feature row ambiguous')
    i = indices[0]
    features = rows[i].split('=',1)[1].split(',')
    if FEATURE in features or len(features)!=len(set(features)):
        raise ValueError('feature already present or duplicated')
    rows[i] = 'feature_defines='+','.join([FEATURE]+features)
    return '\n'.join(rows)+'\n'


def configure(P,R):
    inherited = tuple(R.A.features(BASE/'wplto/resolved-profile.txt'))
    if FEATURE in inherited:
        raise ValueError('predecessor unexpectedly carries feature')
    R.A.expected_features = lambda: (FEATURE,)+inherited
    gate = P.STORAGE_OWNER_CONSUMER_GATE
    old = gate.check
    if not getattr(old,'_boot_only_carrier',False):
        def check(*,target,compile_flags,link_flags,**rest):
            flag = '-D'+FEATURE
            if list(compile_flags).count(flag)!=1:
                raise ValueError('carrier feature not consumed exactly once')
            result = old(target=target,compile_flags=[f for f in compile_flags if f!=flag],
                         link_flags=link_flags,**rest)
            result['boot_only_carrier_feature']=FEATURE
            return result
        check._boot_only_carrier=True
        gate.check=check
    old_inventory = P.final_section_inventory_expectation
    if not getattr(old_inventory,'_boot_only_carrier',False):
        def inventory():
            result = old_inventory()
            names = list(result['names'])
            for name in ('.lisp65_boot_carrier','.rela.lisp65_boot_carrier'):
                if name in names:
                    raise ValueError('carrier section already admitted')
                names.insert(names.index('.llvm_sympart'),name)
            return {**result,'names':names,'boot_only_carrier_authority':AUTH}
        inventory._boot_only_carrier=True
        P.final_section_inventory_expectation=inventory


def inner(raw):
    raw = once(raw,'    SLICE_RECEIPT()\n',
               '    SLICE_RECEIPT()\n    CARRIER.configure(P,R)\n')
    raw = once(raw,"    target=OUT/'bound-feature-profile.txt'\n"
               "    if not target.exists(): shutil.copyfile(BASE/'wplto/resolved-profile.txt',target)\n",
               "    target=OUT/'bound-feature-profile.txt'\n"
               "    text=CARRIER.add_feature((BASE/'wplto/resolved-profile.txt').read_text())\n"
               "    if not target.exists(): target.write_text(text)\n")
    raw = once(raw,"R.C.BOUND_PROFILE.write_text('\\n'.join(lines)+'\\n')",
               "R.C.BOUND_PROFILE.write_text(CARRIER.add_feature('\\n'.join(lines)+'\\n'))")
    raw = once(raw,"    for name in files:\n        target=out/name;target.parent.mkdir(parents=True,exist_ok=True)\n",
               "    injected['c2-substitution.ld']=CARRIER.LINKER.transform(injected['c2-substitution.ld'])\n"
               "    for name in files:\n        target=out/name;target.parent.mkdir(parents=True,exist_ok=True)\n")
    raw = once(raw, "receipt=HERE/'linker-scripts-derived-identical-to-r2.json'",
               "receipt=HERE/'linker-scripts-carrier-successor.json'")
    raw = once(raw,
               "status='PASS: DERIVED-PLUS-INJECTED LINKER SCRIPTS BYTE-IDENTICAL TO THE '\n"
               "               'EXPORT-PUBLICATION-PRODUCT-R2 PREDECESSOR',",
               "status='PASS: PREDECESSOR DERIVATION IDENTICAL BEFORE THE EXPLICIT CARRIER ADDITION',\n"
               "        carrier_fragment_sha256=hashlib.sha256(CARRIER.LINKER.FRAGMENT.encode()).hexdigest(),\n"
               "        supersedes='linker-scripts-derived-identical-to-r2.json: inherited status overstated full identity',")
    # The accepted predecessor already carries both generated C units. Never
    # reconstruct either from the authored tree and lose consumed adaptations.
    raw = once(raw,"    (generated/'vm_boot_overlay.c').write_bytes(\n"
               f"        subprocess.check_output(['git','show','{DIFF_BASE}:src/vm_boot_overlay.c'],cwd=ROOT))\n",'')
    return 'import boot_only_carrier_producer as CARRIER\n'+raw


def main():
    if sys.argv[1:] not in (['command-probe'],['seed']):
        raise SystemExit('command-probe | seed')
    if sys.argv[1:] == ['seed']:
        admission = HERE/'preflight-admission.json'
        if not admission.is_file() or json.loads(admission.read_text()).get('status')!='PASS':
            raise SystemExit('Seed blocked: complete carrier preflight admission missing')
        proof=json.loads(admission.read_text())
        if proof.get('authority')!=AUTH or not proof.get('evidence'):
            raise SystemExit('Seed blocked: unbound admission')
        for row in proof['evidence']:
            if hashlib.sha256((ROOT/row['path']).read_bytes()).hexdigest()!=row['sha256']:
                raise SystemExit('Seed blocked: changed preflight input '+row['path'])
        if (ROOT/'build/boot-only-carrier-product-r1').exists():
            raise SystemExit('Seed budget already entered; no implicit retry')
    # Simultaneous substitution avoids rewriting successor names a second time.
    substitutions = {
        'build/ov-crc16-r1':'build/boot-only-carrier-r1',
        'build/ov-crc16-product-r1':'build/boot-only-carrier-product-r1',
        'build/export-publication-product-r2':'build/ov-crc16-product-r1',
        "AUTH = '0a41035d'":f"AUTH = '{AUTH}'",
        "DIFF_BASE = '40e919d4'":f"DIFF_BASE = '{DIFF_BASE}'",
        'src/c2_boot_chain_commit.s':'src/vm_runtime_overlay.c',
        "'c2_boot_chain_commit.s'":"'vm_runtime_overlay.c'",
        'ov-crc16-leaf-retarget':'boot-only-carrier-placement',
    }
    original=TEMPLATE.read_text()
    text=re.sub('|'.join(re.escape(k) for k in sorted(substitutions,key=len,reverse=True)),
                lambda m:substitutions[m[0]],original)
    scope=dict(__name__='boot_only_carrier_template',__file__=__file__)
    builtins.exec(builtins.compile(text,__file__,'exec'),scope)
    # Artifact-only media adapters may capture the configured inner driver;
    # never intercept construction of this outer template namespace.
    if 'exec' in globals():
        scope['exec']=globals()['exec']
    scope['PRIOR_BASE']={}
    scope['composition']=lambda: dict(
        status='SOURCE PLACEMENT AUTHORITY; NOT NATIVE ACCEPTANCE',authority=AUTH,diff_base=DIFF_BASE,
        members=['src/vm_boot_overlay.c','src/vm_runtime_overlay.c'],feature=FEATURE,
        carrier_cap=704,ordinary_recovery_min=600,new_overlay_slots=0,evidence=[])
    def compile_successor(raw,filename,mode):
        return builtins.compile(inner(raw),filename,mode)
    scope['compile']=compile_successor
    HERE.mkdir(exist_ok=True,parents=True)
    receipt=HERE/'producer-derivation.json'
    value=json.dumps(dict(template=str(TEMPLATE.relative_to(ROOT)),
                         sha256=hashlib.sha256(TEMPLATE.read_bytes()).hexdigest(),
                         authority=AUTH,diff_base=DIFF_BASE,substitutions=substitutions),indent=2)+'\n'
    if receipt.exists() and receipt.read_text()!=value:
        raise ValueError('producer derivation overwrite')
    if not receipt.exists(): receipt.write_text(value)
    scope['main']()


if __name__=='__main__':
    main()
