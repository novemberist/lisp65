"""One isolated fused05b/resident-max form under the d31cb37a contract."""
from pathlib import Path
import difflib
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import set_b_front_relocation_20260926 as R

ROOT=P.ROOT
OUT=ROOT/'build/set-b-front-fused-r1'
once=R.once
vm=R.vm
HELPER='''/* Validated row only; pending state is not a published certificate. */
__attribute__((noinline)) void c2_front_pending_max(c2_stream_context *c,
                                                   uint16_t end) {
    if (end > c->entry_cursor) c->entry_cursor = end;
}
'''

def runtime(s):
    s=R.runtime(s)
    assert s.endswith('\n#endif\n')
    return s[:-len('\n#endif\n')]+'\n'+HELPER+'\n#endif\n'

def decoder(s):
    def phase(f):
        f=once(f,'                || r24(raw + 18) > 0xffffUL\n'
            '                || at > 0xffffUL - r24(raw + 18)',
            '                || !length || r24(raw + 18) > LISP65_C2_BANK2_CODE_LIMIT\n'
            '                || at + length > LISP65_C2_BANK2_CODE_LIMIT - r24(raw + 18)')
        f=once(f,'''                return fail(c, C2_STREAM_ERR_ENTRY);
        }
    }
    c->reserved = 0u; c->phase = 6u;''','''                return fail(c, C2_STREAM_ERR_ENTRY);
            c2_front_pending_max(c, (uint16_t)(r16(de + 2) + length));
        }
    }
    c->reserved = 0u; c->phase = 6u;''')
        return f
    s=R.I.edit_function(s,'c2_stream_phase_05b',phase)
    return once(s,'#if C2_STREAM_PHASE == 20\n',
        '#if C2_STREAM_PHASE == 20\n'
        'extern void c2_front_pending_max(c2_stream_context *, uint16_t);\n')

def main():
    authority=S.require_auth();OUT.mkdir(exist_ok=False)
    names=['lib/stdlib-require.lisp','src/c2_product_runtime.c','src/vm.c',
        'src/optional/set_b_retire_reset.c','src/optional/set_b_retire_control.c',
        'config/set-b-native/includes/c2-stream-decoder.c']
    old={n:(ROOT/n).read_text() for n in names}
    new={n:(R.I.OLD.PREV/n).read_text() if (R.I.OLD.PREV/n).exists() else old[n] for n in names}
    new[names[1]]=runtime(new[names[1]]);new[names[2]]=vm(new[names[2]])
    new[names[-1]]=decoder(old[names[-1]])
    for name,fn in ((names[1],'c2_append_entries_phase'),(names[-1],'c2_stream_phase_05a')):
        assert R.I.function(new[name],fn)==R.I.function(old[name],fn)
    for n,s in new.items():
        p=OUT/'candidate'/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s)
    patch=OUT/'authored.patch'
    patch.write_text(''.join(''.join(difflib.unified_diff(old[n].splitlines(True),new[n].splitlines(True),fromfile='a/'+n,tofile='b/'+n)) for n in names))
    P.write(OUT/'binding.json',dict(status='ISOLATED FUSED05b FORM; OBJECT GATES BEFORE C EXECUTION',
        driver=P.bind(Path(__file__)),source_authority=authority,execution_head='d31cb37a',
        predecessor=P.bind(ROOT/'build/set-b-front-order-r1/receipt.json'),patch=P.bind(patch),
        candidate=[P.bind(OUT/'candidate'/n) for n in names],
        caps=dict(ordinary_helper_and_drift=58,ordinary_total=784,phase04=15,phase05b=137,region0=65205),
        unchanged_function_bodies=['c2_append_entries_phase','c2_stream_phase_05a'],
        limits='No C fault/lifecycle execution before capacity passes; no product admission.',
        product_builds=0,product_links=0,seeds=0,device_contacts=0))
    print('PARKED fused05b plus resident pending-max; exact Entries/05a restored')

if __name__=='__main__':main()
