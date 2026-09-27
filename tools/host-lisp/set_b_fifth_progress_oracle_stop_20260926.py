"""Preserve completed reuse prefix and close guests stalled on loader text."""
from pathlib import Path
import subprocess
import dwx_retroactive_red_replay as R
import set_b_producer as P
import nested_error_recovery_gates as G
import set_b_fifth_oracle_r4_20260926 as O
for driver,root in [('set_b_fifth_carriers_20260926.py','set-b-fifth-functional-carriers-r1'),('set_b_fifth_functional_r3_20260926.py','set-b-fifth-functional-reuse-r3')]:
    out=P.ROOT/'build'/root
    pids=subprocess.check_output(['pgrep','-f','^python3 -B tools/host-lisp/'+driver.replace('.py','.p[y]')+'$'],text=True).split()
    assert len(pids)==1
    m=R.ProbeMonitor(Path('/tmp')/('l65-set-b-'+pids[0]+'-candidate.sock'))
    screen=m.screen();before=(out/'step-require-before-screen.txt' if 'reuse' in root else out/'step-inspect-before-screen.txt').read_text()
    form='(require "defstruct")' if 'reuse' in root else '(require "inspect")'
    assert O.valid(before,screen,form,'T'),O.lines(screen)
    (out/'operator-progress-screen.txt').write_text(screen)
    m.command('t1');captures=[];G.dump(m,out,'operator-progress',captures,{'c2_ready':0x8c})
    arm=m.memory16(0x31)[0];assert arm==134
    P.write(out/'operator-progress-stop.json',dict(reason='Normal LOADING line invalidates r3 adjacency assertion; exact new echo, T and prompt pass r4 oracle.',form=form,arm=arm,captures=captures,action='~exit only this private guest; no product verdict',driver=P.bind(Path(__file__))))
    m.command('~exit')
print('Closed two private guests after preserving loader rows and raw snapshots')
