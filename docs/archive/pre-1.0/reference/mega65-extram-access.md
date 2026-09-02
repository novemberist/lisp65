# MEGA65 erweitertes RAM: Zugriffs-Matrix (Heap-Skalierung)

**Status: GELÖST (xemu-verifiziert, HW-Bestätigung ausstehend).** 2026-07-01.

Ziel: den Lisp-Heap über die 64 KB der Bank 0 hinaus in das erweiterte Chip-RAM
(bis $5FFFF = 384 KB) skalieren. Der residente Kern ist in C (llvm-mos / mos45gs02)
geschrieben, daher muss der Zugriff aus C-generiertem und/oder hand-Asm-Code funktionieren.

## Das Kernproblem und seine Auflösung

Der lange Debugging-Krampf (C-Loops crashten bei Zelle ~19-36, „pure-asm" schien zu
funktionieren, Daten landeten scheinbar nicht) hatte **eine einzige Wurzel**:

> **Zero-Page-indirekte Adressierung `sta ($nn),y` / `lda ($nn),y` geht NICHT durch
> die MEGA65-MAP.** Sie trifft immer die darunterliegende Bank 0.

Damit fällt alles zusammen:
- Der „pure-asm 0 Fehler"-Beweis war eine **Illusion**: er schrieb und las via
  `($04),y` beide auf Bank-0 `$8000` (self-konsistent), erreichte nie das erweiterte RAM.
- Die C-Loop-**Crashes** kamen daher, dass die zp-indirekten Writes auf Bank-0
  `$8000`/`$A000` landeten und die **C-Runtime-Daten überschrieben** → Crash bei Zelle ~19-36.

## Zugriffs-Matrix (was erreicht erweitertes RAM, was nicht)

Alle Zeilen **direkt aus dem 384-KB-Speicher-Dump** (`xmega65 -dumpmem`) verifiziert,
nicht über emulator-interne Rücklesung (die ist teils selbst unzuverlässig, s.u.).

| Methode | Encoding | Erweitertes RAM erreicht? |
|---|---|---|
| **DMA (F018), beide Richtungen** | `$D700`-Liste, bank-Byte an dl[5]/dl[8] | **JA — bank-agnostisch, korrekt** |
| **Absolute durch MAP, WRITE** | `sta $A0xx` mit block5-MAP aktiv | JA (Write) |
| Absolute durch MAP, READ | `lda $A0xx` mit MAP aktiv | **NEIN** (xemu liefert 0/Bank-0) |
| Flat 32-bit READ | `$EA $B2 $nn` (LDA [zp],Z) | **NEIN** (xemu, liefert 0) |
| Flat 32-bit WRITE | `$EA $92 $nn` (STA [zp],Z) | **NEIN** (nur Bank 0) |
| ZP-indirekt R/W | `($nn),y` | **NEIN** (immer Bank 0) |
| Selbstmod. absolute | operand zur Laufzeit patchen | **NEIN** (45gs02 prefetcht Operand) |

### Verifizierter Weg: **DMA-Accessor**

Der einzige Weg, der in **beide Richtungen** zuverlässig und bank-agnostisch das
erweiterte RAM erreicht, ist die **F018-DMA**. Testfall `accdma.c`:
1024 Zellen (8 Byte) bei flach `$50000` (Bank 5), a-Feld jeder Zelle = Zellindex,
via DMA geschrieben und gelesen. **Ground-Truth aus dem Dump: 1024/1024 a-Felder korrekt.**

```c
#define HEAPBANK 0x05                    /* Heap flach bei $50000 */
static uint16_t stg;                     /* Bank-0-Staging (2 Byte) */
static void cell_wr(uint16_t off,uint16_t val){ stg=val; dma(&stg,0, off,HEAPBANK, 2); }
static uint16_t cell_rd(uint16_t off){ dma(off,HEAPBANK, &stg,0, 2); return stg; }
```

DMA-Listenformat (12 Byte, F018B): cmd(0)=0, count(1-2), src(3-4), srcbank(5),
dst(6-7), dstbank(8), rest 0. Trigger: `$D702=0` (MB), `$D701=list_hi`, `$D700=list_lo`.
Das bank-Byte trägt Adressbits 16-19 (→ 1 MB Reichweite mit MB=0).

## Konsequenzen für die Kern-Architektur

- **Heap-Accessoren gehen über DMA**, nicht über Zeiger. `car`/`cdr`/`rplaca`/`rplacd`/
  `cons`/GC-mark greifen Zellfelder über `cell_rd`/`cell_wr(flat_off)` zu.
- Der obj-Wert bleibt int16 getaggt; für erweiterte Heaps wird der Zeiger als
  **Byte-Offset in den Flat-Heap** interpretiert (Zelle = off·8 o.ä.).
- **Kosten:** DMA-Setup pro Zugriff (~Dutzende Zyklen). Für einen skalierten Heap
  akzeptabel; ein späterer **Hybrid** (heiße Zellen in Bank 0 direkt, kalte im
  erweiterten RAM via DMA) kann die Hot-Path-Kosten drücken. Korrektheit zuerst.
- Passt exakt zu Codex' Accessor-Backend-Idee: Bank-0-Backend (direkt) + Extended-Backend (DMA).

## Integration in den Kern (Hybrid-Heap) — GELANDET + xemu-verifiziert

Umgesetzt in zwei Scheiben (Lane K):
- **Increment 1:** Accessor-Naht `cell_type/cell_a/cell_b` + `cell_set_*` (static inline Pflicht,
  sonst JSR-Stack-Overflow) ersetzt `CELL(o).x` in eval/reader/printer/mem. Default 1:1-Bank-0.
- **Increment 2:** `-DLISP65_EXT_HEAP` schaltet den Ueberlauf ins erweiterte RAM zu.
  `MAX_CELLS = HEAP_CELLS (hot, Bank 0) + EXT_CELLS (erweitert, DMA)`. Der heisse Bank-0-Zweig
  bleibt inline; nur `o>>1 >= HEAP_CELLS` ruft die DMA-Helfer (`ext_*` in mem.c). alloc/GC/
  mem_init spannen beide Regionen; Freelist wird hot-first vergeben (Symbole bleiben hot).

**End-to-end xemu-verifiziert (nativer Modus, `smoke-xmega65-prgtest.sh`):** voller Interpreter,
`HEAP_CELLS=600`, `EXT_CELLS=1500`; eine 1000-Elemente-Liste laeuft ueber die Hot-Grenze ins
erweiterte RAM ueber, `gc_collect()` ueber beide Regionen, danach Traversierung via DMA-Accessoren:
**Laenge=1000, Kopf=999 korrekt; `$50000` traegt die Zellen** (Ground-Truth aus dem Dump).

**Mark-Bits — Bitmap GELOEST (2026-07-01):** Beim erweiterten Heap sind die Mark-Bits eine Bitmap
(1 Bit/Zelle), damit grosse `MAX_CELLS` in Bank 0 passen (Default ohne EXT bleibt 1 Byte/Zelle).
Eine erste Bitmap crashte reproduzierbar den GC/load-source-Pfad — **Ursache: der variable Shift
`1u << (i & 7)`**, den das llvm-mos-6502-Backend als Shift-Schleife mit Codegen-Fehler generiert.
Fix: **feste Bit-Lookup-Tabelle** `markbit[8]` statt variablem Shift. Verifiziert (bitmap-Build):
load-source/gc-stress/string-Smokes grün. (Isoliert via Padding-Test: kein bss-Layout-Effekt.)

**Perf-Charakteristik (wichtig):** Jeder erweiterte Zellzugriff ist eine F018-DMA. In **xemu ist
die DMA-Emulation langsam** (~15-20 ms/DMA), daher werden Gross-Heap-Tests dort schnell zu langsam
(1000-Zellen-Lauf ok; 2500+ laufen in die xemu-Zeitgrenze). Auf **echter HW ist F018-DMA µs-schnell**
— darum ist HW der Schiedsrichter fuer Gross-Heap-Tempo. Hybrid mildert: nur Ueberlaufzellen zahlen
DMA, der heisse Bank-0-Arbeitssatz bleibt inline-schnell. mem_init/GC fdeln die Freelist ueber ALLE
Zellen ein (O(MAX_CELLS) DMAs) → `EXT_CELLS` fuer den Deploy nur so gross wie noetig waehlen.

## HW-Gegenprobe (2026-07-01) — Primitive OK, Interpreter-Integration BLOCKIERT

Auf echter MEGA65 (etherload, Feedback via Rahmenfarbe — kein m65/USB → kein Speicher-Readback):

| Test (echte HW) | Ergebnis |
|---|---|
| DMA schreibt/liest Bank 5 (Bank-Unterscheidung) | ✅ GRÜN |
| Accessor a-Feld (2-Byte @off2), 1000 Zellen roundtrip | ✅ GRÜN |
| Accessor type (1-Byte @off0) + b (2-Byte @off4), 500 Zellen | ✅ GRÜN |
| **Voller Interpreter**: 1000er-Liste bauen+traversieren (auch OHNE GC) | ❌ **ROT** (falsche Länge) |

**Alle DMA/Accessor-Primitive sind HW-bestätigt** — jede Feldgröße, jeder Offset, tausende DMAs.
**Aber der volle Interpreter korrumpiert erweiterte Daten auf HW** (in xemu grün!). Der Fehler
sitzt also in der Interpreter-*Nutzung* der Primitive (alloc/freelist/mem_init/`cell_*`-Routing/
Codegen unter Registerdruck), nicht in den Primitiven. Verdacht Nr. 1: `ext_dma` wird tief in
cons/alloc/gc unter hohem Registerdruck aufgerufen; die `"r"`-Constraints (DMA-Listenadresse)
kippen dort. **Aber:** jeder Umbau der Adressübergabe (reine C-volatile-Writes, `"m"`-Operanden,
mit/ohne Barriere/noinline) **bricht den verifizierten xemu-Pfad** (Hang/Länge=0). Nur die
`"r"`-Inline-Asm-Version läuft in xemu — und genau die kippt auf HW.

**Fazit:** Der erweiterte Heap ist **xemu-verifiziert, aber NICHT HW-fertig.** Weiter kommt man
mit Rahmenfarben-Feedback (1 Bit/Test) nicht — nötig ist **m65 über USB-UART** (Speicher-Readback/
Einzelschritt), das aktuell nicht verkabelt ist (nur Netzwerk/etherload). Bis dahin: EXT nur als
xemu-Feature führen, Deploy auf Bank-0-Heap belassen.

## Offen / HW-Arbiter

- Alles oben ist **xemu**-verifiziert. DMA ist auf echter HW gut unterstützt und
  divergiert erfahrungsgemäß weniger als MAP/Flat (die xemu/HW schon einmal
  auseinanderliefen). Trotzdem: **am Gerät gegenprüfen**, bevor als endgültig gilt.
- Die MAP/Flat-Read-Nullen sind evtl. ein xemu-Artefakt; irrelevant, da der
  DMA-Weg beide Richtungen abdeckt.
