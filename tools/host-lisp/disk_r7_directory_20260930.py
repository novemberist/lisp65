"""Current-source directory-chain regressions using the real compiled IDE reader.

Adapted from the independent host probe; no snapshot imports or artifact writes.
"""
from pathlib import Path
import json, hashlib
SNAP = Path(__file__).resolve().parents[2]
import bytecode_p0 as B, bytecode_p0_compiler as C
import d81_persistence_fault as D
import m65d_blank_d81_oracle as O
ledger=json.loads((SNAP/'config/bytecode-abi-ledger.json').read_text())
heap=C.prepare_heap([]);directory={};names={}
for path in ['lib/prelude-m1.lisp','lib/stdlib-bytecode-bridges.lisp','lib/stdlib-einsuite-bridges.lisp','lib/runtime-core.lisp','lib/stdlib-lists.lisp','lib/stdlib-strings.lisp','lib/stdlib-load.lisp','lib/m65-disk.lisp','lib/ide-disk.lisp']:
 for form in C.parse_all((SNAP/path).read_text()):
  if not isinstance(form,list) or form[0]!='defun':continue
  name,code,helpers=C.compile_top_form_with_helpers(form,heap,strict_arity=True,abi_profile='dialect-v2',abi_ledger=ledger,prebuilt_primitives=True)
  for n,c in [(name,code)]+helpers:directory[heap.intern(n)]=c;names[id(c)]=n
for source in ['(defun string->list (s) (%string-codes s))','(defun list->string (s) (%string-from-codes s))']:
 name,code,helpers=C.compile_top_form_with_helpers(C.parse_one(source),heap,strict_arity=True,abi_profile='dialect-v2',abi_ledger=ledger,prebuilt_primitives=True)
 directory[heap.intern(name)]=code;names[id(code)]=name
class Cut(Exception):pass
class DiskVM(B.P0VM):
 def __init__(self,image,cut=None,fail=None,postfail=None,**kw):
  self.image=bytearray(image);self.cut=cut;self.fail=fail;self.postfail=postfail;self.writes=[]
  super().__init__(heap=heap.clone(),directory=directory,code_names=names,max_steps=30000000,abi_profile='dialect-v2',abi_ledger=ledger,**kw)
 def _disk_read_sector_impl(self,t,s):
  if not (1<=t<=80 and 0<=s<40):return False
  self.disk_buf=list(D.get_sector(self.image,t,s));return True
 def _disk_write_sector(self,t,s):
  self.io_counters['disk_write']+=1;n=self.io_counters['disk_write']
  if n==self.fail:return False
  data=bytes(self.disk_buf);off=D.sector_offset(t,s);self.image[off:off+256]=data
  self.writes.append(dict(n=n,track=t,sector=s,data=data.hex()))
  if n==self.cut:raise Cut(n)
  return n!=self.postfail
 def call(self,name,*args):return self.run(directory[self.heap.intern(name)],list(args))
 def text(self,s):return self.heap.string_from_text(s)
 def save(self,name,data,new=False):return self.call('m65d-save-new' if new else 'm65d-save',self.text(name),self.text(data))
def blank(n=1):
 im=D.blank_image(n);h=D.sector_offset(40,0);v=O.blank_user_image();im[h:h+256]=v[h:h+256];return bytes(im)
def seeded(n=9,dirs=2):
 im=blank(dirs)
 for i in range(n):im=D.seed_file(im,'f%03d'%i,('OLD%03d'%i).encode())
 return im
def inspect(im):
 result={};owners={};files={};errors=[]
 try:D.validate_bam(im)
 except Exception as e:errors.append(str(e))
 try:
  for slot in D.directory_slots(im):
   if not slot.record[2]:continue
   name=D.entry_name(slot.record).decode('ascii','replace')
   try:
    data=D.read_record_payload(im,slot.record);files[name]=dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),prefix=data[:40].decode('latin1'))
    for ts in D.file_chain(im,slot.record):owners.setdefault(ts,[]).append(name)
   except Exception as e:errors.append(name+': '+str(e))
 except Exception as e:errors.append(str(e))
 allocated=D.allocated_sectors(im);used=set(owners)
 return dict(files=files,errors=errors,visible_free=[list(ts) for ts in sorted(used-allocated)],leaks=[list(ts) for ts in sorted(allocated-used)],crosslinks={str(k):v for k,v in owners.items() if len(v)>1},directory_link=list(D.get_sector(im,40,3)[:2]))
def run_case(im,name,data,mount=True,new=False,**kw):
 v=DiskVM(im,**kw)
 if mount:mounted=v.call('m65d-remount')
 else:
  v.heap.set_symbol_value(v.heap.intern('m65d-remount'),v.heap.cons(B.NIL,B.NIL));mounted=B.mkfix(0)
 error=None;status=None
 try:status=B.fixval(v.save(name,data,new=new))
 except (Cut,B.VMError) as e:error=type(e).__name__+': '+str(e)
 return dict(mount=v.heap.obj_to_text(mounted),status=status,error=error,writes=v.writes,state=inspect(v.image)),v

def verify():
 rows=[]
 for count,dirs,target in [(9,2,'f000'),(9,2,'f001'),(9,2,'f008'),(17,3,'f008'),(144,18,'f000')]:
  image=seeded(count,dirs); result,vm=run_case(image,target,'NEW',mount=count<144)
  assert result['status']==0 and result['error'] is None, (count, target, result['status'], result['error'])
  state=result['state']
  assert len(state['files'])==count
  assert not any(state[k] for k in ('errors','visible_free','crosslinks','leaks'))
  assert state['directory_link']==[40,4]
  for i in range(count):
   name='f%03d'%i;want='NEW' if name==target else 'OLD%03d'%i
   assert state['files'][name.upper()]['sha256']==hashlib.sha256(want.encode()).hexdigest()
  if count==9:
   for fresh in (False,True):
    if fresh:
     vm=DiskVM(vm.image);assert B.fixval(vm.call('m65d-remount'))==0
    for i in range(count):
     name='f%03d'%i;want='NEW' if name==target else 'OLD%03d'%i
     assert vm.heap.obj_to_text(vm.call('%ide-disk-read-lines',vm.text(name)))=='("'+want+'")'
  rows.append(dict(files=count,target=target,mounted=count<144,status=0,all_payloads_exact=True,fresh_ide_reload=count==9))
 # A genuinely free entry 0 with an onward link, nine files still following.
 image=bytearray(seeded(10,2)); slot=D.directory_slots(image)[0]
 for ts in D.file_chain(image,slot.record): D.set_sector_free(image,*ts,True)
 off=D.sector_offset(slot.track,slot.sector)+slot.index*32
 image[off+2:off+32]=bytes(30)
 result,vm=run_case(image,'fresh','NEW',new=True)
 assert result['status']==0 and len(result['state']['files'])==10
 assert result['state']['directory_link']==[40,4]
 assert not any(result['state'][k] for k in ('errors','visible_free','crosslinks','leaks'))
 vm=DiskVM(vm.image);assert B.fixval(vm.call('m65d-remount'))==0
 for name,want in [('fresh','NEW')]+[('f%03d'%i,'OLD%03d'%i) for i in range(1,10)]:
  assert vm.heap.obj_to_text(vm.call('%ide-disk-read-lines',vm.text(name)))=='("'+want+'")'
 rows.append(dict(files=10,target='fresh',operation='save-new-free-entry-zero',fresh_ide_reload=True,status=0))
 return rows

if __name__=='__main__': print(json.dumps(verify(),indent=2))
