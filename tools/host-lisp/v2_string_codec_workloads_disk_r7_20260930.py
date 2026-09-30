"""Dated current r7 measurement; predecessor receipt remains immutable."""
import v2_string_codec_workloads_r251_20260929 as H
import disk_r7_consumers_20260930 as S
RECEIPT = 'config/v2-string-codec-workloads-disk-r7-receipt-20260930.json'
HISTORY = {**H.HISTORY, **{'tools/host-lisp/v2_string_codec_workloads_r251_20260929.py': '81706f79dc789639263f56fbed835c8af1ad2dff74e0a19b97fda16d7fbed38a', 'config/v2-string-codec-workloads-receipt-r251-r2-20260929.json': 'a56dee872238276a0a38c8a90df7d323b74e0c4892930c774597774e463cd2cd'}}
def compare(old, current):
    S.require([r['path'] for r in old['inputs']] == [r['path'] for r in current['inputs']], 'codec input population drift')
    changed = [a['path'] for a,b in zip(old['inputs'], current['inputs']) if a != b]
    S.require(changed == ['build/bytecode/dialect-v2/sources/lib/m65-disk.lisp', 'build/bytecode/dialect-v2/suites/p0-m65d-lib.json'], 'codec disk input drift')
    for row in current['inputs']:
        if row['path'] in changed:
            S.require(row['sha256'] == S.S.bind(row['path'])['sha256'], 'codec current binding drift')
    expected = S.copy.deepcopy(old)
    expected['inputs'] = current['inputs']
    H.H.H.compare_receipt(expected, current)
    return changed

def derive():
    S.S.history(HISTORY)
    H.H.H.selftest()
    old = S.json.loads((S.ROOT / H.RECEIPT).read_bytes())['current']['measurement']
    current = H.H.H.measure()
    changed = compare(old, current)
    trials=[]
    trial=S.copy.deepcopy(current); trial['inputs'].append(dict(path='unexpected',sha256='0'*64)); trials.append(trial)
    trial=S.copy.deepcopy(current); trial['inputs'].pop(); trials.append(trial)
    trial=S.copy.deepcopy(current); trial['inputs'][0]['sha256']='0'*64; trials.append(trial)
    trial=S.copy.deepcopy(current); i=next(i for i,r in enumerate(trial['inputs']) if r['path'] in changed); trial['inputs'][i]=old['inputs'][i]; trials.append(trial)
    trial=S.copy.deepcopy(current); trial['workloads'][0]['ops']+=1; trials.append(trial)
    for trial in trials:
        try: compare(old,trial)
        except (ValueError,H.H.H.WorkloadError): pass
        else: raise ValueError('codec mutation survived')
    return dict(measurement=current, changed_inputs=changed, mutations_rejected=len(trials), disk_r7=S.measure())

if __name__ == '__main__':
    S.finish('v2_string_codec_workloads', derive, RECEIPT, H, (__file__, H.__file__))
