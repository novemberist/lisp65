# lisp65 — Paralleler Arbeitsstand Richtung MVP

> **Status 2026-07-08:** Dieses Dokument ist historischer Parallelplan. Die
> aktive Produktstrategie steht in `docs/profile-consolidation-strategy.md`;
> die organisatorische Umstellung auf Codex Lead steht in
> `docs/project-lead-transition-plan.md`.

Stand 2026-07-06. Dieses Dokument fasst den damaligen MVP-Pfad zusammen. Die
aktuelle Arbeit steht in `docs/project-status.md`; neue Handoffs landen nur noch
kurz in `docs/collaboration.md`.

## Historische MVP-Definition vom 2026-07-06

Der MVP-Ship ist das **einsuite-full MEGA65-PRG plus extern vorgeladenes Bytecode-Stdlib-EXT-Image**:

```sh
make mvp-ship
```

Artefakte:

- `build/ship/lisp65-mvp-vm-stdlib.prg`
- `build/ship/lisp65-mvp-vm-stdlib.blob.bin`
- `build/ship/mvp-vm-manifest.txt`
- `build/ship/mvp-vm-stdlib-footprint.txt`

Das PRG enthaelt das M4-Full-Profil: IDE, selbstgehosteter lcc als einziger Evaluator
im Geraeteprodukt, residenter F011-load/save-Stack und nativer Bulk-Render. Das EXT-Image
wird vor dem PRG per `etherload -b 0x050000` ins erweiterte RAM geladen und registriert die
kompilierten Stdlib-/IDE-/lcc-Funktionen als `T_BCODE`.

Disk-I/O ist Bestandteil dieses MVPs. Der Disk-Roundtrip ist auf echter MEGA65 mit pass 17/17
validiert; autonome xemu-F011-Smokes bleiben getrennt als Umgebungs-/Harness-Thema.

## Bereits erreicht

- Bytecode-ABI P0 ist gepinnt: `docs/bytecode-abi.md`.
- Embed-/Loader-Vertrag ist spezifiziert: `docs/bytecode-embed-loader.md`.
- K-Lane: VM-Kern, Streaming, Eval-Bridge, Embed-Loader und Literal-Materializer sind
  gelandet und auf echter MEGA65-Hardware bestaetigt.
- L/T-Lane: Stdlib-P0-Artefakt, Host-Compiler/Host-VM-Oracle, Embed-Oracle und
  Drift-Checks stehen.
- T-Lane: `make mvp-vm-stdlib-einsuite-full`, Footprint-Report, `make mvp-ship` und
  `make hw-smoke-vm-stdlib-dry-run` bilden den aktuellen Ship-Pfad.

Aktuelle Referenzwerte:

```text
prg_bytes=40918
prg_load_addr=0x2001
prg_file_end=0xbfd5
prg_file_end_status=ok
heap_cells=254
max_sym=192
namepool=2048
gc_roots=112
stack_gap_bytes=7924
stack_gap_status=ok
noinit_overlay_gap_bytes=1
noinit_overlay_status=ok
boot_overlay_bytes=3785
boot_stack_gap_bytes=4139
stdlib_objects=116
stdlib_cases=159
code_bytes=2870
external_image_bytes=6934
external_metadata_addr=0x050b36
external_metadata_bytes=4064
directory_bytes=812
literal_nodes=124
literal_patches=124
```

## Aktive Nachlaufarbeit

Diese Punkte duerfen parallel laufen, solange die Lane-Regeln eingehalten werden:

- **Ship-Pfad haerten:** `make mvp-ship`, Manifest, Full-Footprint und HW-Dry-Run gruen
  halten.
- **MEGA65-GC-Regression:** `make xemu-mega65-prelude-gc-smoke` baut den nativen
  mega65-GC-Stress-Smoke (`HEAP_CELLS=320`). Der Target ist bewusst noch nicht Teil
  von `make check`, weil der lokale xmega65-MEGA65-Dump-Pfad timeoutet/keinen Dump
  liefert. Historische C64/GO64-Smokes liegen nur noch unter `legacy-xc64-*` und sind
  kein Standard-Gate.
- **HW-Smoke buendeln:** echte Hardware-Runden ueber `make hw-smoke-vm-stdlib`, mit
  den dokumentierten REPL-Pruefpunkten aus `docs/interim-ship.md`.
- **Stdlib-Coverage erweitern:** neue Faelle in `tests/bytecode/stdlib/**` ergaenzen,
  solange `bytecode-p0-stdlib-embed-check` gruen bleibt.
- **VM-Diagnostik:** kompakte Runtime-Statusmeldungen im Ship, ausfuehrliche
  PC/Opcode/Stack/Funktionsdiagnose in Diagnose-Builds (`LISP65_VM_DIAGNOSTICS`).
- **Doku sauber halten:** alte Prelude-only-/F011-/Heap-Dokumente als Referenz
  markieren, aber nicht zum MVP-Gate machen.

## Geparkte Historie

Nicht weiter fuer den MVP ausbauen:

- natives Disk-`(load)`, F011/SD/FAT, D81-Runtime-Load
- `ship-readiness`-/F011-Profilmatrizen
- Bank-0-Heap-Ausbau als Voraussetzung fuer volle Lisp-Source-Einbettung
- DMA-Extended-Heap als wahlfreier Runtime-Objektheap
- der alte Prelude-only-Ship als Produktpfad

Diese Arbeit bleibt dokumentiert, aber geparkt:

- `docs/mega65-file-io-research.md`
- `docs/f011-stdlib-binding-gap.md`
- `docs/extheap-alternatives.md`
- `docs/mega65-extram-access.md`
- `docs/interim-ship.md` Abschnitt "Historische Pfade"

## Standard-Gates

`make check` ist ein MEGA65-MVP-Gate: Host-/Bytecode-Oracles, nativer
MEGA65-VM-Compile-Check, Host-VM-Smoke, `make mvp-ship` und
`make hw-smoke-vm-stdlib-dry-run`. Es fuehrt keine C64/GO64-Smokes aus.
Alte C64-Harnesses sind explizit als `make legacy-c64-check` isoliert.

## Lane-Grenzen

| Lane | Eigentum | Aktueller Fokus |
| --- | --- | --- |
| K | `src/**` | Runtime/VM/Loader/Kernel-Diagnostik |
| L | `lib/**`, `tools/host-lisp/**`, Lisp-Test-Fixtures | Stdlib-Semantik und Coverage |
| T | `scripts/**`, `Makefile`, `docs/**`, Harness | Ship-Pfad, Reports, HW-Smokes, Doku |

Cross-Lane-Regel: `src/*.h`-Aenderungen vorher in `collaboration.md` ankuendigen;
Makefile-/Harness-Aenderungen mit Blick auf K/L-Targets klein halten. Vor Commits:
`make check`, sync/rebase, nochmal `make check`.
