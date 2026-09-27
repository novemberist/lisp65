"""Unique-echo output oracle with intervening loader progress lines admitted.

The final result is exact; the echo must be new, and no intervening error
is tolerated. Historical r3 wrongly required the echo immediately adjacent
to the result, excluding the normal LOADING INSPECT... message.
"""
import time
import inspect
from pathlib import Path
import set_b_fifth_functional_r3_20260926 as O
import set_b_producer as P
import dwx_comfort_resume as C
lines=O.lines

def valid(before,after,form,expected):
    echo='LISP65> '+form.upper();ls=lines(after)
    if echo in lines(before) or echo not in ls[:-2] or len(ls)<3:return False
    at=len(ls)-1-ls[::-1].index(echo)
    return (ls[-2]==expected.upper() and C.active(after)=='LISP65>' and
            not any('***' in x for x in ls[at+1:-2]))

src=inspect.getsource(O.submit)
ns=dict(vars(O),valid=valid);exec(compile(src,__file__,'exec'),ns);submit=ns['submit']

def selftest():
    b='LISP65> ';a='LISP65> (REQUIRE "INSPECT")\nLOADING INSPECT...\nT\nLISP65> '
    f='(require "inspect")'
    assert valid(b,a,f,'T') and not valid(a,a,f,'T')
    assert not valid(b,a.replace('\nT\n','\nNIL\n'),f,'T')
    assert not valid(b,a.replace('LOADING INSPECT...','*** ERROR'),f,'T')
    return 3
