"""One isolated start/length helper-interface form under09c7c983."""
from pathlib import Path
import difflib
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import set_b_front_relocation_20260926 as R

ROOT=P.ROOT
OUT=ROOT/'build/set-b-front-span-r1'
once=R.once
vm=R.vm
HELPER='/* Caller validated the full row; compute the end here and update only pending bytes. */\n_Static_assert(sizeof(((c2_stream_context *)0)->entry_cursor) == 2,\n               "pending cursor must be two bytes");\n_Static_assert(offsetof(c2_stream_context, entry_cursor) == 28,\n               "bound context cursor layout changed");\n__attribute__((noinline)) void c2_front_pending_max(c2_stream_context *c,\n                                                   uint16_t start, uint16_t length) {\n    const uint16_t end = (uint16_t)(start + length);\n    unsigned char *p = (unsigned char *)c;\n    const unsigned char lo = (unsigned char)end;\n    const unsigned char hi = (unsigned char)(end >> 8);\n    enum { off = offsetof(c2_stream_context, entry_cursor) };\n    if (p[off + 1] < hi || (p[off + 1] == hi && p[off] < lo)) {\n        p[off] = lo;\n        p[off + 1] = hi;\n    }\n}\n'

def runtime(s):
    s=R.runtime(s)
    assert s.endswith('\n#endif\n')
    return s[:-len('\n#endif\n')]+'\n'+HELPER+'\n#endif\n'

def decoder(s):
    def phase(f):
        f=once(f,'            uint32_t at; uint16_t length, first;',
            '            uint16_t at, base, start, length, first;')
        f=once(f,'            at = r24(e); length = r16(e + 3); first = r16(e + 5);',
            '            at = r16(e); length = r16(e + 3); first = r16(e + 5);\n'
            '            base = r16(raw + 18); start = r16(de + 2);')
        f=once(f,'                || r24(raw + 18) > 0xffffUL\n'
            '                || at > 0xffffUL - r24(raw + 18)\n'
            '                || r16(de + 2) != (uint16_t)(r24(raw + 18) + at)',
            '                || raw[20] || e[2] || !length\n'
            '                || base > start || at != (uint16_t)(start - base)\n'
            '                || start > (uint16_t)LISP65_C2_BANK2_CODE_LIMIT\n'
            '                || length > (uint16_t)((uint16_t)LISP65_C2_BANK2_CODE_LIMIT - start)')
        f=once(f,'                return fail(c, C2_STREAM_ERR_ENTRY);\n'
            '        }\n    }\n    c->reserved = 0u; c->phase = 6u;',
            '                return fail(c, C2_STREAM_ERR_ENTRY);\n'
            '            c2_front_pending_max(c, start, length);\n'
            '        }\n    }\n    c->reserved = 0u; c->phase = 6u;')
        return f
    s=R.I.edit_function(s,'c2_stream_phase_05b',phase)
    return once(s,'#if C2_STREAM_PHASE == 20\n',
        '#if C2_STREAM_PHASE == 20\n'
        'extern void c2_front_pending_max(c2_stream_context *, uint16_t, uint16_t);\n')

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
    limb=ROOT/'build/set-b-front-limb-r1/candidate'
    for n in (names[0],names[2],names[3],names[4]):assert new[n]==(limb/n).read_text(),n
    prev=R.I.function((limb/names[-1]).read_text(),'c2_stream_phase_05b')
    current=R.I.function(new[names[-1]],'c2_stream_phase_05b')
    assert current==once(prev,'c2_front_pending_max(c, (uint16_t)(start + length));',
        'c2_front_pending_max(c, start, length);')
    for n,s in new.items():
        p=OUT/'candidate'/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s)
    patch=OUT/'authored.patch'
    patch.write_text(''.join(''.join(difflib.unified_diff(old[n].splitlines(True),new[n].splitlines(True),fromfile='a/'+n,tofile='b/'+n)) for n in names))
    P.write(OUT/'binding.json',dict(status='ISOLATED START/LENGTH HELPER FORM; OBJECT GATES BEFORE C EXECUTION',
        driver=P.bind(Path(__file__)),source_authority=authority,execution_head='09c7c983',
        predecessor=P.bind(ROOT/'build/set-b-front-end-close-r1/receipt.json'),patch=P.bind(patch),
        candidate=[P.bind(OUT/'candidate'/n) for n in names],
        caps=dict(ordinary_helper_and_drift=58,ordinary_total=784,phase04=15,phase05b=137,region0=65205),
        unchanged_function_bodies=['c2_append_entries_phase','c2_stream_phase_05a'],
        limits='No C fault/lifecycle execution before capacity passes; no product admission.',
        product_builds=0,product_links=0,seeds=0,device_contacts=0))
    print('PARKED start/length helper interface; exact limb validation; exact Entries/05a restored')

if __name__=='__main__':main()
