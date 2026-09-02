# First-class byte-buffer contract

Status: 1.1-E probe contract; not promoted until its block receipt is accepted.

The optional `buffer` shelf library provides the public API. Its native
carriers are internal CALLPRIMs and are deliberately unavailable through
`funcall`, `apply`, `function-kind`, or the device compiler.

## Public API

- `(bufferp value)` returns canonical `t` or `nil`.
- `(make-buffer length)` allocates a zero-filled mutable byte buffer.
- `(buffer-length buffer)` returns its fixed length.
- `(buffer-ref buffer index)` reads one byte.
- `(buffer-set! buffer index byte)` writes one byte and returns that byte.
- `(string->buffer string)` creates an independent mutable copy.
- `(buffer->string buffer)` transfers ownership by atomically freezing the
  same allocation as an immutable string. The old value is no longer a
  buffer; subsequent buffer operations on it are type errors.

Printing a buffer emits the opaque marker `?`. The marker deliberately exposes
neither length nor payload and is not a readable representation. Unknown heap
object kinds use the same fail-closed marker; in particular, neither a buffer
nor an unknown kind may enter the list printer.

Indexes are zero-based, matching `search`, `position`, and `string-ref`.
Indexes outside `[0, length)`, non-buffer operands, negative lengths, and
values outside `0..255` are type errors. Public functions have strict arity.
Allocation failure is fail-closed: no partial buffer or string is published.

## Memory and loading

The object handle is a stable heap cell. Its contiguous bytes live in the
compacted string arena and may be relocated by collection while the handle is
updated. Buffer and string bytes are therefore suitable for bulk DMA without
returning to one-cons-per-byte representations.

All public wrappers and their names live in the `buffer` L65M container in the
Attic library shelf. The resident product contains only a compact transport
facade; loading the optional library consumes normal session code, directory,
symbol, name-pool, and arena capacity. L65S-v2 has four descriptors and a
strict 160-byte payload offset; v1 shelves are rejected by the v2 decoder.

## Evidence requirements

- Product C carrier tests cover GC relocation, zero fill, mutation, bounds,
  strict arity/type checks, destructive freeze, copy isolation, and OOM.
- A separately implemented Python P0 model runs all public wrapper cases.
- The private carrier IDs are classified by the native-function registry and
  must remain complete in CALLPRIM while explicitly absent from the three
  restricted views.
- Promotion requires `ext_delta <= 0` for the standard composition. Optional
  loading cost is reported separately and is not resident EXT expenditure.
