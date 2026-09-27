"""Fifth-Seed negative delivered media: refusal with READY/live prompt preserved."""
import argparse
import inspect
from pathlib import Path
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import set_b_seed_boot_20260926 as B
ROOT=P.ROOT
NAMES=['missing_record','corrupted_byte','displaced_256']


def main(name):
    S.require_auth();src=inspect.getsource(B.main)
    replacements=[('build/set-b-product-r3/','build/set-b-product-r5/'),
        ("MEDIAROOT/'media-seed/set-b-comfort.d81'", "MEDIAROOT/'controls'/CONTROL/'set-b-comfort.d81'"),
        ("assert result['retirement_latch'] & 128, 'Positive boot failed to arm retirement'", "assert result['retirement_latch']==0, 'Negative medium admitted retirement'"),
        ("assert image == (MEDIAROOT/'media-seed/set-b-tenants.bin').read_bytes(), 'Tenant image differs at first prompt'", "result['tenant_matches_positive']=image == (MEDIAROOT/'media-seed/set-b-tenants.bin').read_bytes()"),
        ("print('PASS',role,'medium boot, READY=1 and arithmetic; candidate arm/tenant check',flush=True)","monitor.command('t1')\n            assert monitor.memory16(truth.symbol('c2r_boot_count').value)[0]==0\n            assert monitor.memory16(truth.symbol('c2_ready').value)[0]==1\n            print('PASS negative',CONTROL,'READY=1, disarmed, arithmetic and live prompt',flush=True)"),
        ('PASS: MEDIUM BOOT AND LIVE PROMPT','PASS: NEGATIVE MEDIUM REFUSED WITH LIVE PROMPT')]
    for a,b in replacements:assert src.count(a)==1,a;src=src.replace(a,b)
    folder=S.OUT/('negative-'+name+'-driver');folder.mkdir(exist_ok=False);(folder/'executed.py').write_text(src)
    P.write(folder/'binding.json',dict(driver=P.bind(Path(__file__)),parent=P.bind(Path(B.__file__)),executed=P.bind(folder/'executed.py'),replacements=replacements,product_links=0))
    ns=dict(vars(B));ns.update(CONTROL=name,MEDIAROOT=ROOT/'build/set-b-seed-medium-r6',__file__=__file__)
    exec(compile(src,str(folder/'executed.py'),'exec'),ns)
    ns['main'](ROOT/('build/set-b-fifth-negative-'+name+'-r1'),'candidate')

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('name',choices=NAMES);main(ap.parse_args().name)
