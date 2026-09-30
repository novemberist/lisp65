"""Dated host-budget seam for ptrace-restricted environments.

All inherited exit populations, I/O assertions, trace rows, return mutations,
declaration omissions and Lisp observations remain in chain_walker_inventory.
Only supplying the exhausted local budget changes from GDB to a C statement
at the same original first-loop boundary; this is not target qualification.
"""
import re, zlib, subprocess, hashlib
from chain_walker_inventory import ROOT, GateError, c_function, c_macro

def c_exit(spec, directory, *, trace=False, mutation=None):
    """Same fixture/control flow, with local-budget injection before its loop.

    The sole new seam is exactly the state assignment formerly made by GDB.
    It neither supplies the return value nor skips the loop or exit guard.
    The generated unit, original body and source are all SHA-bound.
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
static unsigned int disk_file_len=1, disk_file_pos=1, disk_source_link, disk_source_cur;
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
            'DISK_SOURCE_LINK_SECTOR','DISK_SOURCE_OWNS_SCRATCH'))+'\n'
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
    if name not in ('scan_file', 'disk_source_fetch'):
        first_loop = re.search(r'\bwhile\s*\(', body)
        if first_loop is None:
            raise GateError('no executed budget boundary: '+name)
        assignment = 'n = DISK_FILE_MAX' if name == 'disk_chain_to_scratch' else 'fuel = 0'
        witness = 'n, (unsigned)DISK_FILE_MAX' if name == 'disk_chain_to_scratch' else 'fuel, 0u'
        seam = assignment + ';\n' + 'printf("BUDGET_WITNESS %u %u\\n", ' + witness + ');\n'
        body = body[:first_loop.start()] + seam + body[first_loop.start():]
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
    commands = [str(executable)]
    mode = ('natural-sector-fuel' if name == 'scan_file' else
            'caller-stream-position' if name == 'disk_source_fetch' else
            'host-injected-at-original-loop-boundary')
    ran = subprocess.run(commands,text=True,capture_output=True,timeout=15)
    match = re.search(r'RESULT (\d+) READS (\d+) WRITES (\d+) TRACE (\d+)',ran.stdout)
    if ran.returncode or match is None or (mode.startswith('host-injected') and 'BUDGET_WITNESS ' not in ran.stdout):
        raise GateError('C walker did not execute its exit: '+name+'\n'+ran.stdout+ran.stderr)
    result, reads, writes, reason = map(int, match.groups())
    expected_reads = 1 if name in ('scan_file','disk_chain_to_scratch') else 0
    if reads!=expected_reads or writes:
        raise GateError('exhausted walker performed unexpected I/O: '+name)
    if mode.startswith('host-injected'):
        budget=re.search(r'BUDGET_WITNESS (\d+) (\d+)',ran.stdout)
        if budget is None or budget.group(1)!=budget.group(2):
            raise GateError('host seam did not establish exhausted budget: '+name)
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

