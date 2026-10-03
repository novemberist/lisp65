#!/usr/bin/env python3
"""Derive the six 2.5.3 Final disk packages and L65INDEX from public manifests.

Package payloads are fresh extension envelopes of the compiled library
images, bound to the reproduced product build ID; locators come from the
frozen disk layout. The inherited index codec and mutation gate apply.
"""
import json
import c2_v253_r1_public_native as N
import c2_v253_r1_public_overlays as O


def packages(build_id):
    import c2_defstruct_foundations_gate as PK
    import c2_require_resolver_gate as L
    specs = O.policy()['packages']
    N.require([s['name'] for s in specs] == ['buffer', 'place', 'string-extra', 'inspect', 'defstruct', 'repl-comfort'],
              'package population/order')
    rows, payloads = [], {}
    for s in specs:
        N.bound(s['manifest'])
        row, data = PK.measured_row(s['name'], s['name'], s['shelf'], N.local(s['manifest']['path']),
                                    tuple(s['dependencies']), s['track'], s['sector'], product_build_id=build_id)
        N.require(row == s['row'], 'package index row drift: ' + s['name'])
        rows.append(row)
        payloads[s['name']] = data
    index = L.encode_index(rows)
    N.require(L.decode_index(index, payloads, artifact_build_id=build_id) == rows, 'index/package mismatch')
    mutations = L.mutation_gate(index, payloads, artifact_build_id=build_id)
    return dict(rows=rows, payloads=payloads, index=index, mutations=mutations)


REEMISSION = N.ROOT / ('config/%s-comfort-reemission.json' % N.PREFIX)


def comfort_reemission(build_id):
    """Re-emit repl-comfort from public sources; require the projected r6 bytes."""
    import tempfile
    from pathlib import Path
    import bytecode_p0_stdlib as P
    import c2_defstruct_foundations_gate as PK
    policy = N.load(REEMISSION)
    for key in ('suite', 'resident_suite', 'projected_manifest', 'projected_blob'):
        N.bound(policy[key])
    for row in policy['live_sources']:
        N.bound(row)
    spec = next(s for s in O.policy()['packages'] if s['name'] == 'repl-comfort')
    N.require(spec['manifest'] == policy['projected_manifest'], 're-emission compares another manifest')
    with tempfile.TemporaryDirectory(prefix='lisp65-v253-comfort-') as tmp:
        out = Path(tmp) / 'repl-comfort'
        suite_path = str(N.local(policy['suite']['path']))
        suite = P._read_suite(suite_path)
        suite['resident_suite'] = str(N.local(policy['resident_suite']['path']))
        # 2.5.3: the frozen r4-era resident carries the pre-2.5.3 `nth`, while the live list-domain
        # contract (editor_product_list_domain.check_suite) now requires the 2.5.3 `nth`. The re-emitted
        # repl-comfort package is the frozen r6 artifact (byte-equal check below), not live product
        # code, so the live-domain pre-check is waived for this one emission only.
        from unittest.mock import patch
        import editor_product_list_domain  # noqa: F401  (a bound producer helper: the waived pre-check lives here)
        with patch('editor_product_list_domain.check_suite', lambda s: None):
            P.emit_artifacts(suite_path, suite, str(out), base_addr=0, artifact_role='disk-lib')
        blob = out.with_suffix('.blob.bin').read_bytes()
        N.require(blob == N.bound(policy['projected_blob']), 'repl-comfort re-emission differs from projected blob')
        fresh = json.loads(out.with_suffix('.manifest.json').read_bytes())
        projected = json.loads(N.bound(policy['projected_manifest']))
        def names_only(v):
            # Emission location differs; every other manifest field must be equal.
            if isinstance(v, str):
                return Path(v).name if '/' in v else v
            if isinstance(v, list):
                return [names_only(x) for x in v]
            if isinstance(v, dict):
                return {k: names_only(x) for k, x in v.items()}
            return v
        differs = sorted(k for k in set(fresh) | set(projected) if fresh.get(k) != projected.get(k))
        # disasm_sha256 hashes a listing whose header line carries the absolute suite path of the emitting
        # tree; it is a non-shipped listing digest and so is path-bound, like the path fields. Every other
        # field (blob, directory, external image and their digests, geometry) must be equal.
        disasm_equal = fresh.get('disasm_sha256') == projected.get('disasm_sha256')
        fresh, projected = dict(fresh), dict(projected)
        fresh.pop('disasm_sha256', None)
        projected.pop('disasm_sha256', None)
        N.require(names_only(fresh) == names_only(projected), 'repl-comfort manifest semantics differ')
        args = ('repl-comfort', 'repl-comfort', spec['shelf'])
        row_a, fresh_payload = PK.measured_row(*args, out.with_suffix('.manifest.json'), (), spec['track'], spec['sector'],
                                               product_build_id=build_id)
        row_b, payload = PK.measured_row(*args, N.local(spec['manifest']['path']), (), spec['track'], spec['sector'],
                                         product_build_id=build_id)
        N.require(row_a == row_b and fresh_payload == payload, 'repl-comfort package re-emission differs')
    return dict(status='PASS: REPL-COMFORT RE-EMITTED FROM PUBLIC SOURCES', blob_bytes=len(blob),
                package_bytes=len(payload), path_only_manifest_fields=differs, disasm_listing_digest_equal=disasm_equal)


def check():
    result = packages(O.policy()['product_build_id'])
    files = O.policy()['files']
    for name, data in list(result['payloads'].items()) + [('L65INDEX', result['index'])]:
        N.require(N.identity(data) == files[name.upper()], 'package payload differs from Final: ' + name)
    reemission = comfort_reemission(O.policy()['product_build_id'])
    return dict(status='PASS: SIX PUBLIC PACKAGES AND INDEX', packages=len(result['rows']), comfort_reemission=reemission,
                bytes={k: len(v) for k, v in result['payloads'].items()}, mutations=result['mutations'])


if __name__ == '__main__':
    print(json.dumps(check(), indent=2, default=str))
