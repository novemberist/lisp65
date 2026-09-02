# Project Status

Updated: 2026-08-31

Current public release: **lisp65 1.9.0**

Released dialect: **Dialect V2**

Repository status: **published and download-readback verified**

This is the living summary. Release receipts and artifact hashes remain the
authority for exact identities.

## Accepted and published product

| Item | Bound value |
|---|---|
| Selected variant | native Capture client + native prompt editor |
| Public `main` / tag target | `e237fc3da2297119c8a8861d8fb0410044fabbcf` |
| Annotated tag object | `ca76036ba2b7e3210c519485932599a548161dae` |
| Artifact-set SHA-256 | `518237bba41d6e1ff60f51de87e409ea9ccf62a819515dea00d288611ce3e079` |
| Resident PRG SHA-256 | `c91e342839901afa02516ce842bc32d1c077b9a4fa132911aef9d831906ccbff` |
| Linked ELF SHA-256 | `37cb8eff54b5394aff3130c279979ad22441c2d929c75dafc48679e3ad4b190e` |
| Product D81 SHA-256 | `670aa893cc8596f65833f10fdb70db8293dfd3e1146e728c7f37a5879064b216` |
| Work D81 SHA-256 | `bf887cd4f8b14b2e808bccfc223e64bfb1223a61e16e11169be0d34e669c63e3` |
| Product/profile build IDs | `fd162442` / `1b462281` |

The release was published on 2026-08-30. Four assets were downloaded afresh;
all byte counts and SHA-256 values matched. Two varied detached public-source
clones each performed one WPLTO/link and reproduced all 19 selected roles.

## Hardware boundary

v1.9 closes the two oldest interactive limitations:

- The native `lisp65>` prompt owns the insertion-mode editor. Cursor movement,
  insertion and deletion work there without an optional library load.
- Capture and its delivered consumer crossed a forced collection with
  `raw=seen=stored=taken=136`; ordinary prompt input was not lost.

Release-terminal D5 measured **109 free symbol slots and 1,486 free name
bytes**, above the mandatory 32/384 floor. Four representative performance
bodies completed in at most one raster frame.

The claim does not include type-ahead during evaluation, Comfort, balanced
multiline input/history, delimiter matching, cursor blinking, the unresolved
`$22` mechanism, or repairs for the newly inventoried domain findings.

## Product composition

The product D81 contains the resident prompt editor plus IDE, IDEX and M65D;
there is no separate optional-library medium. `INIT.L65` is checked once after
resident readiness and before the first banner. The release medium omits it,
so ordinary boot takes the silent absence path.

The composed Bank-2 ownership map, page-congruent MAP placement,
tuple-equals-`LOADADDR`, bound-equals-consumed headers and delivered-byte
checks remain permanent gates. Capacity is reported as owned intervals and
the largest contiguous hole, never as an uncomposed free-byte sum.

## Current work

The v1.9 release train is complete. Block 2.5 is housekeeping only: runtime
ranking, plan and receipt hygiene, consolidated consumption authority, public
domain/naming audits and an evidence-retention proposal. It changes no product
byte. The following v2 milestone consumes the two audit tables under separate
owner decisions.

## Evidence rules still in force

- Product evidence binds artifact SHAs, not a mutable tree.
- Claims end at the downloaded byte, not at the ELF or packer input.
- New links require complete difference attribution before qualification.
- Device claims remain device claims; host and emulator results do not replace
  hardware timing, storage, reset or keyboard evidence.
- Public refs and release assets are complete only after remote equality and
  digest-verified readback.
