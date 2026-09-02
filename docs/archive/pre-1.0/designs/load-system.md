# Load System Design

Stand: 2026-07-06, mit Nachzug 2026-07-08. Dieses Dokument konkretisiert die
Load-Schicht nach dem M4-MVP. Es ist ein Designvertrag, kein aktiver
Implementierungsauftrag. Der aktuelle MVP ist `make mvp-ship`: Workbench-PRG,
externes Bytecode-Stdlib-Blob und D81 mit ladbarer IDE-Lib plus vorallokierten
Compile-Zielslots. Post-MVP geht es um Suchpfade, Module, Bytecode-Dateiformate
und robustere Nutzer-Libraries.

## Ziele

- Nutzerdateien und Libraries koennen spaeter ohne Rebuild geladen werden.
- Source-Libraries und vorkompilierte Bytecode-Dateien koennen denselben Modulnamen
  bedienen.
- IDE-Commands wie `eval-buffer`, `load-file`, transienter `compile-file`,
  `compile-file-to-lib` und Autoloads bekommen einen stabilen Namens-/
  Suchpfadvertrag.
- Das System vermeidet harte Annahmen ueber F011, D81 oder SD-FAT, solange der
  Hardwarepfad nicht wieder aktiv ist.

## Abgrenzung zum M4-MVP

Heute:

- Stdlib/IDE/lcc liegen als eingebettetes Bytecode-Blob vor.
- `(load)` und `(save)` sind fuer den Full-Produktpfad resident und HW-validiert.
- Der aktuelle Diskpfad ist bewusst klein: F011/D81, einfache Namen und
  Overwrite-in-place fuer Save-Slots.

Post-MVP:

- Suchpfade, Module und portable Dateinamen werden user-sichtbar stabilisiert.
- Datei-I/O bekommt einen breiteren portablen Vertrag.
- Bytecode-Dateien koennen optional schneller geladen werden als Source.

## Dateinamen

Kanonscher Name fuer portable lisp65-Dateien:

- 1 bis 8 Zeichen Basisname, optional 1 bis 3 Zeichen Extension.
- Portable Zeichen: `A-Z`, `0-9`, `-`, `_`.
- Case-insensitiv fuer Dateisystemsuche; intern wird fuer 8.3-Ziele uppercase
  normalisiert.
- Empfohlene Extensions:
  - `.LSP` fuer Source
  - `.LBC` fuer lisp65-Bytecode
  - `.LMD` fuer kleine Modulmetadaten, falls noetig

Beispiele:

- `STRINGS.LSP`
- `SEQ.LBC`
- `USERINIT.LSP`

Lange Namen koennen spaeter im Host/SD-Pfad erlaubt werden, duerfen aber keine
Voraussetzung fuer portable Libraries sein.

## Modulnamen

Ein Modulname ist ein Lisp-Symbol oder String, der auf Dateikandidaten abgebildet wird:

```lisp
(require 'strings)
(load "strings")
```

Kanonische Modulnamen sind lowercase in Doku/Source und uppercase auf 8.3-Medien.
`strings` sucht daher konzeptionell:

1. `STRINGS.LBC`
2. `STRINGS.LSP`

Wenn beide existieren, gewinnt Bytecode, ausser der Nutzer verlangt explizit Source.

## Suchpfade

Konzeptionelle Variable:

```lisp
*load-path*
```

Erster portabler Default:

1. aktuelles Arbeitsverzeichnis / aktueller Disk-Kontext
2. `LIB/`
3. `USER/`

MEGA65-spezifische Abbildung spaeter:

- SD-Root: `/LISP65/`, `/LISP65/LIB/`, `/LISP65/USER/`
- D81-Root: `LISP65.D81` mit Directory-Eintraegen `LIB-*` oder flachen 8.3-Namen
- Emulator-/Host-Pfad: echte Host-Verzeichnisse mit denselben logischen Namen

Der Suchpfadvertrag ist logisch. Welche Transport-Schicht ihn bedient
(Host-`fopen`, SD-FAT, D81, eingebettetes Image), ist eine Backend-Entscheidung.

## Load-Operationen

Minimal:

```lisp
(load "file")      ; Source laden und Top-Level-Formen evaluieren
(require 'module)  ; Modul laden, falls noch nicht provided
(provide 'module)  ; Modul als geladen markieren
```

Spaeter:

```lisp
(compile-file "file")        ; Source transient in die laufende Session kompilieren
(compile-file-to-lib "file") ; Source -> .LBC/L65M-Library-Artefakt
(load-bytecode "file")
(autoload 'function 'module)
```

Rueckgabe:

- `load`: `t` bei Erfolg; Fehler bricht zum Toplevel ab.
- `require`: Modulname oder `t` bei Erfolg; `nil` nur fuer "bereits vorhanden" ist
  nicht vorgesehen, weil das in Scripts leicht Fehlinterpretationen erzeugt.
- `provide`: Modulname.

## Autoloads

Autoload ist eine Symbol-Funktionsbindung mit Modulhinweis:

```lisp
(autoload 'string-trim 'strings)
```

Beim ersten Funktionsaufruf:

1. `require` laedt das Modul.
2. Die echte Funktionsbindung muss danach vorhanden sein.
3. Der urspruengliche Aufruf wird mit denselben Argumenten wiederholt.

Fehlt die Funktion nach dem Laden, ist das ein harter Fehler:

```text
autoload: function not provided
```

Autoloads sind fuer IDE und Help-System wichtig, aber nicht fuer den ersten
Runtime-Load-Slice erforderlich.

## D81-/SD-Konvention

Der spaetere MEGA65-Release darf zwei Artefakte haben:

- self-contained PRG mit eingebetteter Kern-Stdlib
- optionales Library-Medium mit Nutzer-/Zusatzlibraries

Empfohlener SD-Root-Name:

```text
LISP65.D81
```

Empfohlener D81-Inhalt:

```text
LISP65     PRG   ; optionaler Starter oder Kopie des PRG
STRINGS   LSP
STRINGS   LBC
USERINIT  LSP
```

Wichtig: Das ist Packaging-Konvention, keine Aussage, dass der aktuelle MVP D81 zur
Stdlib-Laufzeit liest. Heute wird ein D81 hoechstens als Begleitartefakt oder fuer
spaetere Load-Experimente erzeugt.

## Fehlersemantik

Fehler brechen wie andere Runtime-Fehler zur REPL zurueck:

- `load: not found`
- `load: read error`
- `load: bad bytecode`
- `require: module not found`
- `autoload: function not provided`

Bereits erfolgreich ausgewertete Top-Level-Formen bleiben wirksam. Es gibt fuer den
ersten Slice keinen Transaktions-Rollback.

## Erste Implementierungsscheiben

1. **Host-only Design-Slice:** Host-Oracle fuer Modulnamen, Suchpfadauflösung und
   `provide`/`require`-Registry ohne MEGA65-I/O.
2. **Embedded Source Slice:** `load_source` weiterverwenden, aber aus einem
   abstrakten Source-Provider lesen.
3. **Bytecode File Slice:** `.LBC`-Format aus dem bestehenden Stdlib-Embed-Format
   ableiten; Host-Loader zuerst.
4. **MEGA65 I/O Slice:** erst nach neuer Freigabe der Runtime-I/O-Arbeit; keine
   Vermischung mit dem aktuellen MVP-Gate.

Done fuer den ersten Post-MVP-Load-Slice: Host-Tests beweisen, dass ein Modulname
deterministisch auf Kandidatendateien abgebildet wird, `require` idempotent ist,
`provide` die Registry aktualisiert und Autoload-Eintraege eindeutig beschrieben sind.
