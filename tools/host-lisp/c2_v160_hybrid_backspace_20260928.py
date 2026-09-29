"""Replay the v1.6 hybrid in its source era, including actual assembler inputs."""
import hashlib
import types
from unittest.mock import patch
import evidence_era as E
import c2_v160_input_service_hybrid as H
import backspace_successor_20260928 as B
import ide_exit_successor_20260928 as S

ERA='1e06145b'
RECEIPT='config/c2-v160-hybrid-receipt-backspace-20260928.json'
HISTORY={'tools/host-lisp/c2_v160_input_service_hybrid.py': '684906c38dd318718211120dc7f4ad73793e790c40fe8a080651dbeb1c6365e8', 'config/c2-v160-input-service-hybrid-contract.json': '4a7b791195e56ec148974a4a81f66bdcba3f5d757942983d56da41d388a7eb64'}


def derive():
    pricing_path='tools/host-lisp/c2_v160_input_service_time_pricing.py'
    text=E.era_blob(ERA,pricing_path)
    pricing=types.ModuleType('backspace_historical_hybrid_pricing')
    pricing.__file__=H.PRICE.__file__
    exec(compile(text,ERA+':'+pricing_path,'exec'),pricing.__dict__)
    output=B.ROOT/'build/bytecode/dialect-v2/backspace-hybrid-era'
    output.mkdir(parents=True,exist_ok=True)
    native={}
    for path in ('src/optional/c2_kernal_input_consumer.s','src/c2_kernal_window_equates.inc'):
        raw=E.era_blob(ERA,path)
        target=output/path.rsplit('/',1)[1]
        target.write_bytes(raw)
        native[path]=dict(commit=ERA,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
    original_run=H.subprocess.run
    calls=[]
    def run(command,*args,**kwargs):
        if command and str(command[0]).endswith('/mos-mega65-clang'):
            S.require(command[1]=='-Isrc' and command[2:4]==['-c',str(H.CONSUMER)],'historical assembler command drift')
            command=list(command)
            command[1]='-I'+str(output)
            command[3]=str(output/H.CONSUMER.name)
            calls.append('historical-consumer-and-equates')
        return original_run(command,*args,**kwargs)
    extras=tuple(str(p.relative_to(H.ROOT)) for p in (H.EVAL,H.VM,H.HEADER,H.CAPTURE,H.CONSUMER,H.CONTRACT,H.PLAN,H.PRODUCT,pricing.RESIDENT))
    with patch.object(H,'PRICE',pricing),E.generated_workbench_world(ERA) as generated, E.host_source_world(ERA,extras) as reads,patch.object(H.subprocess,'run',run):
        H.selftest()
        value=H.derive()
    S.require(len(calls)==2,'historical native gates not both executed')
    return dict(historical=value,generated_reads=generated,era_reads=reads,native_inputs=native,
                native_assemblies=len(calls),native_product_links=0,
                pricing_reader=dict(path=pricing_path,commit=ERA,sha256=hashlib.sha256(text).hexdigest()))


if __name__=='__main__':
    B.finish('v160-hybrid',derive,RECEIPT,HISTORY,(__file__,H.__file__))
