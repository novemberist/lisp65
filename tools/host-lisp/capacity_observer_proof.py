#!/usr/bin/env python3
"""Host-only observer source attribution and executed counter mutations.

This proves the inserted observer's source footprint and local semantics.
Row-level functional neutrality is a separate requirement, not inferred here.
"""
import difflib
import hashlib
import json
from pathlib import Path
import resource
import subprocess

from capacity_pc_histogram_tool import BASE, OUT, ROOT, bind
from evidence_era import stable_recorded_on

def main():
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    dest=OUT/'xemu'; output=OUT/'observer-proof';output.mkdir(exist_ok=True)
    manifest=json.loads((OUT/'instrument-build.json').read_text())
    assert bind(ROOT/manifest['binary']['path'])==manifest['binary']
    for record in manifest['patched_sources']:
        assert bind(ROOT/record['path'])==record
    header=ROOT/'tools/host-lisp/fixtures/dwx_pc_histogram.h'
    assert bind(header)==manifest['header']
    assert header.read_bytes()==(dest/'xemu/dwx_pc_histogram.h').read_bytes()
    unchanged=[];changed=[];patch=[]
    for path in sorted(BASE.rglob('*')):
        relative=path.relative_to(BASE)
        if not path.is_file() or path.suffix not in ('.c','.h') or '.git' in relative.parts or relative.parts[0]=='build':continue
        target=dest/relative
        assert target.is_file(),relative
        a=path.read_text();b=target.read_text()
        if a==b:unchanged.append(bind(path));continue
        changed.append(str(relative))
        diff=list(difflib.unified_diff(a.splitlines(True),b.splitlines(True),fromfile='a/'+str(relative),tofile='b/'+str(relative)))
        patch.extend(diff)
        removed=[line[1:] for line in diff if line.startswith('-') and not line.startswith('---')]
        if str(relative)=='xemu/cpu65.c':assert not removed,'observer changes an original CPU instruction'
        elif str(relative)=='targets/mega65/uart_monitor.c':
            assert removed==['\t\t\tif (!strcmp(cmd, "cyclecount")) {\n']
            assert 'else if (!strcmp(cmd, "cyclecount")) {' in b
        else:raise AssertionError(('unattributed source change',relative))
    assert set(changed)=={'xemu/cpu65.c','targets/mega65/uart_monitor.c'}
    added=[str(p.relative_to(dest)) for p in dest.rglob('*') if p.is_file() and p.suffix in ('.c','.h') and '.git' not in p.parts and 'build'!=p.relative_to(dest).parts[0] and not (BASE/p.relative_to(dest)).exists()]
    assert added==['xemu/dwx_pc_histogram.h'],added
    patch.extend(difflib.unified_diff([],header.read_text().splitlines(True),fromfile='/dev/null',tofile='b/xemu/dwx_pc_histogram.h'))
    patchfile=output/'diagnostic-pc-observer.patch';patchfile.write_text(''.join(patch))
    mapping=dest/'targets/mega65/memory_mapper.c'
    text=mapping.read_text();start=text.index('Uint32 memory_cpu_addr_to_linear (');end=text.index('\n}',start)+2
    helper=text[start:end]
    assert 'if (wr_addr_p)\n\t\t*wr_addr_p = wr_addr;' in helper
    assert 'memory_cpu_addr_to_linear(CPU65.pc, NULL)' in (dest/'xemu/cpu65.c').read_text()
    mutations={
        'drop-pc-count':('h->counts[pc]++;','/* omitted */'),
        'drop-dispatch-count':('h->dispatch[a]++;','; /* omitted */'),
        'include-mapped-alias':('if (physical != pc)', 'if (0)'),
        'include-hypervisor':('if (hypervisor)', 'if (0)'),
        'omit-arming':('h->armed = 1;','h->armed = 0;'),
        'ignore-changed-opcode':('h->changed[pc] = 1;','h->changed[pc] = 0;'),
        'ignore-wrap':('h->wraps++;','h->wraps += 0;'),
        'ignore-counter-overflow':('h->counts[pc] == UINT64_MAX','0'),
    }
    fixture=ROOT/'tools/host-lisp/fixtures/dwx_pc_histogram_test.c';results=[]
    for name,edit in [('positive',None),*mutations.items()]:
        case=output/name;case.mkdir(exist_ok=True)
        code=header.read_text()
        if edit:
            old,new=edit;assert code.count(old)==1,(name,old);code=code.replace(old,new)
        (case/header.name).write_text(code);(case/fixture.name).write_bytes(fixture.read_bytes())
        compiled=subprocess.run(['cc','-std=c99','-Wall','-Wextra','-O2',str(case/fixture.name),'-o',str(case/'test')],capture_output=True)
        assert compiled.returncode==0,compiled.stderr
        execution=subprocess.run([str(case/'test')],capture_output=True)
        assert (execution.returncode==0)==(edit is None),(name,execution.returncode)
        results.append(dict(name=name,exit_code=execution.returncode,expected_failure=edit is not None))
    receipt=output/'receipt.json'
    receipt.write_text(json.dumps(dict(recorded_on=stable_recorded_on(receipt),status='SOURCE ATTRIBUTION AND COUNTER MUTATIONS PASS; ROW NEUTRALITY SEPARATE',
        base_manifest=bind(BASE/'dwx-xemu-cycle-probe-adapter.json'),instrument=bind(OUT/'instrument-build.json'),
        diagnostic_patch=bind(patchfile),unchanged_sources=unchanged,changed_sources=changed,added_sources=added,
        generated_build_identity=dict(base=bind(BASE/'build/objs/m-native-mega65-xmega65--make-buildinfo.c'),
            diagnostic=bind(dest/'build/objs/m-native-mega65-xmega65--make-buildinfo.c'),
            attribution='diagnostic fork branch/build identity; generated host metadata, not guest code'),
        translation_helper=dict(source=bind(mapping),first_line=text[:start].count('\n')+1,sha256=hashlib.sha256(helper.encode()).hexdigest(),
            effect='policy arithmetic only; NULL output pointer; no emulated register read'),
        fixture=bind(fixture),mutations=results,guest_cycle_accounting_modified=False,
        limits=['host wall-clock speed is changed','functional row controls remain mandatory','no device timing or physical-keyboard claim']),indent=2)+'\n')
    print('OBSERVER SOURCE ATTRIBUTION PASS; 8 executed mutations rejected')

if __name__=='__main__':main()
