#!/usr/bin/env python3
"""Card 2b source projection from the sealed Renderer, never the parked 2a.

Only materializes sources and a linker fragment. It cannot invoke a compiler,
linker, packer or device. The product adapter owns the one-shot seed budget.
"""
from pathlib import Path
import hashlib
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / 'build/capacity/card2b-r1'
BASE = ROOT / 'build/v2.1/renderer-branch-product-r1/wplto'
SECTION = '.lisp65_rt_card2b_disk'
AUTHORIZATION = 'e0957b82'


def binding(path):
    return dict(path=path.relative_to(ROOT).as_posix(),
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def receipt(name):
    value = json.loads((EVIDENCE/name).read_text())
    for item in value['bindings']:
        path = ROOT/item['path']
        assert binding(path)['sha256'] == item['sha256'], 'stale input: '+str(path)
    return value


def original_inputs():
    result = {}
    for line in (BASE/'resolved-profile.txt').read_text().splitlines():
        if line.startswith('input_sha256='):
            name, digest = line.split('=', 1)[1].rsplit(':', 1)
            assert name not in result
            result[name] = digest
    assert result
    return result


def original(name):
    data = (ROOT/name).read_bytes()
    assert hashlib.sha256(data).hexdigest() == original_inputs()[name], name
    return data.decode()


def checked_replace(text, old, new):
    assert text.count(old) == 1, 'projection anchor drift: '+old
    return text.replace(old, new, 1)


def sources():
    # The accepted probes are input evidence, not an alternate build root.
    # Validate their complete bound population before using a generated body.
    receipt('member-entry-check.json')
    receipt('retention/receipt.json')
    receipt('dispatch/price.json')
    files = {}
    files['src/vm.c'] = (EVIDENCE/'dispatch/vm.c').read_text()
    # The bridge mirrors the existing buffer-service convention: the loader
    # sets ENTRY_NOT_RUN before any fallible work, and the VM ignores result
    # when vm_status is nonzero. No new primitive ID, message or public name.
    assert '(void)vm_runtime_overlay_exec(52,&card2b_disk_frame,&vm_status);' in files['src/vm.c']
    before = original('src/vm.c')
    cases = lambda text: re.findall(r'\bcase\s+(\d+)\s*:', text)
    # A moved case body contains no switch cases; table population unchanged.
    assert cases(before) == cases(files['src/vm.c'])

    io = original('src/io.c')
    attr = '__attribute__((section("'+SECTION+'"))) '
    anchors = (
        'void io_disk_transaction_capture_mount_token(void)',
        '__attribute__((noinline)) unsigned char io_disk_transaction_classify_status(',
        'static __attribute__((noinline)) unsigned char f011_issue_write_guarded(',
        'static unsigned char f011_write_at_guarded(',
        'unsigned char io_disk_write_sector_guarded(',
        'unsigned char io_disk_write_sector(',
    )
    for anchor in anchors:
        io = checked_replace(io, anchor, attr+anchor)
    files['src/io.c'] = io
    asm = original('src/f011_guarded_write.s')
    for name in ('lisp65_f011_mount_token_op', 'lisp65_f011_scratch_buffer'):
        asm = checked_replace(asm, '.section\t.text.'+name+',', '.section\t'+SECTION+',')
    files['src/f011_guarded_write.s'] = asm
    files['src/vm_runtime_overlay.c'] = (EVIDENCE/'retention/vm_runtime_overlay.c').read_text()

    # HEAD contains the 2a nibble-CRC prototype. Reproduce the Renderer leaf,
    # and require its original input SHA rather than trusting a commit label.
    crc = subprocess.check_output(['git', 'show', '7f90c7f6:src/rtov_crc_mem.s'], cwd=ROOT)
    assert hashlib.sha256(crc).hexdigest() == original_inputs()['src/rtov_crc_mem.s']
    files['src/rtov_crc_mem.s'] = crc.decode()
    assert not any('LISP65_RTOV_SESSION_RECORD_CACHE' in text for text in files.values())
    return files


def materialize(out, mapping):
    """Overlay this card's exact inputs on the standard producer mapping."""
    generated = out/'generated-product-sources'
    generated.mkdir(parents=True, exist_ok=True)
    result = dict(mapping)
    for root, text in sources().items():
        target = generated/Path(root).name
        target.write_text(text)
        result[(ROOT/root).resolve()] = target
    return result


def linker_fragment():
    projection = receipt('owner-projection.json')['owner']
    start, end = projection['start'], projection['end']
    payload = projection['payload']['start']
    capacity = projection['payload']['capacity']
    # Separate LMA owner; not another mapped tenant of the F011 MAP window.
    # The payload's physical source is its LOADADDR, not the carrier base.
    return f'''\n/* Card 2b: complete carrier, including its alignment prefix. */
MEMORY {{
    card2b_carrier (rw) : ORIGIN = 0x{start:x}, LENGTH = {end-start}
    card2b_window (rwx) : ORIGIN = 0x{projection['window_vma']:x}, LENGTH = {capacity}
}}
SECTIONS {{
    .noinit.card2b_carrier_prefix 0x{start:x} (NOLOAD) : {{
        __card2b_carrier_start = .;
        . += {projection['prefix']['bytes']};
        __card2b_payload_load_start = .;
    }} >card2b_carrier
    OVERLAY __lisp65_workbench_runtime_overlay_vma : NOCROSSREFS AT(0x{payload:x}) {{
        {SECTION} {{
            KEEP(*({SECTION}))
            KEEP(*(.rodata.card2b_disk_entry .rodata.card2b_disk_body))
        }}
    }} >card2b_window
    .noinit.card2b_carrier_tail (LOADADDR({SECTION}) + SIZEOF({SECTION})) (NOLOAD) : {{
        . += ORIGIN(card2b_carrier) + LENGTH(card2b_carrier)
             - LOADADDR({SECTION}) - SIZEOF({SECTION});
    }} >card2b_carrier
}} INSERT BEFORE .rodata;
__card2b_carrier_end = 0x{end:x};
__card2b_payload_load_end = LOADADDR({SECTION}) + SIZEOF({SECTION});
__lisp65_rt_card2b_disk_start = ADDR({SECTION});
__lisp65_rt_card2b_disk_end = ADDR({SECTION}) + SIZEOF({SECTION});
__lisp65_rt_card2b_disk_entry = card2b_disk_entry;
ASSERT(LOADADDR({SECTION}) == __card2b_payload_load_start,
       "Card 2b payload LOADADDR differs from reserved prefix end");
ASSERT(ADDR(.noinit.card2b_carrier_tail) + SIZEOF(.noinit.card2b_carrier_tail)
       == __card2b_carrier_end, "Card 2b tail reservation does not close its owner");
ASSERT((LOADADDR({SECTION}) & 255) == 0,
       "Card 2b L65R source is not page aligned");
ASSERT(SIZEOF({SECTION}) > 0 && SIZEOF({SECTION}) <= {capacity},
       "Card 2b payload exceeds its own carrier");
ASSERT(__lisp65_rt_card2b_disk_end <= __lisp65_workbench_runtime_overlay_limit,
       "Card 2b member exceeds the CPU window");
'''


if __name__ == '__main__':
    out = EVIDENCE/'candidate-projection'
    mapping = materialize(out, {})
    (out/'card2b-owner.ld').write_text(linker_fragment())
    value = dict(status='SOURCE PROJECTION ONLY; NO COMPILER ENTERED',
        authorization=AUTHORIZATION,
        sources=[dict(authored=str(k.relative_to(ROOT)), generated=binding(v))
                 for k, v in sorted(mapping.items())],
        linker=binding(out/'card2b-owner.ld'),
        authority=binding(Path(__file__)),
        accounting=dict(seed_WPLTO=0, final_C_LTO=0, product_links=0))
    (out/'receipt.json').write_text(json.dumps(value, indent=2)+'\n')
    print(json.dumps(value, indent=2))
