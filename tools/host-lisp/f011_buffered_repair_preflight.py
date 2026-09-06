#!/usr/bin/env python3
"""Host-only repair prerequisite proof; never invokes a product producer."""
import hashlib
import json
from pathlib import Path
import resource
import subprocess
import urllib.request

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'build/v2.1/f011-buffered-repair-preflight'
HEADER=ROOT/'src/f011_buffered_wait.h'
FIXTURE=ROOT/'tests/fixtures/f011-buffered-wait-host.c'
CORE='03b24c6b9d0e456f762fdca0d2dd66ec3c3e1fc6'
URL=f'https://raw.githubusercontent.com/MEGA65/mega65-core/{CORE}/src/vhdl/sdcardio.vhdl'

def bind(p):
    b=p.read_bytes()
    return dict(path=str(p.relative_to(ROOT)),sha256=hashlib.sha256(b).hexdigest(),bytes=len(b))

def main():
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    OUT.mkdir(parents=True,exist_ok=True)
    policy=json.loads((ROOT/'config/c2-interrupt-ownership-policy.json').read_text())
    assert CORE in json.dumps(policy), 'core does not match device authority'
    rtl=OUT/'sdcardio-03b24c6b.vhdl'
    if not rtl.exists():
        raw=urllib.request.urlopen(URL,timeout=30).read()
        with rtl.open('xb') as f: f.write(raw)
    text=rtl.read_text()
    a=text.index('        when ReadingSector =>')
    b=text.index('        when FDCFormatTrackSyncWait =>',a)
    body=text[a:b]
    for token in ("if f011_drq='1' then f011_lost <= '1'; end if;",
                  "f011_buffer_wdata <= unsigned(sd_rdata);",
                  "f011_buffer_write <= '1';", "f011_eq_inhibit <= '1';",
                  'and (sd_buffer_offset="000000000")', "f011_busy <= '0';"):
        assert token in body, 'device RTL mechanism changed: '+token
    header=HEADER.read_text()
    variants={
        'control':header,
        'require-eq':header.replace('(status&0xd8u)==0x40u','(status&0xf8u)==0x60u'),
        'reject-lost':header.replace('(status&0xd8u)==0x40u','(status&0xdcu)==0x40u'),
        'ignore-rnf':header.replace('(status&0xd8u)==0x40u','(status&0xc8u)==0x40u'),
        'ignore-crc':header.replace('(status&0xd8u)==0x40u','(status&0xd0u)==0x40u'),
        'ignore-busy':header.replace('if(!(status&0x80u)) return (status&0xd8u)==0x40u;',
                                    'return (status&0x58u)==0x40u;'),
        'skip-clock-proof':header.replace('if(f011_clock_verified) return 1;', 'return 1;'),
        'lose-stall-escape':header.replace('else if(!--fuel) return 0;', 'else (void)fuel;'),
        'double-cap':header.replace('F011_WAIT_CAP_FRAMES 600u','F011_WAIT_CAP_FRAMES 1200u'),
        'lose-wrap':header.replace('(uint16_t)(now-start)>=','((int)now-(int)start)>='),
        'accept-torn-sample':header.replace('if(a==b)', 'if(1)'),
    }
    results={}
    for name,h in variants.items():
        assert name=='control' or h!=header
        directory=OUT/name; directory.mkdir(exist_ok=True)
        (directory/HEADER.name).write_text(h)
        exe=directory/'check'
        subprocess.run(['/usr/bin/cc','-std=c11','-O2','-I'+str(directory),str(FIXTURE),'-o',str(exe)],check=True)
        try:
            p=subprocess.run([str(exe)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=5)
            outcome=p.returncode
        except subprocess.TimeoutExpired: outcome='watchdog'
        assert (outcome==0)==(name=='control'), (name,outcome)
        results[name]=outcome
    io=(ROOT/'src/io.c').read_text()
    spin=io.index('= 0x20;'); read=io.index('= 0x40;',spin)
    assert not any(x in io[spin:read] for x in ['f011_wait_', 'F011_READ8', 'while ('])
    assert 'f011_status_' not in io
    assert 'f011_status_' not in (ROOT/'src/main.c').read_text()
    result=dict(status='HOST PREREQUISITES PASS; NOT FINAL-LINK QUALIFICATION',
        authority='566c2e23',device_core=CORE,rtl_url=URL,rtl=bind(rtl),
        header=bind(HEADER),fixture=bind(FIXTURE),status_population=256,mutations=results,
        ordinary_sources=[bind(ROOT/'src/io.c'),bind(ROOT/'src/main.c')],
        clock='600-frame cap; one-time progress proof; separate finite stalled-clock fuel, not time',
        accounting=dict(product_WPLTO=0,product_links=0,media=0,device_contacts=0),
        owed=['final ELF clock/placement/attribution','three-patch fork and retroactive requalification',
              'packed prefilter including LOAD_OPEN','hardware cold-start and Comfort'])
    (OUT/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__': main()
