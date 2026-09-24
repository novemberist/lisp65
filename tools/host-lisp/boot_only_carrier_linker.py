"""Card-local linker derivation; no resident or stack owner is enlarged."""
FRAGMENT = '''
/* Boot-only PRG carrier: authenticated file bytes, then runtime-stack lifetime.
 * Keep its load image separate from both shared-window and resident data LMAs.
 */
SECTIONS {
    .lisp65_boot_carrier ALIGN(MAX(__lisp65_workbench_overlay_end,
                                 __lisp65_boot_bank3_stage_end), 2) :
        AT(ALIGN(LOADADDR(.lisp65_resident_island) +
                 SIZEOF(.lisp65_resident_island), 2)) {
        __lisp65_boot_carrier_start = .;
        KEEP(*(.lisp65_boot_carrier))
        __lisp65_boot_carrier_end = .;
    } >ram
} INSERT AFTER .lisp65_resident_island;
ASSERT(SIZEOF(.lisp65_boot_carrier) > 0 &&
       SIZEOF(.lisp65_boot_carrier) <= 704,
       "boot-only carrier exceeds admitted cap");
ASSERT(__lisp65_workbench_required_boot_stack == 512,
       "boot-only carrier cannot change boot-stack reservation");
ASSERT(__lisp65_boot_carrier_end <= __lisp65_workbench_boot_slice_limit,
       "boot-only carrier overlaps boot stack");
ASSERT(__lisp65_boot_carrier_start >= __lisp65_workbench_runtime_overlay_limit,
       "boot-only carrier overlaps runtime window");
ASSERT(vm_install_staged_boot_overlay >= __lisp65_boot_carrier_start &&
       vm_install_staged_boot_overlay < __lisp65_boot_carrier_end &&
       vm_runtime_overlay_install_island >= __lisp65_boot_carrier_start &&
       vm_runtime_overlay_install_island < __lisp65_boot_carrier_end,
       "boot-only installer escaped carrier");
'''


def transform(source):
    if '.lisp65_boot_carrier' in source:
        raise ValueError('carrier already bound')
    for anchor in ('__lisp65_workbench_resident_file_end = __data_load_start + __data_size;',
                   '__lisp65_workbench_boot_slice_limit =',
                   '.lisp65_resident_island 0x1800 : AT(__lisp65_resident_island_seed_lma)'):
        if source.count(anchor) != 1:
            raise ValueError('predecessor linker contract drift: ' + anchor)
    return source + FRAGMENT


def selftest():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    source = (root/'build/ov-crc16-product-r1/wplto/c2-substitution.ld').read_text()
    candidate = transform(source)
    assert candidate[:len(source)] == source
    for mutant in (candidate,source.replace('__data_size;', '__data_size + 1;'),
                   source.replace('__lisp65_workbench_boot_slice_limit =','missing =')):
        try:
            transform(mutant)
        except ValueError:
            pass
        else:
            raise AssertionError('linker mutation escaped')
    print('boot-only-carrier-linker: PASS 3 derivation controls; not a product link')


if __name__ == '__main__':
    selftest()
