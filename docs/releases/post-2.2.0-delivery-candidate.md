# Post-2.2.0 distribution candidate

This is a candidate note, not a release or hardware-acceptance announcement.

The obsolete disk images `IDE`, `IDEX` and `M65D` are removed, reclaiming
193 blocks. Their static implementations and the public `load-lib` routes
remain available. `BUFFER` stays: `(require "buffer")` reads this 398-byte
L65S package from the medium. All five optional packages remain delivered.

The cold-start descriptor and stager use one derived ten-role population.
`AUTOBOOT.C65` and `BOOT.ID` change together; the Lisp runtime, static IDE,
and all retained package payloads remain byteidentical to the Frame final
world. The physical cold start and the prompt-only minibuffer frame await
their joint device session. Historical release notes describe their own
media and are not rewritten by this candidate.
