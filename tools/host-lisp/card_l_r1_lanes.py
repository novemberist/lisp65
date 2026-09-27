"""Card L natural lanes versus 2.4.0 Final; inherited first-input boundary and complete 40-key brackets."""
import argparse,json,os,re,sys,time,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools/host-lisp'))
import native_cycle_stationary as N
import dwx_retroactive_red_replay as R
from elf_truth import ElfTruth
from card_l_r1_common import worlds, preview
p=argparse.ArgumentParser();p.add_argument('--attempt',default='card-l-r1');p.add_argument('--dry-run',action='store_true');opt=p.parse_args()
WORLDS=worlds()
if opt.dry_run:
    for w in WORLDS:
        for cap in (1,8): preview(w,ROOT/f'build/input-cost-natural-{opt.attempt}',w['role']+'-'+str(cap),240)
    print('DRY RUN PASS: 4 natural lanes; all brackets, gate <= 1.02; no emulator launched')
    raise SystemExit(0)
OUT=ROOT/f'build/input-cost-natural-{opt.attempt}'
assert not OUT.exists();OUT.mkdir()
instrument=ROOT/'build/card-l-r1/instrument-lanes.json'
identity=json.loads(instrument.read_text());binary=N.checked_binding(identity['binary'])
histogram=OUT/'pc-current.txt';os.environ['LISP65_DWX_PC_OUTPUT']=str(histogram)
ledger=json.loads((ROOT/'config/bytecode-abi-ledger.json').read_text())
pids={x['canonical_name']:x['id'] for x in ledger['prim_identities']}
args=argparse.Namespace(xemu=binary,rom=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/MEGA65.ROM')),sd_image=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/mega65.img')),timeout=240)
shutil.copyfile(Path(N.__file__),OUT/'observer.py')
def snapshot(m,run,index,phase):
    assert 'DWX PC save: 0' in m.command('~pcsave')
    target=run['dir']/f'pc-{index:02d}-{phase}.txt';target.write_bytes(histogram.read_bytes());return N.bind(target)
class ReadyMonitor(R.ProbeMonitor):
    @R.ROWS.owned_readiness
    def wait_screen(self,required,timeout=20):
        self.command(f'b {WORLD["entry"]:04x}')
        deadline=time.monotonic()+90;early=[]
        try:
            while time.monotonic()<deadline:
                response=self.command('r')
                matches=re.findall(r'^([0-9A-F]{4}) ([0-9A-F]{2}) ([0-9A-F]{2}) ',response,re.M)
                if not matches or int(matches[-1][0],16)!=WORLD['paused_pc']:
                    time.sleep(.01);continue
                answer=self.command('~pcsave')
                if 'DWX PC save: 0' not in answer:
                    early.append(response);self.command('t0');continue
                screen=self.screen();assert 'LISP65>' in R.ROWS.decoded_framebuffer(screen)
                start=R.find_input_start(self,0x0800)
                assert self.memory16(WORLD['entry'])==bytes.fromhex(WORLD['entry_code'])[:16]
                target=OUT/('run-'+RUN_ID)/'ready-entry-pc.txt';target.write_bytes(histogram.read_bytes());binding=N.bind(target)
                entry_calls,screen_calls=N.histogram_calls(binding,WORLD['entry'],pids['screen-put-char'])
                _,key_calls=N.histogram_calls(binding,WORLD['entry'],pids['key-event'])
                self.readiness=dict(authority='1536ef74',entry_pc=WORLD['entry'],paused_pc=int(matches[-1][0],16),mode=int(matches[-1][2],16),
                    entry_calls=entry_calls,key_event_calls=key_calls,prompt_cursor_byte=self.memory16(start)[0],
                    counters=list(self.memory16(COUNTER_ADDRESS)[:4]),screen_calls_at_entry=screen_calls,
                    screen_primitive=pids['screen-put-char'],key_primitive=pids['key-event'],entry_snapshot=binding,
                    ELF=WORLD['ELF'],entry_code=WORLD['entry_code'],registers=response,early_unarmed_breaks=early)
                assert entry_calls==key_calls==1
                assert self.readiness['mode']==2 and self.readiness['prompt_cursor_byte']==0xa0
                assert self.readiness['counters']==[0]*4
                (OUT/('run-'+RUN_ID)/'ready-framebuffer.txt').write_text(screen)
                assert 'DWX PC breakpoint cleared' in self.command('~pcclearbreak')
                return screen
            raise AssertionError('first input-loop entry timeout')
        except BaseException:
            self.command('t1');(OUT/('startup-failure-'+RUN_ID+'.txt')).write_text(self.screen());self.command('~exit');raise
R.ProbeMonitor=ReadyMonitor
rows=[]
for WORLD in WORLDS:
    role=WORLD['role']
    packed=dict(elf=WORLD['ELF'],medium=WORLD['medium'])
    medium=N.checked_binding(packed['medium']);elf=N.checked_binding(packed['elf'])
    args.xemu=N.checked_binding(WORLD['binary'])
    os.environ['LISP65_COST_CONFIG']=WORLD['cost_config']
    e=ElfTruth.read(elf,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj');COUNTER_ADDRESS=e.symbol('C2K_INPUT_EVENTS_RAW').value
    for cap in (1,8):
        RUN_ID=role+'-'+str(cap)
        row=N.completed_cycle_trace(RUN_ID,medium,40,OUT,args,packed['elf'],cap,snapshot,require_ready=True)
        row.update(world=role,batch_cap=cap,medium=packed['medium'],ELF=packed['elf'],observer_binary=WORLD['binary']);N.verify_completion(row)
        rows.append(row);(OUT/'rows.json').write_text(json.dumps(rows,indent=2)+'\n')
        print(role,cap,row['cycle_deltas'],'ready-screen-calls',row['readiness']['screen_calls_at_entry'],flush=True)
    N.checked_binding(packed['medium'])
for row in rows:N.verify_trace(row)
assert N.bind(OUT/'observer.py')['sha256']==N.bind(Path(N.__file__))['sha256']
pairs=[]
for cap in (1,8):
    base,seed=[r for r in rows if r['batch_cap']==cap]
    assert len(base['cycle_deltas'])==len(seed['cycle_deltas'])
    ratio=seed['total_cycles']/base['total_cycles']
    assert ratio<=1.02, (cap,ratio)
    pairs.append(dict(batch_cap=cap,ratio=ratio,ceiling=1.02))
result=dict(status='PASS: NATURAL SINGLE-KEY AND BATCHED LANES <= 1.02',rows=rows,comparisons=pairs,
    instrument=N.bind(instrument),parent_driver=N.bind(ROOT/'build/input-cost-attribution-r6/lanes.py'),
    baseline_identity=WORLDS[0],
    observer=N.bind(OUT/'observer.py'),driver=N.bind(Path(__file__)),
    mutations_rejected=N.selftest()+N.completion_selftest()+N.readiness_selftest(),
    product_builds=0,observer_builds=0,links=0,seeds=0,device_contacts=0,excluded_samples=0)
(OUT/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
print(result['status'],flush=True)

import card_l_r1_latency as L
L.RECEIPT=OUT/'receipt.json'
L.OUT=OUT/'latency-qualification.json'
L.main()
