# AP7 Product and Runtime Boundary Audit (2026-07-11)

Status: active AP7 decision input, not a product, language, ABI, or release
contract. Current product status remains in `docs/project-status.md`.

## Scope

This audit separates three concerns before implementation:

1. the interactive Workbench product;
2. a non-interactive Runtime Export artifact;
3. post-M5 dialect redesign work.

It does not reopen the AP4 layout, change public Lisp semantics, or promote the
existing Runtime Core prototype.

## Current Product Truth

The Workbench is the only interactive product. Its canonical inputs are
`config/workbench.mk`, `mk/workbench.mk`, the Ship-v5 verifier, and the
machine-readable semantic contracts. Its supported development loop is:

- REPL and Editor;
- lcc compile/install;
- source Load/Save;
- compile/load-lib;
- error recovery.

The Runtime Core under `config/runtime-core.mk` is a G2 measurement prototype.
It already proves a useful minimum: VM, GC/heap, symbols, boot loader, and a
named zero-argument bytecode entry without Reader, REPL, evaluator, compiler,
IDE, or lcc. It does not yet prove an export workflow.

## Runtime Measurements

The three existing layouts were rebuilt on 2026-07-11:

| Layout | Result | Relevant measurement | Classification |
| --- | --- | --- | --- |
| Flat PRG | green | 23219 B PRG; 11704 B Bank-0 reserve | measurement prototype; below 12288 B target |
| Fixed-VMA split | green | 19792 B resident PRG + 3515 B boot overlay | diagnostic; requires a separate transport |
| Inline boot overlay | green | 25248 B PRG; 3515 B boot overlay; 15132 B post-boot reserve | recommended Runtime Export base |

The inline path keeps the boot overlay in the PRG, reclaims it before runtime,
and passes the control-flow, boot-gap, file-end, and post-boot-reserve audit.
The application bytecode remains a separately staged, build-bound Bank-5
preload; the path is therefore a small bundle, not a single self-contained
PRG.

## Missing Export Contract

The prototype has no user-selectable application descriptor. Its suite fixes
three test functions and `runtime-main`; the Make variable used by the audit is
not yet passed as `LISP65_RUNTIME_ENTRY` to every target compile. It also lacks:

- an application manifest and dependency closure;
- a Workbench-to-Runtime transformation;
- a Runtime Ship format and package verifier;
- hashed profile inputs and toolchain provenance;
- reproducibility, deploy dry-run, and cold-boot gates;
- fail-closed corruption cases for the application preload.

The current boot loader is suitable only for a fully build-bound preload. A
generic D81 `load-lib` path would require F011 I/O plus the full L65M validator,
commit, transport, and runtime-overlay catalog. That is outside the necessary
M5 scope.

## Architecture Variants

### A. Host-built static suite

The host builds the application and all libraries directly as the boot stdlib.
This is deterministic and cheap, but it does not consume the artifact produced
by the Workbench and therefore does not close the intended export loop.

### B. Sealed L65M bundle (recommended)

The Workbench produces one L65M-v1 application module. A host packer performs
the full preflight, resolves the closed library set, and creates a build-bound
Bank-5 preload. The package binds:

- inline-overlay Runtime PRG;
- application preload;
- original L65M module;
- named zero-argument entry;
- resolved profile and toolchain report;
- SHA-256, build ID, lengths, CRCs, and load addresses.

The target runtime performs no disk loading and contains no IDE or lcc. This is
the smallest design that proves a real Workbench-to-Runtime workflow without
copying Workbench infrastructure into the deployed program.

### C. Dynamic D81 runtime

The runtime loads applications and libraries from arbitrary media. This is a
future plugin/runtime tier, not a v1 requirement. It has the largest resident,
transport, recovery, and hardware-test surface.

## Proposed Runtime Export v1 Boundary

Subject to architecture approval, v1 should use variant B and the inline boot
overlay, with exactly one sealed application module and no runtime disk loader.
Its contracts should be separate from Workbench Ship-v5:

- `runtime-app-v1`: app identity, P0/L65M versions, entry/arity, public exports,
  capabilities, dependency closure, artifact hash, and resource ceilings;
- `runtime-export-profile-v1`: explicit sources/flags, forbidden development
  symbols, budgets, and input hashes;
- `runtime-export-ship-v1`: exact package files, preload binding, profile,
  toolchain, hashes, build ID, lengths, CRCs, and addresses.

Expected gates:

- G0: strict schemas, L65M preflight, export/dependency closure;
- G1: identical app result in Python and native host VM;
- G2: final ELF surface, budgets, package verifier, reproducibility;
- G4: deploy dry-run with exact PRG/preload ordering;
- G5: cold boot, exact result, and corrupt/missing/truncated preload failures.

## Dialect Redesign Placement

AP7 prepares classification only. A future planning inventory must distinguish
three independent axes:

- semantic role: special form, primitive, library, internal;
- delivery: native, boot stdlib, disk library, Runtime Export, not built;
- visibility: public, internal, private inline.

This avoids false global statements. For example, public `eval` is excluded
from the Workbench, while the host behavior fixture still tests evaluation and
the Runtime Core is evaluator-free.

Already implemented redesign foundations include HW math, private IDE/M65D
helpers, IDE/IDEX/M65D tiering, packed strings, and the code/text error channel.
AP7 may define capabilities, exports, dependencies, and open decisions, but it
must not implement alias removal, export interning, `require`/`unload`, a new
Buffer type, string rewrites, new hardware primitives, or the global one-engine
cleanup. Those remain AP8 work after M5.

The local dialect redesign note is planning input only and must not be added to
the semantic-contract registry or Ship hash chain.

## Documentation and Release Findings

1. `README.md` still calls the historical salvage plan binding, although its
   MVP exclusions contradict the current VM/IDE Workbench.
2. The quick start lacks prerequisites, `doctor`, verified-only deployment,
   and a short first Workbench session.
3. `project-status.md` repeats completed AP5 work in its next-work queue and
   mixes current source state with older live package evidence.
4. `project-status.md` and `workbench-gate.md` duplicate generated budgets and
   historical manifest hashes.
5. Generic `ship-check`/`ship-release` still operate on the historical Interim
   artifacts. There is no current G6 Workbench release target, and G3 remains
   unavailable.
6. Several historical design documents still read as active product guidance.

AP7 should establish these document roles:

- `README.md`: prerequisites and one supported user path;
- `project-status.md`: current source/G2 state, last G5 evidence, release state,
  blockers, and queue;
- `decision-log.md`: dated architectural decisions;
- machine-readable contracts and generated reports: profiles, budgets, and
  package truth;
- design/history documents: explicitly classified and, when applicable,
  linked through `superseded_by`.

## Decisions Required Before Implementation

1. Accept or reject sealed L65M bundle + inline boot overlay as Runtime Export
   v1; the alternative is a host-only static suite.
2. Accept or reject namespacing the old Interim `ship-check`/`ship-release` and
   reserving the generic `release` entry for a fail-closed Workbench release
   contract after G3-G5 evidence exists.
3. Accept or reject a machine-readable documentation index with a G0 drift
   check and classifications `current`, `contract`, `proposal`, `reference`,
   `historical`, plus optional `superseded_by`.

No implementation of these decisions is implied by this audit.
