#!/usr/bin/env python3
"""Read-only closure of the F011 successor's final and packed runtime proofs."""
from copy import deepcopy
import json
import f011_status_product_card as C
import f011_status_comfort_prefilter as PACK
import f011_status_disk_prefilter as DISK
import f011_status_final_proof as FINAL
import dwx_comfort_resume as RUN
import dwx_comfort_collection_calibration as CAL
from elf_truth import ElfTruth

def verify_binding(item):
    if item['path']=='tools/host-lisp/dwx_comfort_resume.py':
        from evidence_era import era_bind
        C.require(era_bind('5224d70d',item['path'])==item,'sealed status-world executor drift')
        return
    C.require(C.bind(C.ROOT/item['path'])==item,'evidence binding drift: '+item['path'])

def runtime_semantics(comfort,negative,frames,raw):
    C.require(comfort['status'].startswith('EXECUTED ROWS PASS'),'Comfort runtime incomplete')
    first=next(r for r in comfort['rows'] if r['id']=='F011-first-success')
    record=bytes.fromhex(first['raw'])
    C.require(record[0]==1 and record[1]&0x7c==0x60,'first successful read unobserved')
    C.require(negative['status']=='PASS' and raw[0]==2 and raw[1]&0x7c!=0x60,'first failure unobserved')
    C.require('*** LOAD: CANNOT OPEN' in frames['negative'] and '\nNIL\n' not in frames['negative'],'read error hidden as NIL')
    for name,prompt in [('C2-overclose','L65>'),('C3-abort','LISP65>'),('C3-reentry','L65>')]:
        lines=frames[name].splitlines()
        diagnosis='*** READER: UNMATCHED CLOSE PARENTHESIS' if name=='C2-overclose' else '*** VM: TYPE ERROR'
        C.require(diagnosis in lines and lines[-1].replace('{$A0}',' ').strip()==prompt,'composed display/diagnostic overwritten')
        C.require(lines.index(diagnosis)<len(lines)-1,'prompt overwrote diagnostic row')
    d=comfort['stopped']['derived'];cap=bytes.fromhex(comfort['stopped']['capture']['raw'])
    C.require(d['collections']>=1 and len(set(cap))==1 and cap[0]!=0,'collection/capture unproved')
    C.require(d['free_slots']>=32 and d['free_name_bytes']>=384,'D5 floor')

def run():
    PACK.check()
    pair=[C.bind(C.ELF),C.bind(C.PRG)]
    proof_before=C.bind(FINAL.OUT);FINAL.run()
    C.require(C.bind(FINAL.OUT)==proof_before,'final emitted proof drift')
    runtime=PACK.RUNTIME;neg=DISK.BUILD/'corrupt-directory'
    comfort=C.load(runtime/'receipt.json');negative=C.load(neg/'receipt.json')
    C.require(comfort['product']==C.bind(C.ELF) and comfort['medium']==C.bind(PACK.MEDIUM),'runtime world drift')
    for item in [comfort['fork'],comfort['executor'],comfort['calibration_executor'],comfort['successor_card'],negative['negative_medium']]:verify_binding(item)
    for row in comfort['rows']:
        for key in ('framebuffer','evidence'):
            if key in row:verify_binding(row[key])
    for result in (comfort,negative):
        for evidence in result['outputs'].values():verify_binding(evidence)
    frames={name:RUN.R.ROWS.decoded_framebuffer((runtime/(name+'-framebuffer.txt')).read_text())
            for name in ('C2-overclose','C3-abort','C3-reentry')}
    frames['negative']=RUN.R.ROWS.decoded_framebuffer((neg/'oracle-framebuffer.txt').read_text())
    raw=(neg/'f011-record.bin').read_bytes()
    negative_dump=(C.ROOT/negative['outputs']['memory']['path']).read_bytes()
    address=C.load(FINAL.OUT)['record_owner']['start']
    C.require(negative_dump[address:address+3]==raw,'negative stopped record differs from sealed RAM dump')
    truth=ElfTruth.read(C.ELF,llvm_readobj=C.B.READOBJ,include_section_data=True)
    authority=CAL.model(truth,C.ELF)
    data=comfort['collection_calibration']
    capture=next(r for r in C.load(RUN.SESSION)['rows'] if r['id']=='C4')['collection']
    samples=[(C.load(runtime/f'calibration-sample-{i}-typed.json'),
              C.load(runtime/f'calibration-sample-{i}-deleted.json')) for i in (1,2)]
    derived=json.loads(C.canonical(CAL.derive(data['origin'],samples,capture,authority)))
    C.require(derived==data['plan'],'successor allocation derivation drift')
    CAL.verify_chain(data['origin'],authority);CAL.verify_chain(data['start'],authority)
    CAL.validate_window(data['origin'],data['start'],data['end'])
    runtime_semantics(comfort,negative,frames,raw)
    mutations=[]
    for kind in ('unseen-success','masked-read-error-as-nil','overwritten-diagnostic','gc-before-window','undrained-ring'):
        m=deepcopy(comfort);f=dict(frames)
        if kind=='unseen-success':next(r for r in m['rows'] if r['id']=='F011-first-success')['raw']='0062aa'
        elif kind=='masked-read-error-as-nil':f['negative']='NIL\nLISP65>'
        elif kind=='overwritten-diagnostic':f['C3-abort']=f['C3-abort'].replace('*** VM: TYPE ERROR','LISP65>TYPE ERROR')
        elif kind=='gc-before-window':m['stopped']['derived']['collections']=0
        else:m['stopped']['capture']['raw']='88888800'
        try:runtime_semantics(m,negative,f,raw)
        except RuntimeError:mutations.append(kind)
        else:raise RuntimeError('mutation survived: '+kind)
    boot=C.load(DISK.BUILD/'boot/receipt.json')
    verify_binding(boot['fork'])
    C.require(len(boot['rows'])==6 and boot['fork']==comfort['fork'],'boot comparison incomplete/wrong fork')
    for row in boot['rows']:
        verify_binding(row['medium'])
        for evidence in row['outputs'].values():verify_binding(evidence)
    historical=C.ROOT/'build/v2.1/comfort-collection-calibration-r2'
    original_load=CAL.R.load
    for key in ('executor','calibration_executor'):
        def altered(path):
            value=original_load(path)
            if path==historical/'receipt.json':
                value=deepcopy(value);value[key]['sha256']='0'*64
            return value
        CAL.R.load=altered
        try:
            try:CAL.row_binding(historical)
            except RuntimeError:mutations.append('sealed-'+key+'-identity-divergence')
            else:raise RuntimeError('historical identity mutation survived')
        finally:CAL.R.load=original_load
    C.require(pair==[C.bind(C.ELF),C.bind(C.PRG)],'qualification changed frozen pair')
    print('F011 qualification CHECK PASS; mutations='+str(len(mutations)),flush=True)

if __name__=='__main__':run()
