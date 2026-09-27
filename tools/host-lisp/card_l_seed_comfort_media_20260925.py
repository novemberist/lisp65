"""Library-only companion medium for the bound Card L + Comfort watch row.

Reuse the positive Seed's complete runtime and cold stager unchanged; copy
only the accepted Comfort package/index and recompute on-disk locators.
No compiler, linker or guest execution.
"""
import hashlib,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
import d81_persistence_fault as D
import c2_lite_media_product as M
import c2_require_resolver_gate as L
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'build/card-l-seed-medium-r2/comfort'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def main():
    assert not OUT.exists();OUT.mkdir()
    seed=ROOT/'build/card-l-seed-medium-r2/media-seed/card-l.d81'
    comfort=ROOT/'build/comfort-library-medium-r2/packed/cmf240.d81'
    files=D.visible_files(seed.read_bytes());accepted=D.visible_files(comfort.read_bytes())
    old=L.decode_index(files[b'L65INDEX']);new=L.decode_index(accepted[b'L65INDEX'])
    assert len(new)==len(old)+1 and new[-1]['name']=='repl-comfort'
    strip=lambda r:{k:v for k,v in r.items() if k not in ('track','sector')}
    assert list(map(strip,old))==list(map(strip,new[:-1]))
    for row in old:assert files[row['name'].upper().encode()]==accepted[row['name'].upper().encode()]
    files[b'REPL-COMFORT']=accepted[b'REPL-COMFORT'];files[b'L65INDEX']=accepted[b'L65INDEX']
    entries=[]
    for name,raw in files.items():
        p=OUT/name.decode().lower();p.write_bytes(raw);entries.append((p,name.decode().lower()))
    medium=OUT/'card-l-comfort.d81';M.build_d81(medium,'L65SYS,65',entries);M.D81.stamp_product_boot_marker(medium)
    disk=bytearray(medium.read_bytes());slots={D.entry_name(s.record):s.record for s in D.directory_slots(disk) if s.record[2]}
    for row in new:row['track'],row['sector']=D.file_chain(disk,slots[row['name'].upper().encode()])[0]
    located=L.encode_index(new);assert len(located)==len(files[b'L65INDEX'])
    chain=D.file_chain(disk,slots[b'L65INDEX'])
    for i,(t,s) in enumerate(chain):
        pos=D.sector_offset(t,s);disk[pos:pos+256]=D.chain_sector(located,chain,i)
    medium.write_bytes(disk);files[b'L65INDEX']=located;(OUT/'l65index').write_bytes(located)
    assert D.visible_files(disk)==files
    source=D.visible_files(seed.read_bytes())
    assert all(files[k]==v for k,v in source.items() if k!=b'L65INDEX')
    receipt=dict(status='PASS: LIBRARY-ONLY COMPANION; GUEST ROWS PENDING',medium=str(medium.relative_to(ROOT)),sha256=sha(disk),
      positive_seed_sha256=sha(seed.read_bytes()),accepted_comfort_medium_sha256=sha(comfort.read_bytes()),
      comfort_package_sha256=sha(files[b'REPL-COMFORT']),locator_count=len(new),runtime_files_unchanged=True,compiler_calls=0,links=0)
    (OUT/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
