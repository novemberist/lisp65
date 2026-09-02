# F011-Write-Kalibrierung (SAVE-Kern, Prio 1)

> **KONTEXT-HÄRTUNG (2026-07-13, G6-Freezer-Fund):** `$D680=$81` mappt den
> durch `$D689.7` gewählten Puffer. Ein Freezer kann `$D689=$80` hinterlassen
> und damit den direkten SD-Puffer statt des F011-Puffers sichtbar machen.
> Der kanonische Treiber setzt deshalb vor jeder Transaktion `$D689=$00`,
> etabliert I/O-, Drive-, Track-, Sektor- und Seitenzustand neu und schließt
> das Fenster mit `$D680=$82`. Ein rohes `$D680=$02` ist im F011-Produktpfad
> nicht mehr zulässig. Permanenter Hardwarefall:
> `work-media-save-remount-read` mit erzwungenem `$D689=$80`.

> **✅ ERGEBNIS (2026-07-05, Nutzer am Gerät): VARIANTE A HW-BESTÄTIGT.**
> Kalibrier-Sequenz auf echter MEGA65: `(%disk-write-sector 79 0)` → `t` (Write + Readback-
> Verify), nach Puffer-Wegspülung (Sektor 40 lesen) liefert der frische Read die Rampe korrekt
> (`(%disk-byte 5)`→5, `(%disk-byte 200)`→200). Der Schreibweg $DE00-Fenster + F011-Kommando
> `$84` funktioniert wie der Leseweg. Damit ist die letzte HW-Unbekannte des SAVE-Pfads geklärt;
> der Rest dieses Dokuments bleibt als Referenz für künftige Re-Kalibrierungen.

**Zweck:** Den EINEN unsicheren Baustein des SAVE-Kerns am Gerät klären: den Puffer-Rückweg
beim F011-Schreiben. Lesen ist HW-bewiesen (M1-Weg: `$D680=2` → `$D680=$81` → `$DE00`);
beim Schreiben ist Variante A implementiert (Analogie: `$DE00`-Fenster beschreiben +
F011-Kommando `$84`). Ob sie stimmt, sagt das eingebaute **Readback-Verify**:
`(%disk-write-sector T S)` liefert nur dann `t`, wenn die 256 B bitgenau von der Disk
zurückkommen — ein falscher Weg gibt sauber `nil`, nie stille Korruption.

xemu-F011 ist in dieser Umgebung defekt → Kalibrierung NUR am echten Gerät (wie die
Lese-Kalibrierung 2026-07-04).

## ⚠️ Nur mit Scratch-Disk!

Der Test schreibt echte Sektoren. **Ausschließlich eine Wegwerf-D81 mounten** (Kopie von
`make s5-source-d81`-Output oder leere D81) — nie die Quell-/Arbeits-Disk. Schreibziel ist
Track 79 (weit weg von Directory-Track 40 und den Datei-Tracks 41+).

## Vehikel bauen + deployen

```sh
# Kalibrier-PRG = Load-Profil (F011 + Treewalk-REPL + peek/poke) + Write-Kern:
BASE=$(sed -n 's/^M65VMSTDLIB_LOAD_EXTRA_CFLAGS ?= //p' Makefile)
make mvp-vm-stdlib BYTECODE_STDLIB_SUITE=tests/bytecode/stdlib/p0-stdlib-load-subset.json \
  M65VMSTDLIB_EXTRA_CFLAGS="$BASE -DMEGA65_F011_WRITE"
# -> build/lisp65-mega65-vm-stdlib.prg (~40 KB) + build/bytecode/stdlib-p0.ext.bin
# DANACH make mvp-vm-stdlib ohne Overrides, um den Default (39489) wiederherzustellen!

# Deploy (Scratch-D81 vorher per mega65_ftp auf die SD legen):
mega65_ftp -e -y -c "put scratch.d81 SCRATCH.D81"
scripts/run-on-mega65.sh --mount SCRATCH.D81 --preload-bin 0x050000 build/bytecode/stdlib-p0.ext.bin \
  --run build/lisp65-mega65-vm-stdlib.prg   # bzw. etherload -m SCRATCH.D81 ... -r <prg>
```

## Kalibrier-Sequenz (REPL am Gerät)

```lisp
(+ 1 2)                          ; 1) Boot-Sanity -> 3
(%disk-read-sector 40 0)         ; 2) Lese-Sanity -> t (Header-Sektor)
(dotimes (i 256) (%disk-poke i i)) ; 3) Muster in den Scratch: Byte i = i (Rampe)
(%disk-write-sector 79 0)        ; 4) DER TEST -> t = Variante A funktioniert!
(%disk-read-sector 40 0)         ; 5) Puffer WEGSPUELEN (anderen Sektor lesen)
(%disk-read-sector 79 0)         ; 6) Ziel frisch lesen -> t
(%disk-byte 5)                   ;    -> 5    (Rampe da?)
(%disk-byte 200)                 ;    -> 200
```

**Persistenz-Gegenprobe (schließt reinen Puffer-Erfolg aus):** Gerät resetten, Vehikel neu
starten, Schritte 6 wiederholen — oder am PC nachsehen:
```sh
mega65_ftp -e -y -c "get SCRATCH.D81 back.d81"
# CBM-Logiksektor (T,S) liegt im D81-Image bei Offset ((T-1)*40 + S) * 256:
python3 -c "print(hex(((79-1)*40+0)*256))"   # -> 0xc3000
xxd -s 0xc3000 -l 32 back.d81                # -> 00 01 02 03 ... (Rampe)
```

## Falls Schritt 4 `nil` gibt: Varianten-Erkundung per peek/poke

Variante A ist dann falsch; die Register lassen sich direkt aus der REPL treiben
(`(peek hi lo)` / `(poke hi lo wert)`, Adress-Bytes dezimal: `$D081` = `(208 129)`):

| Experiment | Sequenz |
|---|---|
| Status nach Write | `(peek 208 130)` = `$D082` — Bit 7 BUSY klebt? Fehler-Bits? |
| `$DE00` überhaupt beschreibbar? | nach `(%disk-read-sector 79 0)`: `(poke 222 0 170)` dann `(peek 222 0)` → 170? (Fenster-Offset beachten: Rückgabe-half von f011_read_at war 0 für Sektor 0) |
| `$D087`-Füllweg (klassischer F011-Datenport) | 256× `(poke 208 135 <byte>)` nach Track/Sektor-Setup, dann `(poke 208 129 132)` (= Kmd `$84`) |
| SD-Puffer-Select | `$D689` (= `(214 137)`) Bit-Experimente vor dem Füllen |

Befunde bitte notieren (welche Sequenz → Verify `t`); der C-Kern (`f011_write_at`,
src/io.c) wird dann auf die kalibrierte Sequenz umgestellt — Struktur bleibt
(RMW + Verify), nur die 3–5 Registerschritte ändern sich.

## Danach (SAVE-MVP-Weg)

1. Kalibrierte Sequenz in `f011_write_at` festschreiben, HW-Re-Test.
2. Ketten-Writer (`io_disk_write_chain`: EXT-Datei-Puffer → Sektorkette mit korrekten
   CBM-Links, Overwrite-in-place in vorallozierte Slots — Codex' Slot-Tooling).
3. `(save "name" str)` in der Werkbank; der HW-grüne `(load)` des Maschinenraums liest
   das Ergebnis unverändert → Loop geschlossen.
