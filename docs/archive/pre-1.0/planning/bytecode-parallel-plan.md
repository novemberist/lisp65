# lisp65 — Bytecode-VM + Streaming: Parallel-Plan (Claude ‖ Codex)

**Stand: 2026-07-01.** Macht `docs/bytecode-streaming-plan.md` parallelisierbar. Ziel: Claude
(Runtime, Lane K) und Codex (Compiler/Tooling/Stdlib, Lanes T+L) arbeiten **gleichzeitig und
weitgehend blockierungsfrei**, entkoppelt über einen festen Binär-Vertrag.

## Der Entkopplungspunkt: das Bytecode-Binärformat (ZUERST gemeinsam pinnen)

Alles hängt an **einem** Vertrag — solange der steht, brauchen die Lanes einander nicht:

1. **ISA** — Opcodes + Operandenformate. Basis: `../lisp64v2026/docs/bytecode-v1.md` (Opcodes 0–44
   eingefroren), angepasst an das lisp65-obj-Modell (int16 getaggt, NIL/Fixnum/Zeiger; cons-Heap).
2. **Code-Objekt-Format** — Header (Typ-Tag, Flags, Payload-Länge, Literal-Zeiger) + Payload +
   Literaltabelle (wie bytecode-v1 §Code-Objekt-Format).
3. **Code-Directory + Streaming-Layout** — wie mehrere Code-Objekte im erweiterten RAM liegen
   (flache Basisadresse je Objekt + ein hot-Index Name→(bank/offset/len)), damit der Streaming-
   Loader ein Objekt findet und sequentiell holt.

→ **Deliverable P0 (gemeinsam, klein, blockiert alles):** `docs/bytecode-abi.md` = eingefrorener
Vertrag (ISA-Tabelle + Byte-Layouts + Directory-Format). Danach ist Cross-Lane-Kopplung nur noch
dieser Vertrag + die goldenen Testvektoren (unten).

## Lane K — Claude — Runtime-Engine (`src/**`)

- **K1 VM-Kern:** C-Bytecode-VM (Dispatch-Schleife, Wert-Stack, Opcodes), operiert auf dem
  **hot cons-Heap** (bestehende hot-Accessoren). Neu in C (alte 25k-Zeilen-ACME-VM wird NICHT
  portiert — nur der ISA-Vertrag). Validierbar gegen **hand-geschriebenen** Bytecode.
- **K2 Streaming-Loader:** Code-Objekte flach im erw. RAM; ein kleiner hot-Puffer wird per
  **Bulk-DMA** sequentiell nachgefüllt (PC über flache Code-Adresse). Nur seicht/bulk = HW-🟢.
- **K3 Integration:** VM-Dispatch aus REPL/eval für kompilierte Funktionen; Laufzeit-Daten hot.
- **Braucht von Codex:** nichts zum Start außer P0 — K testet gegen hand-geschriebene Bytecode-
  Objekte. Später gegen Codex' Compiler-Ausgabe.

## Lane T — Codex — Compiler + Tooling (`tools/host-lisp/**`, `scripts/**`, `Makefile`, `docs/**`)

- **T1 Compiler:** Host-Lisp → Bytecode (Python), Vorlage `../lisp64v2026/tools/host-lisp/phase4_*.py`,
  emittiert das P0-Code-Objekt-Format.
- **T2 Host-VM + Disassembler (der Schlüssel zur Entkopplung):** eine **Referenz-VM in Python**
  (Vorlage `phase4_vm.py`) + Disassembler. Damit validiert Codex Compiler **und** Stdlib komplett
  **ohne** Claudes C-VM. Erzeugt die **goldenen Testvektoren** (s.u.).
- **T3 Build/Embed:** Stdlib → Bytecode kompilieren, als Code-Directory ins erw.-RAM-Abbild des
  mega65-Builds einbetten (analog heutigem `-DLISP65_WITH_PRELUDE`, nur Bytecode).
- **T4 Harness:** Bytecode-Smokes (Host-VM-Oracle + xemu + HW-Dry-Run), Drift-Check ISA↔Doc.

## Lane L — Codex — Stdlib-Quelltext (`lib/**`)
- **L1:** die CL-nahe Stdlib, die zu Bytecode kompiliert wird (Codex arbeitet daran bereits).

## Die Cross-Lane-Naht: goldene Bytecode-Testvektoren
Kleine Programme als **{Quelltext, erwarteter Bytecode (hex), erwartetes Ergebnis}**, abgelegt unter
`tests/bytecode/` (Lane T). Vertrag:
- Codex' Compiler muss den erwarteten Bytecode erzeugen; Codex' Host-VM das erwartete Ergebnis.
- **Claudes C-VM muss für denselben Bytecode dasselbe Ergebnis liefern.**
Das ist der einzige Sync, den beide Lanes teilen — kein tägliches Aufeinander-Warten.

## Reihenfolge / Sync
1. **P0 gemeinsam** (bytecode-abi.md) — kurz, blockiert beide. Interface-Header-Regel gilt
   (in collaboration.md ankündigen).
2. **Parallel:** Claude K1→K2→K3; Codex T1+T2 (Compiler+Host-VM), dann T3/T4 + L1.
3. **Integration** an den goldenen Vektoren; danach Stdlib-Teilmenge end-to-end.
4. **HW-Gegenprobe je Stufe** (xemu = Smoke, **HW = Schiedsrichter** — der DMA-Extended-Heap war
   xemu-grün/HW-rot; nichts gilt als fertig ohne Geräte-Bestätigung).

## Was zuerst zu tun ist
- **Claude:** P0-Entwurf schreiben (ISA aus bytecode-v1 + Code-Objekt/Directory-Format), dann K1.
- **Codex:** P0 mitreviewen/pinnen, dann T1+T2 (Compiler + Host-VM) gegen erste goldene Vektoren.
