#!/usr/bin/env python3
"""Execute the actual primitive-15 body with a failing I/O seam.

This is a bounded host semantic test, NOT final-ELF or packed-DWX acceptance.
No product build, source regeneration, media mutation or device access.
"""
from pathlib import Path
import hashlib
import json
import subprocess
import tempfile

from evidence_era import stable_recorded_on

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'src/vm.c'
OUT = ROOT / 'build/v2.1/f011-followup-host-preflight'
RECEIPT = OUT / 'primitive15-receipt.json'

PREFIX = r'''
#include <setjmp.h>
#include <stdint.h>
#include "obj.h"
#include "vm.h"
#include "error_codes.h"
uint8_t vm_status;
static obj vm_t = (obj)0xe002;
static jmp_buf abort_target;
static int calls, result, error;
static unsigned char io_disk_read_sector(uint8_t track, uint8_t sector) {
    if (track != 40 || sector != 3) return 0;
    ++calls;
    return (unsigned char)result;
}
static void lisp_abort_code(lisp65_error_code code) {
    error = code;
    longjmp(abort_target, 1);
}
static obj primitive(unsigned char id, unsigned char n, obj *a) {
    switch (id) {
'''
SUFFIX = r'''
    default: return NIL;
    }
}
int main(void) {
    obj a[2] = { MKFIX(40), MKFIX(3) };
    result = 0;
    if (!setjmp(abort_target)) {
        (void)primitive(15, 2, a);
        return 11; /* A read failure returned instead of entering error path. */
    }
    if (error != LISP65_ERR_LOAD_OPEN || calls != 1) return 12;
    error = calls = 0;
    for (result = 1; result <= 2; ++result) {
        if (setjmp(abort_target)) return 13;
        if (primitive(15, 2, a) != vm_t) return 14;
    }
    if (calls != 2 || error) return 15;
    calls = 0;
    if (primitive(15, 1, a) != NIL || vm_status != VM_TYPEERROR || calls) return 16;
    vm_status = VM_OK;
    a[0] = NIL;
    if (primitive(15, 2, a) != NIL || vm_status != VM_TYPEERROR || calls) return 17;
    return 0;
}
'''

def main():
    source = SOURCE.read_text()
    begin = source.index('    case 15:  /* %disk-read-sector */')
    end = source.index('    case 16:', begin)
    body = source[begin:end]
    abort = '            lisp_abort_code(LISP65_ERR_LOAD_OPEN);'
    if body.count(abort) != 1:
        raise RuntimeError('primitive-15 error seam not uniquely identifiable')
    OUT.mkdir(parents=True, exist_ok=True)
    outcomes = {}
    with tempfile.TemporaryDirectory(prefix='primitive15-', dir=OUT) as tmp:
        tmp = Path(tmp)
        for label, text in [('successor',body), ('read-failure-returns-nil',body.replace(abort,''))]:
            c = tmp/(label+'.c')
            exe = tmp/label
            c.write_text(PREFIX+text+SUFFIX)
            subprocess.run(['cc','-std=c11','-O2','-I',str(ROOT/'src'),str(c),'-o',str(exe)],check=True)
            result = subprocess.run([str(exe)],check=False)
            outcomes[label] = result.returncode
    if outcomes != {'successor':0,'read-failure-returns-nil':11}:
        raise RuntimeError(f'error propagation gate red: {outcomes}')
    receipt = {'format':'f011-primitive15-host-semantic-v1',
        'recorded_on':stable_recorded_on(RECEIPT),
        'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        'extracted_body_sha256':hashlib.sha256(body.encode()).hexdigest(),
        'results':outcomes, 'product_wplto':0, 'product_links':0,
        'device_contacts':0, 'final_elf_qualified':False, 'packed_prefilter_qualified':False,
        'claim':'actual C primitive case, stubbed I/O result; missing error transfer mutation fails'}
    RECEIPT.write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2))

if __name__ == '__main__':
    main()
