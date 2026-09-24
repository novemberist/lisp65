"""Read-only first native IDE entry on the staged candidate, no acceptance shortcut."""
import argparse,hashlib,json,os,re,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=ROOT/'build/dirty-anchor-mini-r1';HERE.mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT/'tools/host-lisp'))
import native_cycle_stationary as N
import dwx_retroactive_red_replay as R
from elf_truth import ElfTruth
ap=argparse.ArgumentParser();ap.add_argument('--attempt',required=True);ap.add_argument('--baseline',action='store_true');opt=ap.parse_args()
OUT=HERE/('native-entry-probe-'+opt.attempt);assert not OUT.exists();OUT.mkdir()
HIST=OUT/'pc-current.txt';os.environ['LISP65_DWX_PC_OUTPUT']=str(HIST)
identity=json.loads((ROOT/'build/dirty-anchor-card-r1/ready-instrument.json').read_text())
role='baseline' if opt.baseline else 'candidate'
prior=next(w for w in identity['worlds'] if w['role']==role)
packed=dict(elf=prior['ELF'],medium=prior['medium'])
t=ElfTruth.read(N.checked_binding(packed['elf']),llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',include_section_data=True)
def code(name,n=None):
    s=t.symbol(name);sec=t.section(s.section)
    return s.value,t.section_bytes(s.section)[s.value-sec.address:s.value-sec.address+(n or s.bytes)]
main,sig=code('_start',16)
assert main==prior['main'] and sig.hex()==prior['signature'] and t.symbol('vm_callprim').value==prior['vm_callprim']
entry,raw=code('c2_kernal_event_poll');assert raw[0]==0xa5
args=argparse.Namespace(xemu=N.checked_binding(prior['binary']),rom=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/MEGA65.ROM')),sd_image=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/mega65.img')),timeout=1200)
class Monitor(R.ProbeMonitor):
    def wait_screen(self,required,timeout=12):return super().wait_screen(required,timeout=240)
R.ProbeMonitor=Monitor
report=dict(status='DIAGNOSTIC ONLY',medium=packed['medium'],ELF=packed['elf'],observer=prior['binary'],driver=N.bind(Path(__file__)),product_builds=0,device_contacts=0)
report['world']=role
ledger=json.loads((ROOT/'config/bytecode-abi-ledger.json').read_text())
screen_pid=next(p['id'] for p in ledger['prim_identities'] if p['canonical_name']=='screen-put-char')
def screen_calls(binding):return N.histogram_calls(binding,entry,screen_pid)[1]
read_pid=next(p['id'] for p in ledger['prim_identities'] if p['canonical_name']=='read-key')
_,dispatch=code('vm_callprim',100)
jump=dispatch.index(bytes.fromhex('0aaaa51a7c'))+5
table=int.from_bytes(dispatch[jump:jump+2],'little')
def mapped_bytes(address,n):
    owners=[s for s in t.sections if 'SHF_ALLOC' in s.flags and s.address<=address and address+n<=s.address+s.bytes]
    assert len(owners)==1,(address,owners)
    s=owners[0];return t.section_bytes(s.name)[address-s.address:address-s.address+n]
read_entry=int.from_bytes(mapped_bytes(table+2*read_pid,2),'little')
assert mapped_bytes(read_entry,2)[0]==0xa5, 'expected two-byte LDA zp at read-key entry'
report['read_entry']=dict(table=table,pid=read_pid,pc=read_entry,first_instruction=mapped_bytes(read_entry,2).hex())
def read_calls(binding):return N.histogram_calls(binding,entry,read_pid)[1]
run=R.start_run('candidate',N.checked_binding(packed['medium']),OUT,args)
m=run['monitor'];owned=False
def row():return m.memory_range(0x0800+24*80,80)
def show(b):return ''.join(chr((x&127)+64) if (x&127)<27 and (x&127)>0 else chr(x&127) for x in b)
def snap(name):
    assert 'DWX PC save: 0' in m.command('~pcsave')
    path=OUT/(name+'.txt');path.write_bytes(HIST.read_bytes());return N.bind(path)
def wait_pc(expected):
    deadline=time.monotonic()+60
    while time.monotonic()<deadline:
        reg=m.command('r');matches=re.findall(r'^([0-9A-F]{4}) ([0-9A-F]{2}) ',reg,re.M)
        if matches and int(matches[-1][0],16)==expected:return reg
        time.sleep(.01)
    raise AssertionError(('native PC timeout',expected))
def wait_poll():return wait_pc(entry+2)
try:
    m.type_text('(edit)\r')
    deadline=time.monotonic()+240
    while time.monotonic()<deadline:
        if bytes((19,3,18,1,20,3,8)) in row():break
        time.sleep(.1)
    else:raise AssertionError('IDE did not open')
    m.begin_breakpoint_connection();owned=True
    m.command(f'b {entry:04x}');report['ready_registers']=wait_poll()
    assert m.memory16(entry)==raw[:16]
    report['ready_row']=show(row());report['ready_row_hex']=row().hex()
    report['ready_pc']=snap('ready');report['ready_cycles']=m.cycle_count()
    report['ready_counters']=list(m.memory16(t.symbol('C2K_INPUT_EVENTS_RAW').value)[:4])
    response=m.command('~keyevent 58 10');report['injection']=response
    assert 'rejected' not in response.lower(),response
    # Successful output path: A=1, LDZ #0, RTS. Break after LDZ, before RTS.
    # Unlike a byte-change watch this also witnesses repeated identical keys.
    success=raw.index(bytes.fromhex('a901a30060'))
    assert raw.count(bytes.fromhex('a901a30060'))==1
    report['success_return_code']=dict(pc=entry+success,bytes='a901a30060')
    zp=m.memory16(raw[1]);event=zp[0]+256*zp[1]
    report['event_pointer']=event
    m.command(f'b {entry+success+2:04x}');m.command('t0')
    report['event_return_registers']=wait_pc(entry+success+4)
    report['event_output']=m.memory16(event)[:2].hex()
    assert report['event_output']=='5810'
    m.command(f'b {entry:04x}');m.command('t0')
    rejected=[]
    for i in range(1000):
        reg=wait_poll();r=row();count=list(m.memory16(t.symbol('C2K_INPUT_EVENTS_RAW').value)[:4])
        completion=snap(f'open-poll-{i}')
        if (opt.baseline or count[3]==1) and bytes((77,45,24,32)) in r and read_calls(completion)>read_calls(report['ready_pc']):
            report['open_registers']=reg;report['open_row']=show(r);report['open_row_hex']=r.hex();report['open_counters']=count
            report['open_cycles']=m.cycle_count()-report['ready_cycles'];report['open_pc']=snap('open');break
        rejected.append(dict(index=i,row=r.hex(),counters=count));report['intermediate_polls']=rejected;m.command('t0')
    else:raise AssertionError('M-x completed entry not observed')
    report['intermediate_polls']=rejected;report['status']='PASS: NATIVE M-X ENTRY DIAGNOSTIC; PAIRED LANES STILL OWED'
    print(report['status'],report['open_cycles'],report['open_row'],flush=True)
    def key(code,expected,tag):
        before=m.cycle_count();prior_count=list(m.memory16(t.symbol('C2K_INPUT_EVENTS_RAW').value)[:4])
        start_row=row();before_pc=snap(tag+'-before')
        zp=m.memory16(raw[1]);pointer=zp[0]+256*zp[1]
        m.queue_one(code);m.command(f'b {entry+success+2:04x}');m.command('t0')
        returned=wait_pc(entry+success+4)
        service_start=m.cycle_count();service_before_pc=snap(tag+'-service-before')
        delivered=m.memory16(pointer)[:2].hex()
        # The next read-key dispatch is an executed input-loop boundary.
        # Periodic event polls during bytecode work are not completion.
        m.command(f'b {read_entry:04x}');m.command('t0')
        next_read=wait_pc(read_entry+2)
        service_cycles=m.cycle_count()-service_start;service_after_pc=snap(tag+'-service-after')
        m.command(f'b {entry:04x}');m.command('t0')
        intermediate=[]
        for i in range(100):
            registers=wait_poll();screen=row();counts=list(m.memory16(t.symbol('C2K_INPUT_EVENTS_RAW').value)[:4])
            witness=snap(tag+f'-poll-{i}')
            # Released 2.2.0 has the acknowledged stale status-cache defect.
            # Its next blocking read-key entry, after the successful event
            # return, proves completion; its stale text is retained, not used
            # as a promise of the repaired display.
            screen_ok=(screen[expected]==160 if isinstance(expected,int) else expected in screen)
            if screen_ok and counts[3]==((prior_count[3]+1)&255) and screen_calls(witness)>screen_calls(before_pc) and read_calls(witness)>read_calls(before_pc):break
            intermediate.append(dict(row=screen.hex(),counters=counts));m.command('t0')
        else:raise AssertionError(('settled screen not observed',tag,screen.hex()))
        result=dict(service_cycles=service_cycles,service_before_pc=service_before_pc,service_after_pc=service_after_pc,tag=tag,code=code,cycles=m.cycle_count()-before,counters_before=prior_count,counters_after=counts,
                    before_pc=before_pc,after_pc=snap(tag+'-after'),registers=registers,next_read=next_read,event=delivered,row=screen.hex(),intermediate=intermediate)
        report.setdefault('keys',[]).append(result)
        (OUT/'progress.json').write_text(json.dumps(report,indent=2)+'\n')
        print(tag,result['cycles'],show(screen),flush=True)
    # Default M-x command is find-file; Return opens that minibuffer.
    key(13,bytes((9,12,5,58,32)),'find-file-open')
    for n in range(1,17):key(97,bytes((1,))*n+b'\xa0',f'key-{n:02d}')
except BaseException as exc:
    report['error']=repr(exc)
    try:report['failure_screen']=m.screen()
    except Exception as screen_error:report['screen_error']=repr(screen_error)
    raise
finally:
    if owned:
        m.command('~pcclearbreak');m.end_breakpoint_connection()
    try:report['shutdown']=R.finish_run(run)
    finally:(OUT/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
