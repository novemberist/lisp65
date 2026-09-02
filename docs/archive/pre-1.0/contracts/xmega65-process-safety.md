# xmega65 Process Safety

Stand: 2026-07-02. Headless-`xmega65`-Smokes koennen bei Hangs oder kaputten
Autostart-Pfaden CPU-lastige Hintergrundprozesse hinterlassen. Das ist ein
Betriebsrisiko fuer den lokalen Entwicklungsrechner und muss im Harness aktiv
abgesichert werden.

## Regel

Neue nicht-interaktive `xmega65`-Starts duerfen nicht direkt `timeout xmega65 ...`
aufrufen. Sie muessen ueber `scripts/xmega65-safe-run.sh` laufen:

```sh
scripts/xmega65-safe-run.sh "$unique_token" "$timeout_seconds" "$emu" [xmega65 args...]
```

`unique_token` muss in der `xmega65`-Commandline vorkommen und fuer genau diesen
Smoke eindeutig sein. Geeignet sind absolute Pfade von `-dumpmem`, `-screenshot`
oder einem temporaeren SD-Image.

`make xmega65-safety-check` ist Teil von `make check` und blockiert direkte
`xmega65`-/`timeout $emu`-Starts in Shell-Skripten. Reine Dokumentations-Heredocs
in Image-Build-Skripten sind erlaubt.

## Was der Safe-Runner tut

- nutzt das bestehende Timeout;
- nutzt, falls verfuegbar, `timeout --kill-after`;
- registriert `EXIT`/Signal-Traps;
- ruft danach `scripts/kill-xmega65-by-token.py "$unique_token"` auf;
- der Killer sendet zuerst `SIGTERM`, wartet kurz und sendet bei weiter passendem
  Token `SIGKILL`.

Damit werden nur `xmega65`-Prozesse beendet, deren Commandline den Smoke-Token
enthaelt. Interaktive oder fremde Emulator-Sessions bleiben unangetastet.

## Umgebungsvariablen

- `XMEGA65_TIMEOUT`: Laufzeitlimit des konkreten Smoke-Skripts.
- `XMEGA65_KILL_AFTER`: harte Nachfrist fuer GNU `timeout --kill-after`, Default
  `5s`.
- `XMEGA65_CLEANUP_GRACE`: Wartezeit zwischen `SIGTERM` und moeglichem `SIGKILL`
  im Token-Killer, Default `2` Sekunden.

## Abgedeckte Skripte

Diese Skripte nutzen den Safe-Runner:

- `scripts/smoke-xmega65.sh`
- `scripts/smoke-xmega65-prgtest.sh`
- `scripts/smoke-xmega65-f011-load.sh`
- `scripts/smoke-xmega65-f011-autoload.sh`
- `scripts/smoke-xc64-legacy.sh`

## Manuelles Aufraeumen

Erst prüfen:

```sh
pgrep -af xmega65
```

Gezielt nach einem bekannten Dump-/Image-Token aufraeumen:

```sh
python3 scripts/kill-xmega65-by-token.py /abs/path/to/smoke-dump.bin
```

Nur im Notfall, wenn keine interaktiven Emulatoren laufen sollen:

```sh
pkill xmega65
```
