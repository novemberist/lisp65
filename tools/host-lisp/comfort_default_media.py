"""Artifact-only replacement Seed media, fixed predecessor geometry, fresh CRCs."""
import os,sys,json,hashlib,struct,copy,subprocess,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools/host-lisp'))
import comfort_library_medium as L
import runtime_overlay_bank as BANK
import c2_product_substitution_link as P
import c2_lite_canonical_product as CAN
import c2_lite_media_product as M
import boot_only_carrier_prg as PRG
import c2_v160_refill_boundary_witness_media_repair as FACADE
from elf_truth import ElfTruth
OUT=ROOT/'build/comfort-default-r2/seed';MED=None;ART=None
BASE=ROOT/'build/nested-error-recovery-seed-medium-r1';OLD=BASE/'materialized'
ELF=ROOT/'build/comfort-default-product-r2/wplto/resident-island-seed.prg.elf'
READOBJ=ROOT/'tools/llvm-mos/bin/llvm-readobj'
def sha(b):return hashlib.sha256(b).hexdigest()
def bind(p):return dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=sha(p.read_bytes()))
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def run(cmd):
 r=subprocess.run(list(map(str,cmd)),cwd=ROOT,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 assert r.returncode==0,r.stdout.decode('latin1');return r.stdout.decode('latin1')
def readbase():
 assert sha((BASE/'packed/hardware-sp-seed.d81').read_bytes())==L.EXPECT['d81']
 return L.D81.visible_files((BASE/'packed/hardware-sp-seed.d81').read_bytes())
def truths():return [ElfTruth.read(p,llvm_readobj=READOBJ,include_section_data=True) for p in [OLD/'lisp65-c2-substitution-linked.prg.elf',ELF]]
def validate_family(fam,value,regions,A,B):
 raw=regions[0];rows=value['slices']
 for row in rows:
  data=regions[row['region_id']][row['file_offset']:row['file_offset']+row['file_size']]
  assert data==B.section_bytes(row['section'])
  assert sha(data)==row['sha256'] and BANK.crc16_ccitt_false(data)==row['crc16']
  record=bytearray(raw[32+32*row['id']:64+32*row['id']]);saved=int.from_bytes(record[22:24],'little');record[22:24]=b'\0\0';assert BANK.crc16_ccitt_false(record)==saved==row['record_crc16']
 projected=bytearray(raw)
 if fam=='session':
  external=rows[52];assert external['region_id']==2 and external['source_address']==0x2ee00
  assert regions[2]==B.section_bytes('.lisp65_rt_card2b_disk')
  for src,dst in ((53,52),(54,53)):
   r=bytearray(raw[32+32*src:64+32*src]);struct.pack_into('<H',r,0,dst);r[22:24]=bytes(2);struct.pack_into('<H',r,22,BANK.crc16_ccitt_false(r));projected[32+32*dst:64+32*dst]=r
  projected[32+32*54:64+32*54]=bytes(32);projected.__setitem__(7,54);BANK._refresh_catalog_crcs(projected)
 bases={r['source_address']-r['file_offset'] for r in rows if r['region_id']==0};assert len(bases)==1
 parsed=BANK.validate_region_images(bytes(projected),bytes(regions[1]),expected_build_id=value['profile_build_id'],expected_vma=value['policy']['common_vma'],max_slice_bytes=value['policy']['max_slice_bytes'],format_version=4,main_source_base=bases.pop(),overflow_source_base=0x5bd00)
 assert len(parsed.slices)==len(rows)-(fam=='session')
 # Reject a stale overflow-header binding while all per-slice fields remain valid.
 if fam=='session':
  stale=bytearray(projected);stale[30]^=1;BANK._refresh_header_crc(stale)
  try:BANK.validate_region_images(bytes(stale),bytes(regions[1]),expected_build_id=value['profile_build_id'],expected_vma=value['policy']['common_vma'],max_slice_bytes=value['policy']['max_slice_bytes'],format_version=4,main_source_base=0x30000,overflow_source_base=0x5bd00)
  except BANK.OverlayBankError:pass
  else:raise AssertionError('stale overflow CRC accepted')
 return dict(slices=len(rows),all_payloads_match_linked_ELF=True,all_record_crcs=True,header_crc16=int.from_bytes(raw[26:28],'little'),directory_crc16=int.from_bytes(raw[24:26],'little'),overflow_header_crc16=int.from_bytes(raw[30:32],'little'))
def prepare():
 assert json.loads((OUT/'inventory.json').read_text())['unclassified_bytes']==0
 assert not MED.exists(),'one artifact preparation; inspect existing output'
 ART.mkdir(parents=True);before=readbase();A,B=truths()
 assert bind(ELF)==json.loads((OUT/'inventory.json').read_text())['ELFs'][1]
 address_log=run(['python3','tools/host-lisp/comfort_state_address.py','--check'])
 import comfort_state_address as ADDRESS
 assert ADDRESS.OUTPUT.read_text()==ADDRESS.generated_text()
 import re
 hi=int(re.search(r'%comfort-state-hi \(\) (\d+)',ADDRESS.generated_text())[1]);lo=int(re.search(r'%comfort-state-lo \(\) (\d+)',ADDRESS.generated_text())[1])
 assert hi*256+lo==B.symbol('lisp65_comfort_state').value==0xbff6
 save(MED/'address-check.json',dict(status='PASS',log=address_log,ELF=bind(ELF),address=hi*256+lo,generated=bind(ADDRESS.OUTPUT)))
 # Exact base files establish all unchanged roles, overwritten below where derived from the Seed.
 for name,data in before.items():(ART/name.decode().lower()).write_bytes(data)
 famproof={};manifests=[]
 for fam in ('boot','session'):
  v=json.loads((OLD/f'runtime-overlays-{fam}-final.json').read_text())
  regions={0:bytearray((OLD/f'runtime-overlays-{fam}-final.bin').read_bytes()),1:bytearray((OLD/v['overflow_storage']['file']).read_bytes())}
  if fam=='session':regions[2]=bytearray((OLD/v['external_storage']['file']).read_bytes())
  for r in v['slices']:
   sec=r['section'];old=A.section_bytes(sec);new=B.section_bytes(sec);assert len(old)==len(new)==r['file_size']
   off=r['file_offset'];rid=r['region_id'];assert regions[rid][off:off+len(old)]==old
   regions[rid][off:off+len(new)]=new;r['sha256']=sha(new);r['crc16']=BANK.crc16_ccitt_false(new)
   at=32+32*r['id'];struct.pack_into('<H',regions[0],at+20,r['crc16']);regions[0][at+22:at+24]=bytes(2)
   r['record_crc16']=BANK.crc16_ccitt_false(regions[0][at:at+32]);struct.pack_into('<H',regions[0],at+22,r['record_crc16'])
  over=regions[1];crc=BANK.crc16_ccitt_false(over)
  struct.pack_into('<I',regions[0],28,len(over)|((crc if over else 0)<<16));BANK._refresh_catalog_crcs(regions[0])
  v['overflow_storage'].update(crc16=crc,sha256=sha(over));v['storage'].update(crc16=BANK.crc16_ccitt_false(regions[0]),sha256=sha(regions[0]));v['catalog'].update(directory_crc16=int.from_bytes(regions[0][24:26],'little'),header_crc16=int.from_bytes(regions[0][26:28],'little'))
  v['elf']=bind(ELF);v['elf']['file']=str(ELF)
  famproof[fam]=validate_family(fam,v,regions,A,B)
  (ART/(fam+'.bin')).write_bytes(regions[0])
  (MED/v['overflow_storage']['file']).write_bytes(over)
  if fam=='session':
   (ART/'region1.bin').write_bytes(over)
   assert regions[2]==before[b'CODE.BIN'][0xee00:0xee00+len(regions[2])]
  path=MED/f'runtime-overlays-{fam}-final.json';save(path,v);manifests.append(path)
 # Mapped Bank-2 data and the E000 window have no changed linked byte.
 for s in A.sections:
  if s.name.startswith(('.lisp65_c2_mapped_','.lisp65_c2_kernal_window.')) and s.section_type!='SHT_NOBITS':assert A.section_bytes(s.name)==B.section_bytes(s.name)
 assert A.section_bytes('.lisp65_c2_vectors')==B.section_bytes('.lisp65_c2_vectors')
 # The established 40-byte verifier/family binding is freshly derived from the rebuilt catalogs.
 table=P.verifier_binding_bytes(*manifests)+P.family_stage_binding_bytes(*manifests);assert len(table)==40
 (MED/'runtime-overlay-verifier-bindings.bin').write_bytes(table)
 prg=MED/'lisp65-c2-substitution-linked.prg';prg.write_bytes(ELF.with_suffix('').read_bytes())
 FACADE.materialize_facade(prg,ELF,MED/'facade-materialization.json')
 unbound=prg.read_bytes();(MED/'lisp65-c2-substitution-unbound.prg').write_bytes(unbound)
 # This also checks every PT_LOAD resident byte against the linked ELF before publication.
 PRG.from_elf(ELF,unbound)
 raw=bytearray(unbound);base=int.from_bytes(raw[:2],'little');at=B.section('.lisp65_runtime_overlay_verifier_bindings').address-base+2
 raw[at:at+40]=table
 oldbinding=json.loads((OLD/'kernal-window-publish-last.json').read_text());window=before[b'WINDOW.BIN'];crc=BANK.crc16_ccitt_false(window)
 assert sha(window)==oldbinding['single_product_link_window']['sha256']
 for r in oldbinding['binding_operands']:
  r['published_value']=(crc>>8)&255 if r['name'].endswith('high') else crc&255
  assert raw[r['file_offset']]==r['compiled_value'];raw[r['file_offset']]=r['published_value']
 save(MED/'kernal-window-publish-last.json',oldbinding)
 prg.write_bytes(raw)
 domain=set(range(at,at+40))|{r['file_offset'] for r in oldbinding['binding_operands']}
 assert all(x==y or i in domain for i,(x,y) in enumerate(zip(unbound,raw)))
 save(MED/'total-publish-last-domain.json',dict(status='passed',changes_outside_declared_domains=0,declared_domain_bytes=len(domain),bound_product_sha256=sha(raw),unbound_product_sha256=sha(unbound)))
 extended=PRG.from_elf(ELF,bytes(raw),publication_dir=MED);(ART/'lisp65.prg').write_bytes(extended)
 CAN.ARTIFACTS=ART
 stage,bootgeometry=CAN.build_boot_stage(ELF,ART/'profile')
 # Emit only the Comfort disk library. This command does not execute the suite cases.
 package=MED/'repl-comfort';log=run(['python3','tools/host-lisp/bytecode_p0_stdlib.py','--emit-artifacts',package,'--artifact-role','disk-lib','--base-addr','0x000000','config/comfort-default-plane/libraries/repl-comfort-suite.json'])
 (MED/'library-emission.log').write_text(log)
 manifest=package.with_suffix('.manifest.json');v=json.loads(manifest.read_text());assert v['code_bytes']==package.with_suffix('.blob.bin').stat().st_size<=1000
 assert v['private_inline_functions']==['%comfort-state-hi','%comfort-state-lo']
 libs=json.loads(L.LIBRARIES.read_text());bid=libs['product_build_id'];specs=[(r['name'],r['shelf'],ROOT/r['manifest']['path'],tuple(r['dependencies'])) for r in libs['libraries']]+[('repl-comfort','repl',manifest,())]
 packages=[]
 for name,shelf,man,deps in specs:
  row,data=L.F.measured_row(name,name,shelf,man,deps,1,1,product_build_id=bid);(ART/name).write_bytes(data)
  if name!='repl-comfort':assert data==before[name.upper().encode()]
  packages.append(dict(name=name,shelf=shelf,manifest=bind(man),dependencies=deps,artifact=bind(ART/name),row=row))
 (ART/'init.l65').write_bytes((ROOT/'config/comfort-default-plane/libraries/INIT.L65').read_bytes())
 save(MED/'runtime-receipt.json',dict(status='PASS: artifact derivation; no product compiler or linker',ELF=bind(ELF),base=bind(BASE/'packed/hardware-sp-seed.d81'),families=famproof,boot_geometry=bootgeometry,publication=bind(MED/'total-publish-last-domain.json'),product_build_id=bid,comfort_bank2_bytes=v['code_bytes'],packages=packages))
 print('PASS runtime/catalog CRCs and six packages; Comfort',v['code_bytes'])
def stager():
 v=json.loads((MED/'runtime-receipt.json').read_text());old=json.loads((BASE/'packed/delivery-population.json').read_text());rows=[]
 for r in old['rows']:
  p=ART/r['name'];rows.append(dict(r,path=p,bytes=p.stat().st_size,crc32=M.crc32(p.read_bytes())))
 M.RECORDS=len(rows);M.DESCRIPTOR_BYTES=M.HEADER_BYTES+M.RECORD_BYTES*len(rows)
 desc,bid=M.make_descriptor(rows,int(sha((ART/'profile').read_bytes())[:8],16));(ART/'boot.id').write_bytes(desc)
 parsed=M.parse_descriptor(desc,bid,rows);negative=M.mutation_gate(desc,bid,rows);domain=M.stage_domain_gate(rows)
 stageout=MED/'stager';stageout.mkdir()
 for n in ('delivery-stager-main.c','delivery-roles.h'):
  source=BASE/'packed'/n
  assert bind(source)['sha256']==old['source' if n.endswith('.c') else 'header']['sha256']
  (stageout/n).write_bytes(source.read_bytes())
 M.STAGER_C=stageout/'delivery-stager-main.c'
 gate=M.compile_stager(bid,rows,build_dir=stageout,stager=ART/'autoboot.c65',stager_map=stageout/'autoboot.c65.map',compile_defines=('-DLISP65_STARTUP_REQUIRE_EXPERIENCE','-Iscripts','-include',str(stageout/'delivery-roles.h')))
 save(MED/'descriptor-stager-receipt.json',dict(status='PASS',descriptor=bind(ART/'boot.id'),build_id=bid,parsed=parsed,mutations=negative,domain=domain,stager=gate,stager_builds=1,product_links=0))
 print('PASS descriptor and cold stager')
def pack():
 v=json.loads((MED/'runtime-receipt.json').read_text());json.loads((MED/'descriptor-stager-receipt.json').read_text());before=readbase()
 runtime=[r['name'] for r in json.loads((BASE/'packed/delivery-population.json').read_text())['rows']]
 variants=[('comfort-default',True,ART/'init.l65'),('control-no-comfort',False,ART/'init.l65'),('control-v240-init',True,ROOT/'config/c2-v240-public-plane/libraries/INIT.L65')]
 result=[]
 for label,comfort,init in variants:
  out=MED/label;out.mkdir(exist_ok=True);medium=out/(label+'.d81')
  entries=[(ART/n,n) for n in ['autoboot.c65','boot.id',*runtime]]+[(init,'init.l65')]
  selected=[r for r in v['packages'] if comfort or r['name']!='repl-comfort']
  entries += [(ART/r['name'],r['name']) for r in selected]
  index=out/'l65index';index.write_bytes(L.L65I.encode_index([r['row'] for r in selected]));entries.append((index,'l65index'))
  if medium.exists():
   provisional=medium.read_bytes()
   assert {L.D81.entry_name(s.record):L.D81.read_record_payload(provisional,s.record) for s in L.D81.directory_slots(provisional) if s.record[2]}=={n.upper().encode():p.read_bytes() for p,n in entries}, 'partial image differs'
  else:M.build_d81(medium,'L65SYS,65',entries)
  M.D81.stamp_product_boot_marker(medium)
  locators=L.L65I.d81_locators(medium);rows=[];payloads={}
  for r in selected:
   row,data=L.F.measured_row(r['name'],r['name'],r['shelf'],ROOT/r['manifest']['path'],tuple(r['dependencies']),*locators[r['name']],product_build_id=v['product_build_id']);assert data==(ART/r['name']).read_bytes();rows.append(row);payloads[r['name']]=data
  index.write_bytes(L.L65I.encode_index(rows))
  # Replacing only the same-sized index leaves package locators stable.
  run(['c1541',medium,'-delete','l65index']);run(['c1541',medium,'-write',index,'l65index'])
  assert all(L.L65I.d81_locators(medium)[n]==locators[n] for n in payloads)
  raw=medium.read_bytes();L.D81.validate_bam(raw);actual=L.D81.visible_files(raw);expected={n.upper().encode():p.read_bytes() for p,n in entries};assert actual==expected
  assert L.L65I.decode_index(actual[b'L65INDEX'],payloads,artifact_build_id=v['product_build_id'])==rows
  mutations=L.L65I.mutation_gate(actual[b'L65INDEX'],payloads,artifact_build_id=v['product_build_id'])
  files={n.decode():dict(bytes=len(data),sha256=sha(data)) for n,data in sorted(actual.items())}
  placement={n.decode():r for n,r in L.directory(raw).items()}
  receipt=dict(status='PASS: every file read back',label=label,medium=bind(medium),index=bind(index),init=bind(init),packages=rows,files=files,placements=placement,mutations=mutations,emulator='NOT RUN; reviewer rows pending')
  save(out/'readback.json',receipt);result.append(receipt)
 save(MED/'media-receipt.json',dict(status='PASS: product plus two controls; host artifact/readback only',media=result,product_links=0,emulator_runs=0,device_contacts=0))
 print(json.dumps([{r['label']:r['medium']['sha256']} for r in result],indent=2))
# Fixed replacement-Seed authority; reject changed inputs before producing artifacts.
INPUT_SHA256 = {'build/comfort-default-product-r2/wplto/resident-island-seed.prg.elf': 'd555f01fbac51bb5fbc035b2b595e95e3c8e3bedc584c87112bca8b073e31444', 'lib/repl-comfort-v250.lisp': '5a9ee1bc588e062b97d1bad26e780c299f80fe929ef6900f504c6a4195a8d12f', 'lib/comfort-state-address.lisp': 'ef9de3ca578ba82d67bd1ff7df4b3e4c0230a2d3ac8422f3adbce3a110d8a1ef', 'config/comfort-default-plane/README.md': 'aae99b44745b2788a4ca71dfe20877b713e28ffdabc807db3093b20a5fe4e6d8', 'config/comfort-default-plane/libraries/INIT.L65': 'c97f5878cb0b862dd101fea0edb9c229246ea6e126eb292cf9f032416fdbeb40', 'config/comfort-default-plane/libraries/libraries.json': 'aa5d6558c91a92ff8e53d968ba10ca57e4ebc796a8b14f7601160f8187e049d8', 'config/comfort-default-plane/libraries/repl-comfort-suite.json': '2384bf4959d0422200f3b880138cd336071b2d8597a3cb8fd1cda87b5514b9d2', 'config/comfort-default-plane/media-authority.json': '8480091e788f905431e365b4bd841c09aa9bb21b26cebb03d667801aeeeefffe', 'config/comfort-default-plane/plane.json': 'e45ef0d351b726d30d3a4e20ed67b3df2ff4e88a661545d898cd8198d459998d'}

def main():
 import argparse
 global MED, ART
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('action',choices=['prepare','stager','pack'])
 parser.add_argument('--output-dir',type=Path,required=True)
 args=parser.parse_args()
 assert os.environ.get('PYTHONDONTWRITEBYTECODE')=='1'
 for name,expected in INPUT_SHA256.items():
  assert sha((ROOT/name).read_bytes())==expected, 'input hash drift: '+name
 MED=args.output_dir.resolve();MED.relative_to(ROOT)
 ART=MED/'artifacts'
 {'prepare':prepare,'stager':stager,'pack':pack}[args.action]()
if __name__=='__main__':main()
