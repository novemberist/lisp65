"""Bind writer/caller census, bounded C results and remaining transport obligations."""
from pathlib import Path
import re,subprocess
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import set_b_front_span_20260926 as F
import set_b_front_certificate_audit_20260926 as A
import set_b_front_span_seal_20260926 as PREVIOUS
from set_b_load_preflight_seal_20260926 import external_binding
ROOT=P.ROOT;OUT=ROOT/'build/set-b-front-paths-close-r2'

def main():
    PREVIOUS.check();authority=S.require_auth();OUT.mkdir(exist_ok=False)
    cp=ROOT/'build/set-b-r1/step4-r6/closure-r1/compiler-inputs.json';c=P.load(cp)
    roots=[r['after'] for r in c['roots']]+c['sources'];assert c['root_count']==74
    for row in roots:assert P.bind(ROOT/row['path'])==row
    span=P.load(F.OUT/'binding.json')
    for row in span['candidate']:assert P.bind(ROOT/row['path'])==row
    runtime=(F.OUT/'candidate/src/c2_product_runtime.c').read_text();vm=(F.OUT/'candidate/src/vm.c').read_text()
    # Direct linked call census inherited from the unchanged fifth ELF; explicitly
    # not a relink or a newly established indirect-call census for this candidate.
    old=ROOT/'build/set-b-front-certificate-audit-r2/receipt.json';a=P.load(old)
    assert (a['linked_call_count'],a['classified_owners'])==(53,44)
    calls=P.load(ROOT/a['linked_calls']['path']);assert set(x['owner'] for x in calls)==set(A.CLASSES)
    owner_rows=[]
    for owner,domain in sorted(A.CLASSES.items()):
        if domain.startswith('retirement-'):rule='Normal owner/image/journal edits preserve charged start/length/generation; recovery invalidates before retirement dispatch. Exact rm_own tested; complete retirement/DMA not executed.'
        elif domain.startswith('rollback-'):rule='Certificate invalidated by rollback/abort caller before writes; exact header/unpublish/plane wipe/finalize tested; DMA code/attic and journal completion remain transport gates.'
        elif domain in ('persistent-or-high-transient-entry-rows','publication-header-and-context','unpublished-image-entry-resolution-root-spans','image-row','session-source-and-bank2-code','append-journal','append-and-export-journal-clear','export-journal'):
            rule='Append begins BUSY before stage; exact entry/header/stage-plane and full installer/terminal tested at named seams. Publish only after transaction end; transient front excluded. Image/code/attic and journal transport remain gates.'
        elif domain.startswith('boot-') or owner in ('main','c2_stream_phase_03b','c2_phase02a_record_read'):
            rule='Prepare-boot resets; boot begins BUSY before decode and publishes only after READY. Source closure only in this commission; native boot remains open.'
        elif domain in ('resolutions','roots','emitter-root-scratch'):
            rule='Does not write entry start/length/generation; bounded resolver/root/emitter owners remain within existing layout. Decoder boot/append callers own publication.'
        else:rule='Transport facade or separately bounded owner outside charged entry fields; inherited linked edge retained. CPU mapping/DMA completion is not proved by host fixtures.'
        owner_rows.append(dict(owner=owner,domain=domain,rule=rule,linked_edges=sum(x['owner']==owner for x in calls)))
    P.write(OUT/'owner-table.json',dict(rows=owner_rows,linked_census=P.bind(old),linked_calls=P.bind(ROOT/a['linked_calls']['path']),
        candidate_binding=P.bind(F.OUT/'binding.json'),unclassified_inherited_owners=0,
        scope='53 inherited direct edges/44 owners plus candidate source hooks. No new linked/indirect raw-I/O closure claim.'))
    witness=[]
    source_rules=dict(A.SOURCE_RULES)
    source_rules.update({'src/c2_phase_scratch.c':r'acquire|release|c2_phase_owner',
        'src/eval.c':r'vm_check_status|vm_status_error_code|lisp_abort_code|LISP65_NUMERIC_ERRORS',
        'src/io.c':r'io_disk_scratch_poke|DISK_EXT_DIR',
        'src/optional/set_b_retire_commit_b.c':r'rm_own|rm_write|entries_offset|c2_u16\(r\+',
        'src/error_codes.h':r'VM_BAD_BYTECODE|VM_OOM'})
    source_rules['src/c2_product_runtime.c'] += r'|c2_front_|c2_runtime\.entry_first|c2_completion_poll'
    source_rules['src/vm.c'] += r'|c2_front_raw_write|vm_status_error_code|LISP65_ERR_VM_BAD_BYTECODE'
    for name,pattern in source_rules.items():
        path=F.OUT/'candidate'/name
        if not path.exists():path=ROOT/name
        hits=[dict(line=i+1,text=line) for i,line in enumerate(path.read_text().splitlines()) if re.search(pattern,line)]
        assert hits,name;witness.append(dict(source=P.bind(path),hits=hits))
    P.write(OUT/'source-witnesses.json',witness)
    raw='''            c2_front_raw_write();
            *(volatile unsigned char *)(uintptr_t)address = (unsigned char)FIXVAL(a[2]);
            c2_front_raw_write();'''
    assert raw in vm
    assert 'if (transient) c2_runtime.entry_cursor = c2_u16(c2aw.record + 12);' in runtime
    assert 'c2_front_abort();\n#ifdef LISP65_C2_BOOT_NAME_INDEX' in runtime
    proofs=[];dependencies=[];external=[]
    for name,count in (('r1',156),('writers-r3',91),('query-r1',138)):
        path=ROOT/f'build/set-b-front-paths-{name}/receipt.json';q=P.load(path);proofs.append(P.bind(path))
        assert q['status'].startswith('PASS') and q['halt'] is None and q['row_count']==q['passing_rows']==count
        cmd=P.load(ROOT/q['command']['path'])['command'].copy();at=cmd.index('-o');del cmd[at:at+2];cmd+=['-M','-MT','fixture']
        r=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True);folder=OUT/name;folder.mkdir();log=folder/'host-dependencies.log';log.write_text(r.stdout+r.stderr)
        assert not r.returncode,r.stderr
        internal=[];deps=[]
        for word in r.stdout.replace('\\\n',' ').split(':',1)[1].split():
            p=(ROOT/word).resolve()
            (internal if p.is_relative_to(ROOT) else deps).append(P.bind(p) if p.is_relative_to(ROOT) else external_binding(p))
        path=folder/'host-dependencies.json';P.write(path,dict(command=cmd,exit=0,log=P.bind(log),internal=internal,external=deps));dependencies.append(P.bind(path));external+=deps
    failed=P.load(ROOT/'build/set-b-front-paths-writers-r1/command.json');assert failed['exit']!=0
    r2=ROOT/'build/set-b-front-paths-writers-r2';q=P.load(r2/'receipt.json');h=P.load(r2/'halt.json')
    assert q['row_count']==22 and q['passing_rows']==21 and h['op']==3
    # The first false range failure is fully attributable to fixture preparation,
    # not to an allowed-range waiver. Product write trace contains no header write.
    assert [x for x in h['changed_bytes'] if x<48]==[12,16,20,24]
    assert all(at>=48 for at,n in h['writes'])
    P.write(OUT/'harness-attribution.json',dict(failed_compile=P.bind(ROOT/'build/set-b-front-paths-writers-r1/command.json'),
        interrupted_fixture=P.bind(r2/'receipt.json'),row=P.bind(r2/'halt.json'),
        cause='r1: extern/static declarations and prototype extraction. r2: snapshot preceded fixture-only prepared-header changes at12/16/20/24; real writes all>=48.',
        correction='r3 captures checkpoint immediately before the selected real phase. Allowed write spans, exact expected bytes and product functions unchanged.',
        product_semantic_failure=False,product_source_revisions=0))
    P.write(OUT/'receipt.json',dict(status='HOST PATH COMMISSION COMPLETE; BOUNDED C PASS; TRANSPORT AND WHOLE-PRODUCT GATES OPEN',
        driver=P.bind(Path(__file__)),execution_head='9013c3fc',source_authority=authority,compiler_authority=P.bind(cp),compiler_inputs=roots,verified_compiler_roots=74,
        predecessor=P.bind(PREVIOUS.SEAL),candidate=P.bind(F.OUT/'binding.json'),capacity=P.bind(ROOT/'build/set-b-front-span-capacity-r1/receipt.json'),
        owner_table=P.bind(OUT/'owner-table.json'),source_witnesses=P.bind(OUT/'source-witnesses.json'),C_proofs=proofs,qualified_C_rows=385,
        host_dependencies=dependencies,host_dependency_external=list({x['path']:x for x in external}.values()),harness_attribution=P.bind(OUT/'harness-attribution.json'),
        this_commission=dict(native_object_compiles=0,native_dependency_calls=0,host_c_compile_attempts=5,host_c_compile_successes=4,host_c_links=4,
            host_dependency_calls=3,product_builds=0,product_links=0,seeds=0,finals=0,guest_runs=0,device_contacts=0),
        consumed=dict(seeds=5,finals=0,product_links=5),authorized_ceiling=dict(seeds=5,finals=1,product_links=5),product_admitted=False,
        unchanged_air=dict(phase05b_free=5,ordinary_floor_margin=8,BSS_floor_margin=1,E000_floor_margin=25,capture_floor_margin=48),
        remaining=['Full completion-fence/journal replay transport chain, including ignored stage-zero write returns and code/attic DMA',
            'Raw CPU mapping/I-O/indirect writer mediation outside the tested notification bracket','Real Lisp exact BAD BYTECODE successor; cold/stack/GC and linked identity'],
        limits='Exact extracted functions under host ABI and bounded memory. Inherited linked census, not a new native linking proof. No claim of full raw-I/O, asynchronous DMA completion, VM/Lisp form execution or product admission.',
        next_proposal='Host-only completion-fence and journal-replay attribution on the unchanged span candidate: close when ignored plane-zero submissions become independently verified, connect the actual completion predicate and replay driver to bounded memory, inject partial/stale/readback failures at each real boundary, and preserve exact error identity. Stop on first unexplained accepted partial publication or missing ownership. No new source form or product build/link/Seed/guest/device.'))
    print('COMPLETE:385 qualified C rows;53 inherited edges/44 owners; native0; host5 attempts/4 successes; product0')
if __name__=='__main__':main()
