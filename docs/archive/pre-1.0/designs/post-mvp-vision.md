# lisp65 — Skizze: Wege nach dem MVP (Compiler · Performance/Games · IDE)

**Stand: 2026-07-01. SKIZZE, keine Verpflichtung.** Sammelt die Richtungsideen aus der Diskussion,
damit sie nicht verloren gehen. Alles hier ist Ausbaupfad *nach* dem MVP; jede Stufe unterliegt
weiterhin der Regel **xemu = Smoke, HW = Schiedsrichter**. Verwandt: `bytecode-streaming-plan.md`,
`bytecode-embed-loader.md`, `bytecode-abi.md`.

## Ausgangslage (was der MVP schenkt)
- Eine **Ein‑Image‑Lisp‑Maschine** auf echter MEGA65: Tree‑Walker‑REPL + Bytecode‑VM, Code als
  Bytecode im erweiterten RAM, per **Bulk‑DMA gestreamt** (HW‑bewiesen). Die zwei üblichen 8‑Bit‑
  Show‑Stopper — *wohin mit dem Code* und *Code größer als RAM ausführen* — sind gelöst.
- Der `CALLPRIM`‑Seam (native Primitive) und `vm_register_embedded` (Directory + `T_BCODE`) sind da.
- Es gibt **keine bekannte HW‑Wand** mehr auf diesen Pfaden (anders als die
  extended‑RAM‑während‑eval‑Wand, die wir architektonisch umschifft haben).

Das Folgende sind **drei ineinandergreifende Stränge**, nicht drei getrennte Projekte.

---

## Strang A — Compiler‑Evolution
1. **Cross‑Compiler → Bytecode (Host):** ist faktisch der MVP (Codex' P0‑Oracle). Danach:
   Vollständigkeit + Optimierung, keine Machbarkeitsfrage.
2. **On‑Device‑Compiler (Lisp → Bytecode, auf der MEGA65):** realistisch, weil die harten Teile
   schon stehen — Reader (Quelle → AST, hot), Macro‑Expansion, Output‑Pfad (`ext_write` → erw. RAM,
   `vm_register_embedded`), und Kompilieren ist **hot‑Heap‑cons‑Manipulation + Byte‑Emission** =
   der *sichere* Zugriff. Gating: **Symboltabelle uint8 → uint16**, transienter Compile‑Heap
   (Funktion‑für‑Funktion), resident‑C vs. selbst‑gehostet.
3. **Self‑Hosting:** Compiler auf dem Host cross‑kompilieren, als Bytecode einbetten, ab dann
   kompiliert er Neues selbst. Kostet ~0 Bank‑0. Der eleganteste Weg.
4. **Selektiver Native‑Backend (45GS02):** gleiches Frontend, Emission von Maschinencode für als
   „schnell" markierte Funktionen. Hebt die Performance‑Decke.

**Weiche, die es früh leicht macht:** Codegen des Cross‑Compilers **portabel/ABI‑nah** halten
(saubere Frontend/Backend‑Trennung, keine host‑spezifischen Emissions‑Tricks). Dann ist On‑Device =
ein *Port*, nicht eine zweite Codebase.

## Strang B — Performance & Games
Kernframe: auf diesen Maschinen macht **die Hardware** die schwere Arbeit (Sprites, Raster‑IRQ,
Bitplanes, DMA‑Copies, Color‑RAM), die CPU *dirigiert* nur. Ein DMA‑Blit kostet gleich viel aus asm
oder aus `CALLPRIM`. Mit 40 MHz (~40× C64) ist Bytecode‑**Logik** völlig ausreichend schnell.
- **Realistisch:** hardware‑getriebene + logik‑gebundene Games (Puzzle, Brett/Strategie, Adventure,
  Plattformer/Shmup mit HW‑Sprites), moderate Objektzahl pro Frame.
- **Stretch in purem Bytecode:** enge Per‑Pixel‑Softwareloops, schwere Per‑Frame‑Physik/AI.
- **Fluchtwege (schon in/nahe der Architektur):** heiße Loops als **native Primitive** (`CALLPRIM`,
  heute); Hot‑Funktion **resident** halten (Fast‑Path = reload‑frei); später **Native‑Backend**
  (Strang A.4) hebt die Decke ganz weg.
- **Nötig:** HW‑Zugriffs‑Primitive (VIC‑IV/Sprite/DMA/Raster als `CALLPRIM`), Raster/Frame‑IRQ →
  Lisp‑Callback (Sorgfalt: GC/Reentrancy), **GC‑Disziplin** (im Hotloop nicht consen).

## Strang C — Die IDE: „Mini‑Emacs" + interaktive Lisp‑IDE (SLIME‑artig)
**Die natürlichste Anwendung**, weil Emacs im Kern „eine Lisp‑Maschine, deren Hauptanwendung ein
Editor ist" — genau das, was wir bauen. Der C/Lisp‑Hybrid fällt fast von selbst aus der Architektur.

**Editor‑Hälfte:**
- **Display fast gratis:** memory‑mapped Textmodus (80 Spalten+); Redisplay = geänderte Zellen
  schreiben. **Color‑RAM memory‑mapped → Syntax‑Highlighting billig.**
- **Puffer:** **Gap‑Buffer** in C; kleine Dateien hot, **große im erw. RAM gefenstert** — dasselbe
  bewiesene Bulk‑DMA‑Streaming (Editieren ist lokal → seicht → sicher).
- **Fast‑C‑Schicht:** Gap‑Ops/Redisplay/Keyboard‑Scan als `CALLPRIM`‑Primitive
  (`insert`,`delete-char`,`point`,`goto-char`,…).
- **Editier‑Logik = Lisp** (Bytecode, gestreamt): Kommandos, Keymaps, Modi. MEGA65‑Tastatur liefert
  Ctrl/Mega → **Emacs‑Chords (`C-x C-s`) lesbar**. Präzedenz: MicroEMACS (C, kleine Maschinen).

**SLIME‑Hälfte — der Clou:** echtes SLIME braucht swank/Netz, **weil Editor und Lisp getrennte
Prozesse sind.** Bei uns = **ein Image**: die Editier‑Kommandos *sind* Lisp‑Funktionen auf derselben
VM wie der editierte Code. Damit ist SLIME‑Interaktivität *leichter* als bei echtem Emacs+SLIME:
- **eval‑in‑place / eval‑defun / eval‑region:** trivial (`eval` auf die Region), kein Protokoll.
- **Live‑REPL** in einem Puffer; **inkrementelles Redefinieren** live (Lisp‑2‑Funktionszellen; mit
  Compiler: umdefinieren → neu kompilieren → `T_BCODE`/Directory‑Eintrag ersetzen).
- **Completion / apropos / inspect:** über die Symboltabelle.

**Langschwanz (später, kein Blocker):** Jump‑to‑Definition (Source‑Positions‑Tracking), echte
**Restarts/Debugger** (Condition‑System statt nur `lisp_abort`/longjmp), Inspector, Fenster/Splits.

---

## Wie die Stränge zusammenhängen (Reihenfolge)
- Die IDE läuft schon mit **On‑Device‑eval** (Tree‑Walker) über der kompilierten Stdlib — sie
  **blockiert nicht** auf dem On‑Device‑Compiler, wird damit nur besser (edit → recompile → live).
- Games profitieren zuerst von HW‑Zugriffs‑Primitiven (`CALLPRIM`), später vom **Native‑Backend**.
- Symboltabelle **uint16** ist ein früher, gemeinsamer Enabler (Compiler *und* IDE symen viel).

## Ehrliche Vorbehalte
- **Umfang** ist groß, aber alles **inkrementell** (Emacs fing klein an): minimaler Puffer +
  insert/delete + REPL‑im‑Puffer + eval‑region zuerst, dann wachsen.
- **Feature‑Langschwänze** (Debugger/Restarts, Native‑Optimierung, Jump‑to‑Def) sind echte Arbeit,
  aber keine prinzipiellen Hürden.
- **Keine HW‑Wand** in Sicht — der Risikocharakter ist „mittelgroßes Engineering", nicht „Forschung".

## Nicht‑Verpflichtung
Skizze zur Richtungsfindung. Konkrete Priorität/Reihenfolge entscheidet der User; jede Stufe wird
am Gerät bestätigt.
