"""One selected storage layout; historical analyses keep their own era.

This module performs no build and writes no files. The storage manifest owns
the new layout; its predecessor is a pinned, unmodified release manifest.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT/'config/storage-owner-manifest.json'
KEYS = {'MAX_SYM', 'NAMEPOOL', 'SYMPOOL_EXT_BANK', 'SYMPOOL_EXT_OFF',
        'SYMVAL_EXT_BANK', 'SYMVAL_EXT_OFF', 'NAMEOFF_EXT_BANK',
        'NAMEOFF_EXT_OFF', 'SYMFN_EXT_BANK', 'SYMFN_EXT_OFF',
        'LISP65_C2_BANK2_CODE_LIMIT'}

def load():
    value = json.loads(MANIFEST.read_text())
    if value['format'] != 'lisp65-storage-owner-v1':
        raise ValueError('unknown storage layout')
    source = value['predecessor_manifest']
    if hashlib.sha256((ROOT/source['path']).read_bytes()).hexdigest() != source['sha256']:
        raise ValueError('storage predecessor manifest drift')
    return value

def values(layout=None):
    m = load() if layout is None else layout
    slots = m['symbol_slots']; pool = m['name_owner']; table = m['table_owner']
    if table['tables'] != ['symval','nameoff','symfn'] or table['bytes_per_slot'] != 2:
        raise ValueError('storage table population drift')
    if slots <= 0 or slots > 4096 or pool['tail_guard'] != 33:
        raise ValueError('symbol index or fixed read tail invalid')
    result = {'MAX_SYM':slots, 'NAMEPOOL':pool['bytes']-pool['tail_guard'],
              'SYMPOOL_EXT_BANK':pool['bank'], 'SYMPOOL_EXT_OFF':pool['offset'],
              'LISP65_C2_BANK2_CODE_LIMIT':m['bank2_code_limit']}
    for i, name in enumerate(table['tables']):
        prefix = name.upper()+'_EXT_'
        result[prefix+'BANK'] = table['bank']
        result[prefix+'OFF'] = table['offset']+i*slots*table['bytes_per_slot']
    if result['SYMFN_EXT_OFF']+slots*2 > 65536-m['floors']['bank5_free']:
        raise ValueError('Bank-5 floor')
    if pool['offset']+pool['bytes'] != 65536:
        raise ValueError('name owner must end at bank boundary')
    return result

def definitions():
    return [f'{name}={value}' for name,value in values().items()]

def replace_definitions(existing):
    """Preserve every non-storage define; remove, never duplicate, old storage values."""
    names = [d.split('=',1)[0] for d in existing]
    if len(names) != len(set(names)):
        raise ValueError('duplicate input definition')
    return [d for d in existing if d.split('=',1)[0] not in KEYS]+definitions()

def stage_limit():
    # The staged C2D prefix is in Bank 5, NOT below the Bank-1 name pool.
    m = load()
    if m['table_owner']['bank'] != 5:
        raise ValueError('staging owner has changed banks')
    return m['table_owner']['offset']

def historical_workbench():
    source = load()['historical_workbench']
    raw = subprocess.check_output(['git','show',source['commit']+':'+source['path']],cwd=ROOT)
    if hashlib.sha256(raw).hexdigest() != source['sha256']:
        raise ValueError('historical workbench provenance drift')
    return raw.decode()

def parse_definitions(text):
    return dict(re.findall(r'(?:-D|["\s])([A-Z][A-Z0-9_]+)=([0-9a-fA-FxXuUlL]+)',text))

def number(value):
    return int(value.rstrip('uUlL'),0)

def historical_values():
    return {k:number(v) for k,v in parse_definitions(historical_workbench()).items()}

def historical_workbench_binding():
    raw = historical_workbench().encode()
    return dict(path=load()['historical_workbench']['path'],bytes=len(raw),
                sha256=hashlib.sha256(raw).hexdigest())

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('action',choices=('defines','stage-limit','json'))
    args = p.parse_args()
    if args.action == 'defines': print(' '.join('-D'+d for d in definitions()))
    elif args.action == 'stage-limit': print(hex(stage_limit()))
    else: print(json.dumps(values(),sort_keys=True))
