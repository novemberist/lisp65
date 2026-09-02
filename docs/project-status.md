# Project Status

Updated: 2026-09-03

Current public release: **lisp65 2.0.1**

Released dialect: **Dialect V2**

Repository status: **published and download-readback verified**

This is the living summary. Release receipts and artifact hashes remain the
authority for exact identities.

## Accepted and published product

| Item | Bound value |
|---|---|
| Selected variant | v2.0 Tier-1 domain discipline + lossless native prompt editor; product bytes unchanged in 2.0.1 |
| Public `main` / tag target | `94dd2be70effdfd2f5da25946d38e5e4cbc787a9` |
| Annotated tag object | `a209f4e75b0ad3bdbbe07869296ff9787c9a9949` |
| Artifact-set SHA-256 | `29a9c3eb63c662a94a24ab9b23582eda66bea5a656912bbe4f65660f1a04c2f2` |
| Resident PRG SHA-256 | `39d317943cc4b39c2c2e8198f124ebe43708a945ba5a88dbd5296a5fc8577d25` |
| Linked ELF SHA-256 | `96ba670981172fab72383d40cf6da24d3318749d03a916014b716d4b881ecd05` |
| Product D81 SHA-256 | `7bd0cd478da52b0d731a1fd837bce16d76832b4d1ae0e836ad63209433d68f2d` |
| Work D81 SHA-256 | `bf887cd4f8b14b2e808bccfc223e64bfb1223a61e16e11169be0d34e669c63e3` |
| Product/profile build IDs | `be969ec2` / `887fc1da` |

The release was published on 2026-09-02. Four assets were downloaded afresh;
all byte counts and SHA-256 values matched. Two varied detached public-source
clones each performed one WPLTO/link and reproduced all 19 selected roles.

## Hardware boundary

v2.0 makes public library domain behavior fail explicitly:

- Twenty-one Tier-1 library functions turn 62 silently wrong domain results
  into explicit errors. `(length "abc")` raised a VM type error on the accepted
  device and returned to one live prompt.
- The hot `car`/`cdr` opcodes remain deliberately permissive: `(car 1)`
  returned the documented `nil`.
- The measured public surface is **545 error-raised / 179
  documented-permissive / 110 silently-wrong** over the same 834-cell
  population.

The release retains the v1.9 interactive properties: the native `lisp65>`
prompt owns the insertion-mode editor, and Capture with its delivered consumer
crossed a forced collection with `raw=seen=stored=taken=138`.

Release-terminal D5 measured **107 free symbol slots and 1,467 free name
bytes**, above the mandatory 32/384 floor. Four representative performance
bodies completed in at most one raster frame, and the final single-key path
measures 902 VM steps.

The claim does not include Tier-2 `car`/`cdr` checks, type-ahead during
evaluation, Comfort, balanced multiline input/history, delimiter matching,
cursor blinking, or the unresolved `$22` mechanism.

## Product composition

The product D81 contains the resident prompt editor plus IDE, IDEX and M65D;
there is no separate optional-library medium, and no other library role is
delivered. `INIT.L65` is checked once after resident readiness and before the
first banner. The release medium omits it, so ordinary boot takes the silent
absence path.

The composed Bank-2 ownership map, page-congruent MAP placement,
tuple-equals-`LOADADDR`, bound-equals-consumed headers and delivered-byte
checks remain permanent gates. Capacity is reported as owned intervals and
the largest contiguous hole, never as an uncomposed free-byte sum.

## Current work

The 2.0.1 documentation-truth update keeps the published 2.0.0 product pair
byte-for-byte and brings the user-facing bundle back onto its measured surface.
Later blocks remain subject to separate owner decisions.

## Evidence rules still in force

- Product evidence binds artifact SHAs, not a mutable tree.
- Claims end at the downloaded byte, not at the ELF or packer input.
- New links require complete difference attribution before qualification.
- Device claims remain device claims; host and emulator results do not replace
  hardware timing, storage, reset or keyboard evidence.
- Public refs and release assets are complete only after remote equality and
  digest-verified readback.
