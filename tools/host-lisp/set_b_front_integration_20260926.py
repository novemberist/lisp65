"""Park lifecycle/decoder/raw-write integration in an isolated source tree."""
from pathlib import Path
import difflib
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import set_b_shared_front_20260926 as EXTRACT
import set_b_shared_front_r2_20260926 as K

ROOT=P.ROOT
OUT=ROOT/'build/set-b-front-integration-r1'
PREV=ROOT/'build/set-b-shared-front-native-r2/candidate'
DECL='''/* Parked front-certificate lifecycle contract. No new context storage. */
void c2_front_boot_reset(void);
uint8_t c2_front_begin(void);
void c2_front_abort(void);
uint8_t c2_front_publish(uint16_t);
'''

def once(s,a,b):
    assert s.count(a)==1,(a[:100],s.count(a));return s.replace(a,b)

def edit_function(s,name,edit):
    old=EXTRACT.function(s,name);return once(s,old,edit(old))

def runtime(s):
    assert K.HELPER in s
    s=once(s,'uint8_t c2_product_boot(void) {',DECL+'\nuint8_t c2_product_boot(void) {')
    def boot(f):
        f=once(f,'    c2_ready = 0; c2_committed_roots',
            '    (void)c2_front_begin();\n    c2_ready = 0; c2_committed_roots')
        return once(f,'    c2_ready = 1;','    c2_ready = 1;\n    (void)c2_front_publish(c2_runtime.entry_cursor);')
    s=edit_function(s,'c2_product_boot',boot)
    s=edit_function(s,'c2_product_prepare_boot',lambda f:once(f,'    c2_ready = 0;',
        '    c2_front_boot_reset();\n    c2_ready = 0;'))
    # Both persistent and transient appends already scan the old low prefix.
    s=edit_function(s,'c2_append_entries_phase',lambda f:once(f,'    w->append = c2_runtime;',
        '    w->append = c2_runtime;\n    w->append.entry_cursor = c2_u16(w->record + 12);'))
    # The decoder cursor is not an undo record after recovery reconstruction.
    s=once(s,'        w->append.entry_cursor = c2_runtime.entry_cursor;',
        '        w->append.entry_cursor = 0u; /* Invalid until a new complete scan. */')
    # Select the sliced definition, not the historical unsliced implementation.
    start=s.index('static C2_KERNAL_RESIDENT uint8_t c2_append_begin(uint16_t length,',
                  s.index('uint8_t c2_append_entries_phase'))
    head=s[:start];tail=s[start:]
    def begin(f):
        f=once(f,'    c2aw.before = before;',
            '    if (!c2_front_begin()) {\n        (void)c2_phase_scratch_release(LISP65_C2_PHASE_OWNER_APPEND);\n        return 0;\n    }\n    c2aw.before = before;')
        f=once(f,'    return c2_phase_scratch_release(LISP65_C2_PHASE_OWNER_APPEND);',
            '    if (transient) c2_runtime.entry_cursor = c2_u16(c2aw.record + 12);\n    return c2_phase_scratch_release(LISP65_C2_PHASE_OWNER_APPEND);')
        return once(f,'v5_reject:\n    {','v5_reject:\n    {\n        c2_front_abort();')
    tail=edit_function(tail,'c2_append_begin',begin);s=head+tail
    s=edit_function(s,'c2_append_rollback',lambda f:once(f,'    uint8_t ok;',
        '    uint8_t ok;\n    c2_front_abort();'))
    # Interrupt cleanup has conditional signatures; put the hook in the common body.
    s=once(s,'    if (vm_runtime_overlay_abort_cleanup() != VM_RUNTIME_OVERLAY_OK) {',
        '    c2_front_abort();\n    if (vm_runtime_overlay_abort_cleanup() != VM_RUNTIME_OVERLAY_OK) {')
    s=edit_function(s,'c2_product_abort_recover',lambda f:once(f,'uint8_t c2_product_abort_recover(void) {',
        'uint8_t c2_product_abort_recover(void) {\n    c2_front_abort();'))
    def staged(f):
        f=once(f,'    if (vm_runtime_overlay_transaction_end() != VM_RUNTIME_OVERLAY_OK) return 0;',
            '    if (vm_runtime_overlay_transaction_end() != VM_RUNTIME_OVERLAY_OK) { c2_front_abort(); return 0; }')
        return once(f,'    return ok;','    if (ok == C2_APPEND_BEGIN_OK) (void)c2_front_publish(c2_runtime.entry_cursor);\n    else c2_front_abort();\n    return ok;')
    s=edit_function(s,'c2_product_append_staged_result',staged)
    def install(f):
        f=once(f,'    if (emit != C2_EMIT_OK || append_ok != C2_APPEND_BEGIN_OK) {',
            '    if (emit != C2_EMIT_OK || append_ok != C2_APPEND_BEGIN_OK) {\n        c2_front_abort();')
        f=f.replace('vm_status = VM_BADOPCODE; return NIL;',
                    'c2_front_abort(); vm_status = VM_BADOPCODE; return NIL;')
        f=once(f,'        return definition_name != NIL ?',
            '        (void)c2_front_publish(c2_runtime.entry_cursor);\n        return definition_name != NIL ?')
        return once(f,'    C2_INSTALL_TRACE_ENTER_INNER();',
            '    (void)c2_front_publish(c2_runtime.entry_cursor);\n    C2_INSTALL_TRACE_ENTER_INNER();')
    return edit_function(s,'c2_product_install',install)

def decoder(s):
    def phase(f):
        marker='''                return fail(c, C2_STREAM_ERR_ENTRY);
        }
    }
    c->reserved = 0u; c->phase = 6u;'''
        addition='''                return fail(c, C2_STREAM_ERR_ENTRY);
            /* entry_cursor is dead after phase 02; append seeds it from the
             * existing full-prefix scan, boot from phase-02's zero. */
            {
                uint16_t base = r16(de + 2), end;
                if (!length || base > LISP65_C2_BANK2_CODE_LIMIT
                    || length > (uint16_t)(LISP65_C2_BANK2_CODE_LIMIT - base))
                    return fail(c, C2_STREAM_ERR_ENTRY);
                end = (uint16_t)(base + length);
                if (end > c->entry_cursor) c->entry_cursor = end;
            }
        }
    }
    c->reserved = 0u; c->phase = 6u;'''
        return once(f,marker,addition)
    return edit_function(s,'c2_stream_phase_05b',phase)

def vm(s):
    old='        *(volatile unsigned char *)(uintptr_t)address = (unsigned char)FIXVAL(a[2]);'
    new='''        {
            extern void c2_front_raw_write(void);
            c2_front_raw_write();
            *(volatile unsigned char *)(uintptr_t)address = (unsigned char)FIXVAL(a[2]);
            c2_front_raw_write();
        }'''
    return once(s,old,new)

def main():
    authority=S.require_auth();OUT.mkdir(exist_ok=False)
    names=['lib/stdlib-require.lisp','src/c2_product_runtime.c','src/vm.c',
        'src/optional/set_b_retire_reset.c','src/optional/set_b_retire_control.c',
        'config/set-b-native/includes/c2-stream-decoder.c']
    old={n:(ROOT/n).read_text() for n in names}
    new={n:(PREV/n).read_text() if (PREV/n).exists() else old[n] for n in names}
    new[names[1]]=runtime(new[names[1]]);new[names[2]]=vm(new[names[2]])
    new[names[-1]]=decoder(new[names[-1]])
    for name,s in new.items():
        p=OUT/'candidate'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s)
    patch=OUT/'authored.patch';patch.write_text(''.join(''.join(difflib.unified_diff(old[n].splitlines(True),new[n].splitlines(True),fromfile='a/'+n,tofile='b/'+n)) for n in names))
    P.write(OUT/'binding.json',dict(status='PARKED INTEGRATED SOURCE; NOT PRODUCT ADMISSION',driver=P.bind(Path(__file__)),
        authority=authority,execution_head='6fcd8207',patch=P.bind(patch),candidate=[P.bind(OUT/'candidate'/n) for n in names],
        certificate=P.bind(K.OUT/'certificate.inc'),
        protocol='Invalidate at append/rollback/abort; publish after terminal transaction end only. Decoder cursor seeded from independently scanned old low; high transient maximum is discarded. Recovery cursor is never an undo value.',
        raw='Before and after each actual poke store; taint persists until trusted boot. Arbitrary corruption of program/runtime state or external debugger writes is not a closed mediation proof.',
        product_builds=0,product_links=0,seeds=0,device_contacts=0))
    print('PARKED lifecycle/decoder/poke integration; no product sources changed')

if __name__=='__main__':main()
