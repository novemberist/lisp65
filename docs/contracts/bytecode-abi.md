# Bytecode ABI extensions

Status: living contract for ABI additions after the frozen pre-1.0 baseline.

The opcode and Prim-ID assignments in
`docs/archive/pre-1.0/contracts/bytecode-abi.md` remain immutable. This
document extends that baseline without renumbering or reinterpreting any
published assignment. Opcode IDs and Prim-IDs are separate 8-bit namespaces.

## Opcode extensions

| Opcode | Mnemonic | Operand | Profile | Contract |
| ---: | --- | --- | --- | --- |
| 20 | `LOGAND` | none | dialect-v2 | Strict binary signed-15-bit bitwise AND |
| 21 | `LOGIOR` | none | dialect-v2 | Strict binary signed-15-bit bitwise OR |
| 22 | `LOGXOR` | none | dialect-v2 | Strict binary signed-15-bit bitwise XOR |
| 23 | `ASH` | none | dialect-v2 | Arithmetic right shift; checked left shift; count -14..14 |

The four identities remain reserved in dialect-v1. A dialect-v1 decoder
therefore rejects them even though the shared ledger retains their permanent
names.

## Prim-ID extensions

CALLPRIM uses stable IDs. New IDs are appended and must be represented in the
ABI ledger, the independent P0 model, and the product VM dispatch. Internal
carrier names beginning with `%` are not public Lisp API merely because they
have a stable ABI identity.

| Prim-ID | Primitive | Profile | Contract |
| ---: | --- | --- | --- |
| 63 | `%buffer-read` | dialect-v2 | Internal first-class-buffer read carrier |
| 64 | `%buffer-write` | dialect-v2 | Internal first-class-buffer mutation carrier |
| 65 | `%buffer-alloc` | dialect-v2 | Internal first-class-buffer allocation carrier |
| 66 | `%c2-control` | dialect-v2 | Internal C2 compiler lifecycle carrier |
| 67 | `%c2d-byte` | dialect-v2 | Private read-only byte window over the published 33,840-byte C2D plane |
| 68 | `intern` | dialect-v2 | Public canonical string-to-symbol operation |

Prim-IDs 69 through 255 remain reserved. The three buffer carriers are
CALLPRIM-only and are deliberately excluded from `apply`, `function-kind`,
and compile-REPL views. Public buffer operations are supplied by the optional
prebuilt `buffer` shelf library. `%c2-control` is likewise CALLPRIM-only; it
owns the exact load, validation, retirement, and abort cleanup of the temporary
compiler tier and is not a public Lisp API. `%c2d-byte` is available only to
prebuilt Bank-2 orchestration: it accepts two strict byte-domain operands
`(lo hi)`, rejects offsets at or above 33,840, reads exactly one byte through
the existing `c2_stream_c2d_read` seam, and returns that byte as a Fixnum. It
owns no resolver policy, write path, registry, string protocol, or overlay
roundtrip and is excluded from `apply` and `function-kind`.
`intern` accepts exactly one string of at most 33 bytes and returns the
canonical interned symbol.  It is public through direct, `funcall`, `apply`,
`function-kind`, and compile-REPL views; every view consumes the same native
function registry row.

## Compatibility

- The frozen dialect-v1 allocation remains unchanged; Prim-IDs 23 through
  255 stay reserved in that profile.
- A dialect-v2 decoder must retain the canonical names for IDs 63 through 68
  even when the optional public library is not loaded.
- Future additions append IDs at 68 or above and update this contract and all
  parity gates in the same change.
