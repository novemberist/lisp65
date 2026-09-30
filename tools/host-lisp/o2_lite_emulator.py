#!/usr/bin/env python3
"""Run existing reviewer instruments with an admitted Final world, in memory.

Seed selectors and frozen historical probe sources stay unchanged on disk.
"""
import json
from pathlib import Path
import sys
from o2_lite_gc_stress import ROOT, FINAL, bind, world


def main():
    medium,elf=world('lite')  # fail before starting any emulator
    import comfort_default_rows as D
    import backspace_rows as B
    D.WORLD['lite']=(medium,bind(medium)['sha256'],elf)
    D.ELF_SHA[elf]=bind(elf)['sha256']
    B.WORLD['lite']=D.WORLD['lite'][:2]
    mode=sys.argv[1];args=sys.argv[2:]
    if mode=='rows': fn=D.main
    elif mode=='backspace':fn=B.main
    elif mode=='lanes':
        import comfort_default_lanes as L
        fn=L.main
    elif mode=='return':
        source=ROOT/'build/lite-throughput-probe-r1/probe4.py'
        scope=dict(__name__='o2_final_return',__file__=str(source))
        exec(compile(source.read_text(),str(source),'exec'),scope)
        scope['WORLD']['lite']=D.WORLD['lite'][:2]
        scope['WORLD']['strings']=D.WORLD['strings'][:2]
        fn=scope['main']
    else:raise ValueError('expected rows, backspace, lanes or return')
    sys.argv=[sys.argv[0],*args]
    print(json.dumps(dict(final_identity=bind(ROOT/FINAL/'final-identity.json'),
                          medium=bind(medium),ELF=bind(elf),instrument=mode),indent=2),flush=True)
    fn()


if __name__=='__main__':main()
