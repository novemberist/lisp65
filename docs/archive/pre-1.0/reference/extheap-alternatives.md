# Erweiterter Heap: alternative Far-RAM-Ansätze (nach HW-Gegenprobe)

**Status: Planungsdoku.** 2026-07-01. Entscheidung mit User: der DMA-pro-Zelle-Ansatz scheitert
auf echter HW; wir brauchen einen anderen Weg. Dieses Dokument fasst den harten Befund zusammen
und legt die Optionen fest.

## Was wir sicher wissen (HW-verifiziert)

DMA-pro-Zelle ins erweiterte RAM (Bank 5, `$50000`) ist **xemu-verifiziert**, auf echter HW aber
NUR im **flachen/seichten Kontext** korrekt. Leiter-Diagnose am Gerät (Rahmenfarben):

- 🟢 DMA→Bank5 (Bank-Unterscheidung), a/b/type-Felder, verkettete Liste + b-Zeiger-Traversierung,
  Routing-Accessoren (`i<HOT ? heap[] : ext_()`), **echtes `alloc`/`freelist`/`cons` OHNE Prelude**.
- 🔴 **Derselbe Interpreter MIT `load_source(prelude)`** — falsche Länge (Korruption).

**Auslöser = erweiterte Zellen allozieren/zugreifen WÄHREND Source geladen wird** (Reader+eval:
tiefe Rekursion + hoher Registerdruck + viele out-of-line `ext_`-JSRs). Genau das ist der Zweck
(große Stdlib ins erweiterte RAM laden). Einfache cons-Schleifen sind unauffällig.

**`ext_dma` ist per C-Umbau NICHT reparierbar:** jede Variante (reine volatile-Writes, `"m"`-
Operanden, `volatile ext_dl`, link-feste Immediate-Adresse, `noinline`, IRQ-Guard `php/sei/plp`)
**bricht den xemu-Pfad** (Hang oder Länge=0). Nur die exakte committed `"r"`-Inline-Asm-Version
läuft in xemu — und die kippt auf HW. Der llvm-mos-Codegen um den DMA-Trigger ist fragil.

**Zwei ununterscheidbare Ursachen (ohne USB nicht trennbar):**
1. **Registerdruck** kippt die DMA-Listenadresse (`"r"`) tief in eval/reader.
2. **HW-Stack-Overflow**: die out-of-line `ext_a/ext_b/ext_type→ext_dma`-JSRs (2 Ebenen/Zugriff)
   treiben den 256-B-6502-HW-Stack in tiefer eval-Rekursion über; auf HW zusätzlich vom KERNAL-ISR
   angestoßen (headless-xemu timet Interrupts anders → dort grün).

## Ansätze (empfohlene Reihenfolge: billig+zielgenau zuerst)

### B — 45gs02-Stack vergrößern *(zuerst, wenn Ursache = Stack)*
Der 45gs02 kann den Hardware-Stack über 256 B hinaus betreiben (16-Bit-SP / relokierbare Stack-
Page). Wenn die Korruption ein Stack-Overflow ist, verschwindet sie mit größerem Stack — **ohne
`ext_dma` anzufassen**. Billig zu testen: Stack-Modus im Startup setzen, Prelude-Growth-Test auf HW.
Grün ⇒ Ursache war Stack, und wir haben den Fix. Risiko: llvm-mos-Runtime-Annahmen zum Stack.

### A — Far-Heap-Zugriff als reines Hand-Assembly mit fester ABI *(wenn Ursache = Registerdruck/Codegen)*
`ext_dma` + die `ext_*`-Accessoren als **hand-geschriebene Asm-Routine** (eigene `.s`-Datei oder
naked-Funktion) mit **fester ZP-ABI** (Parameter in festen ZP-Zellen, Listenadresse als Symbol-
Immediate). Immun gegen Compiler-Regalloc UND minimale JSR-Tiefe (1 Ebene). Umgeht den fragilen
llvm-mos-Codegen komplett. Braucht Makefile-Anfassung (Lane T) für das `.s`-Target.

### C — Arbeitsmengen-/Paging-Modell *(robuster Umbau, letzter Ausweg)*
Aktiv ge-eval'te Zellen immer in Bank 0 (schnell, DMA-frei), erweitertes RAM als Backing-Store,
**Bulk-Paging via DMA im seichten Kontext** (nicht pro-Zelle-in-eval). Am robustesten gegen beide
Ursachen, aber grob: braucht ein Working-Set/Generationen-Schema für einen wahlfrei zugegriffenen
Heap (quasi Virtual Memory). Nur wenn A/B scheitern.

## Ergebnis B + A (2026-07-01): beide erschöpft — Ursache ist der eval-Kontext, nicht die DMA

**B (Stack) widerlegt:** Rekursionstiefe 80 + ext-Zugriff am Grund = GRÜN auf HW. eval ist flacher
(TCO) → kein Stack-Overflow.

**A (Trigger/Codegen) erschöpft — der eigentliche Befund:** Auf echter HW ist ALLES grün, AUSSER
erweiterte Zellen zu allozieren/zugreifen **während `load_source`/eval** läuft:
- 🟢 DMA→Bank5, a/b/type-Felder, verkettete Liste, Routing-Accessoren, **echtes alloc/cons/freelist
  OHNE Prelude** (1000er-Liste), Immediate-Trigger (immchk), **all-hot HEAP=1600 mit Prelude**.
- 🔴 Voller Interpreter **mit `load_source(prelude)`** bei HEAP=600 (Prelude-Zellen im erw. RAM).

Systematisch am Gerät durchgetestet, alle 🔴 bei HEAP=600: Symbol-Hot-Freelist (Symbole nie
extended), naked-Immediate-Trigger (register-druck-immun), Interrupts global aus (`sei`),
`volatile`-Staging (gegen stale LTO-Reads), Stack. **KEINE Kombination behebt es.** xemu ist bei
exakt derselben Config GRÜN (gm65, HEAP=600) — **xemu/HW divergieren im extended-während-eval-Pfad**,
und Rahmenfarben (1 Bit/Lauf) lokalisieren die Ursache nicht.

**Zwischenbilanz:** DMA-pro-Zelle taugt für *seichten* Zugriff (Nachlade-Daten), aber NICHT für den
Hauptzweck (große Stdlib via eval ins erw. RAM laden). All-hot Bank-0 maxt bei ~1000–1600 Zellen
(HEAP=1800 sprengt `.bss` um 4,3 KB) → zu klein für die ~2200-Zellen-Stdlib.

## Ansatz C wird damit zum Hauptweg (Arbeitsmengen-/Paging-Modell)
Er ist der EINZIGE, der die HW-Realität strukturell respektiert: eval fasst NUR Bank-0-Zellen an
(🟢 bewiesen), erweitertes RAM wird ausschließlich per **Bulk-DMA im seichten Kontext** bewegt
(🟢 bewiesen) — nie DMA-pro-Zelle-während-eval (🔴). Kosten: Working-Set/Generationen-Schema für
einen wahlfrei zugegriffenen Heap (Zeiger-Übersetzung/Eviction). Groß, aber die obige Diagnose
sagt genau, welche Bausteine tragen.

## Nicht-verhandelbar bei jedem Ansatz
- **xemu bleibt Smoke, HW ist Schiedsrichter** — der DMA-pro-Zelle-Ansatz war xemu-grün und
  HW-rot. Jeder neue Ansatz MUSS am Gerät bestätigt werden, bevor er als fertig gilt.
- **Default/Deploy bleibt vorerst der Bank-0-Heap** (HW-funktionierend). Erweiterung gegatet.
- Diagnose-Werkzeug: solange nur Netzwerk (etherload, kein m65/USB) → Rahmenfarben (1 Bit/Lauf).
  **m65 über USB-UART** (Speicher-Readback/Disassembly) würde A/B/C massiv beschleunigen.
