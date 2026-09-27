"""Shared read-only identity checks and exact launch previews for Card L reviewer tools."""
import argparse
import json
import os
from pathlib import Path
import shlex
import native_cycle_stationary as N
import dwx_retroactive_red_replay as R
from nested_error_recovery_lanes import cost_config
from elf_truth import ElfTruth

ROOT = Path(__file__).resolve().parents[2]
IDENTITY = ROOT/'build/card-l-r1/instrument-lanes.json'
ROM = Path(str(Path.home() / '.local/share/xemu-lgb/mega65/MEGA65.ROM'))
SD = Path(str(Path.home() / '.local/share/xemu-lgb/mega65/mega65.img'))

def worlds():
    value = json.loads(IDENTITY.read_text())
    assert [w['role'] for w in value['worlds']] == ['baseline', 'candidate']
    for w in value['worlds']:
        for key in ('ELF', 'medium', 'binary'): N.checked_binding(w[key])
        elf = N.checked_binding(w['ELF'])
        assert w['cost_config'] == cost_config(elf)
        truth = ElfTruth.read(elf, llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj', include_section_data=True)
        for name,address_key,code_key,size in [('_start','main','signature',16),('c2_kernal_input_take','entry','entry_code',None)]:
            symbol=truth.symbol(name);section=truth.section(symbol.section)
            assert w[address_key]==symbol.value
            assert w[code_key]==truth.section_bytes(symbol.section)[symbol.value-section.address:symbol.value-section.address+(size or symbol.bytes)].hex()
        assert w['paused_pc']==w['entry']+1
        assert w['main'] == truth.symbol('_start').value
        assert w['vm_callprim'] == truth.symbol('vm_callprim').value
        cpu = Path(w['binary']['path']).parents[2]/'xemu/cpu65.c'
        assert f"dwx_pc_init(&dwx_histogram, {w['main']}, {w['vm_callprim']});" in cpu.read_text()
    assert value['worlds'][0]['ELF']['sha256']=='66165507a8e5ad1d857afdd967f9056be2ce7bbccc332d5328e981398078b47b'
    ready=json.loads((ROOT/'build/card-l-r1/ready-instrument.json').read_text())
    for w,r in zip(value['worlds'],ready['worlds']):
        for key in ('ELF','medium','binary','main','vm_callprim'):assert w[key]==r[key]
    assert value['worlds'][1]['ELF']['sha256'] == '7e57bc17f318dd22a6dbc0212fd5fde5b9598eaf645f4f98d6387e0c3f53f3b5'
    return value['worlds']

def arguments(w, timeout=3600):
    return argparse.Namespace(xemu=N.checked_binding(w['binary']), rom=ROM, sd_image=SD, timeout=timeout)

def preview(w, out, run_id, timeout=3600, binary=None):
    """Same safe runner arguments as R.start_run; PID socket is resolved at invocation."""
    d = out/('run-'+run_id)
    m = d/Path(w['medium']['path']).name
    cmd = [str(R.SAFE_RUNNER), str(d/'memory.bin'), str(timeout), str(binary or N.checked_binding(w['binary'])),
           '-skipconfigfile','-headless','-testing','-sleepless','-besure','-fastboot','-nosound',
           '-rom',str(ROM),'-sdimg',str(d/'system-sd.img'),'-8',str(m),'-autoload','-uartmon',
           f'/tmp/l65-dwx-item6-<PID>-{run_id}.sock','-dumpscreen',str(d/'framebuffer.txt'),'-dumpmem',str(d/'memory.bin')]
    print('WORLD', w['role'], 'ELF', w['ELF']['sha256'], 'medium', w['medium']['sha256'])
    print('COPY', str(SD), '->', str(d/'system-sd.img'))
    print('COPY', w['medium']['path'], '->', str(m))
    print('LISP65_COST_CONFIG='+w['cost_config'], shlex.join(cmd))

def marker(m, out, label):
    from card_l_write_watch_probe_r2 import read_region, verify_marker
    m.command('t1')
    try:
        raw = read_region(m)
        image = (ROOT/'build/card-l-r1/card-l-marker.bin').read_bytes()
        assert N.bind(ROOT/'build/card-l-r1/card-l-marker.bin')['sha256'] == 'b504c29be383360f3f5257e03ca795f7930b8ec146f09632025c3b846038e3bf'
        result = verify_marker(raw, image)
        path = out/(label+'-marker-region.bin'); path.write_bytes(raw)
        return dict(result, snapshot=N.bind(path))
    finally:
        m.command('t0')
