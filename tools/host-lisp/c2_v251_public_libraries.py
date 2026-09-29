#!/usr/bin/env python3
"""Compile the default Comfort library against its public suite authority."""
import argparse
import json
import subprocess
import sys
from pathlib import Path
import c2_v251_public_native as N
def build(output):
    N.check();N.require(not output.exists(),'library output must be fresh');output.mkdir(parents=True)
    prefix=output/'repl-comfort'
    subprocess.run([sys.executable,'-B','tools/host-lisp/bytecode_p0_stdlib.py','--emit-artifacts',str(prefix),'--artifact-role','disk-lib','--base-addr','0x000000','config/comfort-default-plane/libraries/repl-comfort-suite.json'],cwd=N.ROOT,check=True)
    v=json.loads(prefix.with_suffix('.manifest.json').read_text())
    N.require(v['code_bytes']==960 and v['private_inline_functions']==['%comfort-state-hi','%comfort-state-lo'],'Comfort library geometry drift')
    print('PASS: Comfort default library 960 Bank-2 bytes')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);build(p.parse_args().output)
