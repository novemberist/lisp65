"""Exercise actual wrong-source, dropped-row and stale-generation mutations."""
import builtins
import io
from contextlib import contextmanager
from pathlib import Path
import disk_r7_consumers_20260930 as S
import v2_workbench_codemod_disk_r7_20260930 as C
RECEIPT = 'config/disk-r7-consumer-mutations-receipt-20260930.json'

@contextmanager
def substitute(path, raw):
    original, original_io = builtins.open, io.open
    def opened(opener, file, mode='r', *args, **kwargs):
        if isinstance(file, (str, Path)) and Path(file).resolve() == S.ROOT/path:
            S.require(mode in ('r', 'rt', 'rb'), 'mutation write attempted')
            return io.BytesIO(raw) if 'b' in mode else io.StringIO(raw.decode())
        return opener(file, mode, *args, **kwargs)
    with S.patch.object(builtins, 'open', lambda *a,**k: opened(original,*a,**k)), \
         S.patch.object(io, 'open', lambda *a,**k: opened(original_io,*a,**k)):
        yield

def derive():
    S.source_controls()
    suite = S.json.loads((S.ROOT/S.SUITE).read_bytes())
    suite['cases'].pop()
    source = (S.ROOT/S.SOURCE).read_text().replace(
        '(dotimes (i 30 nil) (%disk-poke (+ base (+ i 2)) 0))',
        '(dotimes (i 32 nil) (%disk-poke (+ base i) 0))')
    mutations=[]
    for name,path,raw in [('wrong disk source',S.SOURCE,source.encode()),
                          ('dropped test row',S.SUITE,S.S.canonical(suite))]:
        with substitute(path,raw):
            try: S.source_controls()
            except ValueError as error:
                S.require('binding drift' in str(error),'unexpected binding-mutation failure')
            else: raise ValueError('mutation survived: '+name)
        mutations.append(name)
    generate=C.generate
    def stale(closure, output):
        result=generate(closure,output)
        path=output/'sources/lib/m65-disk.lisp'
        text=path.read_text(); old=text.replace(
            '(dotimes (i 30 nil) (%disk-poke (+ base (+ i 2)) 0))',
            '(dotimes (i 32 nil) (%disk-poke (+ base i) 0))')
        S.require(text!=old,'stale-source mutation anchor absent')
        path.write_text(old)
        return result
    with S.patch.object(C,'generate',stale):
        try: S.measure()
        except AssertionError as error:
            S.require('disk-r7-dir-fill' in str(error),'unexpected stale-generation failure')
        else: raise ValueError('stale generated source survived')
    mutations.append('stale generated source')
    return dict(mutations_rejected=mutations, source=S.S.bind(S.SOURCE))

if __name__ == '__main__':
    S.finish('disk-r7-consumer-mutations',derive,RECEIPT,None,(__file__,C.__file__,S.RECEIPT))
