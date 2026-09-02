# lisp65 — Speicher- & Stack-Modell (Stand & §4.3-Pfad)

Stand: 2026-06-30. Befunde aus der Phase-1-Arbeit; relevant für beide Lanes.

## Historisches Speichermodell (llvm-mos, default, 2026-06-30)
- Damals nutzten `mos-c64` und `mos-mega65` **nur Bank 0** (`$2001–$D000`, ~44 KB).
  Das heutige Standard-Gate ist MEGA65-only; C64/GO64-Smokes sind `legacy-xc64-*`.
  Die **8 MB des MEGA65 liegen brach** (default-Build adressiert sie nicht).
- `mos-mega65` zielt auf **`-mcpu=mos45gs02`**, läuft aber im 64-KB-Speichermodell.
- **Soft-Stack** (`__stack = $D000`, wächst abwärts): hält C-Locals; in der Praxis
  **leicht belegt** (fib(7)-Messung: nur ~416 B). Begrenzt durch `bss_end` darunter.
- **Hardware-Stack** (Page 1, `$0100–$01FF`, 256 B): Rücksprungadressen.
- **Heap:** `heap[HEAP_CELLS]` in Bank-0-BSS, aktuell **2048 Zellen** (`obj.h`,
  per `-DHEAP_CELLS=N` überschreibbar). Mark-Sweep-GC.

## Wichtige Lektion: Test-Harness, nicht Kernel
Frühe „GC-Bug"- und „HW-Stack-Grenze"-Diagnosen waren **falsch** — Artefakte eines
**hartkodierten Test-Sinks** (`$9000`), der je nach Build vom tiefen C-Stack bzw. vom
großen `heap[]` überschrieben wurde. Behoben: Test-Sink ist jetzt ein **statisches
BSS-Array** (`tsink_buf` in `printer.c`), Checker sucht im ganzen Dump.
**Regeln:** (1) Bei Device-Tests nie eine hartkodierte Sink-Adresse annehmen —
statisches Array + Suche-im-Dump. (2) Der **Host-Build (gcc) ist das verlässliche
Semantik-Oracle** (Kern-C ist target-unabhängig: `gcc -I src src/{mem,symbol,reader,
printer,eval}.c <main>`; Flags `-DGC_STRESS`/`-DGC_DISABLE`/`-DHEAP_CELLS=N`).

## Rekursions-Tiefe — aktueller Stand
- **Tail-Rekursion: unbegrenzt** (TCO in `eval_env`, konstanter Stack; verifiziert
  `cnt 1000` device / `cnt 200000` host).
- **Baum-Rekursion** (nicht-Tail, z. B. `fib`): läuft bis zu gesunder Tiefe
  (`fib 10` ✓ device); harte Grenze erst, wenn der Soft-Stack `bss_end` erreicht.
  Mehr Heap (größeres `HEAP_CELLS`) senkt `bss_end` → weniger Stack-Raum: Trade-off
  (3000 Zellen ⇒ nur ~1 KB Stack auf mega65, daher 2048 gewählt).

## §4.3 — Pfad zur 8-MB-Nutzung (post-MVP)
Nicht akut nötig (Bank-0-Heap reicht fürs MVP), aber der eigentliche MEGA65-Vorteil
und „wann, nicht ob". Kernpunkt ist das **Objektmodell**:
- Heute: `obj` = 16-Bit-Zellindex in ein Bank-0-Array (`CELL(o)`); 8 MB nicht erreichbar.
- Für 8 MB: Zellen im erweiterten RAM → `obj`/`CELL` brauchen **32-Bit/Far-Adressierung**
  (45GS02 flat/28-Bit) **oder** ein **Banking-Schema** (MMU / DMAgic-Kopien).
- **Zu untersuchen:** wie weit llvm-mos generische Far-Pointer/Attic-RAM unterstützt
  (SDK hat `_45E100.h`, `dma.hpp`, DMAgic). Wahrscheinlich teils manuell (DMA/Banking),
  kein freier Schalter. Berührt den **Kern** (`obj.h` + jeden Zellzugriff) → eigene
  Architektur-Etappe nach REPL/Library.

## Verwandte Hebel
- **TCO** ✓ (erledigt) — Iteration/Schleifen stack-frei.
- **Nicht-rekursive eval** (expliziter Eval-Stack im Heap) — portable Alternative für
  *sehr* tiefe Baum-Rekursion, falls je nötig; größerer Umbau.
- **45GS02-16-Bit-Stack** (E-Flag) — könnte den Page-1-HW-Stack erweitern; nur relevant,
  falls die HW-Stack-Tiefe je real limitiert (aktuell nicht der Engpass).
