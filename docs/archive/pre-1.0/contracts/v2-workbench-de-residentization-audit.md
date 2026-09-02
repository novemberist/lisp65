# Workbench-v2 De-Residentization Audit

Status: machine-checked audit; the first two bounded migrations are implemented,
the removable-class sweep is complete, and the product is not promoted. The audit source remains
`config/v2-workbench-de-residentization-audit.json`; the immutable prototype
receipt is under `tests/bytecode/dialect-v2/evidence/capability-carrier/`.

## Boundary

The Workbench remains the release product. Runtime Core is an internal proof
artifact and does not replace the Workbench release path. No language family,
AP8 block, runtime slot, permanent island allocation or layout approval is
introduced by this audit.

After `number->string` and the FASL writer, the current v2 diagnostic link
starts its runtime overlay at `$c9d0`. The accepted maximum is `$c356`, so 1658
bytes of real linked VMA reclaim remain. Post-boot reserve is 136 bytes against
a 1536-byte minimum, a 1400-byte deficit. The reserve is derived from the
aligned `__heap_start`, not the preceding `__bss_end` byte.

## Measurement Meaning

Every candidate value is a real MOS LTO/ICF drop-link measurement. It is an
upper bound before replacement code, not a net saving and not promotion
evidence. The durable contract binds the existing CP5 symbol-diff policy and
receipt by SHA. Raw symbol and drop-link tables are retained as external
diagnostic datasets whose SHA values are recorded; their filesystem location is
not a contract input.

| Candidate | Marginal VMA drop | Latency/correctness risk |
| --- | ---: | --- |
| String builders, Prim 26/27 only | 2542 B | Low for the current Workbench closure; high because the pinned atomic-builder contract changes |
| Complete interactive LCC coordinator | 1058 B | Critical: the user compile/install path disappears; insufficient by itself |
| REPL line editor/history/banner | 460 B | Medium-high UX regression; raw read/eval/print remains |
| Boot lifetime cluster | 110 B diagnostic, **0 B planable** | Critical trust/diagnostic loss; not independently removable |

All figures are same-class real MOS LTO/ICF marginal links. They are ceilings,
not additive savings and not promotion evidence. The empty-`repl` experiment is
explicitly rejected: its apparent 30340-byte drop severed the only runtime root
and measured whole-program dead stripping rather than REPL comfort.

The former 1371-byte boot-lifetime value is also rejected. It came from a
nonfunctional `repl(); return 0;` main which skipped clock setup, the bound boot
overlay, stdlib fastpath and resident-island installation. A functional minimal
boot retained those trust steps and saved only 110 VMA bytes by deleting required
diagnostics. The promotionsafe planning value is therefore zero.

The earlier compile-error dispatcher cannot finance the release. Its table prototype
grew by 61 bytes, and the dynamic table variant hit an llvm-mos IRTranslator
failure.

## Removable-Class Sweep

The decisive result is narrower than the feature macro suggests.
`LISP65_V2_NATIVE_STRING_CAPS` combines two responsibility classes:

- Prim 26/27 implement the atomic slice/concat builders. The current Workbench
  artifact emits zero calls to both.
- Prim 28/29 convert strings to and from code lists. They remain live with
  48 and 27 static calls respectively and are not candidates for removal.

Stubbing only 26/27 moves the relaxed runtime-overlay VMA from `$c9d0` to
`$bfe2`, exactly 2542 bytes. A production-gated hard link also passes: it lies
884 bytes below `$c356` and leaves 2676 bytes post-boot reserve, 1140 bytes above
the 1536-byte target. No slot, island byte or VMA pin changes.

That stub is deliberately not promotable. Family evidence still invokes 26/27,
and the atomic GC/OOM/fault contract is already normative. The recommended
architecture decision is therefore a contract split, not a product-only flag:
retain codecs 28/29; retire 26/27 as permanent tombstones; make the current
Workbench code-list implementation the v2 surface; and reopen atomic builders
only in the separately named Buffer/string-construction block. Until that
decision is approved, source, ABI, artifacts and ship gates remain unchanged.

## Implemented Migrations

`number->string` now resides as one public 200-byte CodeObject in Bank 5. Its
result helper is private-inline and creates no symbol or Directory entry. Prim
ID 40 is a permanent v2 tombstone; the reserved v1 ID and v1 behavior remain
unchanged. The real
relaxed LTO/ICF pair reclaimed 82 bytes at `__heap_start` and 80 bytes at the
runtime-overlay VMA. The candidate therefore moves from `$cc78` to `$cc28` and
improves post-boot reserve from -546 to -464 bytes. It still misses `$c356` and
the 1536-byte reserve target, so CP5, G5 and every ship path remain closed.

The warm render-after-insert trace rises from 4183 to 4312 VM instructions
(`+129`, 3.08 percent) and stays below the pinned five-percent regression
budget. `-16384` is additionally pinned to `"-16384"` across Treewalk, native
Compiler-VM, Python-P0 and Lisp-LCC; direct calls, `funcall`, `apply`, type
errors and strict arity are covered by the dedicated fixture. The boot fastpath remains flat-literal
only; the minimum-value digit sequence is built with `cons` and handed to the
same atomic internal string constructor.

The second migration retires v2 Prim ID 34 (`%save-staged`) and implements the
fixed-slot writer as six ordinary Bank-5 CodeObjects. The shared v1 definition
and frozen v1 artifact remain unchanged. The writer preflights the complete
immutable chain, invalidates the first L65M length prefix, writes every tail
sector, rereads and verifies the first link, then commits the complete first
sector last. Any read/write failure or the 255-sector fuel limit returns
fail-closed; an interrupted artifact retains an invalid prefix and cannot be
loaded as a plausible truncated FASL.

The final relaxed MOS LTO/ICF link moves `__heap_start` and the runtime-overlay
VMA from `$cc26/$cc28` to `$c9ce/$c9d0`: exactly 600 bytes net. No slot, island
byte or layout pin changes. The host oracle covers ten payload boundaries,
five deterministic read/write failures, the cyclic 255-sector chain, exact
bytes plus a successful `l65m-contract-v4` reload of the 587-byte Golden, and
validator rejection after every interrupted write. The existing D81 fault, BAM, chain,
directory and `save-new` differential matrix proves that BAM, directory and
neighboring files remain unchanged outside the target chain. The permanent
receipt is
`tests/bytecode/dialect-v2/evidence/capability-carrier/fasl-save-prototype-report.json`.

Hardware `C-x C-k` latency is deliberately not claimed while the v2 Workbench
does not meet its link budgets. Disk-sector I/O dominates the coordinator, but
the live latency measurement remains a CP5/G5 acceptance item.

## Burn-Down

| Step | Net reclaim | VMA gap | Reserve gap |
| --- | ---: | ---: | ---: |
| CP5 start | 0 B | 2338 B | 2082 B |
| `number->string` | 80 B | 2258 B | 2000 B |
| FASL save | 600 B | 1658 B | 1400 B |

The separately approved four-command installer gateway did not validate its
450--650-byte projection. Its real same-baseline MOS LTO/ICF link grew Bank 0
by 486 bytes (`$c9d0` to `$cbb6`). The existing coordinator was already folded
into the resident service; owner validation, persistent session state, abort
cleanup and five-argument dispatch cost more than the displaced loop. The
prototype was fully reverted: Prim 38 remains active, Prim 57 remains reserved,
and no slot, island byte or layout pin changed. The permanent stop receipt is
`tests/bytecode/dialect-v2/evidence/capability-carrier/lcc-installer-gateway-stop-report.json`.

The accepted burn-down therefore remains at the FASL row: 1658 VMA bytes and
1400 reserve bytes are still open. The resident island actually has 680 bytes
free: 2048 bytes capacity minus 1108 bytes immutable code and the later
260-byte root-stack annex. The older 932-byte figure predates that annex and is
retired. Likewise, reducing the Slot-37 contract from 1396 to 1024 bytes is not
an independent 372-byte reclaim: the current measured payload is 1369 bytes and
would not fit. Island and slice-cap remain untouched, not ingredients in the
present capacity proof.

This matters for the ABI-1.1 follow-on. The recommended string split closes the
Workbench link while preserving all 680 island bytes and the existing layout.
Its measured post-boot result leaves 1140 bytes above the 1536-byte target.
Spending the last structural island reserve now would instead leave ABI 1.1
without a credible resident growth path. A new architecture decision is
required before any further product edit.

## De-Residentization Template

Each later service migration follows this checklist:

1. Rank a resident, cold service from a real MOS symbol/drop-link report.
2. Add the public bytecode defun while keeping helpers private-inline or
   Directory-only; no helper may create a public symbol.
3. Retire an emitted Prim ID as a permanent tombstone with its decoder name;
   never reuse it and never modify the frozen v1 profile.
4. Make host P0 and `lcc` emit Directory calls and gate CALLPRIM/tombstone calls
   at zero before removing the native dispatcher case.
5. Pin boundary, arity, direct, `funcall` and `apply` observations, including
   any asymmetric numeric or allocation edge case.
6. Build clean-baseline and dirty-candidate relaxed links from the same Git
   HEAD; bind source, toolchain, flags, artifacts and ELF SHAs.
7. Measure the relevant hot path after migration. A cold classification never
   substitutes for a trace.
8. Promote only if the production VMA and reserve gates close. A useful local
   reclaim remains non-shippable evidence when the total product still fails.

Only the ABI retirement in step 3 requires an individual architecture approval.
Compatible migrations may otherwise be reviewed as a measured batch.

Any implementation must retain STRICT_ARITY, use zero new runtime slots and zero
permanent island bytes, link at or below `$c356`, retain at least 1536 bytes
post-boot reserve and pass the full Workbench G5 matrix. The current string
atomicity contract remains unchanged until the separately approved builder/codecs
split either replaces it or is rejected.

## Gate

```sh
make v2-workbench-deresidentization-audit-selftest
make v2-workbench-deresidentization-audit-check
make v2-workbench-deresidentization-prototype-check
```
