# IDE-Kapazitaet vor AP6 (2026-07-11)

Status: umgesetzt und gegatet. Diese Phase schafft die Kapazitaet fuer AP6,
ohne das eingefrorene AP4-Layout, die P0-Bytecode-ABI oder das L65M-Format zu
aendern.

## Entscheidung

Die bisherige monolithische IDE wird als zwei geordnete Disk-Libs gebaut:

- `IDE`: Pflichtkern fuer den AP7-Loop, Persistenz, Directory, Compile/Load,
  Rendern und grundlegendes Editieren einschliesslich Kill-Line/Yank.
- `IDEX`: optionaler Komfort fuer Wort-/Seitenbewegung, Mark/Region, Suche und
  M-x.

`IDE` enthaelt den fail-closed Hook `%ide-x`. `IDEX` ueberschreibt genau diesen
Eintrag beim Laden. Die normale symbolische CALL-Aufloesung der VM bleibt
unveraendert; es gibt keinen neuen Runtime-Aufrufmodus und keine neue ABI.

40 ausschliesslich interne `%ide-*`-Helfer werden im Artefaktbuild privat
inline kompiliert: 29 im Core und 11 in IDEX. Sie sind danach absichtlich keine
dynamisch aufrufbare REPL-API. Der Hostcompiler verwendet dafuer eine nicht aus
Lisp-Quelltext konstruierbare IR-Markierung, isoliert die ehemalige
Top-Level-Funktionsumgebung und erhaelt die Tailposition. Rekursion, `&rest`,
indirekte Funktionswerte, Symbol-Literale, unbenutzte Allowlist-Eintraege und
verbleibende CALL-Kanten werden fail-closed abgelehnt. Der syntaxbewusste
Walker trennt dabei auswertbare Positionen von Bindern und `case`-Keys; der
fokussierte Unit-/VM-Gate pinnt zusaetzlich Argumentreihenfolge,
Tail-Weitergabe, Binder-Kollision, indirekte Referenzen und Rekursionszyklen.

Vier IDEX-Aufrufe benoetigen private Core-Helfer. Diese Cross-Tier-Menge ist
separat als `resident_private_inline_functions` deklariert und wird in IDEX
expandiert; sie erzeugt keine versteckte Runtime-Abhaengigkeit.

## Artefakte und Oracles

| Artefakt | Eintraege | Code | L65M-Image |
| --- | ---: | ---: | ---: |
| Baseline `ide-full` (nur Oracle) | 219 | 14787 B | 38179 B |
| Produkt-Core `IDE` | 151 | 12085 B | 29677 B |
| Produkt-Komfort `IDEX` | 29 | 3252 B | 8062 B |
| AP6-COW-Kern `M65D` | 35 | 3857 B | 6719 B |

Die Baseline bindet die alte Funktionsmenge. Der Kapazitaetsvertrag verlangt,
dass Core und IDEX zusammen genau die 40 deklarierten privaten Namen auslassen,
nur `%ide-x` physisch ueberlappen und das IDEX-Manifest genau diesen Override
deklariert. Core darf weder per CALL/TAILCALL noch als Literal-/Funktionswert
auf einen IDEX-Eintrag verweisen. Das sequenzielle Full-Oracle laedt logisch
Core und IDEX und fuehrt 125 Faelle aus: 120 IDE-Faelle plus 5
IDEX-spezifische Faelle.

## Gepinnte Kapazitaet

`config/ide-capacity-contract.json` bindet AP6 jetzt als
`measured-manifest-v1` an `build/bytecode/libs/m65d.manifest.json`. M65D misst
35 Directory-Eintraege, 3857 Code-Bytes und 6719 Image-Bytes. Gegen den
bereits geladenen IDE-Core sind 37 Symbole und 623 Namepool-Bytes neu.

Projektion nach `IDE + AP6 + IDEX`:

```text
directory=538, post_align=544/552, headroom=8
symbols=694/720, headroom=26
namepool=9240/9536, headroom=296
ext_peak_headroom=8528
disk_image_headroom=31940
```

Der reale heutige Ladepfad `IDE -> IDEX`, noch ohne AP6, misst:

```text
directory=501, post_align=504/552
runtime_symbols=648/720
runtime_namepool=8539/9536
codebuf_required=56/56
```

Das Codepufferlimit ist exakt belegt. Der Gate-Wert wird nicht vergroessert;
jede weitere Literalzunahme in einem Disk-Lib-Codeobjekt macht den Produktbuild
rot. AP4 bleibt bei 38/64 Runtime-Slots, Overlay-Basis `$c344` und 1811 B
Post-Boot-Reserve unveraendert.

## Produkt- und Testvertrag

- Workbench- und Demo-D81 enthalten `ide`, `idex` und `m65d` als getrennte SEQ-Dateien.
- `(load-lib "ide")` stellt den Pflichtkern bereit.
- `(load-lib "idex")` aktiviert danach die Komfortbefehle.
- `save-buffer-to` laedt `m65d` beim ersten Save automatisch.
- Core-only-Smokes laden IDEX bewusst nicht.
- Der UX-Hardware-Smoke laedt IDEX vor Suche, Region und M-x explizit.
- Der zusaetzliche D81-Eintrag verschiebt den freien M4-Directory-Pin auf Entry
  2 und die nach einem Allocator-Upload verwendeten M5-M7-Pins auf Entry 3.

Massgebliche Gates:

```sh
make bytecode-p0-private-inline-check
make bytecode-p0-ide-full-lib-check
make ide-capacity-check
make workbench-disk-lib-budget-check
make hw-workbench-ux-smoke-dry-run
```

## Grenze und naechster Schritt

Diese Phase implementiert weder Paket-Unload noch `defun-local` in der
Geraete-Toolchain. Die Privatisierung gilt nur fuer vorgebaute, explizit
klassifizierte IDE-Artefakte. Ein allgemeines Direct-Call-/Local-Function-ABI
bleibt ein separates Post-G6-Projekt.

AP6 nutzt die geschaffene Kapazitaet ohne Cap-, ABI- oder AP4-Layoutaenderung.
Der naechste Arbeitsfokus nach der erweiterten Live-G5-Abnahme ist AP7.
