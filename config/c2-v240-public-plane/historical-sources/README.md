# Historical export provenance sources

`defstruct-d13bd166.lisp` is `lib/defstruct.lisp` as committed in `d13bd166`
(SHA-256 `11c9ef05…`). The 2.2.0 and 2.3.0 public plane projections declare
their serialized `defstruct.blob.bin` as built from exactly these bytes. The
live `lib/defstruct.lisp` changed later (Definitions Set A), so the 2.4.0
public export binary contract points those two historical declarations here
and records the superseded live path. This file is provenance only; no 2.4.0
build consumes it.
