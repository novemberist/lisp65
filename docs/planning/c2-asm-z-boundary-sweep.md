# C2 handwritten-assembler Z-boundary sweep

Status: static prelink qualification, 2026-07-28. No product link or hardware
run is claimed by this receipt.

## Question and result

The original 45GS02 gate proved only the input direction: every handwritten
`STZ` must be dominated by Z=0 because 45GS02 `STZ` stores the live Z register.
It did not prove the reverse llvm-mos boundary: generated C may use `STZ` as a
zero store immediately after returning from handwritten assembler.

The gate now derives all typed handwritten entries under `src` and `scripts`,
follows local `JSR`/`RTS` frames, and proves:

- every regular `RTS` and external tail edge carries Z=0;
- every ASM-to-external `JSR` enters with Z=0 and is modeled as returning
  under the same ABI;
- interrupt `RTI` and firmware-chain edges preserve the arbitrary interrupted
  entry Z instead of falsely forcing it to zero;
- nonreturning entries are classified separately;
- every handwritten `STZ` retains the original Z=0 dominance proof.

The source sweep covers 59 typed entries, 87 exit/tail paths and 25 `STZ`
sites. Its selftest rejects 50 `STZ` mutations and 75 `INZ`-before-exit
mutations. The enclosing assembler ABI selftest rejects 160 mutations.

## First Reds and corrections

`lisp65_error_overlay_entry` had four cold error returns after indexed context
reads. They returned status in A with Z unknown. All status paths now join one
`LDZ #0` / `RTS` point. The independently assembled symbol grows from 333 to
339 bytes (+6 bytes); its next product residence and capacity remain a WPLTO
question because this static sweep does not relink the product.

`vm_l65m_batch_repeat` used a symbolic Z index and had no explicit restoration.
The currently generated ABI-version offset resolves to zero, but that value was
not a lifetime proof. The source now restores Z immediately after the indexed
read (+2 source-object bytes). Independently, the canonical C2-lite final ELF
classifies the function as `not-linked-by-c2-lite-profile`, and the one-truth
closure forbids `l65m_batch_repeat.s`; its C2-lite product delta is therefore
zero.

The specifically requested indexed/incrementing entries
`c2_journal_prepare_select`, `l65e_bcode_ordinal`, `vm_c2d_byte`,
`lisp65_ash_tagged`, `c2_append_plan_walk`, and `c2_kernal_window` all pass
every return/tail path. The journal selector's two `$d5` indexed reads are
dominated by its three explicit `LDZ #0` exits.

## Permanent placement

The source proof remains part of `c2_asm_leaf_abi_gate.py`, which is run for
each canonical product ELF. Its full mutation suite is also a direct
`workbench-product` prerequisite, so a newly added handwritten return cannot
enter a public clean build without the Z proof.

Receipts:

- `tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.2-asm-z-boundary-selftest-receipt.json`
- `tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.2-asm-z-boundary-prelink-static-receipt.json`
