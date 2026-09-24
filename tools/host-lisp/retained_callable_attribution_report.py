"""Read captured anchor memory only; halt on published zero code, never replay."""
import hashlib
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'build/retained-callable-attribution-analysis-r1'

def bind(path):
    path = path.resolve()
    return dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())

def u16(data, at):
    return int.from_bytes(data[at:at+2], 'little')

def memory(revision, label, bank):
    return (ROOT/f'build/retained-callable-attribution-r{revision}/{label}-{bank}.bin').read_bytes()

def entry(directory, bank, ordinal):
    at = u16(directory, 30) + ordinal * 10
    row = directory[at:at+10]
    offset, length, base = u16(row, 2), u16(row, 4), u16(row, 6)
    resolution = u16(directory, 32) + base * 2
    return dict(ordinal=ordinal, physical_entry_address=0x50000+at, raw=row.hex(),
                image=row[0], literals=row[1], offset=offset, length=length,
                generation=u16(row, 8), code=bank[offset:offset+length].hex(),
                resolution_base=base, resolutions=directory[resolution:resolution+row[1]*2].hex())

def main():
    a = memory(2, 'before', 'c2d'); b = memory(2, 'first-status', 'c2d')
    preserved = {}
    for name, offset, count in [('header', 0, 48), ('images',48,u16(a,12)*32),
            ('entries',u16(a,30),u16(a,16)*10), ('resolutions',u16(a,32),u16(a,20)*2),
            ('roots',u16(a,34),u16(a,24)*2)]:
        assert a[offset:offset+count] == b[offset:offset+count], name
        preserved[name] = count
    before = memory(2, 'before', 'bank2'); after = memory(2, 'first-status', 'bank2')
    for i in range(u16(a,16)):
        assert entry(a,before,i) == entry(b,after,i)
    d = memory(3, 'decode-return', 'c2d'); bank = memory(3, 'decode-return', 'bank2')
    anonymous = [entry(d,bank,i) for i in [2046,2047]]
    assert anonymous[0]['code'] == 'b5000002030000011b05'
    assert anonymous[1]['resolutions'] == '38e5fcdf'
    word = 0xdffc
    assert ((word >> 1)-0x6000) == 4094 != 2046
    status = memory(2,'first-status','bank0')
    assert status[0x59] == 2 and status[0x2953:0x2957].hex() == '8659a000'
    scratch = memory(3,'decode-return','bank0')
    assert scratch[0xc0f4:0xc0f8].hex() == '0c000700'
    second = {}
    for label in ['fill','before','first-status']:
        dd = memory(4,label,'c2d'); bb = memory(4,label,'bank2'); zz = memory(4,label,'bank0')
        target = entry(dd,bb,878)
        assert target['raw']=='3e0023cc0a009d0c0100' and target['code']=='00'*10
        assert dd[0xd640+693*2:0xd640+693*2+2].hex() == 'dcc6'
        assert ((0xc6dc >> 1)-0x6000) == 878
        for i in range(825,878):
            assert entry(dd,bb,i)['code'] == 'b5000002030000010705'
        second[label] = dict(counts=[u16(dd,o) for o in [12,16,20,24]],
            function_cell_address=0x50000+0xd640+693*2, function_cell='dcc6', target=target,
            image62=dd[48+62*32:48+63*32].hex(), vm_status=zz[0x59])
    zz = memory(4,'first-status','bank0')
    assert zz[0x59] == 2 and zz[0xbb85:0xbb85+10] == bytes(10)
    assert zz[0x5b:0x5e].hex() == 'fe6e03'
    assert zz[0x543e:0x5445].hex() == 'a20286594c4e5f'
    inputs = []
    for revision in range(1,5):
        path = ROOT/f'build/retained-callable-attribution-r{revision}/receipt.json'
        receipt=json.loads(path.read_text())
        driver=receipt['driver']; assert bind(Path(driver['path']))['sha256']==driver['sha256']
        inputs.append(bind(path))
    result = dict(status='HALT: PUBLISHED CODE CORRUPTION; DISTINCT FROM CLEAN DECODER REFUSAL',
        authority='43448850', accepted_world='1e210f3f',
        lambda_case=dict(stage='append decoder phase 12, ERR_RESOLUTION=7, before VM entry',
            entries=anonymous, resolution_word='dffc', decoded_handle=4094, compared_ordinal=2046,
            first_vm_status_store=dict(pc='2953',bytes='8659',value=2),
            preserved_published_bytes=preserved,preserved_code_objects=u16(a,16)),
        capfill_case=dict(snapshots=second, stage='VM object setup: loaded magic 00, expected B5',
            first_vm_status_store=dict(pc='5440',bytes='8659',value=2),
            stopped_pc='5f4e', following_instruction='5442: 4c4e5f JMP $5F4E',
            invalid_code_before_call=True, exact_destructive_writer='NOT ATTRIBUTED: HALT'),
        host=dict(mode='tree',command='build/equivalence-live/dialect-v2-equivalence-check tree build/retained-callable-attribution-analysis-r1/family-host.lisp',
            exit_code=0,binary=bind(ROOT/'build/equivalence-live/dialect-v2-equivalence-check'),
            forms=bind(OUT/'family-host.lisp'),output=bind(OUT/'family-host.txt')),
        inputs=inputs, product_builds=0,observer_builds=0,links=0,seeds=0,device_contacts=0,
        not_executed_after_halt=['remaining shape matrix','persistence/reset cycle','repair object projections','repair Seed budget binding'])
    (OUT/'attribution.json').write_text(json.dumps(result,indent=2)+'\n')
    print(result['status'])
    print('804 prior lambda-case objects preserved; capfill published entry 878 has ten zero bytes before call')
if __name__=='__main__':main()
