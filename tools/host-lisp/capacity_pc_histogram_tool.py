#!/usr/bin/env python3
"""Card-0 diagnostic observer builder; never compiles or changes a product.

The fixed-resident lane rejects ambiguous/changed bytes. Dynamic overlay
ownership is a separate attribution debt, never inferred from a shared VMA.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from elf_truth import ElfTruth
from evidence_era import stable_recorded_on

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'build/dwx/xemu-buffered-repair-three-patch-r2'
OUT = ROOT / 'build/capacity/card0-r3'
ELF = ROOT / 'build/v2.1/renderer-branch-product-r1/wplto/lisp65-c2-substitution-linked.prg.elf'
ELF_SHA = 'c09d6e4d37a7e413133fc8541cc351e5cfc8274fefb7d3aaa325638f39391b2c'

def bind(p):
    return dict(path=str(p.relative_to(ROOT)), sha256=hashlib.sha256(p.read_bytes()).hexdigest())

def replace(text, old, new):
    if text.count(old) != 1: raise ValueError('observer anchor missing/ambiguous: ' + old[:80])
    return text.replace(old, new)

def run(cmd, **kw):
    subprocess.run(cmd, check=True, **kw)

def build(resume=False):
    assert bind(ELF)['sha256'] == ELF_SHA
    manifest = json.loads((BASE / 'dwx-xemu-cycle-probe-adapter.json').read_text())
    assert hashlib.sha256(Path(manifest['binary']['path']).read_bytes()).hexdigest() == manifest['binary']['sha256']
    truth = ElfTruth.read(ELF, llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj', include_section_data=True)
    main, dispatch = truth.symbol('_start'), truth.symbol('vm_callprim')
    assert dispatch.section == '.text'
    start_section = truth.section(main.section)
    signature = truth.section_bytes(main.section)[main.value-start_section.address:main.value-start_section.address+16]
    assert len(signature) == 16
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT/'xemu'
    if dest.exists() and not resume: raise RuntimeError('diagnostic build already exists; no overwrite')
    if not resume: shutil.copytree(BASE, dest)
    header = ROOT/'tools/host-lisp/fixtures/dwx_pc_histogram.h'
    if not resume: shutil.copyfile(header, dest/'xemu/dwx_pc_histogram.h')
    p = dest/'xemu/cpu65.c'
    before = (BASE/'xemu/cpu65.c').read_text()
    addition = '''
#ifdef MEGA65
#include "memory_mapper.h"
#include "dwx_pc_histogram.h"
#include <stdio.h>
#include <stdlib.h>
static dwx_pc_histogram dwx_histogram;
static const unsigned char dwx_start_signature[16] = {START_SIGNATURE};
static int dwx_histogram_bound;
static void dwx_histogram_bind(void) {
    if (dwx_histogram_bound) return;
    dwx_histogram_bound = 1;
    dwx_pc_init(&dwx_histogram, MAIN_PC, DISPATCH_PC);
}
int dwx_histogram_save(void) {
    const char *path = getenv("LISP65_DWX_PC_OUTPUT");
    dwx_histogram_bind();
    if (!path || !*path || dwx_histogram.invalid || !dwx_histogram.armed) return -1;
    FILE *f = fopen(path, "w");
    if (!f) return -1;
    fprintf(f, "H %u %llu %llu %llu\\n", dwx_histogram.armed,
        (unsigned long long)dwx_histogram.instructions,
        (unsigned long long)dwx_histogram.nonidentity,
        (unsigned long long)dwx_histogram.hypervisor);
    fprintf(f, "S %u %u\\n", dwx_histogram.min_sp, dwx_histogram.wraps);
    for (unsigned i=0; i<65536; i++) if (dwx_histogram.counts[i])
        fprintf(f,"P %u %llu %u %u\\n",i,(unsigned long long)dwx_histogram.counts[i],
            dwx_histogram.opcode[i],dwx_histogram.changed[i]);
    for (unsigned i=0; i<256; i++) if (dwx_histogram.dispatch[i])
        fprintf(f,"D %u %llu\\n",i,(unsigned long long)dwx_histogram.dispatch[i]);
    int bad = ferror(f);
    return fclose(f) || bad ? -1 : 0;
}
void dwx_histogram_row_reset(void) {
    dwx_histogram.min_sp = 255; dwx_histogram.wraps = 0;
}
#endif
'''.replace('MAIN_PC', str(main.value)).replace('DISPATCH_PC', str(dispatch.value)).replace('START_SIGNATURE', ','.join(str(x) for x in signature))
    text = replace(before, 'struct cpu65_st CPU65;', 'struct cpu65_st CPU65;\n'+addition)
    text = replace(text, 'static XEMU_INLINE void push ( const Uint8 data )\n{', '''static XEMU_INLINE void push ( const Uint8 data )
{
#ifdef MEGA65
    if (dwx_histogram.armed && !in_hypervisor && getenv("LISP65_DWX_PC_OUTPUT")) {
        if (!CPU65.pf_e || CPU65.sphi != 0x100) dwx_histogram.invalid = 1;
        else dwx_pc_stack(&dwx_histogram, CPU65.s, 1);
    }
#endif''')
    text = replace(text, '\tCPU65.op = readByte(CPU65.pc);', '''\tCPU65.op = readByte(CPU65.pc);
#ifdef MEGA65
    dwx_histogram_bind();
    if (getenv("LISP65_DWX_PC_OUTPUT") && (dwx_histogram.armed ||
        (CPU65.pc == dwx_histogram.main_pc &&
         !memcmp(main_ram + dwx_histogram.main_pc, dwx_start_signature, 16)))) {
        dwx_pc_sample(&dwx_histogram, CPU65.pc,
            memory_cpu_addr_to_linear(CPU65.pc, NULL), CPU65.op, CPU65.a, in_hypervisor);
        if (!in_hypervisor) dwx_pc_stack(&dwx_histogram, CPU65.s, 0);
    }
#endif''')
    if resume and p.read_text() != before: assert p.read_text() == text
    else: p.write_text(text)
    p = dest/'targets/mega65/uart_monitor.c'
    text = (BASE/'targets/mega65/uart_monitor.c').read_text()
    text = replace(text, '#include "input_devices.h"', '#include "input_devices.h"\nextern int dwx_histogram_save(void);\nextern void dwx_histogram_row_reset(void);')
    text = replace(text, 'if (!strcmp(cmd, "cyclecount")) {', '''if (!strcmp(cmd, "pcrowreset")) {
                dwx_histogram_row_reset(); umon_printf("DWX PC row reset");
            } else if (!strcmp(cmd, "pcsave")) {
                umon_printf("DWX PC save: %d", dwx_histogram_save());
            } else if (!strcmp(cmd, "cyclecount")) {''')
    if resume and p.read_text() != (BASE/'targets/mega65/uart_monitor.c').read_text(): assert p.read_text() == text
    else: p.write_text(text)
    assert (dest/'xemu/dwx_pc_histogram.h').read_bytes() == header.read_bytes()
    run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-O2',
         str(ROOT/'tools/host-lisp/fixtures/dwx_pc_histogram_test.c'), '-o', str(OUT/'observer-test')])
    run([str(OUT/'observer-test')])
    sdk = ROOT/'build/dwx/stack-envelope-host-sdk/root/usr/include/SDL2'
    assert (sdk/'SDL_endian.h').is_file()
    gtk_flags = subprocess.check_output(['pkg-config', '--cflags', 'gtk+-3.0'], text=True).strip()
    gtk_libs = subprocess.check_output(['pkg-config', '--libs', 'gtk+-3.0'], text=True).strip()
    runtime = Path('/usr/lib64/libSDL2-2.0.so.0').resolve(strict=True)
    command = ['make', '-C', str(dest/'targets/mega65'), '-j2',
        'SDL2_CFLAGS=-I'+str(sdk)+' -D_GNU_SOURCE=1 -D_REENTRANT',
        'SDL2_LIBS='+str(runtime), 'GTK3_CFLAGS='+gtk_flags, 'XEMUGUI_CFLAGS='+gtk_flags,
        'GTK3_LIBS='+gtk_libs, 'XEMUGUI_LIBS='+gtk_libs]
    with (OUT/'build-local-sdk.log').open('w') as log:
        run(command,
            env=dict(os.environ, TRAVIS_BRANCH='dwx-card0-diagnostic', TRAVIS_COMMIT=manifest['source_commit']),
            stdout=log, stderr=subprocess.STDOUT)
    receipt = OUT/'instrument-build.json'
    receipt.write_text(json.dumps(dict(status='INSTRUMENT BUILT; NEUTRALITY AND POPULATION NOT YET QUALIFIED',
        recorded_on=stable_recorded_on(receipt), product=bind(ELF),
        base_manifest=bind(BASE/'dwx-xemu-cycle-probe-adapter.json'),
        binary=bind(dest/'build/bin/xmega65.native'), header=bind(header),
        patched_sources=[bind(dest/p) for p in ('xemu/cpu65.c','targets/mega65/uart_monitor.c')],
        addresses=dict(product_start=main.value, start_signature=signature.hex(), dispatch=dispatch.value),
        build_command=command,
        claim='fixed resident identity-mapped PC counts; not observed is not unused or movable',
        product_builds=0, device_contacts=0), indent=2)+'\n')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--resume-host-build', action='store_true')
    args = parser.parse_args(); build(args.resume_host_build)
