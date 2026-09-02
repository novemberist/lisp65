# C2-lite Bank-2/3 Chip-RAM hardware prefilter result

Status: **passed receipt-less prefilter; non-product and non-promotable**

Date: 2026-07-21

This is the separate hardware-evidence layer for the Bank-2/3 ownership audit
and C2-lite execution addendum. It does not turn the prefilter into an
authoritative chain receipt and makes no product, capacity, latency or
promotion claim.

## Bound target

- Proof target SHA-256:
  `d1db86361d4ac51e89fc665a466b2b6dc7b7ac541574f45770252989870c2f23`
  (5,580-byte standalone PRG).
- Static report:
  `build/c2-lite/chipram-proof/hardware-pass-20260721/static-report.json`,
  SHA-256
  `4b97b66a3bed86f3cb65a32aceaa419ddd7d3fbc68b7133d6d5a7c2af3537dfd`.
- The report binds the source audit SHA-256
  `4977e82bfd92391bbdf58adb9b4e7064cfa4d49557c62840471a56bf27ebbec6`
  and reviewed reconstruction memo SHA-256
  `631b4aa06f451cb48cae577b9ba4da8993f6abcb74bcad16d7a09aee817a36fa`.
- Pinned chipset-reference SHA-256:
  `107610ae3ea9f7e3f1e78915dcbe2cae1a6f404ca2e538762524a7e58cced220`.
- Audited current core source commit:
  `a9158930665763c592d004c895d52eff4a9eefc3`.

The proof contains no Attic endpoint. It installs its owned `$e000` window by
CPU stores and submits the same 12-byte F018A list through `$d700` as the
product path. Every destination is poisoned before submission; the first CPU
observation after return decides, with no retry, delayed comparison or
convergence fallback.

## Device run

The first manual run reached the green page but the number of `F` keypresses
was uncertain, so it is not the bound observation. The exact same binary was
restarted. In the second run the operator opened and exited the Freezer,
pressed `F` exactly once, observed about two seconds of complete post-return
verification, then saw a green frame and
`PASS - RECEIPT-LESS PREFILTER`.

The device identity captured before that run was:

- core register bytes `6b4cb203`, core `git-03b24c6b`;
- machine serial `TE0000B18447`.

Xemu was not run and is explicitly non-authoritative.

## Results

| Requirement | Observation |
|---|---|
| immediate transfer cases | 12/12 passed |
| delayed successes | 0 |
| lengths | 1, 7, 16, 127, 128, 1,761 and 1,781 B |
| per-case raster deltas | `0,0,1,1,0,0,0,0,0,0,2,1` |
| Bank 2 full identity | CRC-16 `$e3ad`, exact 64 KiB |
| Bank 3 Boot identity | CRC-16 `$f053` before replacement |
| Bank 3 Session identity | CRC-16 `$f37b`, exact 64 KiB |
| native lifetime | Boot generation 1 invalidated; Session generation 2 published |
| stale Boot binding | rejected |
| owned IRQ/NMI/frame source | passed |
| Freezer identity | 2/2 full banks plus owned window passed |
| post-Freezer writeability | 2/2 banks passed |
| Bank 1 | untouched by the complete DMA inventory |

The read-only observation is
`build/c2-lite/chipram-proof/hardware-pass-20260721/hardware-observation.json`,
SHA-256
`e89bb4980ede2c932745eb020a62bc135cec4464f0ebff83e406282575d80c55`.
Its bound captures are:

| Capture | Bytes | SHA-256 |
|---|---:|---|
| mailbox | 256 | `60cb3f25eea6a7f6b4116e158cee169241290fcdc326f0a22bb09c43097559f1` |
| Bank 2 | 65,536 | `392d864545a2d71f67278308ee165036ef8fea5dca1f31daa220630217a13988` |
| Bank 3 Session | 65,536 | `dd6155e93045b1a1b1c582bfe35cfe639b6a45d609dd9ef3b6a388a04b7bbbd3` |
| core registers | 4 | `bd075eada684d364ddb275c939b000db0fddec2bd491a0f8628b280e9026cb53` |

The copies in `hardware-pass-20260721` are mode `0444`; later build reports
cannot rewrite the bound observation.

## Disposition

The hardware prerequisite for C2-lite Option A is green on this device/core.
The subsequent Class-C review approved the addendum's corrected C2D-v6 root
surrogate and authorized its host/product-shaped probe. This prefilter remains
receipt-less and non-authoritative; it authorizes no product link by itself.
