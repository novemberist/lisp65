#!/usr/bin/env python3
"""Write-once r5 requalification: fresh emission, identical r4 runtime/media.

The diagnosed defect is in reviewer input transport. Do not relink or alter
the runtime merely to manufacture a different hash. Rebuild every file payload
in the authenticated r4 disk layout, validate six packages, and bind new proofs.
"""
import json
import os
from pathlib import Path

import bytecode_p0_stdlib as P
import c2_defstruct_foundations_gate as PK
import c2_require_resolver_gate as L
import d81_persistence_fault as D
import o2_lite_r3_host as H
import o2_lite_r4_host as H4
import strings_seed_producer as S

ROOT = H.ROOT
BASE = ROOT/'build/o2-lite-product-r4'
BUILD = ROOT/'build/o2-lite-product-r5'


def once(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as f:
        f.write(raw)


def save(path, value):
    once(path, (json.dumps(value, indent=2, sort_keys=True)+'\n').encode())


def seed():
    assert os.environ.get('PYTHONDONTWRITEBYTECODE') == '1'
    complete = S.load(BASE/'complete.json')
    assert complete['status'] == 'PASS'
    for r in complete['receipts']:
        S.checked(r)
    old_source = S.load(BASE/'proofs/host/receipt.json')['sources']
    assert H4.bindings() == old_source
    assert H.project_editor() == (ROOT/'build/o2-lite-r4-slots-preflight/planes/product-editor.lisp').read_text()
    proofs = [ROOT/('build/'+p+'/receipt.json') for p in
              ('o2-lite-r5-admission-v3','o2-lite-r5-literals-final','o2-lite-r5-transport-final')]
    for path in proofs:
        assert S.load(path)['status'] == 'PASS'
    assert len(S.load(proofs[0])['rows']) == 27
    assert len(S.load(proofs[1])['rows']) == 16
    assert S.load(proofs[0])['sources'] == old_source
    assert S.bind(ROOT/'tools/host-lisp/comfort_default_rows.py') == S.load(proofs[2])['source']
    medium = S.checked(complete['medium'])
    native = S.checked(complete['ELF'])
    assert not BUILD.exists(), 'write-once Seed already claimed'
    BUILD.mkdir()
    save(BUILD/'attempt.json', dict(status='STARTED', producer=S.bind(Path(__file__)),
                                  predecessor=S.bind(BASE/'complete.json')))
    try:
        med = BUILD/'media-r5'
        med.mkdir()
        suite = P._read_suite(str(ROOT/'config/comfort-default-plane/libraries/repl-comfort-suite.json'))
        suite['resident_suite'] = str(ROOT/'build/o2-lite-r4-slots-preflight/planes/resident.json')
        P.emit_artifacts(str(ROOT/'config/comfort-default-plane/libraries/repl-comfort-suite.json'),
                         suite,str(med/'repl-comfort'),base_addr=0,artifact_role='disk-lib')
        manifest = med/'repl-comfort.manifest.json'
        assert (med/'repl-comfort.blob.bin').read_bytes() == (BASE/'media-r4/repl-comfort.blob.bin').read_bytes()
        build_id = S.load(BASE/'media-r4/runtime-receipt.json')['product_build_id']
        row, package = PK.measured_row('repl-comfort','repl-comfort','repl',manifest,(),1,1,
                                        product_build_id=build_id)
        files = D.visible_files(medium)
        assert package == files[b'REPL-COMFORT']
        regenerated = dict(files)
        regenerated[b'REPL-COMFORT'] = package
        # Reconstruct all payload bytes at the frozen, validated sector layout.
        # Preserve BAM, chain links, directory, boot identity and unused slack.
        rebuilt = bytearray(medium)
        reconstructed = 0
        for slot in D.directory_slots(medium):
            if not slot.record[2]:
                continue
            name = D.entry_name(slot.record)
            payload = regenerated[name]
            once(med/'artifacts'/name.decode().lower(),payload)
            cursor = 0
            for track, sector in D.file_chain(medium,slot.record):
                count = min(254,len(payload)-cursor)
                at = D.sector_offset(track,sector)+2
                rebuilt[at:at+count] = payload[cursor:cursor+count]
                cursor += count
            assert cursor == len(payload)
            reconstructed += cursor
        assert bytes(rebuilt) == medium
        once(med/'o2lite.d81',rebuilt)
        persisted = (med/'o2lite.d81').read_bytes()
        D.validate_bam(persisted)
        assert D.visible_files(persisted) == regenerated
        index = L.decode_index(files[b'L65INDEX'])
        packages = {r['name']:regenerated[r['name'].upper().encode()] for r in index}
        assert len(packages) == 6
        assert L.decode_index(regenerated[b'L65INDEX'],packages,artifact_build_id=build_id) == index
        oldrow = next(r for r in index if r['name']=='repl-comfort')
        row.update(track=oldrow['track'],sector=oldrow['sector'])
        assert row == oldrow
        elf = BUILD/'wplto/resident-island-seed.prg.elf'
        once(elf,native)
        for suffix in ('', '.map', '.lto.o'):
            path = BASE/('wplto/resident-island-seed.prg'+suffix)
            if path.is_file():
                once(BUILD/'wplto'/path.name,path.read_bytes())
        sources = [ROOT/p for p in old_source] + [ROOT/'tools/host-lisp'/p for p in
            ('o2_lite_r5_host.py','o2_lite_r5_product.py','comfort_default_rows.py','backspace_rows.py')]
        for path in sources:
            once(BUILD/'sources'/path.relative_to(ROOT),path.read_bytes())
        for path in proofs:
            once(BUILD/'proofs'/path.parent.name/'receipt.json',path.read_bytes())
        save(BUILD/'source.json', dict(status='PASS', sources=[S.bind(p) for p in sources],
            product_source_identity=old_source, committed_source_admission='OPEN; no Git writes'))
        save(BUILD/'media.json',dict(status='PASS',medium=S.bind(med/'o2lite.d81'),
            files=len(files),packages=len(packages),reconstructed_payload_bytes=reconstructed,
            changed_bytes=0,unclassified_bytes=0,predecessor=complete['medium'],index_rows=index))
        save(BUILD/'runtime-identity.json',dict(status='PASS',ELF=S.bind(elf),
            predecessor=complete['ELF'],product_links=0,per_key_resident_changed_bytes=0,
            runtime_changed_bytes=0,library_changed_bytes=0,
            inherited_proofs=[S.bind(BASE/p) for p in ('price.json','capacity.json',
              'proofs/host/receipt.json','proofs/cost-final/cost.json',
              'proofs/copy-heap/receipt.json','proofs/batch-heap/receipt.json')]))
        save(BUILD/'host/receipt.json',dict(status='PASS',admission_rows=27,literal_rows=16,
            singleton_events=642,proofs=[S.bind(p) for p in proofs],target_runs=0))
        import comfort_default_rows as R
        import backspace_rows as B
        assert R.WORLD['lite'] == (med/'o2lite.d81',S.sha(persisted),elf)
        assert R.ELF_SHA[elf] == S.sha(native)
        assert B.WORLD['lite'] == R.WORLD['lite'][:2]
        assert len(R.LITE)==13 and R.PLAN['lite']==R.LITE+R.PRODUCT
        save(BUILD/'reviewer-rows-selftest.json',dict(status='PASS',rows=len(R.LITE),
            input_bytes=len(''.join(next(r[2] for r in R.LITE if r[0]=='lite-input-641'))[:-1]),
            bindings=[S.bind(ROOT/'tools/host-lisp'/p) for p in ('comfort_default_rows.py','backspace_rows.py')]))
        result = dict(status='PASS',seed=1,final=0,product_links=0,
            disposition='runtime-identical r4 requalification; fresh library emission and all-file reconstruction',
            medium=S.bind(med/'o2lite.d81'),ELF=S.bind(elf),
            receipts=[S.bind(BUILD/p) for p in ('source.json','media.json','runtime-identity.json',
                                              'host/receipt.json','reviewer-rows-selftest.json')])
        save(BUILD/'seed.json',result)
        save(BUILD/'complete.json',result)
        return result
    except BaseException as error:
        save(BUILD/'halt.json',dict(status='HALT',error=repr(error)))
        raise


if __name__ == '__main__':
    print(json.dumps(seed(),indent=2))
