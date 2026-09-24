#!/usr/bin/env python3
"""INIT host preflight: execute live Lisp resource guard and native ABI/loader.

Native extraction replaces only the hardware sector supplier and evaluation
callback. It is a component proof, not a target-link or prompt-recovery proof.
"""
from pathlib import Path
import copy
import hashlib
import json
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/host-lisp'))
import host_d81_worlds as D
import chain_walker_inventory as CW
import bytecode_abi_ledger as ABI


def cfun(text, name):
    return CW.c_function(text, name)


def native_run(code):
    with tempfile.TemporaryDirectory() as tmp:
        c = Path(tmp) / 'test.c'
        exe = Path(tmp) / 'test'
        c.write_text(code)
        subprocess.run(['cc', '-std=c99', '-O1', '-Wall', '-Werror',
                        str(c), '-o', str(exe)], check=True, capture_output=True)
        return subprocess.run([str(exe)], capture_output=True).returncode


def prim_test():
    text = (ROOT / 'src/vm.c').read_text()
    arm = text.split('    case 58: /* %list-malformed-error', 1)[1]
    arm = 'case 58: /* %list-malformed-error' + arm.split('    case 59:', 1)[0]
    old = subprocess.check_output(['git', 'show', '80c1bc68:src/vm.c'], cwd=ROOT, text=True)
    old = old.split('    case 58:', 1)[1].split('    case 59:', 1)[0]
    old_body = old[old.index('        if (n != 0)'):]
    assert old_body in arm, 'legacy zero-argument body changed'
    code = '''#include <stdint.h>
typedef uint16_t obj;
#define NIL 0
#define MKFIX(x) (((x)<<1)|1)
enum {VM_TYPEERROR=1,VM_HEAPOOM=2,VM_ARITY=3};
static int vm_status;
static obj call(unsigned n,obj *a) {switch(58) {ARM} return 0;}
int main(void) {obj a[2]={0,0}; unsigned i;
call(0,a); if(vm_status!=VM_TYPEERROR)return 1;
for(i=0;i<65536;i++){a[0]=i;call(1,a);
if(vm_status!=(i==MKFIX(1)?VM_HEAPOOM:VM_ARITY))return 2;}
call(2,a);return vm_status!=VM_ARITY;}
'''.replace('ARM', arm)
    assert native_run(code) == 0
    assert native_run(code.replace('vm_status = VM_HEAPOOM;', 'vm_status = VM_TYPEERROR;')) != 0
    return {'native_one_argument_values': 65536, 'legacy_body_retained': True,
            'wrong_status_mutation': 'rejected'}


def resource_test():
    import resolver_owner_gate as OWNER
    native=OWNER.build(ROOT/'build/init-repair-resource-owner')
    class OwnerVM(D.B.P0VM):
        def _callprim(self,pid,argc,stack,pc=None,native_base=0,frame_slots=0):
            if pid==67 and argc==1:
                arg=self._pop_args(argc,stack)[0]
                if not D.B.is_fix(arg) or not 0<=D.B.fixval(arg)<=255:
                    raise D.B.VMError('TypeError','owner selector byte domain')
                value=native.c2_resolver_owner_part(D.B.fixval(arg))
                return D.B.NIL if value==65535 else D.B.mkfix(value)
            return super()._callprim(pid,argc,stack,pc,native_base,frame_slots)
    full = "(%require-directory-capacities-p (list '(0 . 0) '(0 . 0) '(0 . 0) '(1 . 0) '(0 . 0) '(0 . 0)) '(0 0 0 4096 0 0) '(0 2048 4096 1536))"
    absent = '(require "no-such-package")'
    suite = D.LispSuite('tests/bytecode/libs/p0-stdlib-require-resolver.json', [full, absent])
    world = D.PRESETS['w4-index-2-t18s34']
    value, _ = suite.run(full, world, vm_class=OwnerVM)
    assert isinstance(value, dict) and value['error'] == 'HeapOOM', value
    missing, _ = suite.run(absent, world, vm_class=OwnerVM)
    assert missing == 'nil', missing
    heap, directory = suite.mutated('lib/stdlib-require.lisp',
        '(%list-malformed-error 1)', 'nil', ('%require-directory-capacities-p',))
    old, _ = suite.run(full, world, heap=heap, directory=directory, vm_class=OwnerVM)
    assert old == 'nil', old
    unbound, _ = suite.run(full, world)
    assert isinstance(unbound,dict) and unbound['error']=='TypeError'
    ledger = ABI.load_json(ABI.DEFAULT_LEDGER)
    assert ledger['resource_error_mode'] == ABI.RESOURCE_ERROR_MODE
    for key in ('selector', 'error_code', 'prim_id'):
        wrong = copy.deepcopy(ledger)
        wrong['resource_error_mode'][key] += 1
        try: ABI.validate(wrong, check_mirrors=False)
        except ABI.LedgerError: pass
        else: raise AssertionError('ledger mutation survived: '+key)
    missing_mode = copy.deepcopy(ledger)
    missing_mode.pop('resource_error_mode')
    try: ABI.validate(missing_mode)
    except ABI.LedgerError: pass
    else: raise AssertionError('mode omission survived')
    return {'full_resolutions': value, 'missing_package': missing,
            'old_nil_mutation': 'rejected', 'ledger_controls': 4}


def loader_test():
    src = (ROOT / 'src/io.c').read_text()
    load = cfun(src, 'io_disk_load_chain')
    abort = cfun(src, 'io_disk_source_abort')
    code = '''#include <setjmp.h>
static unsigned disk_file_len,disk_file_pos,disk_source_link,disk_source_cur;
static unsigned char disk_source_active;
static jmp_buf landing;
static unsigned staged, nested, error;
#define LISP65_ERR_LOAD_OPEN 18
#define DISK_SOURCE_LINK_VALID 0x8000u
#define DISK_SOURCE_LINK_PACK(t,s) (0x8000u|((t)<<6)|(s))
static char disk_source_fetch(void){return 0;}
static unsigned disk_chain_to_scratch(unsigned char t,unsigned char s){(void)t;(void)s;staged++;return 10;}
ABORT
static void raise_error(unsigned c){error=c;io_disk_source_abort();longjmp(landing,1);}
#define lisp_abort_static(c,text) raise_error(c)
unsigned char io_disk_load_chain(unsigned char,unsigned char);
static void load_source_stream(char (*fetch)(void)){
 (void)fetch;if(nested)io_disk_load_chain(2,3);
}
LOAD
int main(void){nested=1;
 if(!setjmp(landing)){io_disk_load_chain(1,2);return 1;}
 if(error!=18||staged!=1||disk_source_active)return 2;
 nested=0;if(!io_disk_load_chain(1,2)||disk_source_active||staged!=2)return 3;
 return 0;}
'''.replace('ABORT', abort).replace('LOAD\n', load+'\n')
    assert native_run(code) == 0
    assert native_run(code.replace('disk_source_active = 0;', 'disk_source_active = 1;', 1)) != 0
    cleanup = (ROOT / 'src/interrupt.c').read_text()
    jump = cleanup.split('static void lisp_abort_jump(', 1)[1].split('#ifdef ABORT_FRAME_CAPTURED', 1)[0]
    assert jump.index('io_disk_source_abort();') < jump.index('longjmp(')
    return {'nested': 'LOAD_OPEN before second staging', 'following_load': 'accepted',
            'stuck_guard_mutation': 'rejected',
            'limit': 'component cleanup; final target prompt recovery still required'}


def scratch_test():
    src = (ROOT / 'src/io.c').read_text()
    macros = src[src.index('#define DISK_SOURCE_LINK_VALID'):src.index('static unsigned int disk_source_link;')]
    fetch = cfun(src, 'disk_source_fetch')
    refill = cfun(src, 'disk_source_refill_far')
    code = r'''#include <string.h>
static unsigned disk_file_len,disk_file_pos,disk_source_cur,disk_source_link;
static unsigned char scratch[256];
#define DISK_SOURCE_OWNS_SCRATCH 0x4000u
#define LISP65_F011_READ_FAILED 0xffffu
#define LISP65_RESIDENT_ISLAND_FN
#define LISP65_C2_MAPPED_F011_COLD_FN
MACROS
static unsigned char datum(unsigned p){return (unsigned char)(1+p%251);}
static unsigned char io_disk_byte(unsigned char p){return scratch[p];}
static unsigned disk_chain_count(unsigned char t,unsigned char s,unsigned char nt,unsigned char ns){
 (void)t;(void)s;return nt?254u:(unsigned)(ns-1u);}
static unsigned char io_disk_read_sector(unsigned char t,unsigned char s){
 unsigned i,part=((unsigned)t-1)*40+s,start=part*254,remaining;
 disk_source_cur &= ~DISK_SOURCE_OWNS_SCRATCH;
 if(!t||t>80||s>=40||start>=disk_file_len)return 0;
 remaining=disk_file_len-start;
 scratch[0]=remaining>254?(unsigned char)(1+(part+1)/40):0;
 scratch[1]=remaining>254?(unsigned char)((part+1)%40):(unsigned char)(remaining+1);
 for(i=0;i<254;i++)scratch[2+i]=datum(start+i);
 return 1;}
#ifdef __mos__
static unsigned io_disk_read_sector_link_far(unsigned char t,unsigned char s){
 if(!io_disk_read_sector(t,s))return LISP65_F011_READ_FAILED;
 return scratch[0]|((unsigned)scratch[1]<<8);}
REFILL
#define disk_source_refill disk_source_refill_far
#endif
FETCH
static int run(unsigned len,unsigned interruption,unsigned every){
 unsigned p;disk_file_len=len;disk_file_pos=0;disk_source_cur=0;
 disk_source_link=DISK_SOURCE_LINK_PACK(1,0);
 for(p=0;p<len;p++){
  if(p==interruption||every){memset(scratch,0xee,sizeof(scratch));disk_source_cur &= ~DISK_SOURCE_OWNS_SCRATCH;}
  if((unsigned char)disk_source_fetch()!=datum(p))return 1;
 }
 return disk_source_fetch()!=0||disk_file_pos!=len;
}
int main(void){unsigned p;
 for(p=0;p<767;p++)if(run(767,p,0))return 1;
 if(run(65535,0,1))return 2;
 return 0;}
'''.replace('MACROS', macros).replace('REFILL', refill).replace('FETCH', fetch)
    for cold in (False, True):
        form = ('#define __mos__ 1\n#define LISP65_C2_F011_COLD 1\n' if cold else '') + code
        assert native_run(form) == 0, ('scratch', cold)
        # Old logic advances to the successor when another consumer overwrites
        # the scratch: it loses the current sector's unconsumed suffix.
        mutant = form.replace('(disk_source_cur & DISK_SOURCE_LINK_VALID)\n        ? disk_source_cur : disk_source_link', '0 ? disk_source_cur : disk_source_link')
        mutant = mutant.replace('(disk_source_cur & DISK_SOURCE_LINK_VALID)\n            ? disk_source_cur : disk_source_link', '0 ? disk_source_cur : disk_source_link')
        assert mutant != form and native_run(mutant) != 0, ('scratch mutation', cold)
    return {'executed_source': ['disk_source_fetch', 'disk_source_refill_far'],
            'profiles': ['cold', 'non-cold'], 'interruption_positions_per_profile': 767,
            'every_byte_displaced_length': 65535, 'successor_instead_of_current_mutations': 2,
            'limit': 'native C component; sector transport substituted, target timing not claimed'}


def directory_test():
    src = (ROOT / 'src/io.c').read_text()
    code = r'''#include <string.h>
static unsigned char sector_data[256];
static unsigned reads;
static unsigned char disk_fold(unsigned char c){return c;}
static unsigned char io_disk_byte(unsigned char p){return sector_data[p];}
static unsigned char io_disk_read_sector(unsigned char t,unsigned char s){
 reads++;return t==40&&s==3;}
FUNCTION
int main(void){unsigned char t=0,s=0;
 sector_data[2]=0x82;sector_data[3]=18;sector_data[4]=7;
 memcpy(sector_data+5,"abcdefghijklmnop",16);
 if(!disk_dir_find("abcdefghijklmnop",&t,&s)||t!=18||s!=7||reads!=1)return 1;
 if(disk_dir_find("abcdefghijklmnopq",&t,&s)||reads!=1)return 2;
 return 0;}
'''.replace('FUNCTION', cfun(src, 'disk_dir_find'))
    assert native_run(code) == 0
    assert native_run(code.replace('sector = 3', 'sector = 0')) != 0
    assert native_run(code.replace('if (name_len == 16u) return 0;', 'if (name_len == 255u) return 0;')) != 0
    return {'last_valid_name': 16, 'first_invalid_name': 17, 'start': [40, 3],
            'controls': ['header-sector', 'overlong-alias'],
            'limit': 'actual C lookup; sector supplier substituted'}


def assertion_test():
    mem = (ROOT/'src/mem.c').read_text()
    disk = re.search(r'#if \(DISK_EXT_BASE \+ 256UL \+ DISK_EXT_FILE_MAX\).*?#endif',mem,re.S)
    assert disk
    owner = (ROOT/'src/c2_bank2_code_domain.h').read_text()
    def compiles(source):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'test.c';path.write_text(source)
            return subprocess.run(['cc','-std=c11','-fsyntax-only',str(path)],capture_output=True).returncode==0
    for length,expected in ((0x9600,True),(0x9601,False)):
        source='#define DISK_EXT_BASE 0x6900UL\n#define DISK_EXT_FILE_MAX %dUL\n'%length+disk[0]
        assert compiles(source)==expected
    assert compiles(owner)
    assert not compiles('#define LISP65_C2_LITE_COLD_EVICTION 1\n'+owner)
    assert compiles('#define LISP65_C2_LITE_COLD_EVICTION 1\n#define LISP65_C2_BANK2_CODE_LIMIT 59180UL\n'+owner)
    generator=(ROOT/'tools/host-lisp/c2_product_substitution_link.py').read_text()
    assertion=re.search(r'ASSERT\(ADDR\(\.zp\) \+ SIZEOF\(\.zp\).*?;',generator,re.S)
    assert assertion
    line=assertion[0]
    assert 'ADDR(.lisp65_c2_convergence_zp)' in line
    with tempfile.TemporaryDirectory() as tmp:
        tmp=Path(tmp);asm=tmp/'input.s';obj=tmp/'input.o';script=tmp/'link.ld'
        asm.write_text('.section .zp,"aw"\n.space 0x87\n.section .lisp65_c2_convergence_zp,"aw"\n.byte 0\n')
        subprocess.run(['cc','-c',str(asm),'-o',str(obj)],check=True,capture_output=True)
        outcomes=[]
        for boundary in (0x87,0x86):
            for old in (False,True):
                assertion=line.replace('ADDR(.lisp65_c2_convergence_zp)','0x89') if old else line
                script.write_text('SECTIONS { .zp 0 : { *(.zp) } .lisp65_c2_convergence_zp %d : { *(.lisp65_c2_convergence_zp) } }\n%s'%(boundary,assertion))
                # Section overlap is independently illegal. Disable that
                # diagnostic only here to isolate the assertion under test.
                proc=subprocess.run(['ld','--no-check-sections','-T',str(script),str(obj),'-o',str(tmp/'out')],capture_output=True)
                ok=proc.returncode==0
                assert ok==(boundary==0x87 or old),(boundary,old,ok,proc.stderr.decode())
                outcomes.append(dict(boundary=boundary,old_literal=old,accepted=ok))
    return {'disk_end_exact':65536,'disk_end_plus_one':'rejected',
            'cold_owner_omission':'rejected','zero_page':outcomes,
            'limit':'host compiler/linker assertion tests, not target layout proof'}


def refill_population_test():
    import block_26_f011_replacement_product_card as P
    source=(ROOT/'src/io.c').read_text()
    wrappers=(ROOT/'src/optional/c2_f011_cold_wrappers.s').read_text()
    keys=('validated-publication','shared-validator-retained','single-initial-refill')
    assert all(P.source_checks(source,wrappers)[k] for k in keys)
    mutations={
        'omit-validator':source.replace('count = disk_chain_count(t, s, nt, ns);','count = 254;',1),
        'omit-publication':source.replace('DISK_SOURCE_LINK_PACK(nt, nt ? ns : 0u)','0',1),
        'unbound-initial-sector':source.replace('disk_source_link = DISK_SOURCE_LINK_PACK(track, sector);','disk_source_link = 0;',1)}
    for name,mutant in mutations.items():
        assert mutant!=source
        try:accepted=all(P.source_checks(mutant,wrappers)[k] for k in keys)
        except ValueError:accepted=False
        assert not accepted,name
    return {'refill_bodies':['disk_source_refill_far','disk_source_fetch'],
            'capacity_body':'disk_chain_capacity','mutations_rejected':list(mutations)}


def main():
    result = {'primitive': prim_test(), 'resource': resource_test(), 'loader': loader_test(),
              'scratch': scratch_test(),
              'directory': directory_test(),
              'assertions': assertion_test(),
              'refill_population': refill_population_test(),
              'status': 'PASS', 'product_builds': 0}
    files = ['src/vm.c', 'src/io.c', 'src/interrupt.c', 'lib/stdlib-require.lisp',
             'config/bytecode-abi-ledger.json', 'tools/host-lisp/bytecode_p0.py',
             'src/mem.c','src/c2_bank2_code_domain.h',
             'tools/host-lisp/block_26_f011_replacement_product_card.py',
             'tools/host-lisp/c2_product_substitution_link.py']
    result['sources'] = [{'path': p, 'sha256': hashlib.sha256((ROOT/p).read_bytes()).hexdigest()} for p in files]
    out = ROOT / 'build/init-repair-r1/host-contract.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
