# Phase 5 Hardware Scope

Stand: 2026-06-28. Diese Notiz ist der Vertrag fuer die C64-Hardware-Schicht:
was resident werden darf, was in ladbaren Lisp-Bibliotheken bleibt, und wie native
Komfortprimitive gemessen werden.

## Ist-Stand

- `PEEK`, `POKE` und `SYS` sind resident vorhanden.
- `GETKEY` ist nativ gegated und per VICE-Smoke verifiziert.
- VIC-Sprite und SID-Ton sind per POKE-Smoke auf dem Geraet belegt:
  `phase5-sprite-script-test-screenshot`, `phase5-sid-script-test-screenshot`.
- `SID-VOICE` ist als erstes natives Hardware-Buendel gegated hinter
  `TERM_TEST_PHASE5_SID_VOICE_NATIVE` vorhanden; der Default-Build bleibt ohne Flag
  unveraendert.
- `SPRITE` ist ebenfalls als natives Register-Buendel gegated hinter
  `TERM_TEST_PHASE5_SPRITE_NATIVE` vorhanden; Datenfuellung und Komfort-API bleiben
  ausserhalb des residenten Kerns.
- `lib-c64hw.lsp` enthaelt Konstanten und reine Adress-/Frequenzrechnung.
- `lib-c64fx.lsp` enthaelt reine Algorithmen wie Linienpunkte, Sprite-Bytes und
  Melodie-Frequenzen.
- `lib-c64io.lsp` enthaelt die heutigen Komfortwrapper und schreibt ueber
  `PEEK`/`POKE` in simuliertes oder echtes C64-RAM.

## Schichten

| Schicht | Resident? | Inhalt |
| --- | --- | --- |
| Native Leaf-Primitives | nur nach Messung | kleine atomare Register-Buendel, keine Datenstrukturen, keine Policy |
| `lib-c64hw.lsp` | nein | Konstanten, Registeradressen, SID-Frequenzen, Sprite-X-MSB-Rechnung |
| `lib-c64fx.lsp` | nein | reine High-Level-Algorithmen, erzeugt Daten/Punktlisten/Bytes |
| `lib-c64io.lsp` | nein | POKE-basierte Komfort-API, host-testbar ueber simuliertes RAM |

## Residenzregel

Ein neues natives Hardware-Primitive kommt nur in den Kern, wenn mindestens eine
dieser Bedingungen erfuellt ist:

1. Es buendelt mehrere zusammengehoerige Registerschreibungen, die als POKE-Lisp
   deutlich zu viel Heap, Code oder Laufzeit kosten.
2. Es braucht atomare Register-Konsistenz, die als Lisp-Sequenz sichtbar flackern
   oder Race-artig werden kann.
3. Es ersetzt eine haeufige innere Schleife, deren Kosten per VICE/Host-Messung
   belegt sind.

Alles andere bleibt in `lib-c64io.lsp` oder einer spaeteren ladbaren Bibliothek.
Ein natives Primitive darf keine grossen Tabellen, keine Demo-Policy und keine
Sprite-/Sound-Asset-Daten resident machen.

## Kandidat `SPRITE`

Ziel: eine Register-Buendelung fuer einen Sprite, nicht ein Sprite-System.

Vorgeschlagene Form:

```lisp
(SPRITE n x y color pointer enable)
```

Semantik:

- `n`: Sprite 0..7.
- `x`: 0..511; schreibt Low-Byte nach `$D000 + 2*n` und Bit `n` in `$D010`.
- `y`: schreibt `$D001 + 2*n`.
- `color`: untere 4 Bit nach `$D027 + n`.
- `pointer`: schreibt `$07F8 + n` fuer den Standard-Textscreen.
- `enable`: bei NIL Sprite-Bit in `$D015` loeschen, sonst setzen.
- Rueckgabe: der gesetzte Enable-Wert oder `T`; wichtiger ist die Speicherwirkung.

Nicht Teil von `SPRITE`:

- Sprite-Daten fuellen oder kopieren.
- Multicolor/Expansion/Prioritaet/Kollisionen.
- Bildschirmbasis frei waehlen.
- Animations- oder Objektmodell.

POKE-Fallback:

- `sprite-at`, `sprite-color`, `sprite-on`, `sprite-off` in `lib-c64io.lsp`.
- Datenfuellung bleibt Lisp/POKE oder spaeter FFI/AOT.

Verifikation fuer eine native Umsetzung:

- positiver Smoke ueber `TERM_TEST_SCRIPT_FILE`: Sprite sichtbar, Register-Readback,
  Pointer `$07F8+n`, `$D010`, `$D015`, Farbe.
- negativer/Guard-Smoke: Default-Build bleibt byte-identisch ohne Flag.
- Footprint: PRG-Delta und freie Nodes im `KERNAL_RAM_REPL`-Build dokumentieren.

Umsetzung 2026-06-28:

- Build-Flag: `TERM_TEST_PHASE5_SPRITE_NATIVE`.
- Handler: `hSPRITE`, fuenf numerische Registerargumente plus `enable` als
  NIL/Non-NIL-Wert; keine Datenfuellung, keine Animationslogik, keine Asset-Daten.
- Smoke: `phase5-sprite-native-script-test-screenshot` ueber
  `src/v2/test-scripts/phase5-sprite-native.acme`.
- Register-Readback im Smoke: `(SPRITE 1 300 42 7 13 T)` setzt X-Low `44`, Y `42`,
  `$D010` Bit 1 (`2`), Pointer `$07F9` = `13`, Farbe `$D028` = `7`, Enable `$D015`
  = `2`; `(SPRITE 1 100 43 2 13 NIL)` loescht `$D010` und `$D015`; finaler Marker
  `SPNOK`.
- Footprint im `KERNAL_RAM_REPL`-Testbuild: 14,522 Bytes gegen 14,229 Bytes beim
  POKE-Sprite-Smoke, also +293 Bytes; freie Nodes 8156 gegen 8215 beim POKE-Smoke
  (-59 Nodes).

## Platform-Hi-Res-Smoke

Umsetzung 2026-06-28:

- Script: `src/v2/test-scripts/platform-c64-hires.acme`.
- Target: `make phase5-platform-c64-hires-script-test-screenshot`.
- Belegt sichtbar im VICE-Screenshot: Bitmap-Modus (`$D011`/`$D018`), Bitmapbytes
  ab `$2000` und Screen-RAM-Farbbytes ab `$0400`.

## Kandidat `SID-VOICE`

Ziel: eine Stimme in einem Aufruf konfigurieren, nicht einen Player.

Vorgeschlagene Form:

```lisp
(SID-VOICE voice freq control attack-decay sustain-release volume)
```

Semantik:

- `voice`: 0..2, Basis `$D400 + 7*voice`.
- `freq`: 16-Bit SID-Frequenzregisterwert; Low/High nach Basis+0/+1.
- `control`: nach Basis+4, z. B. Gate+Waveform.
- `attack-decay`: nach Basis+5.
- `sustain-release`: nach Basis+6.
- `volume`: untere 4 Bit nach `$D418`.
- Rueckgabe: `freq` oder `T`; wichtiger ist die Registerwirkung.

Nicht Teil von `SID-VOICE`:

- Notennamen/Oktaven/Frequenztabellen.
- Huellkurvenmodelle, Sequencer, Timing, Melodie.
- Filterrouting und Multi-Voice-Arrangement.

POKE-Fallback:

- `sound`, `play-note`, `play` in `lib-c64io.lsp`.
- Frequenzrechnung bleibt in `lib-c64hw.lsp`/`lib-c64fx.lsp`.

Verifikation fuer eine native Umsetzung:

- positiver Smoke setzt Volume, ADSR, Frequenz und Control; Readback ueber SID-
  Register bzw. OSC3/Random wie im aktuellen SID-Smoke.
- Default-Build ohne Flag byte-identisch.
- Footprint gegen POKE-Skript benennen.

Umsetzung 2026-06-28:

- Build-Flag: `TERM_TEST_PHASE5_SID_VOICE_NATIVE`.
- Handler: `hSIDVOICE`, sechs numerische Argumente, keine Tabellen, keine
  Sequencer-Policy, keine Asset-Daten.
- Smoke: `phase5-sid-voice-native-script-test-screenshot` ueber
  `src/v2/test-scripts/phase5-sid-voice-native.acme`.
- Register-Readback im Smoke: Rueckgabe/Frequenz `40`, Volume `15`, Voice-2-Frequenz
  `$D40E/$D40F` = `40/0`, Control `33`, ADSR `9/240`, `$D41B` bewegt sich, Marker
  `SIVOK`.
- Footprint im `KERNAL_RAM_REPL`-Testbuild: 14,331 Bytes gegen 14,173 Bytes beim
  POKE-SID-Smoke, also +158 Bytes; freie Nodes im Screenshot bleiben bei 8195.

## Reihenfolge

1. `SID-VOICE` und `SPRITE` sind als gegatete Leaf-Primitives implementiert und
   gemessen.
2. Keine weiteren nativen Hardware-Wrapper ohne neuen Mess-/Nutzenbeleg.
3. POKE-Fallbacks und ladbare Lisp-Bibliotheken bleiben primaerer Komfortpfad.
