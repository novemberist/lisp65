"""Materialize and pack the native-diet Seed measurement medium, without Runtime builds.

The already committed producer is loaded without its command-line entry;
its original bytes (and Seed provenance) are not edited for this adapter.
Derived from the Set-A adapter: the five packages are exactly Set-A's
(same plane, same admitted defstruct image); only the Runtime roles come
from the native-diet Seed ELF, and the packer rebuilds the current stager.
"""
from pathlib import Path
import builtins
import inspect
import json
import sys

import native_diet_producer as DRIVER
import capacity_disk_window_media as M
from elf_truth import ElfTruth

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT/'build/native-diet-r4'


def producer():
    captured = []
    def load_only(code, scope):
        assert scope['__name__'] == '__main__'
        scope['__name__'] = 'native_diet_media_configuration'
        builtins.exec(code, scope)
        captured.append(scope)
    argv = sys.argv
    try:
        sys.argv = [str(Path(DRIVER.__file__)), 'command-probe']
        DRIVER.exec = load_only
        DRIVER.main()
    finally:
        sys.argv = argv
        del DRIVER.exec
    assert len(captured) == 1
    return captured[0]['g']


g = producer()
M.OUT = ROOT/'build/native-diet-seed-medium-r5'
M.FINAL = M.OUT/'materialized'
M.PLANE = g['PLANE']
configured = False


def setup():
    global configured
    if configured:
        return
    g['configure']()
    def forbidden(*args, **kwargs):
        raise RuntimeError('Runtime compilation/link forbidden during Seed materialization')
    p = g['P']
    p.compile_link = forbidden
    p.PRODUCT_ARTIFACTS_MANIFEST = M.PLANE/'product/substitution-artifacts.json'
    p.INITIAL_C2D = M.PLANE/'product/initial.c2d-v3.bin'
    p.PRODUCT_SHELF = M.PLANE/'product/product-shelf-v4-direct.bin'
    p.overlay_pack_family, p._validate_family_artifact = M.pack_family, M.validate
    p._family_identity_negative_selftest = M.negative
    truth = ElfTruth.read(g['BUILD']/'wplto/resident-island-seed.prg.elf',
                          llvm_readobj=p.TOOLCHAIN/'llvm-readobj')
    p.VERIFIER_BINDING_BASE = p.LINK60_VERIFIER_BINDING_BASE = truth.section(p.VERIFIER_BINDING_SECTION).address
    configured = True


M.setup = setup


def libraries():
    """Keep four packages exact; substitute only the admitted defstruct image."""
    raw = (ROOT/'build/init-echo-r1/library-media.py').read_text()
    raw = raw.replace('build/init-echo-product-r1-preflight/setup-owned/static-plane/narrow-static',
                      str(g['PLANE'].relative_to(ROOT)))
    # Adapt its inner source transformation before evaluation. The original
    # manifest and measured predecessor stay checked for all five packages.
    needle = "exec(compile(raw,str(source),'exec'),globals())"
    assert raw.count(needle) == 1
    addition = '''
old="            row,data=LIB.measured(spec,(1,1),build_id)"
new="""            if name=='defstruct':
                admitted=json.loads((ROOT/'build/definition-group-composition-r6/receipt.json').read_text())['package']['candidate']
                candidate=ROOT/admitted['path']
                assert bind(candidate)['sha256']==admitted['sha256']
                spec=(*spec[:3],candidate,spec[4])
                specs[specs.index(next(s for s in specs if s[0]==name))]=spec
            row,data=LIB.measured(spec,(1,1),build_id)"""
assert raw.count(old)==1
raw=raw.replace(old,new)
'''
    raw = raw.replace(needle, addition+'\n'+needle)
    # The delivery stager derivation predates the accepted CRC32 stager card.
    # Apply exactly that card's one-function delta and require the result to
    # be byteidentical to its accepted generated source (build/stager-crc32-r2).
    old_write = "  generated.write_text(base['source'])"
    assert raw.count(old_write) == 1
    raw = raw.replace(old_write, """  live=(ROOT/'scripts/r3-cold-stager-main.c').read_text()
  source=base['source'].replace(D.c_function(base['source'],'crc32_step'),D.c_function(live,'crc32_step'))
  assert source==(ROOT/'build/stager-crc32-r2/stager-main.c').read_text(),'stager is not the accepted CRC32 stager source'
  generated.write_text(source)""")
    scope = dict(__name__='native_diet_libraries', __file__=str(HERE/'library-media.py'))
    builtins.exec(compile(raw, str(ROOT/'build/init-echo-r1/library-media.py'), 'exec'), scope)
    scope['install']()


def pack():
    libraries()
    setup()
    import hardware_sp_seed_media as BASE
    record = json.loads((M.OUT/'materialization.json').read_text())
    record['materialized_prg'] = record['prg']
    M.write(M.OUT/'materialization.json', record)
    BASE.OUT, BASE.FINAL, BASE.PLANE, BASE.SEED = M.OUT, M.FINAL, M.PLANE, g['BUILD']
    BASE.setup, BASE.bind = setup, M.bind
    BASE.authority = lambda: dict(commit='4e3bdafe', role='native-diet-fourth-seed',
        measurement_only=True, product_builds=0, host_images=1, device_contacts=0)
    original = BASE.COMPOSE.mapped_section_rows
    def composed(truth, names):
        rows = original(truth, names)
        data, source, _, _, owner = M.payload(M.FINAL/'lisp65-c2-substitution-linked.prg.elf')
        assert all(source+len(data)<=start or source>=start+len(raw) for start,raw,_ in rows)
        return sorted(rows+[(source, data, g['R'].B.D.SECTION)])
    BASE.COMPOSE.mapped_section_rows = composed
    code = inspect.getsource(BASE.pack)
    assert code.count('assert len(prefix)==47795') == 1
    code = code.replace('assert len(prefix)==47795', 'assert len(prefix)==EXPECTED_EXTENT')
    namespace = dict(BASE.__dict__)
    emission = json.loads((HERE/'plane.json').read_text())
    assert g['R'].C.bind(g['PLANE']/'v6-semantics/bank2-static-code.bin')['sha256'] == emission['bank2']['sha256']
    namespace['EXPECTED_EXTENT'] = emission['plane_bytes']
    builtins.exec(compile(code, str(Path(BASE.__file__)), 'exec'), namespace)
    namespace['pack']()


if __name__ == '__main__':
    if sys.argv[1:] == ['materialize']:
        setup(); M.materialize()
    elif sys.argv[1:] == ['resume']:
        setup(); M.resume()
    elif sys.argv[1:] == ['pack']:
        pack()
    else:
        raise SystemExit('materialize | resume | pack')
