# IDE API Terminology

Stand: 2026-07-09.

Dieses Dokument pinnt die Begriffe fuer die Workbench-/IDE-API. Ziel ist, dass
`compile` nicht zwei verschiedene Dinge bedeutet.

## Begriffe

- **Transient compile:** Quelle wird kompiliert und direkt in der laufenden
  Lisp-Session installiert oder ausgefuehrt. Es entsteht kein Disk-Artefakt.
  Reservierte Namen: `compile-buffer`, `compile-file`, `eval-buffer`,
  `eval-region`, `eval-defun`. Im aktuellen Workbench-MVP ist davon
  `eval-buffer` vorhanden.
- **Library/FASL emit:** Quelle wird in einen persistenten L65M/FASL-
  Library-Slot geschrieben. Zukuenftige Namen tragen explizit `to-lib` oder
  `to-fasl`: `compile-buffer-to-lib`, `compile-file-to-lib`,
  `compile-string-to-lib`.
- **Emit and load:** Quelle wird in einen L65M/FASL-Slot geschrieben und danach
  sofort per `load-lib` in die laufende Session geladen. Zukuenftige Namen
  tragen explizit `and-load`: `compile-buffer-to-lib-and-load`,
  `compile-file-to-lib-and-load`. Im Workbench-MVP ist das kein eigener
  Public-Wrapper; `C-x C-k` macht intern `compile-buffer-to-lib` plus
  `load-lib`.

## Aktueller MVP-Stand

Die Workbench-MVP-API trennt die benutzbaren IDE-Wrapper inzwischen nach
Zielsemantik:

| Name | Aktuelle Bedeutung |
| --- | --- |
| `compile-string source dst` | Legacy: schreibt `source` als L65M/FASL-Lib in den vorallokierten Slot `dst`; entspricht kuenftig `compile-string-to-lib`. Rueckgabe bleibt `t`/`nil`; nach `nil` liefert `(compile-error)` Details. |
| `eval-buffer buffer` | Transient: liest alle Top-Level-Formen aus dem benannten IDE-Buffer, kompiliert/installiert sie via `lcc-run` in die laufende Session und schreibt kein Disk-Artefakt. MVP-Signatur ist bewusst schmal: `buffer` ist ein Name-String, Rueckgabe bei sauberem EOF ist `t`. |
| `compile-buffer-to-lib dst [buffer]` | Schreibt Buffer-Source als L65M/FASL-Lib in Slot `dst`. |
| `compile-file-to-lib src dst` | Liest Source aus Disk-Slot `src`, schreibt L65M/FASL-Lib nach `dst`. |

Compile-/FASL-Ausgaben schreiben aktuell nur in vorhandene/vorallokierte
D81-SEQ-Slots. Source-Save hat im Workbench-MVP einen schmalen Sonderfall:
`save-buffer-to` kann genau einen neuen normalen Source-Namen anlegen, indem es
den versteckten Reserve-Slot `tmp` beschreibt und dessen Directory-Eintrag auf
den Zielnamen umbenennt. Das erzeugt keine freie BAM-Allokation und resize't
keine Dateien; nach Verbrauch von `tmp` sind weitere neue Source-Dateien erst
nach neu gebautem D81 oder zusaetzlichem Reserve-Slot moeglich.
Die IDE-Wrapper `compile-buffer-to-lib` und `compile-file-to-lib`
akzeptieren im Workbench-MVP nur `fasl*`-Zielslots; andere Ziele liefern
`nil` und `(ide-error) => "not fasl"`. `compile-string` bleibt die
Low-Level-Backend-Bruecke und meldet Fehler ueber `(compile-error)`.
`eval-buffer` nutzt dieselbe Reader-Naht wie `compile-string`, meldet
IDE-seitige Auswahlfehler ueber `(ide-error)` und ist im Editor ueber
`M-x eval-buffer` erreichbar. `eval-region`/`eval-defun` bleiben deferred, bis
die ladbare IDE-Disk-Lib wieder mehr Code-/Metadatenreserve hat.

Im M-x-Command-Set zeigt die Workbench `compile-load` an. Das ist ein UI-Name
fuer `compile-buffer-to-lib` plus anschliessendes `load-lib`, damit der
haeufige Editorpfad kurz bleibt und zugleich die Public-API eindeutig ist.

## UI-Regel

Neue UI-Texte sollen die Zielsemantik nennen:

- `Compile+load:` fuer den aktuellen `C-x C-k`-Pfad.
- `Compile to lib:` fuer reines persistentes Emit ohne Laden.
- `Compile:` nur fuer kuenftiges transient direkt in die Session kompilieren.

## Migrationsregel

Neue Compile-Funktionen ohne `to-lib`/`to-fasl` duerfen nur transiente
Semantik bekommen. Historische Profile koennen weiter einen Legacy-
`compile-file` enthalten; im Workbench-MVP ist der persistente Datei-Emitter
`compile-file-to-lib`.
