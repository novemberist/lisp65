"""One isolated phase04/05a placement under the 775c4083 owner caps."""
from pathlib import Path
import difflib
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import set_b_front_integration_r2_20260926 as I
ROOT=P.ROOT
OUT=ROOT/'build/set-b-front-relocation-r1'
once=I.OLD.once
vm=I.vm

def runtime(s):
    s=I.runtime(s)
    s=once(s,'    w->append.entry_cursor = c2_u16(w->record + 12);\n','')
    def guard(f):
        return once(f,'''    return (uint8_t)(base <= LISP65_C2_SESSION_BYTES
        && c2aw.length <= LISP65_C2_SESSION_BYTES - base);''','''    if (base > LISP65_C2_SESSION_BYTES
        || c2aw.length > LISP65_C2_SESSION_BYTES - base) return 0;
    /* The guard proved c == &c2aw.append; the context copy has finished. */
    c2aw.append.entry_cursor = c2_u16(c2aw.record + 12);
    return 1;''')
    return I.edit_function(s,'c2_append_source_domain_guard',guard)

def decoder(s):
    def phase(f):
        f=once(f,'        ec = r16(h + 10); lc = r16(h + 12); eo = r16(h + 14);',
            '''        ec = r16(h + 10); lc = r16(h + 12); eo = r16(h + 14);
        /* Header fields are captured; reuse its dead prefix for Bank-2 base.
         * This is provisional until unchanged phase05b binds every row. */
        if (!c2_stream_c2d_read((uint16_t)(c->images_offset
                + image * 32u + 18u), h, 3u))
            return fail(c, C2_STREAM_ERR_IO);''')
        return once(f,'''                return fail(c, C2_STREAM_ERR_ENTRY);
        }
    }
    c->reserved = 0x5au;''','''                return fail(c, C2_STREAM_ERR_ENTRY);
            at += r24(h) + length;
            if (at > LISP65_C2_BANK2_CODE_LIMIT)
                return fail(c, C2_STREAM_ERR_ENTRY);
            if (at > c->entry_cursor) c->entry_cursor = (uint16_t)at;
        }
    }
    c->reserved = 0x5au;''')
    return I.edit_function(s,'c2_stream_phase_05a',phase)

def main():
    authority=S.require_auth();OUT.mkdir(exist_ok=False)
    names=['lib/stdlib-require.lisp','src/c2_product_runtime.c','src/vm.c',
        'src/optional/set_b_retire_reset.c','src/optional/set_b_retire_control.c',
        'config/set-b-native/includes/c2-stream-decoder.c']
    old={n:(ROOT/n).read_text() for n in names}
    new={n:(I.OLD.PREV/n).read_text() if (I.OLD.PREV/n).exists() else old[n] for n in names}
    new[names[1]]=runtime(new[names[1]]);new[names[2]]=vm(new[names[2]])
    new[names[-1]]=decoder(old[names[-1]])
    assert I.function(new[names[1]],'c2_append_entries_phase')==I.function(old[names[1]],'c2_append_entries_phase')
    assert I.function(new[names[-1]],'c2_stream_phase_05b')==I.function(old[names[-1]],'c2_stream_phase_05b')
    for n,s in new.items():
        p=OUT/'candidate'/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s)
    patch=OUT/'authored.patch';patch.write_text(''.join(''.join(difflib.unified_diff(old[n].splitlines(True),new[n].splitlines(True),fromfile='a/'+n,tofile='b/'+n)) for n in names))
    P.write(OUT/'binding.json',dict(status='ISOLATED RELOCATION FORM; PRICE BEFORE SEMANTIC QUALIFICATION',
        driver=P.bind(Path(__file__)),source_authority=authority,execution_head='775c4083',
        predecessor=P.bind(ROOT/'build/set-b-front-placement-r1/receipt.json'),patch=P.bind(patch),
        candidate=[P.bind(OUT/'candidate'/n) for n in names],
        caps=dict(phase04=96,phase05a=352,region0=65536),
        unchanged_function_bodies=['c2_append_entries_phase','c2_stream_phase_05b'],
        limits='New error/read/lifecycle qualification remains open. No product admission.',
        product_builds=0,product_links=0,seeds=0,device_contacts=0))
    print('PARKED phase04/05a form; exact Entries/05b source restored')

if __name__=='__main__':main()
