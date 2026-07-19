# Host Models and Verification Tools

This directory contains lisp65 host oracles, generators, linters, package
verifiers, and several historical LISP 64 reference models. Start with the
project [Development Guide](../../docs/development.md); the Makefile is the
supported entry point for maintained gates.

## Normal entry points

```sh
make check-source
make check-host
make check-product
```

Run individual tools through their Make targets so generated prerequisites and
profile flags remain correct. Direct Python invocation is intended mainly for
tool development and self-tests.

## Maintained lisp65 tools

| Tool | Purpose |
| --- | --- |
| `document_index.py` | validates the complete tracked Markdown classification |
| `source_syntax_check.py` | checks tracked and new Python/shell source syntax |
| `project_doctor.py` | read-only, gate-specific toolchain preflight |
| `ci_gate.py` | clean-checkout wrapper for source and host gates |
| `semantic_contracts.py` | strict contract registry and adapter runner |
| `bytecode_p0.py` | pinned P0 code-object model, disassembler, heap, and VM |
| `bytecode_p0_compiler.py` | P0 compiler and golden-vector checks |
| `bytecode_p0_stdlib.py` | stdlib/library compiler, bundle builder, and L65M emitter |
| `bytecode_p0_drift_check.py` | opcode/primitive identity parity across archived ABI, Python, and C |
| `code_object_arity_contract.py` | strict-arity layout and executor/validator parity |
| `v2_native_function_registry.py` | generates and checks primitive views from one registry |
| `workbench_ship.py` | builds and verifies the historical workbench ship format |
| `overlay_package.py` | builds and verifies profile-bound overlay packages |
| `r6_g6_seal.py` / `r6_g6_seal_offline.py` | seals final G6 hardware acceptance |
| `r7_release.py` / `r7_release_offline.py` | reproduces the historical 1.0.1-light package from its seal |
| `r7_release_v11.py` / `r7_release_v11_offline.py` | materializes and verifies the 1.1.0 release from the registered Wave 3 G6 seal |
| `bank0_lifetime_report.py` | classifies physical Bank-0 allocations and ICF aliases |
| `bank0_reclaim_report.py` | ranks measured reclaim candidates |
| `ide_bytecode_cost_report.py` | static editor bytecode and render-contract cost report |
| `ide_bytecode_dynamic_report.py` | dynamic host VM trace for editor scenarios |

Reader, evaluator, prelude, IDE, closure, fixed-point, persistence, package,
capacity, and evidence tools follow the same naming pattern and are wired into
the Make gates. Their module docstrings and `--help` output are authoritative.

## Historical LISP 64 models

`lisp64.py`, `vm-model.py`, `phase4_vm.py`, `phase4_srcexpr.py`,
`phase4_disasm.py`, and `compact-model.py` preserve earlier C64/LISP 64
semantics and experiments. They remain useful independent differential
oracles, but they are not simulations of the released MEGA65 product.

The historical interpreter models language behavior without ROM banking,
native memory layout, real garbage-collection timing, SID/VIC effects, or
cycle accuracy. When it disagrees with a product-bound lisp65 fixture, the
product contract wins.

Example historical invocation:

```sh
python3 tools/host-lisp/lisp64.py --echo path/to/forms.lsp
python3 tools/host-lisp/lisp64.py --repl path/to/prelude.lsp
```

## Evidence boundaries

- Host models prove only their declared semantic or structural domain.
- Emulator tools are prefilters and do not make hardware-timing claims.
- Hardware receipts bind exact product SHAs and physical cycle IDs.
- Sealed archives verify offline and never consult these live tools by path.

Detailed pre-1.0 design context is retained only in the private proof
repository. It is not part of the curated public source snapshot.
