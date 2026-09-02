# REPL Boot Banner: “λ LISP65”

Status: the originally authorized implementation was rejected by real-hardware
visual acceptance on 2026-07-16. The corrected block-lambda rendering and its
incremental capacity delta were hardware-accepted and owner-authorized the same
day. Product promotion is allowed; the regular wave repin remains outstanding.

## Appearance

The banner occupies rows 0–7 on the first REPL start. The first prompt is on
row 9.

```text
  ██           ██      ████    ██████   ██████    ██████   ██████
   ██          ██       ██     ██       ██  ██    ██       ██
    ██         ██       ██     ██████   ██████    ██████   ██████
    ███        ██       ██         ██   ██        ██  ██       ██
  ██  ██       ██       ██         ██   ██        ██  ██       ██
 ██    ██      ██████  ████    ██████   ██        ██████   ██████
 ──────────────────────────────────────────────────────────────────
                                            WORKBENCH - DIALECT V2
```

- The explicit coordinate table is normative where the prose art differs.
- The lambda uses yellow reverse-video spaces as a six-row staircase. This is
  deliberately charset-independent: in the product's mixed-case charset,
  screen codes 77 and 78 are the letters `M` and `N`, not diagonal graphics.
- Block letters use reverse-video spaces through `scr_put_at` attribute bit 7
  and white color 1.
- The separator uses screen code 64 in columns 1–66. `screen-put-char` owns
  each light-gray color store and a following raw screen-byte write publishes
  the line glyph through the pinned Workbench contract (`$0800`, 80 columns).
  The canonical Workbench does not enable the resident
  `LISP65_SCREEN_WRITE_STRING` capability, so the banner must not depend on
  CALLPRIM 12.
- The subtitle is light gray and starts at column 44. The ASCII hyphen is the
  accepted 1.1 rendering. A middle dot remains a cosmetic follow-up until its
  PETSCII mapping is measured and pinned rather than guessed.
- Letter starts: L=15, I=23, S=29, P=37, 6=45, 5=53. S and 5 deliberately
  share a glyph.
- Lambda runs `(row: column,length)`: `0:2,2`; `1:3,2`; `2:4,2`;
  `3:4,1 + 5,2`; `4:2,2 + 6,2`; `5:1,2 + 7,2`.

## Implementation contract

The banner body is Lisp compiled by lcc and executed by the product VM. A
minimal native seam is unavoidable because the native REPL owns both
`scr_init()` and the first prompt. After `scr_init()` and before that prompt,
the seam calls `%repl-banner` through
`LISP65_BYTECODE_STDLIB_REPL_BANNER_ENTRY`.

The existing stdlib generator emits that ordinal from the same function list
that emits the directory; no handwritten ordinal is allowed. This is a launch
seam, not a second banner implementation.

The corrected compact ASCII run stream is decoded by three persistent internal
entries:

- `%banner-separator`: 89 bytes;
- `%banner-run`: 142 bytes;
- `%repl-banner`: 145 bytes.

`%banner-runs` and `%banner-subtitle` are private-inline helpers. The three
persistent entries are neither public nor exported. The original authorized
banner already moved aligned resident use from 208 to 216. The correction adds
one raw entry (210 to 211) but remains within the same 216-entry alignment
bucket, so post-alignment directory headroom stays at 168.

The REPL cursor, floor, limit and status values are byte-sized. Every product
profile is bounded by `REPL_BUF_MAX <= 255`, and the preprocessor rejects
values outside 2–255. This correction pays for the launch seam and moves the
overlay base from `$c354` to `$c304`.

## Measured capacity

The real product link supersedes the original 150–200-byte estimate.

| Dimension | Baseline | Banner candidate | Delta |
|---|---:|---:|---:|
| Post-boot Bank-0 reserve | 1,795 B | 1,876 B | +81 B |
| Standard-composition EXT headroom | 25,537 B | 25,186 B | −351 B |
| Symbol headroom | 391 | 389 | −2 |
| Name-pool headroom | 5,668 B | 5,643 B | −25 B |
| Directory post-align headroom | 176 | 168 | −8 |
| Overlay headroom | 2 B | 82 B | +80 B |
| Boot-overlay size | 1,669 B | 1,669 B | ±0 |

The hardware correction is measured separately against that authorized banner
candidate:

| Dimension | Authorized banner | Corrected candidate | Increment |
|---|---:|---:|---:|
| Post-boot Bank-0 reserve | 1,873 B | 1,873 B | ±0 |
| Standard-composition EXT headroom | 25,186 B | 25,161 B | −25 B |
| Symbol headroom | 389 | 388 | −1 |
| Name-pool headroom | 5,643 B | 5,625 B | −18 B |
| Directory post-align headroom | 168 | 168 | ±0 |
| Overlay headroom | 80 B | 80 B | ±0 |
| Boot-overlay size | 1,669 B | 1,669 B | ±0 |

The boot overlay is not byte-identical: its absolute relocations change when
the VMA moves from `$c354` to `$c304`. Its source, size and control-audit shape
remain unchanged; the wave product repin owns the new SHA.

## Acceptance gates

- `make v11-repl-banner-visual-check` executes the real generated banner in
  the P0 VM and rejects mutations to screen writes, primitive-call shape,
  separator pokes, prompt advance, or return value.
- `make v11-repl-banner-vm-check` executes the generated Workbench artifact in
  the native C VM with ASAN/UBSAN and derives the optional
  `screen-write-string` capability from the actual product profile. It rejects
  a banner that only works because a host test invents an unavailable product
  primitive.
- The oracle pins 235 visible writes: 147 lambda/letter cells, 66 separator
  cells, and 22 subtitle cells. It also pins nine linefeeds and prompt row 9.
- The REPL screenshot verifier is row-agnostic and carries a banner-prefix
  self-test; it does not assume a row-0 prompt.
- The canonical differential link must reproduce every authorized capacity
  value above.
- A real-hardware screenshot is mandatory for visual acceptance. The corrected
  probe is bound by SHA-256
  `7bc0ff2468c8dcbd089f000422dc62f4f607f2e7394ae04790f06ef4d3725e6c`;
  it shows the full block lambda, wordmark, separator, subtitle, and clean first
  prompt. Wave 1 may not seal until the corrected sources are promoted into the
  candidate consumed by the regular repin.
- The regular R4/R5/R6 repin and single-device G6 remain mandatory.

The banner remains product-authored: after the minimal generated launch seam,
its complete appearance is drawn by Lisp code compiled by lcc and run by the
Workbench VM.
