#!/usr/bin/env python3
"""Qualify withdrawal of the EQ patch without rewriting sealed fork evidence."""
import argparse
from copy import deepcopy
import json
from pathlib import Path

import dwx_delivered_world_boot as BOOT
import dwx_retroactive_red_replay as RED
import dwx_xemu_cycle_probe_adapter as ADAPTER
from evidence_era import stable_recorded_on

ROOT=RED.ROOT
BUILD=ROOT/'build/dwx/buffered-repair-three-patch-requalification-r1'
MANIFEST=ROOT/'build/dwx/xemu-buffered-repair-three-patch-r2/dwx-xemu-cycle-probe-adapter.json'
ROLES=('base_patch','transport_patch','cycle_patch')

def write(path,value):
    path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')

def binding(path):
    v=RED.bind(path)
    return {k:v[k] for k in ('path','sha256')}

def main():
    global BUILD
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',type=Path,default=BUILD)
    BUILD=parser.parse_args().out.resolve()
    assert ROOT/'build/dwx' in BUILD.parents
    assert not BUILD.exists(), 'requalification is one-shot'
    manifest=RED.load(MANIFEST)
    assert manifest['status']=='PASS' and tuple(p['role'] for p in manifest['patches'])==ROLES
    assert manifest['source_commit']==RED.load(BOOT.CONTRACT_PATH)['xemu_source']['commit']
    binary=Path(manifest['binary']['path'])
    assert RED.sha256(binary)==manifest['binary']['sha256']
    for p in manifest['patches']: assert RED.sha256(ROOT/p['path'])==p['sha256']
    ADAPTER.verify_sources(MANIFEST.parent)
    ADAPTER.selftest()
    BUILD.mkdir(parents=True)
    # Candidate identity for bootstrap only. The live admission contract is
    # not promoted until boot AND all sealed regressions have executed.
    identity={k:manifest[k] for k in ('source_commit','patches','patched_source_sha256')}
    identity['binary_sha256']=manifest['binary']['sha256']
    blind=deepcopy(RED.load(BOOT.BLIND_CONTRACT_PATH))
    blind['qualified_tool_identity']=identity
    candidate=BUILD/'candidate-blind-contract.json';write(candidate,blind)
    BOOT.BLIND_CONTRACT_PATH=candidate
    old=RED.load(ROOT/'build/dwx/navigation-requalification-r1/receipt.json')
    args=argparse.Namespace(xemu=binary,adapter_manifest=MANIFEST,
        d81=Path(old['inputs']['product_d81']['path']),
        rom=Path(old['inputs']['rom']['path']),
        sd_image=Path(old['inputs']['system_sd']['path']),out=BUILD/'boot',timeout=30)
    boot=BOOT.run_boot(args)
    assert boot['status']=='PASS' and boot['prefilter_tool_identity']==identity
    write(BUILD/'boot-receipt.json',boot)
    cfg=deepcopy(RED.load(RED.CONTRACT_PATH))
    cfg['inputs']['cycle_probe_manifest']=binding(MANIFEST)
    cfg['inputs']['cycle_probe_binary']=binding(binary)
    cfg['inputs']['fork_requalification_receipt']=binding(BUILD/'boot-receipt.json')
    contract=BUILD/'retroactive-contract.json';write(contract,cfg)
    RED.CONTRACT_PATH=contract
    RED.PATCH_ROLES=ROLES
    RED.RECEIPT_PATH=BUILD/'retroactive-receipt.json'
    RED.selftest()
    args.out=BUILD/'reds';args.timeout=90
    RED.build(args)
    receipt=RED.load(RED.RECEIPT_PATH)
    RED.validate_receipt(receipt,cfg)
    assert receipt['bar']['all_reproduced']
    out=BUILD/'receipt.json'
    write(out,dict(status='PASS: THREE-PATCH FORK REQUALIFIED',
        recorded_on=stable_recorded_on(out),manifest=binding(MANIFEST),
        tool_identity=identity,boot=binding(BUILD/'boot-receipt.json'),
        retroactive=binding(RED.RECEIPT_PATH),reproduced_reds=3,
        live_admission_promoted=False,device_acceptance_claimed=False,
        claim='emulated framebuffer/memory/cycles only; no physical timing or keyboard claim'))
    print('THREE-PATCH REQUALIFICATION PASS: boot and 3/3 sealed reds',flush=True)

if __name__=='__main__': main()
