#!/usr/bin/env python3
"""Gate every live 1581 link walker against the shared corruption cases."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
import zlib
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
FORMAT = "lisp65-1581-chain-walker-inventory-v1"


class GateError(RuntimeError):
    pass


WALKERS: tuple[dict[str, Any], ...] = (
    {
        "id": "cold-stager-file",
        "path": "scripts/r3-cold-stager-main.c", "language": "c", "name": "scan_file",
        "kind": "file-data", "sector_limit": 3226, "large_case": "accept",
        "requires": [
            "uint16_t fuel", "expected_length + R3_LOGICAL_SECTOR_PAYLOAD - 1ul",
            "if (!next_track && !next_sector)", "next_track == track && next_sector == sector",
        ],
    },
    {
        "id": "cold-stager-descriptor",
        "path": "scripts/r3-cold-stager-main.c", "language": "c", "name": "load_descriptor",
        "kind": "fixed-file-data", "sector_limit": 4, "large_case": "reject",
        "requires": [
            "uint8_t fuel = 4", "uint16_t used", "!next_track && !next_sector",
            "next_track == track && next_sector == sector", "!track && used == R3_DESCRIPTOR_BYTES",
        ],
    },
    {
        "id": "cold-stager-directory",
        "path": "scripts/r3-cold-stager-main.c", "language": "c", "name": "find_file",
        "kind": "directory", "sector_limit": 64, "large_case": "not-applicable",
        "requires": ["uint8_t fuel = 64", "next_sector == sector"],
    },
    {
        "id": "c-file-capacity",
        "path": "src/io.c", "language": "c", "name": "disk_chain_capacity",
        "kind": "file-data", "sector_limit": 153, "large_case": "reject",
        "requires": ["fuel = DISK_CHAIN_FUEL", "disk_chain_count", "return t ? 0 : cap"],
    },
    {
        "id": "c-file-save",
        "path": "src/io.c", "language": "c", "name": "io_disk_save_impl",
        "kind": "file-data", "sector_limit": 153, "large_case": "reject",
        "requires": ["fuel = DISK_CHAIN_FUEL", "disk_chain_count", "return t == 0"],
    },
    {
        "id": "c-file-stage",
        "path": "src/io.c", "language": "c", "name": "disk_chain_to_scratch",
        "kind": "file-data", "sector_limit": 153, "large_case": "reject",
        "requires": ["!nt && !ns", "nt == t && ns == s", "cnt > remaining", "return n"],
    },
    {
        "id": "c-source-stream",
        "path": "src/io.c", "language": "c", "name": "disk_source_fetch",
        "kind": "coupled-file-data", "sector_limit": 153, "large_case": "reject",
        "requires": ["disk_file_pos >= disk_file_len", "if (!(link & DISK_SOURCE_LINK_VALID) || !t",
                     "DISK_SOURCE_LINK_PACK(nt, nt ? ns : 0u)"],
    },
    {
        "id": "c-directory",
        "path": "src/io.c", "language": "c", "name": "disk_dir_find",
        "kind": "directory", "sector_limit": 64, "large_case": "not-applicable",
        "requires": [
            "fuel = 64", "if (nt == 0) return 0", "nt != 40u", "ns >= 40u",
            "nt == track && ns == sector",
        ],
    },
    {
        "id": "ide-effective-count",
        "path": "lib/ide-disk.lisp", "language": "lisp", "name": "%ide-disk-effective-count",
        "kind": "file-data", "sector_limit": 255, "large_case": "reject",
        "requires": ["%ide-disk-link-valid-p", "-1"],
    },
    {
        "id": "ide-read-chain",
        "path": "lib/ide-disk.lisp", "language": "lisp", "name": "%ide-disk-read-chain",
        "kind": "file-data", "sector_limit": 255, "large_case": "reject",
        "requires": ["%ide-disk-link-valid-p", "nil"],
    },
    {
        "id": "ide-directory",
        "path": "lib/ide-disk.lisp", "language": "lisp", "name": "%ide-disk-find",
        "kind": "directory", "sector_limit": 64, "large_case": "not-applicable",
        "requires": ["(> fuel 0)", "(1- fuel)", "%disk-directory-link-valid-p"],
    },
    {
        "id": "ide-directory-list",
        "path": "lib/ide-disk.lisp", "language": "lisp", "name": "%ide-dir-scan-directory",
        "kind": "directory", "sector_limit": 64, "large_case": "not-applicable",
        "requires": ["(> fuel 0)", "(1- fuel)", "%disk-directory-link-valid-p"],
    },
    {
        "id": "m65d-old-chain",
        "path": "lib/m65-disk.lisp", "language": "lisp", "name": "%m65d-read-old-chain",
        "kind": "file-data", "sector_limit": 33, "large_case": "reject",
        "requires": ["(= fuel 0)", "%m65d-pair-member-p", "(< next-sector 1)", "(- fuel 1)"],
    },
    {
        "id": "m65d-directory",
        "path": "lib/m65-disk.lisp", "language": "lisp", "name": "%m65d-dir-scan",
        "kind": "directory", "sector_limit": 40, "large_case": "not-applicable",
        "requires": ["(= fuel 0)", "(= next-sector sector)", "(- fuel 1)"],
    },
    {
        "id": "fasl-slot-capacity",
        "path": "lib/lcc-fasl.lisp", "language": "lisp", "name": "%compile-slot-capacity",
        "kind": "file-data", "sector_limit": 255, "large_case": "reject",
        "requires": ["(> next-sector 0)", "(= next-track track)", "(= next-sector sector)", "(1- fuel)"],
    },
    {
        "id": "fasl-slot-directory",
        "path": "lib/lcc-fasl.lisp", "language": "lisp", "name": "%compile-slot-find",
        "kind": "directory", "sector_limit": 64, "large_case": "not-applicable",
        "requires": ["(> fuel 0)", "(1- fuel)", "%disk-directory-link-valid-p"],
    },
    {
        "id": "resident-load-directory",
        "path": "lib/stdlib-load.lisp", "language": "lisp", "name": "%load-scan-directory",
        "kind": "directory", "sector_limit": 64, "large_case": "not-applicable",
        "requires": ["(> fuel 0)", "(1- fuel)", "%disk-directory-link-valid-p"],
    },
    {
        "id": "resident-load-lib-directory",
        "path": "lib/stdlib-load-lib.lisp", "language": "lisp", "name": "%load-lib-scan-directory",
        "kind": "directory", "sector_limit": 64, "large_case": "not-applicable",
        "requires": ["(> fuel 0)", "(1- fuel)", "%disk-directory-link-valid-p"],
    },
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


EXIT_CONTRACT = ROOT / 'config/chain-walker-exits.json'
EXECUTION_RECEIPT = ROOT / 'build/chain-walker-exits/receipt.json'


def declarations(value=None):
    if value is None:
        value = json.loads(EXIT_CONTRACT.read_text())
    if value.get('format') != 'lisp65-chain-walker-executed-exits-v1':
        raise GateError('walker exit declaration format absent')
    exits = value.get('exits', {})
    if set(exits) != {row['id'] for row in WALKERS}:
        raise GateError('walker exit declaration population incomplete or excessive')
    for name, row in exits.items():
        if set(row) != {'name', 'value'} or not all(isinstance(v, str) and v for v in row.values()):
            raise GateError('walker exit name/value absent: '+name)
    return exits


def c_function(source, name):
    body = c_body(source, name)
    start = source.index(body)
    return source[source.rfind('\n', 0, start)+1:start]+body


def c_macro(source, name):
    match = re.search(r'^#define '+re.escape(name)+r'\b(?:[^\n]*\\\n)*[^\n]*', source, re.M)
    if not match:
        raise GateError('host unit macro authority missing: '+name)
    return match.group()


def c_exit(spec, directory, *, trace=False, mutation=None):
    """Compile unchanged control flow; debugger supplies exhausted local budget.

    Host I/O stubs only provide a successful environment for reaching the
    tested edge. They do not compute the walker's result. DE00 is redirected
    to host RAM; cold declarations select the portable C definition.
    This proves the declared exit, not target timing, ABI or full traversal.
    """
    source = (ROOT/spec['path']).read_text()
    name = spec['name']
    body = c_function(source, name)
    if name == 'disk_chain_to_scratch':
        # The source's mutually exclusive far/local function declaration
        # closes its #if immediately after the opening brace.
        if ') {\n#endif' not in body:
            raise GateError('cold/local declaration boundary changed')
        body = body.replace(') {\n#endif', ') {', 1)
    if trace and 'C2_V21_TRACE_FAIL' not in body:
        raise GateError('trace adapter requested for a non-trace walker')
    original_body = body
    guard = 'if (track) return C2_V21_TRACE_FAIL(C2_V21_TRACE_CHAIN_FUEL);'
    if mutation is not None:
        if body.count(guard) != 1:
            raise GateError('fuel-edge mutation anchor absent')
        body = body.replace(guard, '' if mutation=='drop-guard' else 'if (track) return '+mutation+';')
    body = re.sub(r'\(volatile (?:uint8_t|unsigned char) \*\)0x[dD][eE]00',
                  '(volatile unsigned char *)host_disk', body)
    prelude = '''#include <stdint.h>
#include <stdio.h>
static unsigned reads, writes;
static unsigned char host_disk[512] = {[2]=77,[3]=77};
static unsigned char sector_payload[254], descriptor[1024];
static unsigned char c2_v21_stage_trace[32], c2_v21_stage_trace_role, c2_v21_stage_trace_attempt;
static const unsigned char stage_domain=0;
#define LISP65_RESIDENT_ISLAND_FN
static unsigned int disk_file_len=1, disk_file_pos=1, disk_source_link;
static void lisp65_f011_unmap_buffer(void) {}
static void edma_copy(uint32_t a,uint32_t b,uint16_t n) {}
static unsigned char io_disk_read_sector(unsigned char t,unsigned char s) {
 ++reads; host_disk[0]=t;host_disk[1]=(s+1)%40;return 1;
}
static uint8_t f011_read(uint8_t t,uint8_t s,uint16_t *off) {
 *off=0;return io_disk_read_sector(t,s);
}
static unsigned int f011_read_at(unsigned char t,unsigned char s) {
 io_disk_read_sector(t,s);return 0;
}
static unsigned char io_disk_byte(unsigned char i) {return host_disk[i];}
static void io_disk_scratch_poke(unsigned char i,unsigned char v) {host_disk[i]=v;}
static unsigned char io_disk_write_sector(unsigned char t,unsigned char s) {++writes;return 1;}
static unsigned char ext_disk_get(unsigned int p) {return 0;}
static void ext_disk_put(unsigned int p,unsigned char v) {}
static unsigned char disk_fold(unsigned char c) {return c;}
static uint8_t name_matches(const volatile uint8_t *p,const char *n) {return 0;}
'''
    if name != 'find_file':
        prelude += 'static uint8_t find_file(const char *n,uint8_t *t,uint8_t *s) {*t=1;*s=0;return 1;}\n'
    if name != 'disk_dir_find':
        prelude += 'static unsigned char disk_dir_find(const char *n,unsigned char *t,unsigned char *s) {*t=1;*s=0;return 1;}\n'
    if name != 'disk_chain_capacity':
        prelude += 'static unsigned int disk_chain_capacity(unsigned char t,unsigned char s) {return 0;}\n'
    if spec['path'].startswith('scripts/'):
        prelude += '\n'.join(c_macro(source, key) for key in
                              ('R3_LOGICAL_SECTOR_PAYLOAD','R3_MAX_MEDIA_BYTES'))+'\n'
        # Preserve the source's full profile-selection block. The host
        # portable branch is selected by the same preprocessor, not a price
        # literal copied from a different stager profile.
        start=source.index('#ifdef LISP65_C2_LITE_MEDIA_STAGER')
        end=source.index('#endif',start)+len('#endif')
        prelude += source[start:end]+'\n'+c_macro(source,'R3_DESCRIPTOR_NAME')+'\n'
        enum = re.search(r'enum c2_v21_stage_trace_reason \{.*?\};', source, re.S)
        if not enum:
            raise GateError('trace reason authority missing')
        prelude += enum.group()+'\n'
        prelude += '\n'.join(c_function(source, helper) for helper in
            ('c2_v21_trace_wr32','c2_v21_trace_begin','c2_v21_trace_fail',
             'c2_v21_trace_scan_begin','c2_v21_trace_sector','crc32_step'))+'\n'
        macros = re.findall(r'^#define C2_V21_TRACE_FAIL\(reason\) .*$', source, re.M)
        if len(macros) != 2:
            raise GateError('trace/non-trace macro population changed')
        prelude += macros[0 if trace else 1]+'\n'
        if trace:
            prelude = '#define LISP65_V21_STAGE_TRACE\n'+prelude
    else:
        obj = (ROOT/'src/obj.h').read_text()
        prelude += c_macro(obj,'DISK_EXT_FILE_MAX')+'\n'
        prelude += c_macro((ROOT/'src/mem.h').read_text(),'LISP65_EXT_DISK_FILE_OFFSET')+'\n'
        prelude += '\n'.join(c_macro(source, key) for key in (
            'DISK_FILE_MAX','DISK_EXT_FILE','DISK_CHAIN_FUEL','LISP65_F011_READ_FAILED',
            'DISK_SOURCE_LINK_VALID','DISK_SOURCE_LINK_PACK','DISK_SOURCE_LINK_TRACK',
            'DISK_SOURCE_LINK_SECTOR'))+'\n'
        prelude += c_function(source,'disk_chain_count')+'\n'
    calls = {
        # A valid payload CRC prevents an omitted fuel guard from looking
        # fail-closed merely because the later CRC check rejects the fixture.
        'scan_file': 'scan_file("TEST",0,0,254,'+str(zlib.crc32(bytes([77,77])+bytes(252)))+'u)',
        'load_descriptor': 'load_descriptor()',
        'find_file': 'find_file("TEST",&track,&sector)',
        'disk_chain_capacity': 'disk_chain_capacity(1,0)',
        'io_disk_save_impl': 'io_disk_save_impl("TEST",0,0)',
        'disk_chain_to_scratch': 'disk_chain_to_scratch(1,0)',
        'disk_source_fetch': 'disk_source_fetch()',
        'disk_dir_find': 'disk_dir_find("TEST",&track,&sector)',
    }
    if name not in calls:
        raise GateError('no executable C adapter: '+name)
    unit = prelude+body+'\nint main(void) { unsigned char track,sector;\n'
    unit += 'unsigned int result='+calls[name]+';\n'
    unit += 'printf("RESULT %u READS %u WRITES %u TRACE %u\\n",result,reads,writes,c2_v21_stage_trace[3]);'
    if name=='scan_file':
        unit += 'printf("EXPECTED_TRACE %u\\n",(unsigned)C2_V21_TRACE_CHAIN_FUEL);'
    unit += 'return 0;}\n'
    path = directory/'unit.c'; executable = directory/'unit'
    path.write_text(unit)
    built = subprocess.run(['cc','-std=c11','-O0','-g',str(path),'-o',str(executable)],
                           text=True,capture_output=True)
    if built.returncode:
        raise GateError('C walker does not compile: '+name+'\n'+built.stderr)
    if name in ('scan_file','disk_source_fetch'):
        # scan_file naturally spends its single-sector fuel; source_fetch
        # gets its coupled stream-position budget from the caller state.
        commands = [str(executable)]
        mode = 'natural-sector-fuel' if name == 'scan_file' else 'caller-stream-position'
    else:
        first_loop = re.search(r'\bwhile\s*\(', body)
        if first_loop is None:
            raise GateError('no executed budget boundary: '+name)
        line = prelude.count('\n')+body[:first_loop.start()].count('\n')+1
        assignment = 'n = DISK_FILE_MAX' if name == 'disk_chain_to_scratch' else 'fuel = 0'
        if name == 'disk_chain_to_scratch':
            # GDB has no C preprocessor; the bound value is the live macro
            # evaluated by the compiler in a global, not a pasted capacity.
            unit = unit.replace('int main(void)', 'const unsigned int host_byte_ceiling=DISK_FILE_MAX;\nint main(void)')
            path.write_text(unit)
            subprocess.run(['cc','-std=c11','-O0','-g',str(path),'-o',str(executable)],check=True,capture_output=True)
            assignment = 'n = host_byte_ceiling'
        commands = ['gdb','-q','-nx','-batch',str(executable),
                    '-ex',f'break {path}:{line}','-ex','run',
                    '-ex','set variable '+assignment,
                    '-ex','printf "BUDGET_WITNESS %u %u\\n", '+('n, host_byte_ceiling' if name == 'disk_chain_to_scratch' else 'fuel, 0'),
                    '-ex','continue']
        mode = 'debugger-at-original-loop-boundary'
    ran = subprocess.run(commands,text=True,capture_output=True,timeout=15)
    match = re.search(r'RESULT (\d+) READS (\d+) WRITES (\d+) TRACE (\d+)',ran.stdout)
    if ran.returncode or match is None or (mode.startswith('debugger') and 'BUDGET_WITNESS ' not in ran.stdout):
        raise GateError('C walker did not execute its exit: '+name+'\n'+ran.stdout+ran.stderr)
    result, reads, writes, reason = map(int, match.groups())
    expected_reads = 1 if name in ('scan_file','disk_chain_to_scratch') else 0
    if reads!=expected_reads or writes:
        raise GateError('exhausted walker performed unexpected I/O: '+name)
    if mode.startswith('debugger'):
        budget=re.search(r'BUDGET_WITNESS (\d+) (\d+)',ran.stdout)
        if budget is None or budget.group(1)!=budget.group(2):
            raise GateError('debugger did not establish exhausted budget: '+name)
    if name == 'scan_file' and reads != 1:
        raise GateError('stager did not spend its derived one-sector fuel')
    if name == 'scan_file' and trace and mutation is None:
        expected=re.search(r'EXPECTED_TRACE (\d+)',ran.stdout)
        if expected is None or reason!=int(expected.group(1)):
            raise GateError('stager trace did not witness fuel exhaustion')
    return dict(walker=spec['id'], trace=trace, value=str(result), budget_mode=mode,
                reads=reads,writes=writes,trace_reason=reason,
                source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                body_sha256=hashlib.sha256(original_body.encode()).hexdigest(),
                unit_sha256=hashlib.sha256(unit.encode()).hexdigest(),stdout=ran.stdout)


LISP_EXIT_EXPRESSIONS = {
    'ide-effective-count': '(%ide-disk-effective-count 1 0 0 12 10)',
    'ide-read-chain': "(%ide-disk-read-chain 1 0 0 1 nil '(77))",
    'ide-directory': '(%ide-disk-find nil 40 0 0)',
    'ide-directory-list': "(%ide-dir-scan-directory 40 0 0 '(88 77))",
    'm65d-old-chain': "(list (%m65d-read-old-chain 1 0 0 '(77)) (m65d-status))",
    'm65d-directory': '(list (%m65d-dir-scan nil 40 0 0 nil) (m65d-status))',
    'fasl-slot-capacity': '(%compile-slot-capacity 1 0 0 123)',
    'fasl-slot-directory': '(%compile-slot-find nil 40 0 0)',
    'resident-load-directory': '(%load-scan-directory nil 40 0 0)',
    'resident-load-lib-directory': '(%load-lib-scan-directory nil 40 0 0)',
}


def lisp_exits(exits):
    import bytecode_p0_stdlib as H
    specs = [row for row in WALKERS if row['language']=='lisp']
    if set(LISP_EXIT_EXPRESSIONS) != {row['id'] for row in specs}:
        raise GateError('Lisp execution adapter population incomplete')
    sources = sorted({row['path'] for row in specs} | {'lib/ide-buffer.lisp','lib/dialect-v2/lists-core.lisp'})
    suite = dict(format='lisp65-bytecode-p0-stdlib-subset-v1',
        sources=sources, functions=[row['name'] for row in specs]+['%ide-rev-onto','%m65d-set','m65d-status','list'],
        strict_arity=True, max_call_args=12, abi_profile='dialect-v2',
        cases=[dict(name=row['id'],expr=LISP_EXIT_EXPRESSIONS[row['id']],expect=exits[row['id']]['value']) for row in specs])
    result = H.check_suite(str(EXIT_CONTRACT), suite)
    result['emitted_functions'] = {
        name: dict(payload_sha256=hashlib.sha256(code.payload).hexdigest(),
                   bytes=len(code.payload),nargs=code.nargs,nlocals=code.nlocals)
        for name,code in result.pop('code_by_name').items()}
    if {row['name'] for row in result['observations']} != {row['id'] for row in specs}:
        raise GateError('Lisp execution did not observe every declared case')
    return dict(source_bindings=[dict(path=p,sha256=sha256(ROOT/p)) for p in sources],
                cases=suite['cases'],execution=result)


def execute_exits(*, controls=False):
    exits = declarations()
    rows = []
    mutations = []
    with tempfile.TemporaryDirectory(prefix='walker-exits-') as tmp:
        root = Path(tmp)
        for spec in WALKERS:
            if spec['language']=='lisp':
                continue  # Closed by the separately compiled Lisp population below.
            if spec['language']!='c':
                raise GateError('no executable adapter for walker: '+spec['id'])
            source = (ROOT/spec['path']).read_text()
            traces = (False,True) if 'C2_V21_TRACE_FAIL' in c_body(source,spec['name']) else (False,)
            for trace in traces:
                directory=root/(spec['id']+str(int(trace)));directory.mkdir()
                row=c_exit(spec,directory,trace=trace)
                if row['value']!=exits[spec['id']]['value']:
                    raise GateError('executed walker exit differs from declaration: '+spec['id'])
                rows.append(row)
        lisp=lisp_exits(exits)
        observed={r['walker'] for r in rows}|{r['name'] for r in lisp['execution']['observations']}
        if observed!=set(exits):
            raise GateError('unexecuted walker in declared population')
        if controls:
            spec=next(row for row in WALKERS if row['id']=='cold-stager-file')
            for trace in (False,True):
                for index, expr in enumerate(('0','(1)','1 + 0','drop-guard')):
                    directory=root/f'mutant-{trace}-{index}';directory.mkdir()
                    row=c_exit(spec,directory,trace=trace,mutation=expr)
                    passes=row['value']==exits[spec['id']]['value']
                    if passes!=(expr=='0'):
                        raise GateError('executed return-value mutation failed: '+expr)
                    mutations.append(dict(expression=expr,trace=trace,accepted=passes))
            for name in exits:
                value=json.loads(EXIT_CONTRACT.read_text());value['exits'].pop(name)
                try: declarations(value)
                except GateError: mutations.append(dict(missing_declaration=name,rejected=True))
                else: raise GateError('undeclared walker survived')
            changed={key:dict(value) for key,value in exits.items()}
            changed['ide-directory-list']['value']='nil'
            try: lisp_exits(changed)
            except Exception as error:
                if "expected 'nil' got '(77 88)'" not in str(error):
                    raise
                mutations.append(dict(unbound_partial_to_nil='rejected'))
            else: raise GateError('partial-result declaration mutation survived')
    result=dict(format='lisp65-chain-walker-executed-exits-v1',status='pass',
        declarations=dict(path=str(EXIT_CONTRACT.relative_to(ROOT)),sha256=sha256(EXIT_CONTRACT),exits=exits),
        c=rows,lisp=lisp,mutations=mutations,observed=sorted(observed),
        claim='Executed exhausted-budget exits only. Host RAM/I/O seams and debugger-supplied local budgets; no target ABI, timing or full-chain validity claim.')
    EXECUTION_RECEIPT.parent.mkdir(parents=True,exist_ok=True)
    EXECUTION_RECEIPT.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    return result


def c_body(text: str, name: str) -> str:
    match = re.search(rf"\b{re.escape(name)}\s*\([^;]*?\)\s*\{{", text, re.S)
    if not match:
        raise GateError(f"C walker not found: {name}")
    start = text.find("{", match.start())
    depth = 0
    for index in range(start, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[match.start():index + 1]
    raise GateError(f"unterminated C walker: {name}")


def lisp_body(text: str, name: str) -> str:
    marker = f"(defun {name}"
    start = text.find(marker)
    if start < 0:
        raise GateError(f"Lisp walker not found: {name}")
    depth = 0
    in_string = False
    escaped = False
    comment = False
    for index in range(start, len(text)):
        char = text[index]
        if comment:
            if char == "\n":
                comment = False
            continue
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == ";":
            comment = True
        elif char == '"':
            in_string = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    raise GateError(f"unterminated Lisp walker: {name}")


def chain(sectors: int) -> dict[tuple[int, int], tuple[int, int]]:
    links: dict[tuple[int, int], tuple[int, int]] = {}
    for index in range(sectors):
        current = (1 + index // 40, index % 40)
        if index + 1 == sectors:
            links[current] = (0, 2)
        else:
            links[current] = (1 + (index + 1) // 40, (index + 1) % 40)
    return links


def walk_model(
    links: dict[tuple[int, int], tuple[int, int]], limit: int, *, file_data: bool,
) -> str:
    current = (1, 0)
    seen: set[tuple[int, int]] = set()
    for _ in range(limit):
        if current in seen or current not in links:
            return "reject"
        seen.add(current)
        next_track, next_sector = links[current]
        if next_track == 0:
            if file_data and next_sector == 0:
                return "reject"
            return "accept"
        if not 1 <= next_track <= 80 or not 0 <= next_sector < 40:
            return "reject"
        current = (next_track, next_sector)
    return "reject"


def data_case(kind: str, limit: int, case: str) -> str:
    file_data = kind != "directory"
    if case == "greater-than-255-sectors":
        if not file_data:
            return "not-applicable"
        return walk_model(chain(258), limit, file_data=True)
    if case == "zero-tail":
        if not file_data:
            return "not-applicable"
        return walk_model({(1, 0): (0, 0)}, limit, file_data=True)
    if case == "self-reference":
        return walk_model({(1, 0): (1, 0)}, limit, file_data=file_data)
    raise GateError(f"unknown shared case: {case}")


def verify() -> dict[str, Any]:
    rows = []
    bindings: dict[str, dict[str, Any]] = {}
    validators = []
    coordinators = []
    for spec in (
        {
            "id": "c-file-link-decoder", "path": "src/io.c", "language": "c",
            "name": "disk_chain_count",
            "requires": ["if (!nt)", "if (!ns) return 255u", "nt == t && ns == s", "return 254u"],
        },
        {
            "id": "ide-file-link-decoder", "path": "lib/ide-disk.lisp", "language": "lisp",
            "name": "%ide-disk-link-valid-p",
            "requires": ["(= next-track 0)", "(> next-sector 0)", "(= next-track track)", "(= next-sector sector)"],
        },
        {
            "id": "resident-directory-link-decoder", "path": "lib/stdlib-load.lisp", "language": "lisp",
            "name": "%disk-directory-link-valid-p",
            "requires": [
                "(= next-track 0)", "(= next-track 40)", "(< next-sector 40)",
                "(= next-track track)", "(= next-sector sector)",
            ],
        },
    ):
        path = ROOT / spec["path"]
        text = path.read_text(encoding="utf-8")
        body = c_body(text, spec["name"]) if spec["language"] == "c" else lisp_body(text, spec["name"])
        missing = [token for token in spec["requires"] if token not in body]
        if missing:
            raise GateError(f"{spec['id']} misses structural guards: {missing}")
        validators.append({
            "id": spec["id"], "path": spec["path"], "function": spec["name"],
            "zero_tail": "reject", "self_reference": "reject", "status": "pass",
        })
        bindings[spec["path"]] = {"path": spec["path"], "sha256": sha256(path)}
    for spec in WALKERS:
        path = ROOT / spec["path"]
        text = path.read_text(encoding="utf-8")
        body = c_body(text, spec["name"]) if spec["language"] == "c" else lisp_body(text, spec["name"])
        missing = [token for token in spec["requires"] if token not in body]
        if missing:
            raise GateError(f"{spec['id']} misses structural guards: {missing}")
        observed_large = data_case(spec["kind"], spec["sector_limit"], "greater-than-255-sectors")
        if observed_large != spec["large_case"]:
            raise GateError(f"{spec['id']} large-chain classification drift")
        rows.append({
            "id": spec["id"], "path": spec["path"], "function": spec["name"],
            "language": spec["language"], "kind": spec["kind"],
            "sector_accounting": (
                "16-bit-or-fixnum-for-file-data; bounded-8-bit-for-40/64-sector-directory-domain"
            ),
            "sector_limit": spec["sector_limit"],
            "corrupt_zero_tail": data_case(spec["kind"], spec["sector_limit"], "zero-tail"),
            "self_reference": data_case(spec["kind"], spec["sector_limit"], "self-reference"),
            "greater_than_255_sectors": observed_large,
            "status": "pass",
        })
        bindings[spec["path"]] = {
            "path": spec["path"], "sha256": sha256(path),
        }
    cases = [
        {
            "id": "greater-than-255-sectors", "sectors": 258,
            "rule": "accept only the media-sized cold stager; bounded user APIs reject rather than truncate",
            "status": "pass",
        },
        {
            "id": "link-byte-zero-in-final-sector", "terminal_link": [0, 0],
            "rule": "file-data walkers reject before reading payload byte 256; directory walkers use track zero as their format terminator",
            "status": "pass",
        },
        {
            "id": "self-reference", "link": "current-track/current-sector",
            "rule": "reject immediately where identity is retained, otherwise terminate at the documented domain fuel without publishing a partial success",
            "status": "pass",
        },
    ]
    executed = execute_exits()
    return {
        "format": FORMAT,
        "status": "pass",
        "executed_exits": executed,
        "scope": "all live 1581 on-media link walkers in product C and Lisp sources",
        "criteria": {
            "sector_accounting": "no 8-bit truncation for file-data chains; explicitly bounded counters for finite directory/descriptor domains",
            "corrupt_link_clamp": "zero-byte file terminators and invalid/self links fail closed",
            "fuel_or_cycle_bound": "every walker has length-derived fuel, a format-domain fuel, or a byte-ceiling bound",
        },
        "shared_cases": cases,
        "shared_link_validators": validators,
        "chain_coordinators": coordinators,
        "walkers": rows,
        "excluded_non_walkers": [
            "M65D new-chain allocation and write recursion consume validated in-memory pair lists, not on-media link bytes",
            "the Wave-1 preallocated C1 FASL slot walker and commit-last writer are retired; compile-string now publishes through M65D COW",
            "archived m65-disk-alloc*.lisp prototypes are not product inputs",
            "host D81 parsers are independent witnesses, not device walkers",
        ],
        "deviations": [],
        "source_bindings": sorted(bindings.values(), key=lambda row: row["path"]),
        "claim_limit": "This receipt proves structural guards and the common host model. Hardware timing and F011 transport remain outside this gate.",
    }


def selftest() -> None:
    execute_exits(controls=True)
    if data_case("file-data", 3226, "greater-than-255-sectors") != "accept":
        raise GateError("large media model rejected the cold-stager case")
    if data_case("file-data", 255, "greater-than-255-sectors") != "reject":
        raise GateError("bounded model accepted a truncated large chain")
    if data_case("file-data", 153, "zero-tail") != "reject":
        raise GateError("zero-tail mutation accepted")
    if data_case("directory", 64, "self-reference") != "reject":
        raise GateError("directory self-reference mutation accepted")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        if args.selftest:
            selftest()
            print("chain-walker-inventory: SELFTEST PASS models=4 executed-return-controls=8 declaration-omissions=18 partial-result=1")
            return 0
        receipt = verify()
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        print(f"chain-walker-inventory: PASS walkers={len(receipt['walkers'])} cases=3 deviations=0")
        return 0
    except (GateError, OSError, UnicodeError) as exc:
        print(f"chain-walker-inventory: FAIL: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
