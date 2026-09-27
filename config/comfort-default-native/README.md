# Comfort default native authority (pending)

This overlay inherits the consumed 2.4.0 Final, not working HEAD's native
feature population. `manifest.json` binds the exact predecessor, replacement
`sources/repl.c`, include closure and linker authority.

Phase A r2 replaces symbol lookup with direct volatile byte access.
`storage-owner-r2.json` records the one-byte high-BSS owner in
`linker/full-map-linker/c.ld`: 9 bytes remain, above the inherited floor of 5.
The generated Lisp address comes from this linker declaration. The new
`.bss.lisp65_comfort_state` input is claimed before the ordinary BSS wildcard;
the output lies at the end of the startup-zeroed high-BSS span.

`AUTH_PENDING` / `DIFF_BASE` identify the incoming HEAD; these edits are an
uncommitted overlay. For object-only verification run:

```
PYTHONDONTWRITEBYTECODE=1 python3 build/comfort-default-r2/verify-r2.py
```

Projection: .text +12, .rodata +0, BSS +1; no new native callee.
No product link, Seed, runtime acceptance or LTO price is claimed.
See the appended r2 section in `build/comfort-default-r1/preflight-report.md`.
