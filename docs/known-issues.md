# Known Issues and Retired Exceptions

This is the maintained user-facing issue register for lisp65 1.2.0. Sealed
historical documents retain the wording that was true when they were issued;
this page states the current product boundary.

## Active product limitation: Freezer during a definition

Status: **documented; C2.3-deferred**

Enter the Freezer only while the REPL prompt is visible or the evaluator is
otherwise idle. Freezer entry during a persistent definition or append
transaction is not supported in C2.2.

If it happens:

1. Return from the Freezer with F3.
2. Cold-restart lisp65 from the product disk.
3. Re-enter the interrupted definition before relying on it.

Idle Freezer entry and return are hardware-proven for the 1.2 product identity.
Freezer entry while a definition is open is not. The C2.2 cross-invariant
matrix classifies that crossing as documented/C2.3-deferred, and no release
receipt may relabel it as proven.

## Informative performance positions

These measurements are visible by design but carry no release limit:

- one-argument published call: 68 frames;
- GC envelope: 89 frames for one collection and 96 contract block reads;
- cold boot: a 27.653-second upper bound from BASIC `RUN` to a captured screen
  during C2-lite stabilization. The prompt may have appeared earlier.

They are not regressions against a claimed 1.2 ceiling. The only 1.2
definition-call performance claims are the nullary first-call and warm-call
ceilings below.

## Retired: 1.1 definition-to-first-call latency exception

Status: **retired by the promoted 1.2 product**

The 1.1 exception allowed a first call after persistent definition to take
95--98 frames, with a 10-frame warm call, while requiring C2 as the non-
renewable 1.2 cure. It did not change the performance target and could not
renew automatically.

The retirement conditions are all satisfied:

- measurement separated product execution from harness and transport time;
- the acceptance ceilings were fixed before measurement at 16 frames first
  call and 10 frames warm;
- the Link-66 hardware run measured 1 frame first call and 0 frames warm;
- the final G5 repeat measured 0 and 0 frames;
- nested evaluation and RUN/STOP abort left the C2D state byte-identical;
- fresh G5 and G6 bound the same final product identity;
- promotion sealed the exact product and package sets.

Retirement scope is intentionally narrow. It proves the published nullary-call
path and does not create a performance claim for calls with arguments, GC, or
cold boot.

Machine-readable authority:
`config/v12-known-issues.json`.
