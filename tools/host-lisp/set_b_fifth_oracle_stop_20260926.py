"""Close only the private guest of the saturated-screen result oracle."""
from pathlib import Path
import dwx_retroactive_red_replay as R
import set_b_producer as P
out=P.ROOT/'build/set-b-fifth-functional-reuse-r1'
m=R.ProbeMonitor(Path('/tmp/l65-set-b-1188504-candidate.sock'))
screen=m.screen();(out/'operator-oracle-stop-screen-final.txt').write_text(screen)
P.write(out/'operator-oracle-stop.json',dict(reason='G.submit counts occurrences; CAPFILL has saturated the scrolling screen. Latest form/result/live prompt visible, but count cannot increase. Instrument invalid; stop private guest without a product verdict.',screen=P.bind(out/'operator-oracle-stop-screen-final.txt'),action='~exit on this guest monitor only',prior_ad_hoc_attempt='ValueError binding a relative path before ~exit; no guest action in that attempt'))
print(m.command('~exit'))
