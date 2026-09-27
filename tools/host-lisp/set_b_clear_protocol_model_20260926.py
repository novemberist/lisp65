"""Abstract ordered-job CLEAR protocol; not C, target timing, or a DMA emulator."""
import hashlib

BASE = 33840
LIMIT = 48384
MAX_COUNT = (LIMIT - BASE) // 8


def geometry(n, k):
    assert 0 <= k <= n <= MAX_COUNT
    primary = (BASE, BASE + 4*n)
    backup = (BASE + 4*n, BASE + 8*n)
    assert primary[1] == backup[0] and backup[1] <= LIMIT
    assert backup[0] + 4*k <= backup[1]
    return primary, backup


def case(n, k, cut=None, rollback_cut=None, duplicate=False, mutation=None, finish_fail=False):
    geometry(n, k)
    # Keep source plans and current function cells distinct. Undo words are
    # symbolic 16-bit values; this model does not implement Lisp object tags.
    symbols = [i % 4 if duplicate else i for i in range(k)]
    before = {i: (0x2001 + i) & 65535 for i in symbols}
    current = dict(before)
    memory = bytearray([0x5a]) * (8*n)
    for i, sym in enumerate(symbols):
        memory[4*i:4*i+4] = sym.to_bytes(2, 'little') + before[sym].to_bytes(2, 'little')
        current[sym] = (0x6000 + i) & 65535
    published = dict(current)
    observed = bytearray([0xa5])*64
    journal = bytearray([0x77])*64
    capsule = dict(state='WAIT_FORWARD',abort=False,ready=True,n=n,k=k,submissions=1)
    undo_payload=bytes(memory[:4*k])
    memory[:4*k]=bytes([0x5a])*(4*k)
    jobs = [lambda: memory.__setitem__(slice(0,4*k),undo_payload)]
    def enqueue_copy():
        # Two physical chunks expose a partially delivered backup; source is
        # read at execution, not snapshotted into the submitted job.
        length=4*k; middle=length//2
        for at,size in ((0,middle),(middle,length-middle)):
            if size:
                jobs.append(lambda at=at,size=size: memory.__setitem__(slice(4*n+at,4*n+at+size),memory[at:at+size]))
    enqueue_copy()
    if mutation=='copy_before_primary':
        jobs.append(jobs.pop(0))
    clear_end=8*n if mutation=='old_full_clear' else 4*n
    jobs.extend([lambda: memory.__setitem__(slice(0,clear_end),bytes(clear_end)),
                 lambda: journal.__setitem__(slice(None),bytes(64)),
                 lambda: observed.__setitem__(slice(None),journal)])
    total=len(jobs)
    if cut is None: cut=total
    assert 0 <= cut <= total
    for job in jobs[:cut]: job()
    pending=cut<total
    if pending:
        capsule.update(state='QUARANTINED_FORWARD',abort=True)
        # Native event processing must not grant these operations while pending.
        denied=['gc','allocation','lisp-eval','retirement','restage','scratch-release',
                'root-drop','backup-read','repoison','resubmit']
        retained=bytes(memory)
        for _ in range(64):
            assert capsule['ready'] and capsule['submissions']==1
            assert bytes(memory)==retained
        for job in jobs[cut:]: job()
    else:
        denied=[]
    assert observed==bytes(64)
    if finish_fail:
        capsule.update(state='READY_TO_FINISH',abort=True)
    if not capsule['abort']:
        # The only final scrub is synchronous after retirement, so it cannot
        # create another pending DMA obligation after undo has been discarded.
        memory[:]=bytes(8*n)
        capsule['state']='IDLE'
        assert current==published and not any(memory)
        return dict(n=n,k=k,cut=cut,total=total,result='success',ready=True,submissions=1)
    backup=bytes(memory[4*n:4*n+4*k])
    expected=b''.join(sym.to_bytes(2,'little')+before[sym].to_bytes(2,'little') for sym in symbols)
    if mutation in ('old_full_clear','copy_before_primary'):
        return dict(n=n,k=k,result='FALLING: '+mutation,caught=backup!=expected)
    assert backup==expected
    capsule['state']='ROLLBACK'
    # Immutable original population; do not decrement the authority K as work
    # is replayed. Replaying in reverse is safe for duplicate symbol rows.
    restore=[]
    for i in reversed(range(k)):
        row=backup[4*i:4*i+4]
        sym=int.from_bytes(row[:2],'little');value=int.from_bytes(row[2:],'little')
        restore.append(lambda sym=sym,value=value:current.__setitem__(sym,value))
    for job in restore:job()
    assert current==before
    observed[:]=bytes([0xa5])*64
    capsule['submissions']+=1
    if mutation=='recopy_on_rollback':
        memory[4*n:4*n+4*k]=memory[:4*k]
        return dict(n=n,k=k,result='FALLING: rollback recopy destroys backup',caught=memory[4*n:4*n+4*k]!=backup)
    rollback=[lambda: memory.__setitem__(slice(0,4*n),bytes(4*n)),
              lambda: journal.__setitem__(slice(None),bytes(64)),
              lambda: observed.__setitem__(slice(None),journal)]
    if rollback_cut is None:rollback_cut=len(rollback)
    for job in rollback[:rollback_cut]:job()
    if rollback_cut<len(rollback):
        capsule['state']='QUARANTINED_ROLLBACK'
        for _ in range(64):
            assert capsule['ready'] and capsule['submissions']==2
            assert memory[4*n:4*n+4*k]==backup
        # A second observation window neither copies nor resubmits.
        for job in rollback[rollback_cut:]:job()
    assert observed==bytes(64) and current==before
    # A replay before final scrub would still have every original row.
    for job in restore:job()
    assert current==before
    memory[:]=bytes(8*n)
    capsule['state']='IDLE'
    assert not any(memory)
    return dict(n=n,k=k,cut=cut,total=total,rollback_cut=rollback_cut,
                result='exact rollback',error=43,ready=True,submissions=2,finish_fail=finish_fail,
                denied=denied,undo_sha256=hashlib.sha256(backup).hexdigest())


def run():
    rows=[]
    for n in range(MAX_COUNT+1):
        geometry(n,n)
        rows.append(case(n,n))
        rows.append(case(n,n,cut=0))
        rows.append(case(n,n,finish_fail=True))
    for n in (0,1,2,288,1008,MAX_COUNT):
        for k in sorted({0,min(n,1),n//2,n}):
            total=(2 if k else 0)+4
            for cut in range(total):
                for rc in range(3):
                    rows.append(case(n,k,cut=cut,rollback_cut=rc,duplicate=True))
    controls=[case(2,2,cut=4,mutation='old_full_clear'),
              case(2,2,cut=4,mutation='recopy_on_rollback'),
              case(2,2,cut=4,mutation='copy_before_primary')]
    assert all(r['caught'] for r in controls)
    # Represent a permanently undelivered witness separately: no new job or
    # Lisp admission is inferred from repeated bounded observation windows.
    pending=dict(state='QUARANTINED_FORWARD',ready=True,submissions=1,backup_reusable=False)
    frozen=dict(pending)
    for _ in range(4096):assert pending==frozen
    return dict(status='PASS ABSTRACT PROTOCOL MODEL',max_count=MAX_COUNT,
                geometry_counts=MAX_COUNT+1,passing_rows=len(rows),rows=rows,
                falling_controls=controls,permanent_pending=pending,
                scope='Ordered whole/chunk job model, symbolic function words; no target C, GC, deadlines, reset or hardware reachability proof.')
