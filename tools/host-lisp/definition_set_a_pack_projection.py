"""Conservative isolated-object slice envelope through the production packer.

Payload padding is a size projection only, never executable candidate code.
The separate Card-2b owner is checked unchanged, not dropped from the claim.
"""
from pathlib import Path
import argparse
import hashlib
import json

import runtime_overlay_bank as B
from elf_truth import ElfTruth
import c2_v230_public_overlays as THIRD

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'build/transient-retirement-product-r1/wplto'


def bind(p):
    p = p.resolve()
    data = p.read_bytes()
    return dict(path=str(p.relative_to(ROOT)), bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', required=True, type=Path)
    out = ap.parse_args().out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    mp = BASE/'runtime-overlays-session-final.json'
    m = json.loads(mp.read_text())
    elf = BASE/m['elf']['file']
    assert bind(elf)['sha256'] == m['elf']['sha256']
    truth = ElfTruth.read(elf, llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',
                          include_section_data=True)
    inputs = [mp, elf]
    envelopes = {}
    for name, path in (
        ('.lisp65_rt_c2append_reserve_persistent_bounds', ROOT/'build/definition-set-a-projection-r2/c2_product_runtime-after.o'),
        ('.lisp65_rt_c2append_reserve_persistent_code', ROOT/'build/definition-set-a-projection-r2/c2_product_runtime-after.o'),
        ('.lisp65_rt_c2emit_literal_atom', ROOT/'build/definition-set-a-projection-r2/c2_session_emitter-after.o'),
    ):
        obj = ElfTruth.read(path, llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj')
        envelopes[name] = obj.section(name).bytes
        inputs.append(path)
    rows, slices = [], []
    helper = ROOT/'build/definition-helper-overlay-r1/projection.json'
    helper_projection = json.loads(helper.read_text())
    helper_size = next(r['bytes'] for r in helper_projection['rows'] if r['name'] == 'after')
    envelopes['.lisp65_rt_c2emit_literal_atom'] = max(
        envelopes['.lisp65_rt_c2emit_literal_atom'], helper_size)
    inputs.extend([helper, ROOT/'build/definition-helper-overlay-r1/after.elf'])
    bases = {r['source_address']-r['file_offset'] for r in m['slices'] if r['region_id'] == 0}
    assert len(bases) == 1
    for row in m['slices']:
        if row['region_id'] == 2:
            continue
        data = truth.section_bytes(row['section'])
        assert len(data) == row['file_size']
        size = max(len(data), envelopes.get(row['section'], len(data)))
        spec = B.SliceSpec(**{k: row[k] for k in (
            'id', 'name', 'section', 'start_symbol', 'end_symbol',
            'entry_symbol', 'flags', 'abi_version', 'capability_mask', 'region_id')})
        slices.append(B.ExtractedSlice(spec, row['vma'], row['vma']+size,
                                      row['entry'], data+bytes(size-len(data))))
        if row['section'] in envelopes:
            rows.append(dict(section=row['section'], consumed_bytes=len(data),
                             isolated_bytes=envelopes[row['section']], envelope=size))
    main, overflow, parsed = B.build_region_images(slices,
        profile_build_id=m['profile_build_id'], expected_vma=m['policy']['common_vma'],
        max_slice_bytes=m['policy']['max_slice_bytes'], format_version=4,
        main_source_base=bases.pop(),
        overflow_source_base=(m['overflow_storage']['bank']<<16)+m['overflow_storage']['address'])
    ext, source, vma, entry, owner = THIRD.payload(elf)
    assert len(ext) <= owner['payload']['capacity']
    assert (source, len(ext)) == (m['external_storage']['source_address'], m['external_storage']['bytes'])
    assert len(main) <= 65536
    assert len(overflow) <= m['overflow_storage']['capacity']
    (out/'main-size-projection.bin').write_bytes(main)
    (out/'overflow-size-projection.bin').write_bytes(overflow)
    result = dict(status='PASS: CONSERVATIVE SIZE PROJECTION; NOT CANDIDATE EXECUTABLE',
        slices=rows, main_bytes=len(main), main_free=65536-len(main),
        overflow_bytes=len(overflow), overflow_capacity=m['overflow_storage']['capacity'],
        external_owner_unchanged=owner, external_bytes=len(ext),
        inputs=[bind(p) for p in dict.fromkeys(inputs)], producer=bind(Path(__file__)),
        budget=dict(seed=0, final=0, product_link=0))
    (out/'receipt.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
