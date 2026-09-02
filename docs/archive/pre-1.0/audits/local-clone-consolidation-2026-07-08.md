# Local Clone Consolidation

Stand: 2026-07-08. Ziel: permanente Clone-Drift beenden und `../lisp65` als
einzigen aktiven Integrations-Worktree nutzen.

## Ergebnis

Aktiv:

- `../lisp65` — kanonischer Worktree, trackt `origin/main`.
- `../lisp65.git` — lokaler bare Remote.

Archiviert:

- `../lisp65-archive/2026-07-08/lisp65-codex`
- `../lisp65-archive/2026-07-08/lisp65-claude`

Sicherungen:

- `../lisp65-archive/2026-07-08/lisp65-codex.bundle`
- `../lisp65-archive/2026-07-08/lisp65-claude.bundle`
- `../lisp65-archive/2026-07-08/lisp65-codex-status.txt`
- `../lisp65-archive/2026-07-08/lisp65-claude-status.txt`
- `../lisp65-archive/2026-07-08/lisp65-codex-branches.txt`
- `../lisp65-archive/2026-07-08/lisp65-claude-branches.txt`
- `docs/archive/local-clones/lisp65-codex-wip-2026-07-08.patch.gz`

## Audit-Befund

`../lisp65-codex` enthielt uncommitted Diffs in `Makefile`,
`docs/bank0-full-suite-strategy.md` und `docs/collaboration.md`. Der Inhalt
entsprach historischem S5-Proof-/Doku-WIP, dessen relevante Arbeit im heutigen
Hauptrepo bereits vorhanden ist. Der Diff wurde als Patch gesichert, aber nicht
in den aktiven Stand uebernommen.

`../lisp65-claude` war auf `main` veraltet und enthielt Claudes Branch
`claude/eager-antonelli-2526ec`, dessen relevante Workbench-Commits auf
`origin/main` integriert wurden. Der komplette Clone wurde zusaetzlich als
Bundle gesichert.

## Regel

Neue parallele Arbeit wird nicht mehr in `../lisp65-codex` oder
`../lisp65-claude` gestartet. Falls Claude einen zweiten Arbeitskontext
braucht:

```sh
scripts/create-claude-worktree.sh <thema>
```

Das erzeugt `../lisp65-work/claude-<thema>` auf Branch `claude/<thema>`.
Fuer andere parallele Arbeit gilt dasselbe Muster mit einem passenden
Branch-Prefix.

Nach Integration wird der Worktree entfernt:

```sh
git worktree remove ../lisp65-work/claude-<thema>
```
