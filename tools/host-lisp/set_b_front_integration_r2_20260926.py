"""Correct extraction of source functions with alternate preprocessor braces."""
import inspect
from pathlib import Path
import set_b_producer as P
import set_b_front_integration_20260926 as OLD

ROOT=P.ROOT
OUT=ROOT/'build/set-b-front-integration-r2'

def function(s,name):
    start=s.index(name+'(');start=s.rfind('\n',0,start)+1
    brace=s.index('{',start);end=s.index('\n}\n',brace)+3
    return s[start:end]

def edit_function(s,name,edit):
    old=function(s,name);return OLD.once(s,old,edit(old))

NS=dict(vars(OLD),OUT=OUT,edit_function=edit_function,__file__=__file__)
for name in ('runtime','decoder','main'):
    exec(compile(inspect.getsource(getattr(OLD,name)),__file__+':'+name,'exec'),NS)
runtime=NS['runtime'];decoder=NS['decoder'];vm=OLD.vm

def main():
    d=ROOT/'build/set-b-front-integration-driver-r2';d.mkdir(exist_ok=False)
    p=d/'executed.py';p.write_text('\n'.join(inspect.getsource(getattr(OLD,n)) for n in ('runtime','decoder','main')))
    P.write(d/'binding.json',dict(driver=P.bind(Path(__file__)),parent=P.bind(Path(OLD.__file__)),executed=P.bind(p),
        correction='Use top-level source closing line; alternative preprocessor branches make raw brace counting invalid. r1 failed before candidate write or any compiler call.'))
    NS['main']()

if __name__=='__main__':main()
