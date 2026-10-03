#!/usr/bin/env python3
"""Standalone 2.5.3 public media packer (successor of c2_v251_r2 media).

Derives all 20 2.5.3 Final D81 payloads from one freshly linked native pair (ELF +
raw PRG) and public inputs only, then writes the frozen disk layout:

  plane      SHELF.BIN, static code prefix (six public manifests); C2D.BIN
  families   BOOT.BIN, SESSION.BIN, REGION1.BIN (geometry template + ELF slices)
  native     CODE.BIN (plane + card2b + mapped owners), WINDOW.BIN
  resident   LISP65.PRG (facade, verifier table, publish-last window CRC)
  boot       BOOTSTAGE.BIN, BOOT.ID (descriptor over the derived rows)
  stager     AUTOBOOT.C65 (cold stager compile; fixture only in preflight
             when explicitly requested)
  libraries  six packages + L65INDEX; PROFILE and INIT.L65 public files

No retained medium, family image or predecessor ELF is read.
"""
import hashlib
import json
import shutil
from pathlib import Path

import c2_v253_r1_public_native as N
import c2_v253_r1_public_overlays as O

ROOT = N.ROOT


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def bind(path):
    raw = Path(path).read_bytes()
    return dict(path=str(Path(path).resolve().relative_to(ROOT)), bytes=len(raw), sha256=sha(raw))


def save(path, value):
    Path(path).write_bytes(N.canonical(value))


def publish(B, elf, raw_prg, med, window, family_paths):
    """Resident PRG: facade, 40-byte verifier table, publish-last CRC bytes."""
    import c2_product_substitution_link as P
    import boot_only_carrier_prg as PRG
    import c2_v160_refill_boundary_witness_media_repair as FACADE
    import runtime_overlay_bank as BANK
    policy = O.policy()['publish_last']
    table = P.verifier_binding_bytes(*family_paths) + P.family_stage_binding_bytes(*family_paths)
    N.require(len(table) == 40, 'verifier/family binding extent')
    (med / 'runtime-overlay-verifier-bindings.bin').write_bytes(table)
    prg = med / 'lisp65-c2-substitution-linked.prg'
    prg.write_bytes(raw_prg)
    facade = FACADE.materialize_facade(prg, elf, med / 'facade-materialization.json')
    unbound = prg.read_bytes()
    (med / 'lisp65-c2-substitution-unbound.prg').write_bytes(unbound)
    PRG.from_elf(elf, unbound)
    raw = bytearray(unbound)
    at = B.section('.lisp65_runtime_overlay_verifier_bindings').address - int.from_bytes(raw[:2], 'little') + 2
    raw[at:at + 40] = table
    crc = BANK.crc16_ccitt_false(window)
    operands = []
    for row in policy['binding_operands']:
        N.require(raw[row['file_offset']] == row['compiled_value'], 'compiled publish-last operand drift: ' + row['name'])
        value = (crc >> 8) & 255 if row['name'].endswith('high') else crc & 255
        raw[row['file_offset']] = value
        operands.append(dict(row, published_value=value))
    save(med / 'kernal-window-publish-last.json', dict(format=policy['format'], binding_operands=operands,
                                                       window_crc16=f'0x{crc:04x}'))
    domain = set(range(at, at + 40)) | {r['file_offset'] for r in operands}
    N.require(len(raw) == len(unbound) and all(x == y or i in domain for i, (x, y) in enumerate(zip(unbound, raw))),
              'publication changed undeclared bytes')
    save(med / 'total-publish-last-domain.json', dict(
        status='passed', changes_outside_declared_domains=0, declared_domain_bytes=len(domain),
        bound_product_sha256=sha(bytes(raw)), unbound_product_sha256=sha(unbound)))
    prg.write_bytes(raw)
    extended = PRG.from_elf(elf, bytes(raw), publication_dir=med)
    return bytes(raw), extended, facade


def stager(med, art, profile, fixture=None):
    """Descriptor over derived rows; cold stager compile (4 commands + host ABI)."""
    import c2_lite_media_product as M
    p = O.policy()['delivery']
    rows = []
    for r in p['rows']:
        path = art / r['name']
        data = path.read_bytes()
        rows.append(dict(r, path=path, bytes=len(data), crc32=M.crc32(data)))
    saved = {k: getattr(M, k) for k in ('RECORDS', 'DESCRIPTOR_BYTES', 'STAGER_C', 'STAGER_S',
                                        'ASM_CONTRACT_INCLUDE', 'ASM_CONTRACT_INCLUDE_TOKEN')}
    try:
        M.RECORDS = len(rows)
        M.DESCRIPTOR_BYTES = M.HEADER_BYTES + M.RECORD_BYTES * len(rows)
        descriptor, bid = M.make_descriptor(rows, int(sha(profile)[:8], 16))
        (art / 'boot.id').write_bytes(descriptor)
        parsed = M.parse_descriptor(descriptor, bid, rows)
        negative = M.mutation_gate(descriptor, bid, rows)
        domain = M.stage_domain_gate(rows)
        if fixture is not None:
            shutil.copyfile(fixture, art / 'autoboot.c65')
            gate = dict(status='FIXTURE; stager compile not exercised')
        else:
            out = med / 'stager'
            out.mkdir()
            for key, name in (('source', 'delivery-stager-main.c'), ('header', 'delivery-roles.h')):
                (out / name).write_bytes(N.bound(p[key]))
            M.STAGER_C = out / 'delivery-stager-main.c'
            M.ASM_CONTRACT_INCLUDE = med / 'stager-contract.inc'
            token = '.include "' + str(M.ASM_CONTRACT_INCLUDE.relative_to(ROOT)) + '"'
            assembly = saved['STAGER_S'].read_text()
            N.require(assembly.count(saved['ASM_CONTRACT_INCLUDE_TOKEN']) == 1, 'stager include seam drift')
            M.STAGER_S = med / 'cold-stager-chain.s'
            M.STAGER_S.write_text(assembly.replace(saved['ASM_CONTRACT_INCLUDE_TOKEN'], token))
            M.ASM_CONTRACT_INCLUDE_TOKEN = token
            gate = M.compile_stager(bid, rows, build_dir=out, stager=art / 'autoboot.c65',
                                    stager_map=out / 'autoboot.c65.map',
                                    compile_defines=(*p['compile_defines'], str(out / 'delivery-roles.h')))
    finally:
        for k, v in saved.items():
            setattr(M, k, v)
    return dict(build_id=bid, parsed=parsed, mutations=negative, domain=domain, stager=gate)


def pack(elf, raw_prg_path, out, *, stager_fixture=None):
    """Derive every payload and the D81 into `out` (fresh, under ROOT)."""
    import c2_lite_canonical_product as CAN
    import c2_v253_r1_public_plane as PLANE
    import c2_v253_r1_public_libraries as LIB
    import c2_v253_r1_public_media as MEDIA
    policy = O.policy()
    out = Path(out)
    N.require(out.resolve().is_relative_to(ROOT) and not out.exists(), 'media output must be fresh and under the root')
    med, art = out, out / 'artifacts'
    art.mkdir(parents=True)
    elf, raw_prg_path = Path(elf), Path(raw_prg_path)
    B = O.truth(elf)
    elf_row = bind(elf)
    plane = PLANE.artifacts()
    payloads = {}

    def put(name, raw):
        (art / name.lower()).write_bytes(raw)
        payloads[name] = raw

    fams, paths = O.families(B, med, elf_row)
    put('BOOT.BIN', bytes(fams['boot'][1][0]))
    put('SESSION.BIN', bytes(fams['session'][1][0]))
    put('REGION1.BIN', bytes(fams['session'][1][1]))
    put('CODE.BIN', O.code(B, plane['code'], bytes(fams['session'][1][2])))
    window = O.window(B)
    put('WINDOW.BIN', window)
    put('SHELF.BIN', plane['shelf'])
    N.require(len(plane['c2d']) <= policy['c2d_bytes'], 'C2D prefix exceeds reset domain')
    put('C2D.BIN', plane['c2d'] + bytes(policy['c2d_bytes'] - len(plane['c2d'])))
    bound_prg, extended, facade = publish(B, elf, raw_prg_path.read_bytes(), med, window, paths)
    put('LISP65.PRG', extended)
    profile = N.bound(policy['profile'])
    put('PROFILE', profile)
    put('INIT.L65', N.bound(policy['init']))
    saved = CAN.ARTIFACTS
    try:
        CAN.ARTIFACTS = art
        stage, geometry = CAN.build_boot_stage(elf, art / 'profile')
    finally:
        CAN.ARTIFACTS = saved
    payloads['BOOTSTAGE.BIN'] = stage.read_bytes()
    N.require(plane['build_id'] == policy['product_build_id'], 'plane/product build ID mismatch')
    libs = LIB.packages(plane['build_id'])
    for name, data in libs['payloads'].items():
        put(name.upper(), data)
    put('L65INDEX', libs['index'])
    boot = stager(med, art, profile, stager_fixture)
    payloads['BOOT.ID'] = (art / 'boot.id').read_bytes()
    payloads['AUTOBOOT.C65'] = (art / 'autoboot.c65').read_bytes()
    drift = sorted(n for n, raw in payloads.items() if N.identity(raw) != policy['files'].get(n))
    N.require(set(payloads) == set(policy['files']), 'derived payload population')
    N.require(not drift, 'HALT: derived payloads differ from Final: ' + repr(drift))
    medium = med / 'lisp65-product.d81'
    medium.write_bytes(MEDIA.assemble(payloads))
    N.require(N.identity(medium.read_bytes()) == policy['medium'], 'HALT: reproduced D81 differs')
    roles = {name: bind(art / name.lower()) for name in sorted(payloads)}
    result = dict(
        status='PREFLIGHT ONLY (stager fixture)' if stager_fixture else 'PASS: PUBLIC MEDIA BYTEIDENTICAL',
        medium=bind(medium), roles=roles,
        extended_resident=roles['LISP65.PRG'], c2_resident_prg=bind(med / 'lisp65-c2-substitution-linked.prg'),
        elf=elf_row, raw_prg=bind(raw_prg_path), facade=facade, boot_geometry=geometry,
        families={f: dict(slices=len(v['slices']), storage=v['storage']['sha256']) for f, (v, _) in fams.items()},
        packages=dict(rows=libs['rows'], mutations=libs['mutations']), descriptor=boot,
        all_files_verified=True, files=len(payloads))
    save(med / 'receipt.json', result)
    return result


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('elf', type=Path); p.add_argument('prg', type=Path); p.add_argument('out', type=Path)
    a = p.parse_args()
    print(json.dumps(pack(a.elf, a.prg, a.out), indent=2, default=str))
