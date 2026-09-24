"""Dated artifact-only media adapter: retain full PRG prefix, append carrier.

Reuse the predecessor's unchanged catalog and library composition. The only
new product-file operation is explicit ELF-to-VMA carrier extraction before
descriptor generation, so destination CRC covers the complete new file.
"""
import builtins
import hashlib
import json
from pathlib import Path
import sys

import boot_only_carrier_prg as PRG
import boot_only_carrier_elf_gate as ELF

ROOT=Path(__file__).resolve().parents[2]
TEMPLATE=ROOT/'tools/host-lisp/ov_crc16_seed_media.py'


def configure():
    text=TEMPLATE.read_text()
    # Drop only the predecessor's historical narrative, not executable code.
    text=text[text.index('from pathlib import Path'):]
    text=text.replace('ov_crc16','boot_only_carrier').replace('ov-crc16','boot-only-carrier')
    scope=dict(__name__='boot_only_carrier_media_configuration',__file__=__file__)
    builtins.exec(compile(text,__file__,'exec'),scope)
    import c2_lite_media_product as MEDIA
    inherited=MEDIA.stage_artifact_map

    def stage(contract,artifacts,*,write):
        elf=artifacts['linked-product-elf']
        prefix=artifacts['c2-resident-prg']
        linked=ELF.check(elf)
        data=PRG.from_elf(elf,prefix.read_bytes(),publication_dir=elf.parent)
        out=scope['M'].OUT/'extended-resident.prg'
        if write and not out.exists():
            out.write_bytes(data)
        if not out.is_file() or out.read_bytes()!=data:
            raise ValueError('extended resident artifact drift; never overwrite')
        def bind(p):
            return dict(path=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size)
        receipt=dict(status='PASS',template=bind(TEMPLATE),elf=bind(elf),
                     prefix=bind(prefix),extended=bind(out),linked=linked,
                     extent_delta=len(data)-prefix.stat().st_size,
                     destination_crc='descriptor generated from extended role; not ordinary file-end')
        target=scope['M'].OUT/'extended-resident.json'
        encoded=json.dumps(receipt,indent=2)+'\n'
        if write and not target.exists(): target.write_text(encoded)
        if not target.is_file() or target.read_text()!=encoded:
            raise ValueError('extended resident receipt drift')
        return inherited(contract,{**artifacts,'c2-resident-prg':out},write=write)

    MEDIA.stage_artifact_map=stage
    return scope


def archive_pre_descriptor():
    out=ROOT/'build/boot-only-carrier-seed-medium-r1'
    packed=out/'packed'; archive=out/'pre-descriptor-attempt-1'
    allowed={'artifacts/bank2-static-code.bin','artifacts/boot-bank3-stage.raw.bin',
             'artifacts/boot-overlay.raw.bin','artifacts/bootstage.bin'}
    found={str(p.relative_to(packed)) for p in packed.rglob('*') if p.is_file()}
    if found!=allowed or archive.exists():
        raise ValueError('not the known pre-descriptor stop; no implicit pack retry')
    records={str(p.relative_to(packed)):hashlib.sha256(p.read_bytes()).hexdigest()
             for p in packed.rglob('*') if p.is_file()}
    packed.rename(archive)
    (out/'pre-descriptor-attempt-1.json').write_text(json.dumps(dict(
        status='PRESERVED: PREFIX GUARD STOP BEFORE DESCRIPTOR OR STAGER',
        files=records,product_builds=0,stager_builds=0,media_links=0,
        cause='VMA-only prefix comparison confused mapped code and postlink bindings'),indent=2)+'\n')


if __name__=='__main__':
    if sys.argv[1:]==['archive-pre-descriptor']:
        archive_pre_descriptor()
        raise SystemExit(0)
    if sys.argv[1:] not in (['configure-only'],['materialize'],['resume'],['pack']):
        raise SystemExit('configure-only | materialize | resume | pack | archive-pre-descriptor')
    scope=configure()
    if sys.argv[1:]==['configure-only']:
        print('PASS: media adapter configured; no compiler, linker or pack invoked')
    elif sys.argv[1:]==['pack']:
        scope['pack']()
    else:
        scope['setup']()
        getattr(scope['M'],sys.argv[1])()
