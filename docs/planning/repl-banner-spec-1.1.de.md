# REPL-Boot-Banner „λ LISP65“

Status: Die ursprünglich autorisierte Implementierung wurde am 2026-07-16 von
der Sichtabnahme auf echter Hardware verworfen. Die korrigierte Block-Lambda-
Darstellung und ihr zusätzliches Kapazitätsdelta wurden noch am selben Tag auf
Hardware abgenommen und vom Owner autorisiert. Die Produktpromotion ist frei;
die reguläre Wellen-Neupinnung steht noch aus.

## Erscheinungsbild

Der Banner belegt beim ersten REPL-Start die Zeilen 0–7. Der erste Prompt
steht auf Zeile 9.

```text
  ██           ██      ████    ██████   ██████    ██████   ██████
   ██          ██       ██     ██       ██  ██    ██       ██
    ██         ██       ██     ██████   ██████    ██████   ██████
    ███        ██       ██         ██   ██        ██  ██       ██
  ██  ██       ██       ██         ██   ██        ██  ██       ██
 ██    ██      ██████  ████    ██████   ██        ██████   ██████
 ──────────────────────────────────────────────────────────────────
                                            WORKBENCH - DIALECT V2
```

- Bei Abweichungen der Textgrafik ist die explizite Koordinatentabelle
  normativ.
- Das Lambda besteht aus gelben Reverse-Video-Spaces als sechszeilige
  Blocktreppe. Das ist absichtlich zeichensatzunabhängig: Im Mixed-Case-
  Zeichensatz des Produkts sind die Screencodes 77 und 78 die Buchstaben `M`
  und `N`, keine Diagonalgrafik.
- Die Blockschrift besteht aus Reverse-Video-Spaces über Bit 7 des
  `scr_put_at`-Attributs und Weiß als Farbe 1.
- Die Trennlinie verwendet Screencode 64 in den Spalten 1–66.
  `screen-put-char` übernimmt jeden hellgrauen Farbstore; ein folgender roher
  Screenbyte-Write veröffentlicht die Linienglyphe über den gepinnten
  Workbench-Vertrag (`$0800`, 80 Spalten). Die kanonische Workbench aktiviert
  die residente Fähigkeit `LISP65_SCREEN_WRITE_STRING` nicht, deshalb darf der
  Banner nicht von CALLPRIM 12 abhängen.
- Der hellgraue Untertitel beginnt in Spalte 44. Der ASCII-Bindestrich ist die
  akzeptierte 1.1-Darstellung. Der Mittelpunkt bleibt kosmetische
  Wiedervorlage, bis seine PETSCII-Abbildung gemessen und gepinnt ist.
- Startspalten: L=15, I=23, S=29, P=37, 6=45, 5=53. S und 5 verwenden
  absichtlich dasselbe Glyphenmuster.
- Lambda-Runs `(Zeile: Spalte,Länge)`: `0:2,2`; `1:3,2`; `2:4,2`;
  `3:4,1 + 5,2`; `4:2,2 + 6,2`; `5:1,2 + 7,2`.

## Implementierungsvertrag

Der Bannerkörper ist Lisp, von lcc kompiliert und in der Produkt-VM
ausgeführt. Eine minimale native Naht ist unvermeidbar, weil die native REPL
sowohl `scr_init()` als auch den ersten Prompt besitzt. Nach `scr_init()` und
vor diesem Prompt ruft sie `%repl-banner` über
`LISP65_BYTECODE_STDLIB_REPL_BANNER_ENTRY` auf.

Der bestehende Stdlib-Generator erzeugt dieses Ordinal aus derselben
Funktionsliste wie das Directory. Ein handgeschriebenes Ordinal ist verboten.
Die Naht startet den Banner, sie implementiert ihn nicht ein zweites Mal.

Der korrigierte kompakte ASCII-Runstream wird von drei persistenten internen
Einträgen ausgeführt:

- `%banner-separator`: 89 B;
- `%banner-run`: 142 B;
- `%repl-banner`: 145 B.

`%banner-runs` und `%banner-subtitle` sind private Inline-Helfer. Die drei
persistenten Einträge sind weder öffentlich noch exportiert. Der ursprünglich
autorisierte Banner hatte die ausgerichtete residente Nutzung bereits von 208
auf 216 erhöht. Die Korrektur fügt einen rohen Eintrag hinzu (210 auf 211),
bleibt aber im selben 216er-Align-Bucket; der Directory-Headroom nach Align
bleibt daher 168.

REPL-Cursor, Untergrenze, Limit und Status sind bytegroß. Alle Produktprofile
sind durch `REPL_BUF_MAX <= 255` begrenzt; Werte außerhalb 2–255 werden bereits
vom Präprozessor abgelehnt. Diese Korrektur bezahlt die Launch-Naht und
verschiebt die Overlay-Basis von `$c354` auf `$c304`.

## Gemessene Kapazität

Der reale Produktlink ersetzt die ursprüngliche Schätzung von 150–200 B.

| Dimension | Baseline | Banner-Kandidat | Delta |
|---|---:|---:|---:|
| Bank-0-Reserve nach Boot | 1.795 B | 1.876 B | +81 B |
| EXT-Headroom der Standardkomposition | 25.537 B | 25.186 B | −351 B |
| freie Symbole | 391 | 389 | −2 |
| Namepool-Headroom | 5.668 B | 5.643 B | −25 B |
| Directory-Headroom nach Align | 176 | 168 | −8 |
| Overlay-Headroom | 2 B | 82 B | +80 B |
| Boot-Overlay-Größe | 1.669 B | 1.669 B | ±0 |

Die Hardwarekorrektur ist separat gegen diesen autorisierten Banner-Kandidaten
vermessen:

| Dimension | Autorisierter Banner | Korrigierter Kandidat | Zusatzdelta |
|---|---:|---:|---:|
| Bank-0-Reserve nach Boot | 1.873 B | 1.873 B | ±0 |
| EXT-Headroom der Standardkomposition | 25.186 B | 25.161 B | −25 B |
| freie Symbole | 389 | 388 | −1 |
| Namepool-Headroom | 5.643 B | 5.625 B | −18 B |
| Directory-Headroom nach Align | 168 | 168 | ±0 |
| Overlay-Headroom | 80 B | 80 B | ±0 |
| Boot-Overlay-Größe | 1.669 B | 1.669 B | ±0 |

Das Boot-Overlay ist nicht byteidentisch: Seine absoluten Relokationen ändern
sich mit der VMA-Verschiebung von `$c354` nach `$c304`. Quelle, Größe und Form
des Control-Audits bleiben unverändert; die Wellen-Neupinnung übernimmt den
neuen SHA.

## Abnahme-Gates

- `make v11-repl-banner-visual-check` führt den real generierten Banner in
  der P0-VM aus und verwirft Mutationen an Screenwrites, Form der
  Primitivaufrufe, Trennlinien-Pokes, Prompt-Vorschub oder Rückgabewert.
- `make v11-repl-banner-vm-check` führt das generierte Workbench-Artefakt mit
  ASAN/UBSAN in der nativen C-VM aus und leitet die optionale Fähigkeit
  `screen-write-string` aus dem echten Produktprofil ab. Das Gate verwirft
  einen Banner, der nur funktioniert, weil ein Hosttest eine im Produkt
  inaktive Primitive erfindet.
- Das Oracle pinnt 235 sichtbare Writes: 147 Lambda-/Buchstabenzellen,
  66 Trennlinienzellen und 22 Untertitelzellen. Zusätzlich pinnt es neun
  Zeilenvorschübe und Prompt-Zeile 9.
- Der REPL-Screenshot-Verifier ist zeilenunabhängig und besitzt einen
  Banner-Präfix-Selbsttest; er setzt keinen Prompt in Zeile 0 voraus.
- Der kanonische Differenzlink muss alle oben autorisierten Kapazitätswerte
  reproduzieren.
- Ein Screenshot echter Hardware ist für die Sichtabnahme verpflichtend. Die
  korrigierte Probe ist an SHA-256
  `7bc0ff2468c8dcbd089f000422dc62f4f607f2e7394ae04790f06ef4d3725e6c`
  gebunden; sie zeigt Block-Lambda, Schriftzug, Trennlinie, Untertitel und den
  sauberen ersten Prompt vollständig. Die Welle darf erst siegeln, wenn die
  korrigierten Quellen in den Kandidaten der regulären Neupinnung promotet sind.
- Reguläre R4/R5/R6-Neupinnung und Single-Device-G6 bleiben verpflichtend.

Der Banner bleibt vom Produkt selbst gezeichnet: Nach der minimalen,
generatorgebundenen Startnaht entsteht sein vollständiges Erscheinungsbild
aus Lisp-Code, den lcc kompiliert und die Workbench-VM ausführt.
