"""Execute final descriptor-producing instruction slices, without DMA/I/O.

Bounded functional CPU model only, not a timing or whole-loader proof.
"""
import hashlib,json,re,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/host-lisp'))
from elf_truth import ElfTruth
from cpu6502 import CPU
import runtime_overlay_bank as BANK

def bind(p):return dict(path=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest())

def extract(elf):
 t=ElfTruth.read(elf,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',include_section_data=True)
 f=t.symbol('vm_runtime_overlay_exec_family');job=t.symbol('rtov_edma_job')
 assert job.section=='.bss' and job.bytes==20
 text=subprocess.check_output([str(ROOT/'tools/llvm-mos/bin/llvm-objdump'),'-d','--disassemble-symbols='+f.name,str(elf)],text=True)
 ins={}
 for line in text.splitlines():
  m=re.match(r'\s*([0-9a-f]+):\s+((?:[0-9a-f]{2}\s+)+)\s*\w+',line)
  if m and f.value<=int(m[1],16)<f.value+f.bytes:ins[int(m[1],16)]=bytes.fromhex(m[2])
 triggers=[pc for pc,b in ins.items() if b==b'\x8d\x05\xd7'];assert len(triggers)==1
 end=triggers[0]+3
 stores=[pc for pc,b in ins.items() if len(b)==3 and b[0] in (0x8d,0x8e,0x8c,0x9c) and job.value<=int.from_bytes(b[1:],'little')<job.value+20]
 assert len(stores)==20 and max(stores)<end
 # The straight-line block receives the checked record in the software
 # frame and the checked payload length in rc7:rc6. Derive its frame offset
 # from the emitted pointer construction; no PC or frame-offset literal.
 starts=[pc for pc,b in ins.items() if pc<min(stores) and b==b'\x18' and
         ins.get(pc+1)==b'\xa5\x02' and ins.get(pc+3,b'')[:1]==b'\x69' and ins.get(pc+5)==b'\x48']
 assert starts
 start=max(starts);offset=ins[start+3][1]
 deststore=next(pc for pc,b in ins.items() if len(b)==3 and b[0]==0x8d and int.from_bytes(b[1:],'little')==job.value+14)
 assert ins[deststore-2]==b'\xb1\x02' and ins[deststore-4][:1]==b'\xa0'
 destoffset=ins[deststore-4][1]
 raw=b''.join(b for pc,b in ins.items() if start<=pc<end)
 assert len(raw)==end-start
 return dict(elf=elf,truth=t,start=start,end=end,raw=raw,frame_offset=offset,
             destination_low_offset=destoffset,job=job.value,instructions=ins)

class Model(CPU):
 def __init__(self):super().__init__();self.writes=[]
 def wr(self,a,v):self.writes.append((a&65535,v&255));super().wr(a,v)
 def step(self):
  op=self.rd(self.PC)
  if op==0x9c:self.fetch();self.wr(self.fetch16(),0)
  elif op==0x5a:self.fetch();self.push(self.Y)
  elif op==0x7a:self.fetch();self.Y=self.pull();self.set_zn(self.Y)
  else:super().step()

def execute(code,record,length,vma,patch=None):
 c=Model();c.mem[code['start']:code['end']]=code['raw']
 frame=0x9000;c.mem[2:4]=frame.to_bytes(2,'little')
 c.mem[8]=length>>8;c.mem[9]=length&255
 at=frame+code['frame_offset'];c.mem[at:at+len(record)]=record
 c.mem[frame+code['destination_low_offset']]=vma&255
 c.mem[code['job']:code['job']+20]=bytes([0xa5])*20
 if patch is not None:patch(c,code)
 c.PC=code['start'];count=0
 while c.PC<code['end']:
  assert code['start']<=c.PC<code['end'] and count<200
  c.step();count+=1
 assert c.PC==code['end'] and c.SP==0xfd
 writes=[(a-code['job'],v) for a,v in c.writes if code['job']<=a<code['job']+20]
 assert sorted(a for a,v in writes)==list(range(20))
 trigger=[(a,v) for a,v in c.writes if 0xd700<=a<=0xd70f]
 assert trigger==[(0xd703,1),(0xd702,0),(0xd704,0),(0xd701,code['job']>>8),(0xd705,code['job']&255)]
 return bytes(c.mem[code['job']:code['job']+20])

def expected(row):
 source=row['source_address'];n=row['file_size'];vma=row['vma']
 return bytes([0x0b,0x80,(source>>20)&255,0x81,0,0x85,1,0,0,n&255,n>>8,
               source&255,(source>>8)&255,(source>>16)&15,vma&255,vma>>8,0,0,0,0])

def context(record,row):
 fields=BANK.ENTRY.unpack(record)
 source=fields[2] | (((fields[11]>>8)&15)<<16) | (((fields[11]>>16)&255)<<20)
 assert source==row['source_address'] and fields[3]==row['file_size']
 # This is the verifier's output ABI, not the catalog's serialized layout.
 # Derive field offsets from the actual compiled context declaration.
 path=ROOT/'build/capacity/card2b-product-r1/wplto/generated-product-sources/vm_runtime_overlay.c'
 source_text=path.read_text();body=re.search(r'typedef struct \{([^{}]+)\} rtov_verify_context;',source_text).group(1)
 offsets={};n=0
 for typ,name in re.findall(r'\b(rtov_read_fn|uint16_t|uint8_t)\s+(\w+)\s*;',body):
  offsets[name]=n;n+=1 if typ=='uint8_t' else 2
 assert list(offsets)[:10]==['read','file_off','file_len','entry_off','payload_crc','payload_off','image_limit','flags','slot','count']
 value=bytearray(64)
 for name,x in [('file_off',source&65535),('file_len',fields[3]),('entry_off',fields[6]),('payload_crc',fields[9])]:
  value[offsets[name]:offsets[name]+2]=x.to_bytes(2,'little')
 value[offsets['slot']]=(source>>16)&15;value[offsets['count']]=(source>>20)&255
 return value

def run():
 paths=[ROOT/'build/v2.1/renderer-branch-product-r1/wplto/lisp65-c2-substitution-linked.prg.elf',
        ROOT/'build/capacity/card2b-product-r1/wplto/lisp65-c2-substitution-linked.prg.elf']
 codes=[extract(p) for p in paths];cases=[]
 # Every actual final boot/session descriptor, including the new region-2
 # member, is checked. Records are read from the packed catalog binaries.
 base=paths[1].parent
 for family in ('boot','session'):
  manifest=base/f'runtime-overlays-{family}-final.json'
  value=json.loads(manifest.read_text());raw=(base/f'runtime-overlays-{family}-final.bin').read_bytes()
  for row in value['slices']:
   at=BANK.HEADER_SIZE+row['id']*BANK.ENTRY_SIZE;record=raw[at:at+BANK.ENTRY_SIZE]
   assert len(record)==32
   row={**row,'vma':value['policy']['common_vma']}
   outputs=[execute(code,context(record,row),row['file_size'],row['vma']) for code in codes]
   assert outputs[0]==outputs[1]==expected(row),(family,row['id'],[x.hex() for x in outputs],expected(row).hex())
   cases.append(dict(family=family,id=row['id'],expected=outputs[0].hex(),catalog=bind(manifest)))
 # Mutate each of the 20 descriptor stores and the final trigger. No
 # changed output byte, missing write, or trigger displacement may pass.
 mutations=[];code=codes[1]
 row={**value['slices'][-1],'vma':value['policy']['common_vma']};record=raw[BANK.HEADER_SIZE+row['id']*32:BANK.HEADER_SIZE+(row['id']+1)*32]
 sites=[pc for pc,b in code['instructions'].items() if code['start']<=pc<code['end'] and len(b)==3 and b[0] in (0x8d,0x8e,0x8c,0x9c) and code['job']<=int.from_bytes(b[1:],'little')<code['job']+20]
 for pc in sites+[code['end']-3]:
  def patch(cpu,code,pc=pc):cpu.mem[pc+1]^=0x40
  try:assert execute(code,context(record,row),row['file_size'],row['vma'],patch)==expected(row)
  except AssertionError:mutations.append(pc)
  else:raise AssertionError('descriptor store/trigger mutation survived')
 result=dict(status='PASS',worlds=[bind(p) for p in paths],cases=cases,mutations=mutations,
  instruction_slices=[dict(start=c['start'],end=c['end'],bytes=c['raw'].hex(),
                          frame_offset=c['frame_offset'],destination_low_offset=c['destination_low_offset']) for c in codes],
  model=bind(ROOT/'tools/host-lisp/cpu6502.py'),tool=bind(Path(__file__)),
  context_abi=bind(base/'generated-product-sources/vm_runtime_overlay.c'),
  claim='Executed emitted descriptor/trigger slices for every final catalog record; functional only, not timing or whole-loader reachability.')
 (ROOT/'build/capacity/card2b-r1/descriptor-successor.json').write_text(json.dumps(result,indent=2)+'\n')
 print('PASS',len(cases),'record descriptors',len(mutations),'mutations')
 return result
if __name__=='__main__':run()
