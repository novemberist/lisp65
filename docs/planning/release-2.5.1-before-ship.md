# 2.5.1 — Before-Ship

2026-09-29, preparation r3. Ship/Publish remains delegated to the reviewer
by the [plan journal](post-2.4.0-plan.md). This preparation makes no Git
writes, device/emulator contacts or network calls. The reviewer first
commits the documents, then runs the post-commit sealing script.

## Sealed full host run and conversions

`build/release-v2.5.1-check-host-r4/receipt.json`: **exit 0**, 3066.870840 s,
HEAD `daa35d529fc6afff2f75b4564dec74a31304352e` before and after.
23,651 protected files and 46,785 sealed artifacts; zero changed protected
files, zero changed sealed artifacts. Receipt SHA-256:
`738347d9c9e1c808a91fe3ea7a75b69b906a77fbef030b8ea82e724dc056933b`.
Log `build/release-v2.5.1-check-host-r4/check-source.log`, SHA-256:
`c549d08d2498c8cdbe5be4aa4492ba01caf928dae28e35b00802919529c894a3`.
No failed or tolerated target. This run applies to the named commit;
subsequent documentation and packaging checks are separate.

r2 on 2757ec77 and r3 on bd55b65a each had one string-codec workload red.
bd55b65a introduced the four-input successor; daa35d52 converted it to the
six inputs in a fresh generated tree with new codec and Card-5 receipts.
Measurements remain unchanged. Conversion chain:
`build/release-v2.5.1/check-host-r2-conversion.md` and its dated successor
`build/release-v2.5.1/check-host-r3-conversion-r3.md`.

## Final and two qualifying reproductions

Final seal:
`tests/bytecode/dialect-v2/evidence/architecture-blocks/strings-final-20260929.json`
(SHA-256 `414f3a0e4096f74d61ae3f6f9ec64f3b77adf145da11352259aba584006d93d7`).
It records PASS; the opening draft wording in the historical
[strings report](strings-final-report.md) is not the final seal authority.
Emulator `build/strings-rows-r2/receipt.json`: 72/72 PASS.
Two qualifying independent public reproductions are
`build/release-v2.5.1/repro-r2-1/` and `repro-r2-2/`, bound by
`config/c2-v251-r2-20260929-reproductions.json`. ELF, PRG, LTO and D81
match Final byte for byte. Earlier Backspace reproductions are historical.
Packaging reuses reproduced bytes without a new product build or link.

ELF: `d514e4980c636cab0c6ae1ee9bea77afdd3a4fdf58f01995aba5ff822e89ed05`.
D81: `9978daa146b89cf71ad1d3f290d80cf74b197911e7854859f9e4aa9bb2fce441`.
All bound producer inputs must remain unchanged in the new projection;
every documentation/consumer delta is enumerated by the package receipt.

## Scope, device claims, accepted cost and known issues

Scope: C-x q IDE exit, small Backspace tail change, editor list walks and
the Comfort multi-line string evaluation/display fix. Native typing is
**MEASURED** 3.24 M → 1.58 M cycles/key, about 80 → 39 ms. Backspace
code-object reads 1,200–1,800 → 53/key are projected; the historical small
tail change reduced VM instructions 7/19/26% at 10/40/70 characters.

The [device report](release-2.5.1-device-report.md) binds fresh S251.D81
readback, 13/13 rows, 20.9 s initialization and 40.5 s prompt (host clock).
Owner physical typing/Backspace feel, string example and C-x q passed.
Stopwatch cold boot and physical RUN/STOP remain pending; no new physical
measurement is inferred from the automated receipts. Physical C-x C-c
remains a known issue. Continuation lines remain uneditable after Return;
Up/Down walk history; the multi-line editing card follows 2.5.1.

Accepted named Comfort cost: +8 symbols, +105 name bytes, +1 code image,
+7 C2D entries/roots, five additional boot collections; after exit,
+12 live cells and +2.1% matched forced-collection cycles (natural −1.7%).
These are emulator measurements, not worst-case device pause guarantees.
Top-level anonymous lambda refusal, non-reused code-image slots, the
12-argument bound and absent-require LOADING before NIL remain.
Set B and Card L are excluded.

The [dated release-note successor](../releases/2.5.1-before-ship-r3.md)
is the publication body; the original r2 release notes remain historical.

## Package and reviewer seal

The r3 package explicitly includes these documents, the current plan and
parked-items register as exceptions to the historical export exclusions.
Current-tree assets in `build/release-v2.5.1/r3/ready-assets/` are a real,
verified preparation set, **pending the reviewer documentation commit**.
Their JSON records report that limitation; they are not publication seals.

After committing the explicit `commit-paths-r3.txt` list, the reviewer runs
`build/release-v2.5.1/seal-after-commit-r3.py --final`. It creates a fresh
`r3/sealed/` generation against that commit, double-packs, independently
verifies all four assets and writes final-before-ship.json,
v251-before-ship-receipt.json, ship-readback.json and
github-release-prepared.json. No future commit ID is invented. The reviewer
then commits the generated proof receipt and makes annotated proof/v2.5.1,
creates the source-projection commit and annotated v2.5.1, then publishes.
Exact commands: `build/release-v2.5.1/reviewer-next-steps-r3.md`.
The public archive supports the reproduced product recipe, not every
historical private-evidence gate. Public main history must be preserved.
