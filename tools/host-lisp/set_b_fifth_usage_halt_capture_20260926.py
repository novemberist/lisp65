"""Seal the first unexpected workload result and stop only its private guest."""
from pathlib import Path
import subprocess
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import dwx_retroactive_red_replay as R
import nested_error_recovery_gates as G
import set_b_fifth_oracle_r4_20260926 as O
out=P.ROOT/'build/set-b-fifth-functional-reuse-r3'
pids=subprocess.check_output(['pgrep','-f','^python3 -B tools/host-lisp/set_b_fifth_functional_r3_20260926.p[y]$'],text=True).split();assert len(pids)==1
m=R.ProbeMonitor(Path('/tmp')/('l65-set-b-'+pids[0]+'-candidate.sock'))
screen=m.screen();before=(out/'step-require-before-screen.txt').read_text()
assert O.valid(before,screen,'(require "defstruct")','NIL')
(out/'halt-screen.txt').write_text(screen)
m.command('t1');captures=[];G.dump(m,out,'halt',captures,{'c2_ready':0x8c})
arm=m.memory16(0x31)[0];tenant=m.memory_range(0x5de80,8192);journal=m.memory_range(0x5de20,72)
P.write(out/'qualification-halt.json',dict(status='HALT: require defstruct returns NIL after 50 successful prompt redefinitions',expected='T',actual='NIL',form='(require "defstruct")',captures=captures,arm=arm,ready=m.memory16(0x8c)[0],tenant_intact=tenant==(S.PRODUCT/'set-b-tenants.bin').read_bytes(),journal=journal.hex(),screen=P.bind(out/'halt-screen.txt'),driver=P.bind(Path(__file__)),limits='First observed unexpected result; failing internal stage and resource cause not attributed. No later form submitted. Other product gates stopped.'))
m.command('~exit')
print('HALT captured; guest closed; no further qualification')
