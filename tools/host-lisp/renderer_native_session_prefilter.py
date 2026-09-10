#!/usr/bin/env python3
"""Bound native renderer session rows, over the exact packed image, headless."""
import argparse,json,time
from pathlib import Path
import renderer_native_session_media as M
import dwx_retroactive_red_replay as R
import dwx_comfort_resume as C
from elf_truth import ElfTruth

ROOT=M.ROOT;OUT=M.OUT
FORK=ROOT/'build/dwx/buffered-repair-three-patch-requalification-r2/receipt.json'

def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def contract():
    old=json.loads((ROOT/'config/v2.1-comfort-buffered-repair-device-session.json').read_text())
    smokes=next(r for r in old['rows'] if r['id']=='G7')['performance_forms']
    return dict(authority='831a48eb',pair=M.pair(),
        groups=[dict(id='native',rows=[
            dict(id='car',form='(car 1)',value='NIL'),
            dict(id='length',form='(length "abc")',value='*** VM: TYPE ERROR'),
            dict(id='define-probe',form='(defun v20-perf-probe (x) (+ x 1))',value='V20-PERF-PROBE'),
            *[dict(id='smoke-'+str(i+1),**r) for i,r in enumerate(smokes)],
            dict(id='d5-marker',form='(+ 4 5)',value='9')]),
        dict(id='recursion-known-issue',rows=[
            dict(id='define-depth',form='(defun sp-depth (n) (if (= n 0) 0 (+ 1 (sp-depth (- n 1)))))',value='SP-DEPTH'),
            dict(id='depth-12',form='(sp-depth 12)',value='12'),
            dict(id='depth-13',form='(sp-depth 13)',failure='repeated E29')]),
        dict(id='printer-known-issue',rows=[
            dict(id='define-nest',form='(defun sp-nest-build (n x) (if (= n 0) x (sp-nest-build (- n 1) (list x))))',value='SP-NEST-BUILD'),
            dict(id='prepare-nest',form='(progn (setq sp-nest (sp-nest-build 23 7)) 777)',value='777'),
            dict(id='print-23',form='(progn (print sp-nest) (terpri) 823)',failure='repeated E29')])],
        choreography={'independent_starts':3,'D5_before_expected_failures':True,
          'after_expected_failure':'stop immediately; no further Lisp input or resume; restore fresh image for next start',
          'device_variant':'B: power off >=30 seconds, power on, owner Freezer-mount then start; not automatic boot A'},
        claim_boundary='Framebuffer and stopped RAM only; no Freezer, physical keyboard, wall-clock or device acceptance claim')

def execute(group):
    M.check();cfg=contract()
    path=OUT/'prefilter-row-contract.json'
    if path.exists():assert json.loads(path.read_text())==cfg
    else:write(path,cfg)
    selected=next(g for g in cfg['groups'] if g['id']==group)
    fork=json.loads(FORK.read_text());assert fork['status']=='PASS: THREE-PATCH FORK REQUALIFIED' and fork['reproduced_reds']==3
    manifest=ROOT/fork['manifest']['path'];assert M.bind(manifest)['sha256']==fork['manifest']['sha256']
    manifest_value=json.loads(manifest.read_text());binary=Path(manifest_value['binary']['path'])
    assert M.bind(binary)['sha256']==fork['tool_identity']['binary_sha256']==manifest_value['binary']['sha256']
    assert len(fork['tool_identity']['patches'])==3
    packed=json.loads((OUT/'packed-receipt.json').read_text());medium=Path(packed['medium']['path'])
    runout=OUT/group;runout.mkdir()
    args=argparse.Namespace(xemu=binary,rom=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/MEGA65.ROM')),
         sd_image=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/mega65.img')),timeout=180)
    truth=ElfTruth.read(Path(cfg['pair']['elf']['path']),llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj')
    run=None;rows=[];error=None
    original_monitor=R.ProbeMonitor
    class StartupMonitor(original_monitor):
        def wait_screen(self,*a,**kw):
            try:return super().wait_screen(*a,**kw)
            except Exception:
                self.command('t1')
                (runout/'startup-stop-framebuffer.txt').write_text(self.screen())
                (runout/'startup-stop-registers.txt').write_text(self.command('r'))
                self.command('~exit')
                raise
    R.ProbeMonitor=StartupMonitor
    try:
        run=R.start_run(group,medium,runout,args);m=run['monitor']
        boot=m.screen();(runout/'boot-framebuffer.txt').write_text(boot)
        decoded=R.ROWS.decoded_framebuffer(boot)
        assert 'WORKBENCH 2.0.0' in decoded and C.active(boot)=='LISP65>' and 'CANNOT OPEN' not in decoded
        rows.append(dict(id='boot',passed=True,oracle=M.bind(runout/'boot-framebuffer.txt')))
        for row in selected['rows']:
            before=m.screen();m.type_text(row['form']+'\n');deadline=time.monotonic()+25;okay=False
            while time.monotonic()<deadline:
                screen=m.screen();decoded=R.ROWS.decoded_framebuffer(screen)
                if row.get('failure'):
                    okay=decoded.count('*** E29')>=2
                elif 'max_frames' in row:
                    okay=C.active(screen)=='LISP65>' and any(C.fresh_result(before,screen,str(n)+' '+row['value']) for n in range(row['max_frames']+1))
                else:okay=C.active(screen)=='LISP65>' and C.fresh_result(before,screen,row['value'])
                if okay:break
                time.sleep(.03)
            m.command('t1');screen=m.screen();p=runout/(row['id']+'-framebuffer.txt');p.write_text(screen)
            rows.append(dict(id=row['id'],passed=okay,oracle=M.bind(p),expected=row))
            print(group,row['id'],'PASS' if okay else 'RED',flush=True)
            assert okay,'bound framebuffer oracle failed: '+row['id']
            if row['id']=='d5-marker':
                values={}
                for name in ('nsym','npool'):
                    s=truth.symbol(name);raw=m.memory_range(s.value,s.bytes)
                    values[name]=dict(address=s.value,bytes=s.bytes,raw=raw.hex(),used=int.from_bytes(raw,'little'))
                write(runout/'d5-raw.json',values)
            elif not row.get('failure'):m.command('t0')
    except Exception as e:
        error=repr(e);raise
    finally:
        R.ProbeMonitor=original_monitor
        outputs=None
        if run:
            run['monitor'].command('t1');outputs=R.finish_run(run)
        write(runout/'receipt.json',dict(status='RED' if error else 'PASS',error=error,rows=rows,
            contract=M.bind(path),pair=M.pair(),medium=M.bind(medium),fork=M.bind(FORK),
            binary=M.bind(binary),outputs=outputs,device_acceptance_claimed=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('group',choices=['native','recursion-known-issue','printer-known-issue']);a=p.parse_args()
    execute(a.group)
