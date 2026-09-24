"""Count native allocations by the consumed VM buffer owner, existing worlds."""
from pathlib import Path
import os, sys
from elf_truth import ElfTruth

ROOT=Path(__file__).resolve().parents[2]
world=sys.argv[1];assert world in ('before','seed')
elf=ROOT/('build/definition-set-a-product-r2/wplto/resident-island-seed.prg.elf' if world=='seed' else
          'build/transient-retirement-product-r1/wplto/lisp65-c2-substitution-linked.prg.elf')
t=ElfTruth.read(elf,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj')
os.environ['LISP65_DEF_ALLOC_PC']=str(t.symbol('alloc').value)
source=ROOT/'tools/host-lisp/definition_set_a_stage_ledger.py'
raw=source.read_text().replace('build/definition-set-a-stage-observer-r1/', 'build/definition-set-a-allocation-observer-r1/')
needle="exec(compile(raw, str(source), 'exec'), dict(__name__='__main__', __file__=__file__))"
pos=raw.rfind(needle)
patch="raw = raw.replace('build/definition-set-a-seed-medium-r1', 'build/definition-set-a-seed-medium-r2')\n"
patch+="raw = raw.replace('stages-{world}-{{slots}}-r1', 'auth-alloc-{world}-{{slots}}-r1').replace('stages-{world}-{{slots}}-r2', 'auth-alloc-{world}-{{slots}}-r1')\n"
raw=raw[:pos]+patch+raw[pos:]
exec(compile(raw,str(source),'exec'),dict(__name__='__main__',__file__=__file__))
