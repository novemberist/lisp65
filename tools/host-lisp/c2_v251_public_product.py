#!/usr/bin/env python3
"""Comfort Final qualification and independent public-source reproduction.

Preflight checks the retained authority; build requires a fresh exported tree
and delegates to the explicit public replay/media successors.
"""
import argparse
import json
import c2_v251_public_native as N
ROOT=N.ROOT
OUT=ROOT/'build/public-v2.5.1'
def load(p):return json.loads(p.read_text())
def preflight():
    result=N.selftest()
    import c2_v251_public_plane as plane
    result['plane']=plane.check()
    import c2_v251_public_includes as I
    result['includes']=I.check()
    a=load(N.AUTHORITY)
    for row in a['raw_pair'].values():N.bound(row)
    N.bound(a['seal']);N.bound(a['final_report'])
    import c2_v251_public_media as M
    result['media']=M.check()
    result['status']='PASS: BACKSPACE FINAL IDENTITY AND PUBLIC SOURCE AUTHORITY'
    return result
def build():
    import c2_v251_public_reproduction as R
    return R.build()
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['preflight','check','build']);a=p.parse_args()
    if a.mode=='check' and (OUT/'reproduction.json').exists():
        import c2_v251_public_reproduction as R
        result=R.check()
    else:result=build() if a.mode=='build' else preflight()
    print(json.dumps(result,indent=2))
