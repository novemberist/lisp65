# MEGA65 Hardware Stress Tests

Stand: 2026-07-08. Ziel dieser Tests ist nicht ein weiterer schneller
Smoke-Test, sondern das Aufdecken versteckter Fehler, die erst durch längere
Läufe, wiederholte Allokation, Code-Window-Wechsel, Closure-Materialisierung,
Disk-Zugriffe oder echte Eingabe-/Renderpfade sichtbar werden.

## Testebenen

| Ebene | Transport | Zweck |
| --- | --- | --- |
| Sichtbarer Selftest | Etherload | PRG läuft autonom, zeigt grünen/roten Rahmen und PASS/FAIL-Zeile |
| Disk-/F011-Test | Etherload + `mega65_ftp` | D81 hochladen, mounten, `load`/`save`/FASL gegen echte F011-Pfade prüfen |
| JTAG-Diagnose | `m65` | Tastatur automatisieren, Screenshot/Textscreen prüfen, Speicherbereiche/Zähler dumpen |
| Langlauf | Etherload oder JTAG | Wiederholte Szenarien über Minuten, um GC-/DMA-/State-Leaks zu finden |

## Hardware-Opportunity-Smokes

Diese kleinen PRGs testen MEGA65-Hardware-Hebel isoliert, bevor daraus
Produktpfade werden. Sie starten wie die anderen HW-Smokes per Etherload und
verwenden keinen Hard-Reset.

```sh
make hw-access-smoke-dry-run
make hw-color-ram-smoke-dry-run
make hw-edma-screen-smoke-dry-run

make hw-access-smoke
make hw-color-ram-smoke
make hw-edma-screen-smoke
```

Erwartete sichtbare Marker:

```text
hw access pass 8/8
color ram pass 2/2
edma screen pass 7/7
```

`hw-access-smoke` prueft als Pflichtfaelle:

- Legacy-F018-DMA Bank-4-Roundtrip als Kontrollpfad.
- Enhanced-DMA Copy und Fill nach Bank 4.
- Enhanced-DMA Roundtrip gegen Attic RAM (`$8000000`).
- 45GS02-Flat-Access gegen bank-0-High-RAM (`$0fffa`).
- Q-Registerpfad (`LDQ`/`STQ`/`ADCQ`).
- MEGA65-Hardware-Multiplier und -Divider.

Zusaetzlich protokolliert er `flat_bank4_obs`: ein 45GS02-Flat-Write nach Bank
4 mit DMA-Readback. Dieser Messwert ist bewusst noch kein roter Pflicht-Gate,
weil fruehere Befunde hier xemu/HW-Divergenzen gezeigt haben.

`hw-color-ram-smoke` prueft als Pflichtfaelle:

- Enhanced-DMA Fill/Readback des vollen 28-bit-Color-RAM-Bereichs bei
  `$FF80000`.
- Enhanced-DMA Copy eines kleinen Farbmusters in die sichtbare Screen-Zeile.

Zusaetzlich protokolliert er `flat_cell_obs`: ein einzelner Flat-Write nach
`$FF80000` mit EDMA-Readback. Auch dieser Pfad ist vorerst explorativ.

`hw-edma-screen-smoke` prueft als Pflichtfaelle:

- erkannte 80x25-kompatible Screen-Geometrie;
- EDMA-Copy von 24 sichtbaren Screen-RAM-Zeilen eine Zeile nach oben;
- EDMA-Fill der neu freien letzten Screen-RAM-Zeile;
- EDMA-Copy von 24 Color-RAM-Zeilen bei `$FF80000` eine Zeile nach oben;
- EDMA-Fill der neu freien letzten Color-RAM-Zeile;
- JTAG-lesbare Result-Symbole fuer Screen- und Color-RAM-Ground-Truth.

Das ist der konkrete Gate fuer einen spaeteren EDMA-basierten
Screen-/Color-Scroll-Prototyp. Er ersetzt noch keinen Produktpfad.

JTAG-Readback der exportierten Result-Symbole:

```sh
make hw-access-smoke-readback-dry-run
make hw-color-ram-smoke-readback-dry-run
make hw-edma-screen-smoke-readback-dry-run

make hw-access-smoke-readback
make hw-color-ram-smoke-readback
make hw-edma-screen-smoke-readback
```

Die Readback-Ziele nutzen `scripts/hw-opportunity-readback.py`, loesen die
Result-Symbole aus dem jeweiligen `.prg.elf` auf und lesen sie per
`m65 --memsave`. Auch hier wird kein `m65 -F` ausgefuehrt.

### Live-HW-Protokoll: Hardware-Opportunity 2026-07-07

Transport: Etherload direkt aus laufendem Produkt/Test, **kein `m65 -F`**.
Readback: JTAG `/dev/ttyUSB1` per `m65 --memsave`.

`hw-access-smoke`:

```text
access: pass 8/8
  legacy_dma=PASS got=0x003f want=0x003f
  edma_copy=PASS got=0x003f want=0x003f
  edma_fill=PASS got=0x005a want=0x005a
  edma_attic=PASS got=0x00a6 want=0x00a6
  flat_bank0=PASS got=0x006a want=0x006a
  q_reg=PASS got=0x5679 want=0x5679
  math_mul=PASS got=0xb25a want=0xb25a
  math_div=PASS got=0x000c want=0x000c
  flat_bank4_obs=FAIL got=0x00ff want=0x007b
```

Entscheidung: EDMA nach Bank 4, EDMA nach Attic RAM, Bank-0-Flat-Access,
Q-Register und HW-Math sind auf echter HW gruen. Der explorative
`flat_bank4_obs` ist rot und bleibt kein Produktpfad.

`hw-color-ram-smoke`:

```text
color: pass 2/2
  edma_fill=PASS got=0x0006 want=0x0006
  edma_pattern=PASS got=0x0001 want=0x0001
  flat_cell_obs=FAIL got=0x00ff want=0x0002
```

Entscheidung: EDMA-Color-RAM-Fill und EDMA-Pattern-Readback sind auf echter HW
gruen. Der explorative Flat-Write nach `$FF80000` ist rot; Color RAM bleibt
damit EDMA-only.

Screenshot-Syntax fuer dieses `m65`-Build:

```sh
tools/m65tools/m65 -l /dev/ttyUSB1 -Sbuild/hw/hw-color-ram-smoke.png \
  > build/hw/hw-color-ram-smoke-screen.txt
```

Wichtig: `-S` ohne Leerzeichen und ohne `=` verwenden. Mit Leerzeichen wird der
Dateiname als PRG-Argument interpretiert; mit `=` versucht dieses Tool-Build
eine Datei mit fuehrendem Gleichheitszeichen zu schreiben.

### Live-HW-Protokoll: EDMA-Screen/Color 2026-07-08

Transport: Etherload direkt aus laufendem Produkt/Test, **kein `m65 -F`**.
Readback: JTAG `/dev/ttyUSB1` per `m65 --memsave`.
Screenshot: `build/hw/hw-edma-screen-smoke.png`.

```text
screen: pass 7/7
  geometry=PASS got=0x1950 want=0x1950
  screen_copy_top=PASS got=0x0002 want=0x0002
  screen_copy_last_visible=PASS got=0x0019 want=0x0019
  screen_tail_fill=PASS got=0x0020 want=0x0020
  color_copy_top=PASS got=0x0002 want=0x0002
  color_copy_last_visible=PASS got=0x000a want=0x000a
  color_tail_fill=PASS got=0x0001 want=0x0001
```

Entscheidung: EDMA kann auf echter HW eine 80x25-Textseite inklusive 28-bit
Color RAM um eine Zeile nach oben kopieren und die neu freie Zeile fuellen.
Damit ist ein kleiner EDMA-basierter Screen-/Color-Scroll-Prototyp technisch
freigegeben; Produktintegration bleibt von Footprint- und IDE-Stabilitaetsgate
abhaengig.

## Pilot: Full-HW-Stress

Der erste neue Test ist:

```sh
make hw-stress-full-dry-run
make hw-stress-full
make hw-stress-dmaprof
make hw-stress-deep-dry-run
make hw-stress-deep
sh scripts/hw-stress-full.sh --dry-run
sh scripts/hw-stress-full.sh --ip 'fe80::...%enp35s0'
```

Er baut das aktuelle `mvp-vm-stdlib-einsuite-full`-Profil, ersetzt nur `main`
durch `scripts/hw-stress-main.c` und fährt mit demselben externen Stdlib-Blob:

```sh
sh scripts/run-on-mega65.sh \
  --preload-bin 0x050000 build/bytecode/stdlib-p0.ext.bin \
  --run build/lisp65-hw-stress-full.prg
```

Erwartung am Gerät:

```text
stress pass 15/15
```

Der Test deckt ab:

- Top-Level-`eval` und native/Bytecode-Bridges.
- `lcc-run` mit rekursiven Funktionen.
- Rekursive Listenallokation und wiederholtes Verwerfen temporärer Listen.
- Closure-Capture und wiederholtes `funcall`.
- `defmacro` plus sofortige Nutzung.
- Einen String/List-Roundtrip.
- Runtime-Health: kein `gc_badobj`; einzelne Checks schlagen bei OOM fehl.

Optional kann der Test mit DMA-/VM-Zählern gebaut werden:

```sh
sh scripts/hw-stress-full.sh --dma-prof --ip 'fe80::...%enp35s0'
```

Die sichtbare PASS/FAIL-Ausgabe bleibt gleich. Die zusätzlichen Zähler werden
per JTAG-Dump über `m65 --memsave` ausgelesen:

```sh
python3 scripts/hw-jtag-counters.py \
  --elf build/lisp65-hw-stress-full-dmaprof.prg.elf \
  --device /dev/ttyUSB1 \
  --prefix hw-stress-full-dmaprof
```

Diese Variante ist knapp am `$C000`-Etherload-Limit und ist als Diagnoseprofil
gedacht, nicht als dauerhaftes Produkt-Gate.

## Deep-Dive-Spezialtests

Die zehn optionalen Bughunting-Tests laufen nicht als ein großes PRG: das Full-
Profil ist dafür zu knapp. Stattdessen sind sie in zwei Shards geteilt, beide
weiterhin mit `prg_file_end < $C000`:

```sh
make hw-stress-deep1-dry-run
make hw-stress-deep2-dry-run
make hw-stress-deep-dry-run

make hw-stress-deep1
make hw-stress-deep2
make hw-stress-deep
```

Erwartete Marker:

```text
stress deep1 pass 5/5
stress deep2 pass 5/5
```

`deep1` deckt Runtime-/Compiler-Fehler ab:

- **GC-Lifetime-Torture:** live gehaltene verschachtelte Listen überstehen
  absichtlichen Allokations-Churn.
- **VM-Code-Window-Thrash:** mehrere kleine Bytecode-Funktionen werden in enger
  Schleife wechselnd aufgerufen.
- **Closure-Churn:** wiederholte Closure-Factories mit Capture und `funcall`.
- **Macro-in-Compiled-Code:** ein frisch installierter Makro wird in einer danach
  kompilierten Funktion genutzt.
- **REPL-/Reader-Recovery-Kern:** ein absichtlicher `undefined function`-Abort
  wird per Harness-Toplevel gefangen; die nächste Form muss korrekt laufen.

`deep2` deckt Bibliotheks-/IDE-Oberfläche ab:

- **Symbol-/Equal-Churn:** viele neue Symbolnamen plus rekursives `equal`.
- **String-Pipeline:** `string-append`, `string-upcase`, `search` und Suffix-Test.
- **IDE-Buffer-Burst:** Insert, Split, Insert, Delete auf dem IDE-Buffer-Modell.
- **Numeric-Edges:** `/`, Dialekt-`mod`/`remainder` mit negativem Dividend,
  `clamp`, `max`, `min`.
- **Screen/Runtime-Health:** `screen-size`, `screen-bulk-p` und `gc_badobj == 0`.

`--dma-prof` ist fuer diese Shards bewusst gesperrt: `deep1-dmaprof` liegt aktuell
ueber der Etherload-Invariante. Fuer Zaehlermessungen weiter das normale
`hw-stress-dmaprof` nutzen.

### Live-HW-Protokoll 2026-07-07

Transport: Etherload direkt aus laufendem Produkt/Test, **kein `m65 -F`**.
Readback: JTAG `/dev/ttyUSB1`, finaler Screenshot + Counter-Dump.

| Profil | Artefakt | Ergebnis | Counter |
| --- | --- | --- | --- |
| `deep1` | `build/lisp65-hw-stress-deep1.prg`, `prg_file_end $bffb` | `stress deep1 pass 5/5` | `gc_runs=25`, `gc_badobj=0`, `mem_oom=0` |
| `deep1` repeat ohne Rebuild | gleiches Artefakt | `stress deep1 pass 5/5` | `gc_runs=25`, `gc_badobj=0`, `mem_oom=0` |
| `deep2` | `build/lisp65-hw-stress-deep2.prg`, `prg_file_end $be80` | `stress deep2 pass 5/5` | `gc_runs=13`, `gc_badobj=0`, `mem_oom=0` |

Readback-Artefakte liegen unter `build/hw/`, u. a.
`hw-stress-live-deep1-fixed-*`, `hw-stress-live-deep1-repeat-*` und
`hw-stress-live-deep2-fixed-*`.

Gefundene und behobene Harness-Auffaelligkeiten:

- Die ersten Deep-Formen waren zu aggressiv komprimiert (`lcc-run'...`,
  `string-append"..."`) und wurden vom Reader als falsche Symbolnamen gelesen.
  Die Teststrings enthalten jetzt die noetigen Token-Trennzeichen.
- Der JTAG-Textdump enthaelt ANSI-Farbsequenzen zwischen Zeichen. Der
  Redeploy-Runner strippt ANSI nun vor dem PASS-Marker-Check.
- Der Numeric-Edge-Test erwartete zunaechst CL-`mod`; lisp65 pinnt `mod` aber als
  `remainder` mit Vorzeichen des Dividenden. Erwartung ist jetzt `(mod -3 5) => -3`.
- Ein einzelner frueher Deep1-Readback zeigte `gc_badobj=4`, wurde danach mit
  korrigiertem Shard und einem Repeat-Lauf nicht reproduziert (`gc_badobj=0`).
  Beobachtung offen halten, aber kein bestaetigter Bug.

## Redeploy-Stress

Der zweite automatisierte Test kapselt die inzwischen bewiesene Normalpraxis:
mehrere Etherload-Deploys direkt aus dem laufenden Produkt/Test heraus, ohne
`m65 -F` und ohne erneutes SHIFT+£-Scharfstellen.

```sh
make hw-stress-redeploy-dry-run
make hw-stress-redeploy
make hw-stress-redeploy-deep-dry-run
make hw-stress-redeploy-deep
sh scripts/hw-stress-redeploy.sh --count 10 --ip 'fe80::...%enp35s0'
```

Der Runner:

- baut die Stress-Artefakte einmalig;
- deployt Blob+PRG `N` mal per Etherload;
- zieht final einen JTAG-Screenshot;
- prüft den finalen Textdump auf `stress pass 15/15`;
- liest bekannte Runtime-Zähler über `scripts/hw-jtag-counters.py` aus.

Wichtige Optionen:

- `--count <n>`: Anzahl der Redeploy-Zyklen.
- `--dma-prof`: Redeploys mit DMA-Profil-PRG fahren.
- `--device /dev/ttyUSB1`: JTAG-Gerät für Screenshot/Counter.
- `--expect <text>`: erwarteten Marker im finalen Textdump ändern.
- `--no-expect`: finalen Marker-Check überspringen.
- `--no-readback`: nur Etherload-Zyklen fahren.

## Weitere sinnvolle Tests

1. **JTAG-IDE-Typing-Burst**
   Über `m65 -T` schnelle Folgen von Zeichen, Backspace, Cursorbewegungen und
   Enter senden. Danach Screenshot/Textscreen ziehen und mit Buffer-Inhalt
   vergleichen. Ziel: Koaleszenz-, Dirty-Hint-, Cursor- und Wraparound-Fehler.

2. **Disk-Slot-Abuse**
   D81 mit mehreren vorallozierte Slots bauen, nacheinander kurze, lange und
   grenznahe Source-Strings speichern, zurückladen und ausführen. Ziel:
   F011-Sektorgrenzen, Padding, Slot-Overwrite und `load`/`save`-State.

3. **FASL-Recompile-Loop**
   Mehrere kleine Funktionen wiederholt per `compile-file` in denselben FASL-Slot
   schreiben, laden und aufrufen. Ziel: FASL-Trailer, Lib-Registrierung,
   VM-Directory-Reuse und Literal-Lifetime.

4. **On-Demand-Lib-Churn**
   Dev-Core booten, Pilot-Libs in wechselnder Reihenfolge laden (`place`, `ide`,
   später `fmt`, `fixed`, `strx`) und danach repräsentative Funktionen aus jeder
   Lib aufrufen. Ziel: Symbol-/VM-Dir-Headroom, Literal-Keep und Lade-Reihenfolge.

5. **GC-Watermark-Langlauf**
   Ein autonomes PRG erzeugt und verwirft über Minuten Listen, Strings und
   Closures, prüft periodisch feste Summen und zeigt `gc_runs`/`gc_badobj`.
   Ziel: seltene Mark-/Sweep-/EXT-Heap-Fehler.

6. **DMA-Window-Thrash**
   Viele kleine Funktionen in wechselnder Reihenfolge aufrufen, mit kleinem
   `VM_CODEBUF`-Profil. Ziel: Code-Fenster-Nachladen, DMA-Listen-Härtung und
   Symbol-/Namepool-EXT-Zugriffe.

7. **REPL-Recovery**
   Absichtlich fehlerhafte Formen eingeben (`undefined function`, Typfehler,
   abgebrochene Listen), danach korrekte Formen auswerten. Ziel:
   Fehlerzustand-/Screen-/Reader-Recovery ohne Clear-Screen-Nebenwirkungen.

8. **Redeploy-Runde ohne Hard-Reset**
   Mehrfach Blob-Preload und PRG-Start direkt per Etherload aus dem laufenden
   Produkt heraus. Ziel: fragile Annahmen über warmen Gerätezustand und
   wiederholte Blob-/PRG-Deploys. `m65 -F` gehoert nicht in diesen Normaltest,
   weil der harte Reset das SHIFT+£-Remote-Flag loescht und manuell neu
   scharfgestellt werden muss. Automatisiert durch `scripts/hw-stress-redeploy.sh`.

Die Tests sollten nicht alle in `make check` landen. `make check` bleibt host- und
dry-run-orientiert; echte Hardware-Langläufe sollten explizit gestartet werden.
