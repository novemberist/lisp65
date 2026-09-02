# lisp65 — Salvage-Manifest & Bootstrap-Plan

Stand: 2026-06-30. Dieses Dokument hält fest, **warum** wir neu starten, **was** aus
`../lisp64v2026` übernommen wird, **was** wegfällt, und in **welcher Reihenfolge** der
neue MEGA65-native Kern hochgezogen wird.

---

## 0. Leitprinzipien (verbindlich, Nutzer-Vorgaben 2026-06-30)

1. **Automatisiert testen vor visuell prüfen.** Eine **xemu-Toolchain muss stehen** —
   wir dürfen uns nicht auf manuelle Sichtkontrolle auf echter Hardware verlassen.
   Schnelle, automatisierte Smokes (Host-Oracle + **xemu headless**) sind die Regel;
   echte HW ist Schiedsrichter für HW-nahe Befunde, nicht der Alltags-Loop. (§7)
2. **Keine Dialekt-Altlasten.** **So CL-nah wie möglich.** Die alten LISP-64-
   Eigenheiten werden **nicht** übernommen; `salvage/lisp/` dient als *Logik-/Test-
   Referenz*, nicht als Sprach-Vorlage. `docs/reference/dialect-vs-cl.md` ist die
   Liste dessen, was wir bewusst **anders** (CL-konform) machen. (§6)
3. **Feature-Nähe zu MEGA65 BASIC 10.** Ziel ist Komfort auf BASIC-10-Niveau —
   Convenience-Funktionen für **Grafik, Sound** etc. — nur eben als Lisp. (§5 Phase 6)
4. **Klares, erreichbares MVP; nicht in Tests verlieren.** Ein scharf umrissenes MVP
   (unten) ist das Ziel; Tests dienen dem MVP, nicht umgekehrt. Kein Grind. (§MVP)

---

## MVP-Ziel (scharf umrissen)

**Definition of Done für das MVP:** Eine **interaktive lisp65-REPL, die nativ auf dem
MEGA65 läuft** und folgendes kann — nicht mehr:

- **Sprache (CL-Subset):** Reader, `eval`/`apply`, lexikalische Bindung + Closures,
  `defun`/`defmacro`/`let`/`let*`/`cond`/`if`/`quote`/`setq`, Kern-Primitive
  (Arithmetik, `cons`/`car`/`cdr`/`list`/`eq`/`equal`/Prädikate), Listen-Basics,
  einfache Fehlerbehandlung (`error` + Abfangen).
- **REPL:** Tastatur-Eingabe + Bildschirm-Ausgabe nativ, Edit einer Zeile, Ergebnis-
  Druck, Fehlermeldung ohne Absturz.
- **MEGA65-Komfort (BASIC-10-nah, kleiner Satz):** je ein paar Convenience-Fns für
  **Grafik** (z. B. Linie/Rechteck/Plot) und **Sound** (Ton spielen) — genug, um
  „damit kann man auf dem MEGA65 was machen" zu zeigen.
- **Laden/Speichern:** ein kleines Lisp-Programm von Disk laden und ausführen.
- **Qualität:** Host-/Bytecode-Oracles und MEGA65-MVP-Build/Dry-Run grün
  (heutiges `make check`; alte C64/GO64-Smokes sind nur noch `legacy-xc64-*`).

**Bewusst NICHT im MVP:** voller CLOS, kompletter `loop`/`format`, Bytecode-VM,
On-Device-Editor/Paredit, FFI, 8-MB-Heap-Optimierung über das Nötige hinaus,
ANSI-Konformität. Diese kommen *nach* dem MVP, falls überhaupt.

---

## 1. Warum Neustart (ehrliche Abwägung)

Das Altprojekt steckt aus zwei strukturellen Gründen fest, nicht aus Unfähigkeit:

1. **Falsches Fundament für das neue Ziel.** Es baut auf dem alten LISP-64-MacLisp-
   Dialekt (`*`=Kommentar, `MINUS`/`DIFFERENCE`, `F`=False-Atom, keine
   String-Primitive). Das Ziel ist aber CL-nah → jede Dialekt-Eigenheit ist
   **vererbte Schuld**; `cl-compat` ist nur Furnier darüber.
2. **„MEGA65 via C64-Kompatibilitätsmodus" ist die fragile Mitte.** Weder ein
   fokussiertes C64-Produkt noch ein echtes MEGA65-Backend. Genau dort lief der
   lange Grind (Dutzende „Narrow/Classify quote COND"-Commits). Beleg, dass diese
   Schicht trügerisch ist: Befund #1 (Müllzeichen beim Tippen) erwies sich auf
   **echter Hardware** als reines **VICE-Emulations-Artefakt** — kein Code-Bug.

Konsequenz: Nicht der Lisp-Code ist das Problem, sondern der **hardware- und
dialektgebundene Kernel**. Den ersetzen wir; die oberen Schichten erben wir.

---

## 2. Salvage vs. Wegwerfen (gemessen am Altprojekt)

| Schicht | Umfang | Entscheidung |
| --- | --- | --- |
| 6502-Assembly-Kernel (`src/v2`, ~56.000 Z., 107 Module) | sehr groß | **Wegwerfen als Code** — C64-/6502-gebunden. Lektionen (GC, Reader-Chunking, VM-Format) übertragen sich als *Design*, nicht als Code. |
| Lisp-Bibliotheken + Tests (`lisp/*.lsp`, ~7.800 Z., davon ~6.000 Tests) | mittel | **Salvage** → `salvage/lisp/`. Größtenteils portabel; Dialekt-Oberfläche mechanisch auf CL umstellbar. Tests = künftige CL-Subset-Konformitäts-Suite. |
| Host-Interpreter (`tools/host-lisp`, ~6.800 Z. Python) | mittel | **Salvage** → `tools/host-lisp/`. Semantik-Oracle, Test-Runner, möglicher Bootstrap-Host. |
| Docs/Specs (~4.500 Z.) | klein | **Salvage (kuratiert)** → `docs/reference/`. Reines Design. |
| C64-HW-Libs (`lib-c64hw/term/key`, ~3.500 Z.) | klein | **Referenz** — Muster für die MEGA65-Pendants; nicht direkt übernehmen. |
| MEGA65-Vorarbeit (`lib-mega65hw`, `lib-platform-mega65`, ~500 Z.) | klein | **Salvage** — direkter Startpunkt fürs HW-Backend. |
| HW-Test-Pipeline (etherload/mega65_ftp + Harness) | — | **Salvage (Kronjuwel)** — hat bereits #1 als Emulator-Phantom entlarvt. |

**Fazit:** Wir werfen ~56k Assembly-Zeilen weg, behalten aber **~⅔ der *wertvollen*
Arbeit** (Bibliotheken, Specs, Tests, Oracle, HW-Loop, Designwissen).

---

## 3. Was bereits hier liegt

Siehe `README.md`-Tabelle. Inventar:
- `tools/m65tools/` — komplette HW-Tools (Binaries).
- `tools/host-lisp/` — `lisp64.py` + `host_bcvm.py`/`phase4_vm.py` (VM-Modell) +
  `compact-model.py`/`fixedpoint-model.py` + `run-tests.sh`.
- `salvage/lisp/` — **alle** `.lsp` (Libs + Tests), inkl. C64-spezifischer als Muster.
- `docs/reference/` — `bytecode-v1`, `platform-layer`, `dialect-vs-cl`,
  `language-reference`, `phase5-hardware`, `mega65-hardware-testing`,
  `mega65-lisp-start-path`, `cons-layout-density`, `architecture`, Architekturnotizen.
- `scripts/` — `run-on-mega65.sh`, `check-mega65-readiness.sh`, Screen-Oracle,
  xemu-PRG-Smoke, xemu-Kill-Helfer.

Bewusst **nicht** übernommen: die ~hunderte `check-mega65-*-diagnostic.py` (C64-Compat-
Eval-Bisektion = Grind-Schuld) und der gesamte Assembly-Baum.

---

## 4. Offene Entscheidungen (vor dem ersten Kernel-Code)

### 4.1 Kernel-Sprache: C vs. Hand-Assembly  ← ✅ ENTSCHIEDEN: C via **llvm-mos**
**Entscheidung 2026-06-30 (nach Phase-0-Spike, `spike/README.md`):** Kernel in **C**,
Compiler **llvm-mos** (natives `mos-mega65`-Target, auf echter HW validiert, ~22 %
kleinerer Compute-Code als cc65). cc65 verworfen (nur C64-Target). m65compiler bleibt
optionaler späterer Vergleich, ist aber nicht blockierend. Heiße Pfade später
punktuell in 45GS02-Assembly.

Der C64 erzwang Hand-Assembly (64 KB, 1 MHz). Der MEGA65 (**8 MB RAM, 40 MHz,
45GS02 mit flachen 32-Bit-Zeigern**) hebt diesen Zwang auf. Ein Lisp-Kern **in C**
ist realistisch und **5–10× schneller zu bauen/evolvieren** als Hand-Assembly.

- **Empfehlung:** Kern in **C** (Reader, Speicher/GC, Eval, Printer), heiße Pfade
  später punktuell in 45GS02-Assembly. Toolchain-Spike zuerst (siehe Phase 0,
  `spike/README.md`).
- **C-Toolchain-Kandidaten:**
  - **llvm-mos** (Frontrunner) — moderner LLVM-Optimizer, natives `mos-mega65`-Target
    **und** `mos-c64`; erprobtes Ökosystem, vorgebautes SDK. Iteration 1: deutlich
    kleinerer Code als cc65.
  - **cc65** — älter, schwächere Codegen, nur C64-Mode; konservative Baseline.
  - **m65compiler** (`cc45`, https://github.com/CTalkobt/m65compiler) — **MEGA65-nativ
    für 45GS02** mit 32-Bit-Q-Register-Longs und flacher 28-Bit-Adressierung, was
    direkt aufs Lisp-Speichermodell passt. Reif (v1.0), aber wenig erprobt
    (Einzelentwickler) → vielversprechender Herausforderer, **nicht** Default. Im
    Spike objektiv gegen llvm-mos benchmarken (offene Fragen: Lizenz, Install-Friktion).
- **Risiko/Prüfpunkt:** Codegen-Qualität & MEGA65-Runtime-Größe/-Tempo bei *echter
  Logik* (Compute-Benchmark) auf echter HW messen, *bevor* wir uns festlegen — nicht
  nach Hello-World-Größe oder Reputation.

### 4.2 CL-Subset-Umfang
Verbindliche Liste festlegen (Reader-Syntax, Zahlentypen inkl. Fixed-Point?,
Symbole/Packages-light, Conditions, `loop`/`format`-Subset). Quelle: die bereits
designten Specs + die salvageten Test-Suites als De-facto-Spezifikation.

### 4.3 Speicher-/Objektmodell
Flaches 8-MB-Modell mit 32-Bit-Zeigern (45GS02) statt der C64-Page/Handle-Akrobatik.
GC-Wahl (Mark-Sweep vs. Stop-&-Copy) — `cons-layout-density.md` als Input.

### 4.4 Bootstrap-Host
Host-Interpreter (`lisp64.py`) als Oracle behalten; Option: ihn zum
**Cross-Compiler/Image-Builder** ausbauen, der Lisp-Libs zu einem ladbaren
MEGA65-Image bäckt (analog SAVE-Format, aber CL-sauber).

---

## 5. Bootstrap-Reihenfolge (Phasen)

- **Phase 0 — Toolchain-Spike:** ✅ **erledigt.** C-Sprache + llvm-mos festgelegt
  (`spike/README.md`), nativer MEGA65-Code auf echter HW validiert.
- **Phase 0.5 — Automatisierte Test-Toolchain (historisch):** ✅ **erledigt.**
  Der alte `make xemu-smoke`/`scripts/smoke-xemu.sh`-Pfad war ein C64/GO64-Smoke.
  Er ist inzwischen aus dem Standard-Gate entfernt; heutiges `make check` nutzt
  Host-/Bytecode-Oracles plus nativen MEGA65-MVP-Build/Dry-Run. Historische
  C64/GO64-Smokes liegen unter `legacy-xc64-*`.
- **Phase 1 — Kern-Runtime:** 🟡 *in Arbeit.* Objektmodell/Allocator/Printer ✅
  (`src/lisp65.c`, M1.0). Offen: **Reader**, Minimal-Eval
  (`quote/if/lambda/let/cond/setq` + Apply), Speicher/GC.
- **Phase 2 — REPL auf MEGA65:** Tastatur/Screen-I/O nativ (40/80-Spalten),
  REPL-Loop, Fehler-/Backtrace-Grundlage.
- **Phase 3 — Sprache CL-nah:** lexikalische Bindung + Closures, `defun`/`defmacro`,
  echte Zahlen-/String-/Listen-Primitive, Conditions (`error`/`handler-case`).
- **Phase 4 — Standardbibliothek (CL-nah neu):** Funktionalität aus `salvage/lisp/`
  als **CL-saubere** Libs (neu, nicht dialekt-portiert — Leitprinzip 2), gegen
  (CL-angepasste) Test-Suites grün.
- **Phase 5 — Editor/IDE:** Paredit/IDE-Schicht (Logik host-erprobt) nativ.
- **Phase 6 — MEGA65-BASIC-10-Komfort (Leitprinzip 3):** Convenience-Schicht auf
  BASIC-10-Niveau über `lib-platform`-Abstraktion — **Grafik** (Screen/Plot/Line/
  Rect/Circle), **Sound** (Ton/Play), Sprites, Datei-I/O — als Lisp-Funktionen.

> **MVP-Schnitt:** Das MVP (oben) umfasst Phase 0.5–3 **plus** einen *kleinen* Satz
> aus Phase 6 (etwas Grafik + Sound) und Laden/Speichern. Phasen 4/5 und die volle
> Phase 6 liegen **hinter** dem MVP.

---

## 6. Standardbibliothek: CL-nah **neu**, nicht dialekt-portiert (Leitprinzip 2)

**Kein** mechanischer Port der LISP-64-Oberfläche. `salvage/lisp/` ist **Logik- und
Test-Referenz** (welche Algorithmen, welche Fälle), **nicht** Sprach-Vorlage. Die
neuen Libs werden **CL-konform** geschrieben.

- `docs/reference/dialect-vs-cl.md` ist die Liste dessen, was wir bewusst **anders**
  machen: CL-Kommentare `;`, `*`=Multiplikation (nicht Kommentar), `defun`/`defmacro`
  statt `DE`/`DF`/`DM`, `+ - * /` statt `PLUS`/`DIFFERENCE`/`TIMES`/`QUOTIENT`,
  `nil`/`t` statt `F`-False-Atom, `case` statt `SELECTQ`, echte Strings/`format`
  statt der Dialekt-Lücken.
- **Reihenfolge (Abhängigkeit):** Kern-Makros (`let*`/`when`/`cond`-Helfer) →
  Sequenz-/Listen-Lib → `loop`-Subset → `defstruct` → (post-MVP: CLOS, IDE/Paredit).
- Jede Lib bekommt eine **CL-saubere** Test-Suite (aus den alten `*-tests.lsp`
  übersetzt) als laufende Konformitätsprüfung — auf Host-Oracle **und** xemu.

---

## 7. Test- & HW-Loop-Strategie (Leitprinzip 1)

**Automatisiert ist der Default, visuell ist die Ausnahme.**
- **Ebene 1 — Host-Oracle** (`tools/host-lisp`): Sprach-Semantik (Reader/Eval-Fälle).
- **Ebene 2 — xemu headless (Alltags-Loop):** Kernel-PRG booten, Bildschirm-/
  Ergebnis-Ausgabe **maschinell** prüfen (Screen-Oracle). **Muss früh stehen**
  (Phase 0.5) — wir prüfen nicht dauerhaft per Auge auf echter HW.
- **Ebene 3 — echte Hardware** (etherload/mega65_ftp): **Schiedsrichter** für
  HW-nahe Befunde, nicht der tägliche Loop.
- **Lehre aus lisp64v2026-#1:** Bei CIA-/Timing-/Matrix-nahen Befunden **auf echter
  HW gegenprüfen** — Emulatoren lügen genau dort. Aber: das ist die Ausnahme; für
  Sprach-/Logik-Fortschritt zählt der automatisierte Loop.
- HW-Readiness: MEGA65 im Remote-Modus (DIP 2 = ON, SHIFT+£ bis LED grün-gelb),
  Firewall UDP 4510 offen; `etherload --discover` muss greifen. Etherload-
  Soft-Resets erhalten das Remote-Flag; ein harter JTAG-Reset (`m65 -F`) loescht
  es und erfordert erneutes SHIFT+£-Scharfstellen.

---

## 8. Nächste Schritte

1. ✅ **Phase 0.5 erledigt** — heute durch `make check` als MEGA65-MVP-Gate ersetzt;
   historische C64/GO64-Smokes liegen unter `legacy-xc64-*`.
2. **Phase 1 weiter — Reader** (Text → Objektgraph), dann Minimal-Eval; jeder Schritt
   bekommt einen xemu-Smoke-Fall (Reader-Roundtrip, Eval-Ergebnis).
3. **Speichermodell-Untersuchung** (4.3): wie aus llvm-mos die vollen 8 MB / flache
   45GS02-Adressierung erreichen — bestimmt das endgültige Heap-Design.
