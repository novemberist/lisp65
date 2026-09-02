# Claude Worktree Workflow

Stand: 2026-07-08. Claude arbeitet nicht mehr in einem permanenten
`lisp65-claude`-Clone. Neue Claude-Arbeit laeuft in kurzlebigen Git-Worktrees
unter:

```text
/home/alex/quicklisp/local-projects/lisp65-work/claude-<thema>
```

Der kanonische Integrations-Worktree bleibt:

```text
/home/alex/quicklisp/local-projects/lisp65
```

Claude darf den Integrations-Worktree lesen, soll dort aber nicht direkt
editieren oder committen.

## Neuen Claude-Worktree anlegen

Aus dem kanonischen Repo:

```sh
cd /home/alex/quicklisp/local-projects/lisp65
scripts/create-claude-worktree.sh <thema>
```

Beispiel:

```sh
scripts/create-claude-worktree.sh ide-scroll-diagnosis
```

Das erzeugt:

```text
Worktree: /home/alex/quicklisp/local-projects/lisp65-work/claude-ide-scroll-diagnosis
Branch:   claude/ide-scroll-diagnosis
```

## Arbeitsregeln fuer Claude

- Immer von `origin/main` starten.
- Nur im eigenen `../lisp65-work/claude-<thema>`-Worktree editieren.
- Keine Arbeit in `../lisp65`, `../lisp65-claude` oder `../lisp65-codex`.
- Keine Architekturentscheidung nur im Handoff verstecken; dauerhafte
  Entscheidungen gehoeren in `docs/decision-log.md` oder die passende
  Strategiedoku.
- Vor Uebergabe mindestens `git status --short --branch` und die relevanten
  Gates notieren.

## Handoff an Codex

Claude liefert in `docs/collaboration.md` oder in der Nachricht an den User:

```text
Branch/Commit:
Worktree:
Ziel:
Dateien:
Kommandos:
Footprint/Budget:
HW/JTAG:
Ergebnis:
Risiken:
Naechster sinnvoller Schritt:
```

Codex reviewed den Branch/Diff im Integrations-Worktree, laeuft die noetigen
Gates und integriert nach `main`.

## Aufraeumen nach Integration

Nach Merge/Push entfernt Codex den Worktree:

```sh
cd /home/alex/quicklisp/local-projects/lisp65
git worktree remove ../lisp65-work/claude-<thema>
```

Falls ein Branch nach der Integration nicht mehr gebraucht wird:

```sh
git branch -d claude/<thema>
```
