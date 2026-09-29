"""Read a freshly authored generated closure at its logical paths, including children."""
import builtins
import io
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
import strings_successor_r2_20260928 as S
from strings_scratch_20260928 import scratch

@contextmanager
def current_generated(root):
    import v2_workbench_codemod as C
    import evidence_era as E
    target=root/'authored-generated'
    C.generate(C.DEFAULT_CLOSURE,target)
    # The codemod encodes its physical output directory in suite references.
    # Keep logical provenance paths; opened() below supplies the fresh bytes.
    for suite in (target/'suites').glob('*.json'):
        text=suite.read_text()
        text=text.replace(str(target),str(C.DEFAULT_OUTPUT))
        text=text.replace(str(target.relative_to(S.ROOT)),str(C.DEFAULT_OUTPUT.relative_to(S.ROOT)))
        suite.write_text(text)
    def opened(original,file,mode='r',*args,**kwargs):
        if isinstance(file,(str,Path)) and mode in ('r','rb','rt') and E.host_source_commit() is None:
            p=Path(file).resolve()
            if p.is_relative_to(C.DEFAULT_OUTPUT):
                relative=p.relative_to(C.DEFAULT_OUTPUT)
                if relative.parts[0] in ('suites','sources'):
                    file=target/relative
        return original(file,mode,*args,**kwargs)
    a,b,run=builtins.open,io.open,subprocess.run
    def child(command,*args,**kwargs):
        command=list(command)
        if len(command)>1 and command[1]=='tools/host-lisp/bytecode_p0_stdlib.py':
            command[1]='tools/host-lisp/strings_generated_r11_20260929.py'
        return run(command,*args,**kwargs)
    with patch.object(builtins,'open',lambda *a_,**kw:opened(a,*a_,**kw)),patch.object(io,'open',lambda *a_,**kw:opened(b,*a_,**kw)),patch.object(subprocess,'run',child):
        yield

if __name__=='__main__':
    import bytecode_p0_stdlib as P
    with scratch() as root, current_generated(root):
        raise SystemExit(P.main())
