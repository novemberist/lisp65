"""Conservative source-wide alias/reuse inventory for the ownership worksheet."""
from pathlib import Path
import subprocess
import set_b_producer as P

ROOT=P.ROOT
OUT=ROOT/'build/set-b-barrier-owner-r1'
CANDIDATE=ROOT/'build/set-b-barrier-read-r1/candidate'


def main():
    assert not (OUT/'access-addendum.json').exists()
    files=subprocess.check_output(['rg','--files','src','config/set-b-native',
        '-g','*.c','-g','*.h','-g','*.s','-g','*.inc'],cwd=ROOT,text=True).splitlines()
    selected=sorted({CANDIDATE/p if (CANDIDATE/p).is_file() else ROOT/p for p in files})
    pattern=r'lisp65_c2_phase_scratch|c2_phase_scratch_(acquire|release)|c2_phase_owner|\b(RX|JJ|c2aw|c2ew)\b'
    command=['rg','-n',pattern]+[str(p.relative_to(ROOT)) for p in selected]
    result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    output=OUT/'all-source-scratch-aliases.txt';output.write_text(result.stdout)
    touched=sorted({line.split(':',1)[0] for line in result.stdout.splitlines()})
    runtime=(CANDIDATE/'src/c2_product_runtime.c').read_text()
    assert 'c2aw.before = before; c2aw.main_ordinal = main_ordinal;' in runtime
    assert 'c2_stream_context before; uint16_t main;' in runtime
    assert 'w->before = &w->append;' in runtime
    P.write(OUT/'access-addendum.json',dict(driver=P.bind(Path(__file__)),command=command,exit=0,
        source_population=[P.bind(p) for p in selected],matched_files=touched,
        result=P.bind(output),matches=len(result.stdout.splitlines()),
        scope='All c/h/s/inc under src and config/set-b-native, substituting parked candidate copies where present. Conservative textual edges, including inactive code; not a preprocessed call graph.',
        extra_lifetime_obligation='before and main_ordinal may point into returning caller frames. Retaining phase scratch alone cannot preserve those referents. Recovery must reconstruct from validated durable facts (existing journal reconstruction sets before=&append), not resume through expired caller pointers.',
        compiler_calls=0,product_changes=0))
    print('BOUND',len(selected),'source files;',len(touched),'with scratch aliases;',len(result.stdout.splitlines()),'textual edges; caller-pointer obligation recorded')


if __name__=='__main__':main()
