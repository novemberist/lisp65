# MVP Ship

Stand: 2026-07-06, superseded 2026-07-08. Dieses Dokument beschreibt den alten
`einsuite-full`-Ship-Pfad. Der aktuelle MVP-Ship ist die Workbench; siehe
`docs/project-status.md` und `docs/workbench-gate.md`.

Historisch baute `make mvp-ship` das MEGA65-PRG plus ein extern vorgeladenes
Bytecode-Stdlib-EXT-Image:

- Boot: natives MEGA65-Produktprofil `mvp-vm-stdlib-einsuite-full`
- Stdlib/IDE/lcc: kompilierte Bytecode-Funktionen als separates EXT-Artefakt
- Laufzeit: EXT-Image wird vor dem PRG per `etherload -b 0x050000` ins erweiterte RAM geladen
- Aufruf: REPL/Eval laufen lcc-first ueber Bytecode; Treewalk ist im Produktprofil gestripped
- Disk-I/O: F011 `(load)` und `(save)` sind resident
- Render: nativer Bulk-Render via `screen-write-string`

Der Dateiname dieses Dokuments bleibt vorerst aus Historiengruenden erhalten. Der alte
`interim-ship`/Prelude-only-D81-Pfad ist nur noch Referenz und kein MVP-Gate.
Die detaillierten Referenzwerte weiter unten stammen teilweise aus dem frueheren
VM-Stdlib-Ship und sind historische Messwerte; die maschinenlesbare Wahrheit fuer den
aktuellen Ship steht in `build/ship/mvp-vm-manifest.txt` und
`build/ship/mvp-vm-stdlib-footprint.txt` nach `make mvp-ship`.

## Bauen

```sh
make check
make mvp-ship
```

Artefakte:

- `build/ship/lisp65-mvp-vm-stdlib.prg` — historisches einsuite-full-MVP-PRG
- `build/ship/lisp65-mvp-vm-stdlib.blob.bin` — EXT-Preload-Image: Codeobjekte ab `0x050000`,
  Metadata-Trailer im generierten Full-Blob
- `build/ship/mvp-vm-manifest.txt` — Build- und Deploy-Metadaten
- `build/ship/mvp-vm-stdlib-footprint.txt` — PRG-/Stdlib-Footprint

Das native Build-Profil ist:

```text
M65VMSTDLIB_CFLAGS=-Oz -Wall
HEAP_CELLS=254
MAX_SYM=192
NAMEPOOL=2048
GC_ROOTS=112
defines=-DLISP65_VM -DLISP65_EMBED_STDLIB -DLISP65_EMBED_DMA
        -DLISP65_SYMPOOL_EXT
        -DLISP65_BYTECODE_STDLIB_EMIT_METADATA
        -DLISP65_STDLIB_EXTERNAL_BLOB -DLISP65_STDLIB_BOOT_OVERLAY
        -DLISP65_MARK_BITMAP
min_stack_gap_bytes=1200
min_boot_stack_gap_bytes=512
max_prg_file_end=0xc000
```

Aktueller Referenz-Footprint:

```text
status=ok
prg_bytes=40918
prg_load_addr=0x2001
prg_payload_bytes=40916
prg_file_end=0xbfd5
prg_file_end_status=ok
heap_cells=254
stdlib_external_blob=1
stdlib_boot_overlay=1
heap_start=0xb10c
stack_addr=0xd000
stack_gap_bytes=7924
stack_gap_status=ok
noinit_start=0xb107
noinit_end=0xb10b
noinit_bytes=4
boot_overlay_start=0xb10c
boot_overlay_end=0xbfd5
boot_overlay_bytes=3785
noinit_overlay_gap_bytes=1
noinit_overlay_status=ok
boot_stack_gap_bytes=4139
boot_stack_gap_status=ok
boot_budget_status=ok
boot_required_symbols=157
boot_max_sym=192
boot_sym_headroom=35
boot_required_namepool_bytes=1344
boot_namepool=2048
boot_namepool_headroom=704
objects=116
functions=116
cases=159
code_bytes=2870
blob_end_addr=0x050b36
external_image=build/bytecode/stdlib-p0.ext.bin
external_image_bytes=6934
external_metadata_addr=0x050b36
external_metadata_offset=2870
external_metadata_bytes=4064
directory_bytes=812
literal_nodes=124
literal_patches=124
```

Die Testcases werden nicht in das Produkt-PRG oder Blob eingebettet. Sie bleiben
Host-/Oracle-Coverage; das Produkt-Blob enthaelt nur die Stdlib-Codeobjekte. Das PRG
enthaelt aktuell noch die Boot-Metadaten, die der native Materializer fuer Literal-Patches und
`T_BCODE`-Registrierung braucht; dieselben Daten liegen parallel im EXT-Metadata-Trailer.

Footprint-Tradeoff 2026-07-02: Die CL-nahen Output-Funktionen (`princ`, `prin1`,
`print`, `terpri`, `write*`) liegen als Kern-Primitive im MVP. Dafuer ist das
`format`-Subset aktuell nicht im Produkt-Embed enthalten; es bleibt separat
host-/bytecode-getestet und kann wieder ins Embed, sobald Bank-0/Overlay-Headroom
verfuegbar ist.

## Deploy / Run

Dry-run ohne Hardware:

```sh
make hw-smoke-vm-stdlib-dry-run
```

Echte Hardware:

```sh
make hw-smoke-vm-stdlib
```

Automatischer sichtbarer Stdlib-Selftest auf echter Hardware:

```sh
make hw-smoke-vm-stdlib-selftest
```

Dieser Target baut `build/lisp65-mega65-vm-stdlib-hw-selftest.prg`, laedt vorher das
Stdlib-Blob nach `0x050000` und evaluiert dann 11 feste
Stdlib-Formen ohne interaktive Eingabe. Erwartung am Geraet:

```text
gruen: lisp65 hw-selftest PASS 11/11
rot:   lisp65 hw-selftest FAIL ...
```

Optional direkt ueber das Script:

```sh
scripts/hw-smoke-vm-stdlib.sh --no-build --ip 'fe80::...%eth0'
scripts/hw-smoke-vm-stdlib-selftest.sh --no-build --ip 'fe80::...%eth0'
```

Der Wrapper nutzt `scripts/run-on-mega65.sh`, laedt zuerst das Blob per
`etherload --halt -b 0x050000` und startet danach das PRG per `etherload -r`.
Die lokale `etherload`-Hilfe unterstuetzt `-b|--bin <addr>` mit Hex-Adresse; der konkrete
Zwei-Transfer-Ablauf muss beim ersten echten Hardwarelauf trotzdem bestaetigt werden. Vor einem
echten Lauf muss der MEGA65 im Remote-Modus sein.

Manuelle REPL-Pruefpunkte nach Boot:

```lisp
(length '(1 2 3))              ; => 3
(nth 2 (list 7 8 9 10))        ; => 9
(length (reverse '(1 2 3 4)))  ; => 4
```

## Verifikation

Regelmaessig auszufuehren:

```sh
make check
make bytecode-p0-stdlib-artifacts
make mvp-ship
make hw-smoke-vm-stdlib-dry-run
make hw-smoke-vm-stdlib-selftest-dry-run
```

`make check` ist ein MEGA65-MVP-Gate und fuehrt keine C64/GO64-Smokes aus. Es baut
den Selftest und prueft dessen Etherload-Kommando per Dry-Run, startet aber keine
echte Hardware und keine xmega65-Session. Alte C64-Harnesses sind nur noch ueber
`make legacy-c64-check` erreichbar.

`make bytecode-p0-stdlib-artifacts` ist die goldene Referenz fuer den nativen Loader:
Manifest+Blob werden hostseitig rekonstruiert, Literale ueber die Patch-Tabelle
materialisiert, und alle Stdlib-Cases laufen durch die Host-VM. Der C-Materializer muss
dieselben gepatchten Objekte liefern.

## Historische Pfade

Diese Targets und Dokumente bleiben fuer Referenz/Rueckbau im Repo, sind aber kein
aktueller Ship-Pfad:

- `make interim-ship` — alter Prelude-only-PRG+D81-Pfad
- `make f011-*`, `stdlib-d81`, F011-Profilmatrizen
- native Disk-`load`, F011/SD/FAT, `ship-readiness`
- Bank-0-Heap- und DMA-Extended-Heap-Experimente

Referenzen:

- `docs/bytecode-embed-loader.md`
- `docs/bytecode-abi.md`
- `docs/extheap-alternatives.md`
- `docs/mega65-file-io-research.md`
- `docs/f011-stdlib-binding-gap.md`
