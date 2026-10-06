#!/usr/bin/env python3
"""Derive the six 2.5.4 Final disk packages and L65INDEX from public manifests.

Package payloads are fresh extension envelopes of the compiled library
images, bound to the reproduced product build ID; locators come from the
frozen disk layout. The inherited index codec and mutation gate apply.
"""
import json
import c2_v254_r1_public_native as N
import c2_v254_r1_public_overlays as O


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


# 2.5.4 re-emits TWO packages (c254_config.PACKAGES_REEMIT): REPL-COMFORT, as in 2.5.3, and DEFSTRUCT.  Both are
# carried in the same form: the projected compiled manifest and blob are the build input; the re-emission from the
# public sources is a check that must give the projected bytes.  The recipe is the Seed's (c254_product.emit_package):
# suite sources = the live package sources, one emission-only case, the suite's own resident chain replaced by a
# FROZEN projected resident (REPL-COMFORT: the r4-era resident; DEFSTRUCT: the projected 2.5.4 product resident).
# The live list-domain pre-check is waived for both emissions: for REPL-COMFORT as in 2.5.3 and in the Seed (the
# frozen resident carries the pre-2.5.3 `nth`); for DEFSTRUCT because that pre-check needs the contract document
# docs/nth-domain-successor-20260930.md, which the public export does not carry (the Seed, in the private tree,
# ran it and it passed).  In both cases the byte comparison with the projected artifact is the check.
REEMISSIONS = {'repl-comfort': ('comfort-reemission', 'PASS: REPL-COMFORT RE-EMITTED FROM PUBLIC SOURCES'),
               'defstruct': ('defstruct-reemission', 'PASS: DEFSTRUCT RE-EMITTED FROM PUBLIC SOURCES')}


def reemission(build_id, name):
    """Re-emit one package from public sources; require the projected bytes."""
    import tempfile
    from pathlib import Path
    import bytecode_p0_stdlib as P
    import c2_defstruct_foundations_gate as PK
    config, status = REEMISSIONS[name]
    policy = N.load(N.ROOT / ('config/%s-%s.json' % (N.PREFIX, config)))
    N.require(policy['package'] == name and policy['list_domain_waiver'] is True,
              're-emission policy is for another package')
    for key in ('suite', 'resident_suite', 'projected_manifest', 'projected_blob'):
        N.bound(policy[key])
    for row in policy['live_sources'] + policy['resident_sources']:
        N.bound(row)
    spec = next(s for s in O.policy()['packages'] if s['name'] == name)
    N.require(spec['manifest'] == policy['projected_manifest'], 're-emission compares another manifest')
    with tempfile.TemporaryDirectory(prefix='lisp65-v254-reemit-') as tmp:
        out = Path(tmp) / name
        suite_path = str(N.local(policy['suite']['path']))
        suite = P._read_suite(suite_path)
        suite['sources'] = [str(N.local(r['path'])) for r in policy['live_sources']]
        suite['cases'] = [dict(name='emission-only', expr='nil', expect='nil')]
        suite.pop('resident_suites', None)
        suite['resident_suite'] = str(N.local(policy['resident_suite']['path']))
        if policy['list_domain_waiver']:
            # The re-emitted package is compared byte for byte with the projected artifact, so the live-domain
            # pre-check (editor_product_list_domain.check_suite) is waived for this one emission only; the
            # reason per package is recorded in the policy (list_domain_waiver_reason).
            from unittest.mock import patch
            import editor_product_list_domain  # noqa: F401  (a bound producer helper: the waived pre-check lives here)
            with patch('editor_product_list_domain.check_suite', lambda s: None):
                P.emit_artifacts(suite_path, suite, str(out), base_addr=0, artifact_role='disk-lib')
        else:
            P.emit_artifacts(suite_path, suite, str(out), base_addr=0, artifact_role='disk-lib')
        blob = out.with_suffix('.blob.bin').read_bytes()
        N.require(blob == N.bound(policy['projected_blob']), name + ' re-emission differs from projected blob')
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
        N.require(names_only(fresh) == names_only(projected), name + ' manifest semantics differ')
        args = (name, name, spec['shelf'])
        deps = tuple(spec['dependencies'])
        row_a, fresh_payload = PK.measured_row(*args, out.with_suffix('.manifest.json'), deps, spec['track'], spec['sector'],
                                               product_build_id=build_id)
        row_b, payload = PK.measured_row(*args, N.local(spec['manifest']['path']), deps, spec['track'], spec['sector'],
                                         product_build_id=build_id)
        N.require(row_a == row_b and fresh_payload == payload, name + ' package re-emission differs')
    return dict(status=status, blob_bytes=len(blob), package_bytes=len(payload), path_only_manifest_fields=differs,
                disasm_listing_digest_equal=disasm_equal)


def comfort_reemission(build_id):
    return reemission(build_id, 'repl-comfort')


def defstruct_reemission(build_id):
    return reemission(build_id, 'defstruct')


def check():
    result = packages(O.policy()['product_build_id'])
    files = O.policy()['files']
    for name, data in list(result['payloads'].items()) + [('L65INDEX', result['index'])]:
        N.require(N.identity(data) == files[name.upper()], 'package payload differs from Final: ' + name)
    comfort = comfort_reemission(O.policy()['product_build_id'])
    defstruct = defstruct_reemission(O.policy()['product_build_id'])
    return dict(status='PASS: SIX PUBLIC PACKAGES AND INDEX', packages=len(result['rows']), comfort_reemission=comfort,
                defstruct_reemission=defstruct,
                bytes={k: len(v) for k, v in result['payloads'].items()}, mutations=result['mutations'])


if __name__ == '__main__':
    print(json.dumps(check(), indent=2, default=str))
