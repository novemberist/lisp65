"""Price ordinary constant data against its next fixed owner, never text slack."""
def measure(truth):
    names = truth.sections_by_name
    if '.lisp65_runtime_overlay_verifier_bindings' not in names:
        return {'selected': False, 'reason': 'not the fixed full-map verifier layout'}
    data = truth.section('.rodata')
    next_owner = truth.section('.lisp65_runtime_overlay_verifier_bindings')
    if data.address > next_owner.address:
        raise ValueError('ordinary rodata starts beyond its fixed next owner')
    free = next_owner.address - data.address - data.bytes
    if free < 0:
        raise ValueError(f'ordinary rodata overlaps verifier owner by {-free} bytes')
    return dict(selected=True, start=data.address, bytes=data.bytes,
                end=data.address+data.bytes, limit=next_owner.address,
                free_bytes=free, floor_bytes=0,
                next_owner=next_owner.name)


def selftest():
    from types import SimpleNamespace as N
    class Truth:
        def __init__(self, size):
            self.sections_by_name = {
                '.rodata': N(name='.rodata',address=0xb61d,bytes=size),
                '.lisp65_runtime_overlay_verifier_bindings': N(
                    name='.lisp65_runtime_overlay_verifier_bindings',address=0xb98c,bytes=40)}
        def section(self, name): return self.sections_by_name[name]
    assert measure(Truth(879))['free_bytes'] == 0
    assert measure(Truth(878))['free_bytes'] == 1
    for size in (880, 897):
        try: measure(Truth(size))
        except ValueError: pass
        else: raise AssertionError('overlap accepted')
    print('PASS: ordinary rodata owner; exact fit, one free byte, +1 and failed Seed +18 rejected')


if __name__ == '__main__':
    selftest()
