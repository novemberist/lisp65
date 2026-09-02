# Buffer and string construction block (ABI 1.1)

Status: deferred. This block is not part of the dialect-v2 CP5 release scope.

The block owns the first-class buffer representation and the replacement for
the retired staging builders `%string-slice` (Prim 26) and
`%string-concat-list` (Prim 27). Those IDs are permanent tombstones and must
never be reused. Any future atomic builder or span-DMA gateway receives new
Prim-IDs from the then-current reserved range.

The current v2 implementation materializes strings from rooted code lists
through private Prim 28/29. It retains the streaming arena codec and guarantees
that the VM returns no result after OOM, so a partial string is not observable
to Lisp. Internal scratch is reclaimed by the next GC. It does not claim a
transactional arena rollback, span-DMA, or constant-allocation guarantee.

Reopening criteria:

1. `first-class-buffer` has a pinned type, lifetime, pinning, freeze, and GC
   contract.
2. GC-during-construction, arena-full, abort, and overlap fixtures exist before
   implementation.
3. New Prim-IDs and their decoder names are allocated by the ABI ledger.
4. Minibuffer, render, and format workload receipts justify the optimization.
5. The 1140-byte ABI-1.1 headroom remains separately budgeted; spending it is
   an explicit architecture decision.
