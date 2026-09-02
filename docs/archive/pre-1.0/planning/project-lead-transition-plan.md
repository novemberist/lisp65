# Project-Lead-Transition: Codex als allein handlungsfaehiger Lead

Stand: 2026-07-08. Ziel dieses Plans ist nicht, Claude aus dem Projekt zu
verbannen. Ziel ist, dass lisp65 fuer eine laengere Phase auch ohne Claude
weiterentwickelt werden kann: Codex muss Kernel-/Runtime-, Lisp-/Stdlib-/IDE-,
Build-/Harness- und Doku-Arbeit selbst fuehren, integrieren und testen koennen.

## Zielbild

- `origin/main` bleibt die einzige technische Wahrheit.
- Es gibt ein sichtbares Produktziel: die Workbench, plus spaeteren
  Runtime-Export fuer fertige Programme.
- Projektzustand, Entscheidungen und offene Risiken liegen in kurzen,
  dauerhaften Dokumenten, nicht in einem langen Live-Handoff-Protokoll.
- Codex ist Lead und Integrator ueber alle Bereiche. Claude ist optionaler
  Contributor, Reviewer oder Spezialist, aber kein erforderliches Gate.
- Parallelarbeit passiert nur ueber getrennte Worktrees/Branches oder klar
  begrenzte Codex-Subagent-Auftraege.

## Neue Rollen

**Codex Lead**

- priorisiert Arbeit und haelt Produktlinie, Budget und Gates zusammen;
- reviewed und integriert alle Beitraege, auch von Claude oder Subagenten;
- besitzt die abschliessende Entscheidung, ob ein Profil, Target oder Doc als
  Produktstand gilt;
- sorgt dafuer, dass jede Architekturentscheidung mit Messdaten oder einem
  expliziten Risiko dokumentiert ist;
- schreibt keine "temporaren" Chat-Entscheidungen, ohne sie danach in die
  passende Projektdoku zu ueberfuehren.

**Claude optional**

- kann weiter Runtime-/HW-/Debug-Handoffs liefern;
- arbeitet nicht mehr als exklusiver Owner von `src/**`;
- liefert Aenderungen vorzugsweise als Branch/Commit mit Testergebnis,
  Messwerten und klarer Restunsicherheit;
- darf blockierende Rueckfragen stellen, aber die Roadmap haengt nicht an einer
  Antwort.

**Codex-Subagenten optional**

- werden nur fuer eng begrenzte Aufgaben eingesetzt: Audits, alternative
  Root-Cause-Analysen, Testgenerierung, isolierte Implementierungsslices;
- bekommen einen getrennten Worktree/Branch oder eine reine Read-only-Aufgabe;
- duerfen nicht direkt `main` pushen und nicht im Integrations-Worktree
  arbeiten;
- liefern Ergebnis, Diff und Testprotokoll. Der Lead integriert selbst.

## Quellen der Wahrheit nach der Konsolidierung

Diese Struktur soll die bisherige `collaboration.md`-Wand ersetzen:

| Zweck | Datei |
| --- | --- |
| Einstieg, Produktstatus, Standardbefehle | `README.md` |
| Aktueller Zustand, naechste Arbeit, rote Gates | `docs/project-status.md` (neu) |
| Produkt-/Profilstrategie | `docs/profile-consolidation-strategy.md` |
| Bank-0-/Budgetstrategie | `docs/mega65-native-budget-strategy.md` |
| Architekturentscheidungen mit Datum | `docs/decision-log.md` (neu) |
| Claude-/Subagent-Handoffs waehrend der Uebergangsphase | `docs/collaboration.md` als Inbox |
| Historische Parallelplaene | `docs/parallel-plan.md`, `docs/bytecode-parallel-plan.md` als Referenz |

`docs/collaboration.md` bleibt nur noch als kurze Inbox fuer frische Handoffs
erhalten. Die alte Chronik ist nach `docs/archive/collaboration-2026-07-08.md`
verschoben; dauerhafte Entscheidungen werden in die passenden Strategie- oder
Statusdokumente uebernommen.

## Worktree- und Branch-Modell

**Standard**

- `main` in diesem Worktree ist Integrations- und Review-Arbeitsstand.
- Vor groesseren Aenderungen: `git pull --rebase`, Status pruefen, dann
  kurzer Arbeitsbranch oder separater Worktree.
- Branch-Namen: `codex/<bereich>-<thema>`, z. B.
  `codex/runtime-compile-string-gate`.
- Kleine Doku-/Planungsfixes koennen direkt auf `main` passieren, wenn der
  Arbeitsbaum sauber ist.

**Parallelarbeit**

- Jeder parallele Worker bekommt einen eigenen Worktree, z. B.
  `../lisp65-work/<topic>`.
- Keine zwei Worker schreiben gleichzeitig in denselben Working Tree.
- Subagenten bekommen eine Dateiliste oder klare Read-only-Grenzen.
- Integration passiert nur durch Codex Lead im Haupt-Worktree.

**Claude**

- Wenn Claude weiter mitarbeitet, behandelt Codex Claude wie einen externen
  Contributor: Branch/Commit lesen, Diff reviewen, Gates auswerten, dann
  integrieren oder Rueckfrage formulieren.
- Claude arbeitet pro Aufgabe in einem kurzlebigen Worktree unter
  `../lisp65-work/claude-<thema>` auf Branch `claude/<thema>`.
- Der vorbereitete Helfer ist `scripts/create-claude-worktree.sh <thema>`;
  der genaue Ablauf steht in `docs/claude-worktree-workflow.md`.
- Es gibt keine permanente Lane, die Codex nicht anfassen darf.

## Lokale Verzeichnis-Konsolidierung

Der alte Aufbau mit mehreren permanenten Projekt-Clones (`lisp65`,
`lisp65-claude`, `lisp65-codex`) war fuer die harte Claude/Codex-Lane-Trennung
nuetzlich, ist aber fuer die Codex-Lead-Phase ein Drift-Risiko:

- jeder Clone hat eigene `origin/*`-Refs und kann unbemerkt hinterherlaufen;
- lokale Diffs in alten Clones sind leicht zu uebersehen;
- Build-Artefakte, generierte Dateien und Toolchain-Zustand werden
  uneinheitlich;
- "gruen" ist nicht eindeutig, wenn nicht klar ist, welcher Clone getestet
  wurde.

Zielzustand auf dieser Maschine:

- `../lisp65.git` bleibt der lokale bare Remote.
- `../lisp65` ist der kanonische Integrations-Worktree fuer Codex Lead.
- Neue parallele Arbeit entsteht als kurzlebiger `git worktree`, z. B.
  `../lisp65-work/claude-<thema>`, nicht als permanenter Voll-Clone.
- `../lisp65-codex` und `../lisp65-claude` sind archiviert und werden nicht
  fuer neue Arbeit reaktiviert.

Status 2026-07-08: beide alten Voll-Clones wurden auditiert und nach
`../lisp65-archive/2026-07-08/` verschoben. Sicherungen und Patch liegen in
`docs/local-clone-consolidation-2026-07-08.md`.

Regel ab sofort: Neue Codex- oder Claude-Arbeit startet nicht mehr in
`../lisp65-codex` oder `../lisp65-claude`. Claude-Ergebnisse kommen aus einem
kurzlebigen `../lisp65-work/claude-<thema>`-Worktree als Branch/Commit/Patch
plus Handoff.

Historischer Audit-Befehl vor dem Entfernen alter Clones:

```sh
git -C ../lisp65-codex status --short --branch
git -C ../lisp65-codex diff --stat
git -C ../lisp65-codex branch -vv --all

git -C ../lisp65-claude status --short --branch
git -C ../lisp65-claude branch -vv --all
```

Nur wenn keine ungesicherte Arbeit mehr vorhanden ist, darf ein alter Clone
archiviert oder geloescht werden.

## Lanes werden Work Packages

Die alten Lanes bleiben als Denkmodell nuetzlich, aber nicht als
Eigentumsgrenzen:

- **Runtime/Kernel:** `src/**`, VM, GC, Reader/Printer, Symboltabelle, Disk,
  Hardware-Naehe.
- **Lisp/Stdlib/Compiler/IDE:** `lib/**`, lcc, Workbench-Features, Demos,
  Sprachinventar.
- **Build/Harness/Docs:** `Makefile`, `scripts/**`, Tests, HW-Gates,
  Strategiedoku.

Cross-cutting Arbeit ist erlaubt, muss aber klein bleiben und die betroffenen
Gates nennen. Header-/ABI-Aenderungen brauchen weiter eine explizite
Entscheidung, weil sie Compiler, Host-VM, Embed-Artefakte und Runtime koppeln.

## Benotigte Handoffs von Claude

Damit Codex die aktuelle Claude-Arbeit ohne Wissensloch uebernehmen kann,
brauche ich genau diese Informationen, sobald Claude mit dem Profiltest fertig
ist:

1. **Exakter Stand:** Branch, Commit, Diff-Basis und ob alles auf `origin/main`
   gelandet ist.
2. **Profiltest:** Kommandos, CFLAGS/Targets, Footprint-Ausgabe,
   `stack_gap`, `bank0_reserve`, `MAX_SYM`, `VM_DIR_MAX`, `GC_ROOTS`.
3. **HW-Ergebnis:** Etherload/JTAG-Kommandos, sichtbares Verhalten,
   relevante Counter/Dumps, ob `m65 -F` vermieden wurde.
4. **Rote Gates:** was ist kaputt, reproduzierbar, flaky oder nur
   beobachtet.
5. **Runtime-Invarianten:** kurze Karte fuer VM/GC/Symboltabelle/String-Arena,
   Disk-I/O, FASL/L65M, Screen/IDE; besonders alles, was nicht offensichtlich
   aus dem Code hervorgeht.
6. **Offene Hypothesen:** Welche Annahmen sind gemessen, welche nur plausibel.
7. **Nicht gemergte WIP-Arbeit:** lokale Branches, Patches, temporaere
   Diagnose-Targets, die nicht verloren gehen duerfen.

Minimalformat fuer kuenftige Handoffs:

```text
Branch/Commit:
Ziel:
Dateien:
Kommandos:
Footprint/Budget:
HW/JTAG:
Ergebnis:
Risiken:
Naechster sinnvoller Schritt:
```

## Konsolidierungsphasen

### P0: Uebergang absichern

- Claudes aktuelles Profiltestergebnis aufnehmen und in `docs/project-status.md`
  zusammenfassen.
- Keine neuen Nutzerprofile zulassen, solange sie nicht als Produkt,
  Diagnose, Referenz oder Runtime-Export klassifiziert sind.
- Offene rote Gates und Budgetwerte in einem kurzen Statusblock erfassen.

### P1: Doku entflechten

- `docs/project-status.md` anlegen: aktueller Produktpin, Gates, offene
  Blocker, naechste drei Arbeiten.
- `docs/decision-log.md` anlegen: kurze, datierte Entscheidungen statt
  Handoff-Prosa.
- `docs/collaboration.md` auf Inbox reduzieren und die alte Live-Wand in ein
  Archiv verschieben.
- `docs/parallel-plan.md` als historischen Stand markieren und nicht mehr als
  aktuelle Roadmap referenzieren.
- README auf Workbench-Kandidat, Profilstrategie und aktuelle Standard-Gates
  aktualisieren.

### P2: Build- und Profilmatrix konsolidieren

- Makefile-Targets in Produkt, Diagnose, Referenz, Runtime-Export und Obsolete
  klassifizieren.
- Genau ein Workbench-Kandidat bleibt der sichtbare Produktpfad.
- `make check` bleibt stabil und fuehrt keine historischen Profilvarianten aus.
- Footprint-/Budget-Reports werden fuer den Workbench-Kandidaten kanonisch.
- Alte Targets werden erst entfernt, wenn sie weder Diagnose- noch
  Referenzwert haben.

### P3: Runtime-Verantwortung voll uebernehmen

- Codex erstellt eine kompakte Runtime-Karte: VM, GC, Symboltabelle, Objektmodell,
  Reader/Printer, Disk, Screen/IDE, Boot/Embed.
- Fuer jeden bisherigen Claude-Spezialbereich gibt es mindestens einen
  reproduzierbaren Test- oder Diagnosepfad.
- Root-Cause-Arbeit bekommt ein Schema: Hypothese, Messpunkt, Entscheider,
  Rueckbauplan.

### P4: Subagent-Workflow einfuehren, aber sparsam

- Subagenten nur einsetzen, wenn ihre Arbeit eindeutig parallelisierbar ist.
- Jeder Subagent bekommt Scope, erlaubte Dateien, erwartete Ausgabe und Gate.
- Keine Architekturentscheidungen durch Subagenten; sie liefern Befunde.
- Codex Lead reviewed den Diff, laeuft Tests und committed.

### P5: Produktarbeit fortsetzen

Nach der Konsolidierung geht die technische Prioritaet weiter wie in
`docs/profile-consolidation-strategy.md` und
`docs/mega65-native-budget-strategy.md`:

1. Workbench-Kandidat mit Compile-String/Compile-Buffer-Gate gruen pinnen.
2. `mvp-ship` erst nach gruenem Workbench-Gate umhaengen.
3. Bank-0-Reclaim als naechstes strukturelles Projekt planen, nicht weitere
   halb-funktionale Profile erfinden.
4. Runtime-Export nach dem Workbench-Pin separat spezifizieren.

## Arbeitsstil ab jetzt

- Ich arbeite standardmaessig als Lead/Integrator, nicht nur als Lane-T-Worker.
- Bei offenen Implementierungsdetails entscheide ich konservativ anhand von
  Code, Messwerten und bestehenden Projektregeln.
- Ich frage Claude nur dann an, wenn Wissen nicht aus Repo, Tests oder HW-Logs
  rekonstruierbar ist oder wenn ein frischer HW-Befund seine laufende Arbeit
  betrifft.
- Ich halte Zwischenentscheidungen kurz in `docs/project-status.md` oder
  `docs/decision-log.md`, damit ein spaeterer Codex-Run ohne Chat-Kontext
  weiterarbeiten kann.

## Akzeptanzkriterien

Die Umstrukturierung ist gelungen, wenn:

- ein neuer Codex-Run von `README.md` zu `docs/project-status.md` findet und
  ohne Claude-Chat den aktuellen Stand versteht;
- keine aktuelle Roadmap mehr sagt, dass Claude exklusiv `src/**` besitzt;
- `docs/collaboration.md` nicht mehr die einzige Wahrheit ist;
- Produkt-, Diagnose-, Referenz- und Runtime-Targets unterscheidbar sind;
- Workbench-Gates, Budgetwerte und rote Tests an einer Stelle sichtbar sind;
- Claude-Beitraege optional integrierbar sind, aber das Projekt nicht blockieren.
