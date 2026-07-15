# Implementation Contracts

This page maps maintained product properties to their machine-readable sources
and verification gates. Detailed pre-1.0 design documents are preserved under
`docs/archive/pre-1.0/`; they provide provenance, not a second source of truth.

| Property | Authority | Primary gate |
| --- | --- | --- |
| Dialect V2 surface and profile | `config/dialect-contract.json`, `config/dialect-migration-contract.json`, `config/dialect-profile-selection.json` | dialect contract and family gates in `make check-source` |
| Native primitive identities and visibility | `config/v2-native-function-registry.json` | registry generation and cross-view parity report |
| Bytecode IDs and compatibility | `config/bytecode-abi-ledger.json`, `src/vm.h`, `tools/host-lisp/bytecode_p0.py` | `make bytecode-p0-drift-check` |
| Code-object arity | `config/code-object-arity-contract.json` | `tools/host-lisp/code_object_arity_contract.py` |
| L65M library format | emitters, validators, and L65M fixtures under `config/` and `tests/bytecode/` | package and loader contract gates |
| Product artifact identity | R4 seal and `config/promotion-register.json` | `make promotion-register-check` |
| G5/G6 hardware evidence | R5/R6 manifests and sealed case receipts | offline archive verifiers |
| Capacity floors | product footprint receipts and capacity ledgers | footprint and capacity-delta gates |

## Stability rules

- Numeric bytecode and primitive identities are never silently reused.
- A public primitive exists in every required dispatch view or carries an
  explicit, reasoned restriction in the registry.
- Dialect V2 code objects use strict arity. Optional parameters default to NIL;
  default forms and supplied-p variables are not part of 1.0.
- Cross-container calls use exported names. Container-local private entries may
  use ordinals and remain anonymous.
- Product evidence binds artifact SHAs. A product-byte change requires fresh
  applicable hardware evidence.
- Every promoted change reports Bank 0, EXT, symbols, name-pool bytes, and
  directory-slot deltas.

When prose and a generated value disagree, stop and repair the prose or gate;
do not reinterpret a sealed receipt.
