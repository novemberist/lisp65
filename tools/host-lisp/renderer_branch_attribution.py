#!/usr/bin/env python3
"""Close renderer compiler roots against the measured assembler objects."""
import json
from pathlib import Path
import renderer_branch_product_card as CARD
import f011_frame_attribution as A
from evidence_era import stable_recorded_on


def run():
    CARD.configure()
    R = CARD.F
    A.D = R
    evidence = R.ROOT/'build/v2.1/renderer-branch-pricing-r1'
    forms = {
        '056-l65e_bcode_ordinal.s.o': ('l65e_bcode_ordinal-original.o', 'renderer-repaired.o', 18, 36),
        '063-c2_map_cpu_read.s.o': ('c2_map_cpu_read-original.o', 'map-reader-repaired.o', 1, 2),
    }

    def assembly(name, before, after):
        assert name in forms, 'uncommissioned assembly change: '+name
        old, new, sites, delta = forms[name]
        expected_before, expected_after = evidence/old, evidence/new
        assert before.read_bytes() == expected_before.read_bytes(), 'unbound predecessor assembler bytes'
        assert after.read_bytes() == expected_after.read_bytes(), 'unbound repaired assembler bytes'
        return {'status': 'PASS', 'before_microobject': R.C.bind(expected_before),
                'after_microobject': R.C.bind(expected_after), 'sites': sites,
                'object_code_delta': delta, 'whole_object_byte_identity': True}

    source = R.C.load(R.PREFLIGHT_RECEIPT)['profile']
    assert source['changed_authored_roots'] == sorted(CARD.DIRECT)
    for path in CARD.DIRECT:
        assert R.C.B.profile_inputs(R.PROFILE)[path] == R.C.bind(R.ROOT/path)['sha256']
    for seed in (True, False):
        value = A.derive(seed, asm_attributor=assembly)
        value['role'] = 'RENDERER-PCREL16-REPAIR'
        value['authorization'] = CARD.authority()
        value['source_preflight'] = R.C.bind(R.PREFLIGHT_RECEIPT)
        repairs = [r for r in value['compiler_roots'] if r['family'] == 'bound assembler repair']
        assert len(repairs) == (0 if seed else 2)
        out = R.BUILD/('seed-to-final-attribution.json' if seed else 'predecessor-attribution.json')
        value['recorded_on'] = stable_recorded_on(out)
        out.write_text(json.dumps(value, indent=2)+'\n')
        print('ATTRIBUTION PASS', out.name, 'roots', len(value['compiler_roots']),
              'changed PRG bytes', len(value['PRG_changed_bytes']))


if __name__ == '__main__':
    run()
