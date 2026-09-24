"""Disjoint semantic-stage and GC accounting on both unchanged worlds."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
world = sys.argv[1]
assert world in ('before', 'seed')
source = ROOT/'tools/host-lisp/definition_set_a_emitter_ledger.py'
raw = source.read_text()
raw = raw.replace("emitter-{world}-{{slots}}-r2", "stages-{world}-{{slots}}-r1")
if world == 'seed':
    raw = raw.replace('stages-{world}-{{slots}}-r1', 'stages-{world}-{{slots}}-r2')
raw = raw.replace('build/definition-set-a-emitter-observer-r1/build/bin/xmega65.native',
                  'build/definition-set-a-stage-observer-r1/build/bin/xmega65.native')
needle = "exec(compile(raw, str(source), 'exec'), dict(__name__='__main__', __file__=__file__))"
assert raw.count(needle) == 1
injection = '''
expanded = next(i for i,x in enumerate(entries) if x['name']=='%c2-run-expanded')
source_ordinal = next(i for i,x in enumerate(entries) if x['name']=='%c2-source-form')
listing = manifest.with_name('stdlib-p0.disasm.txt').read_text()
block = listing.split(f'[{expanded}] %c2-run-expanded\\n')[1].split('\\n[')[0]
compile_lit = next(i for i,x in enumerate(entries[expanded]['literals']) if isinstance(x,dict) and x.get('symbol')=='%c2-compile-form')
import re
call = re.search(r'([0-9a-f]{4}) CALL lit='+str(compile_lit)+r' argc=1', block)
assert call
if 'definition-set-a' in str(manifest):
    source_block = listing.split(f'[{source_ordinal}] %c2-source-form\\n')[1].split('\\n[')[0]
    assert '0011 CALL lit=1 argc=1' in source_block and '0032 CALL lit=1 argc=1' in source_block
for key, value in [('INSTALL_PC',truth.symbol('c2_product_install').value),
                   ('APPEND_PC',truth.symbol('c2_append_begin').value),
                   ('ADD_PC',truth.symbol('c2_session_emit_add').value),
                   ('FINAL_PC',truth.symbol('c2_session_emit_finalize').value),
                   ('GC_PC',truth.symbol('gc_collect').value),
                   ('LCC_ORDINAL',ordinal),('EXPANDED_ORDINAL',expanded),
                   ('SOURCE_ORDINAL',source_ordinal),('EXPAND_RESUME',4),
                   ('COMPILE_RESUME',int(call.group(1),16)+3)]:
    os.environ['LISP65_DEF_'+key] = str(value)
'''
replacement = "raw = raw.replace('args = argparse.Namespace(', " + repr(injection) + " + '\\nargs = argparse.Namespace(', 1)\n" + needle
raw = raw.replace(needle, replacement)
exec(compile(raw, str(source), 'exec'), dict(__name__='__main__', __file__=__file__))
