# Plattform-Layer — backend-agnostische Hardware-API

Stand: 2026-06-30 · Prototyp (host-getestet). Kontext: Plattform-Vision in
`Projektnotizen_Architektur_2026-06-24.md` §2; Phasen `roadmap.md` (P5/P7/P8).

## Ziel

Eine **dünne, kleine** Hardware-Abstraktion, damit Anwendungen **dieselbe API**
auf PC (Host), C64 und später MEGA65 nutzen. Der Wert: die High-Level-Algorithmen
(Linien, Rechtecke, …) sind **einmal** geschrieben und laufen über jedes Backend;
nur die wenigen Backend-Primitive sind pro Plattform verschieden. Reine ladbare
Lisp-Bibliothek — **kein** residenter `.acme`-Code, kollisionsfrei zur VM-Arbeit.

## Schichten

```
Anwendung
   │   ruft High-Level-API
lib-platform.lsp        (backend-agnostisch: Algorithmen + Dispatch)
   │   ruft Backend-Primitive plat-*
Backend                 (mock | C64 | MEGA65)
   │
Hardware / Host
```

## High-Level-API (`lib-platform.lsp`)

| Funktion | Bedeutung |
| --- | --- |
| `(read-key)` | nächste Taste als Code, `0` wenn keine |
| `(plot X Y C)` | Punkt/Zelle `(X,Y)` in Farbe `C` |
| `(draw-line X0 Y0 X1 Y1 C)` | Linie (ganzzahliger Bresenham) |
| `(draw-rectangle X0 Y0 X1 Y1 C)` | Rechteck-Umriss (vier Linien) |
| `(fill-rectangle X0 Y0 X1 Y1 C)` | gefülltes Rechteck (Y1≥Y0) |
| `(clear-screen C)` | Bildschirm/Hintergrund in Farbe `C` |
| `(play-tone V FREQ WAVE)` | Stimme `V` mit Frequenz/Wellenform tönen |
| `(play-sample V FREQ WAVE)` | Alias auf `play-tone` (Notiz §2) |
| `(load-file NAME)` | Datei laden |

Geplant (noch nicht implementiert, in den Notizen genannt): `mouse-position`,
`mouse-buttons`.

## Backend-Vertrag (jedes Backend MUSS definieren)

| Primitiv | Bedeutung |
| --- | --- |
| `(plat-plot X Y C)` | einen Punkt/eine Zelle setzen |
| `(plat-clear C)` | Bildschirm/Hintergrund löschen |
| `(plat-getkey)` | Taste als Code, `0` wenn keine |
| `(plat-tone V FREQ WAVE)` | Ton ausgeben |
| `(plat-load NAME)` | Datei laden |

Die Primitive werden zur **Aufrufzeit** namentlich aufgelöst — ein Backend wird
einfach vor dem ersten API-Aufruf geladen (definiert). Backend-Wechsel = anderes
Backend-File laden.

## Backends

| Primitiv | Mock (Host, Test) | C64 (`lib-platform-c64.lsp`) | MEGA65 direkt (`lib-platform-mega65.lsp`) | MEGA65 sichtbar (`lib-platform-mega65-bank4.lsp`) |
| --- | --- | --- | --- | --- |
| `plat-plot` | zeichnet Op in `*OPS*` auf | Hi-Res-Bitmapbit `$2000` + Screen-RAM-Farbbyte `$0400` | monochrome H640-Bitplane 0 (`$2000`), Farbe `0` loescht, nonzero setzt | ROM-SCREEN-Bank-4-Framebuffer ab `$40000` |
| `plat-clear` | Op | `POKE` `VIC-BORDER`/`VIC-BACKGROUND`, Bitmap-Modus `$D011`/`$D018` | VIC-IV-Key, H640/BPM, Bitplane-Enable/Basis | Border/Background plus 16000 Bank-4-Bytes auf `0` |
| `plat-getkey` | FIFO aus `*KEYS*` | `GETKEY` (Phase-5-Natives) | nativ | nativ |
| `plat-tone` | Op | SID-Register per `POKE` (Stimme `V`) | kompatibler SID0 per `POKE` | kompatibler SID0 per `POKE` |
| `plat-load` | Op | `LOAD` | zunaechst `LOAD` | zunaechst `LOAD` |

MEGA65 hat aktuell zwei bewusst getrennte Grafik-Contracts:
`DIRECT-H640` ist das bestehende host-testbare `$2000`-Backend in
`lib-platform-mega65.lsp`; `ROM-SCREEN-BANK4` ist der sichtbare BASIC65-
`SCREEN 640,200,1`-Pfad mit 16000 Bytes ab linear `$40000` und eigenem
Backend-File `lib-platform-mega65-bank4.lsp`. Die Helper
`m65-platform-backend`, `m65-visible-screen-backend` und
`m65-screen-bank4-byte-offset` halten diese Grenze explizit.

## Test / Status

- **Host:** `python3 tools/host-lisp/lisp64.py lisp/prelude.lsp lisp/lib-platform.lsp
  lisp/platform-tests.lsp` → `PASS=29 FAIL=0`. Verifiziert u.a. Bresenham
  (horizontal/vertikal/diagonal exakt), Rechteck-Umriss (Ecken, kein Inneres) vs.
  Füllung (Inneres), `read-key`-FIFO, Ton/Datei/Clear-Dispatch — über das
  Mock-Backend, also backend-unabhängig.
- **Portable Demo:** `python3 tools/host-lisp/lisp64.py lisp/prelude.lsp
  lisp/lib-platform.lsp lisp/platform-demo.lsp lisp/platform-demo-tests.lsp`
  → `PASS=20 FAIL=0`. `demo-dashboard` zeichnet Rahmen, Kopfleiste, Balken und
  Liniengraph nur über die Platform-API; `demo-step` beweist Key→Ton und
  Key→`load-file`-Dispatch gegen das Mock-Backend.
- **C64-Backend:** `python3 tools/host-lisp/lisp64.py lisp/prelude.lsp
  lisp/lib-c64hw.lsp lisp/lib-platform-c64.lsp lisp/platform-c64-tests.lsp`
  → `PASS=15 FAIL=0`. Verifiziert mit simuliertem RAM: `plat-plot` setzt
  Hi-Res-Bitmapbits und Screen-RAM-Farbbytes; `plat-clear` waehlt Bitmap-Modus und
  Registerfarben; SID-Dispatch bleibt intakt.
- **MEGA65-Backend-Schnitt:** `python3 tools/host-lisp/lisp64.py lisp/prelude.lsp
  lisp/lib-platform.lsp lisp/lib-mega65hw.lsp lisp/lib-platform-mega65.lsp
  lisp/platform-mega65-tests.lsp` → `PASS=50 FAIL=0`. Verifiziert mit
  simuliertem RAM: H640-Bitplane-Adressmathematik, ROM-SCREEN-Bank-4-Geometrie
  (`$40000`, 16000 Bytes, 80 Bytes/Zeile), expliziter Direct-vs.-Bank-4-
  Backend-Contract, Bit-Setzen/-Loeschen,
  VIC-IV-Key/H640/BPM/Bitplane-Register (`$D030=$64`, `$D031=$F0`, `$D033=$22`
  fuer `$2000`), kompatibler SID0-Dispatch und die
  generische Platform-API (`clear-screen`, `draw-line`, `play-tone`) ueber das
  MEGA65-Backend. Dieser Host-Test ist bewusst noch kein xemu-/Geraete-Smoke und
  noch keine
  Farbebenen-/Palette-Implementierung.
- **MEGA65-Bank-4-Backend-Schnitt:** `python3 tools/host-lisp/lisp64.py
  lisp/prelude.lsp lisp/lib-platform.lsp lisp/lib-mega65hw.lsp
  lisp/lib-platform-mega65-bank4.lsp lisp/platform-mega65-bank4-tests.lsp`
  → `PASS=20 FAIL=0`. Verifiziert mit erweitertem Host-RAM: `clear-screen`
  leert die 16000 Bytes ab `$40000`, `draw-line`/`plat-plot` setzen und loeschen
  Bits im sichtbaren ROM-SCREEN-Framebuffer; SID0 bleibt kompatibel.
- **MEGA65-Bank-4-Lisp-LOAD-Smoke:** `python3 tools/host-lisp/lisp64.py
  lisp/prelude.lsp lisp/lib-platform.lsp lisp/lib-mega65hw.lsp
  lisp/platform-mega65-bank4-load-tests.lsp` → `PASS=6 FAIL=0`. Der Test laedt
  `lib-platform-mega65-bank4.lsp` per `(LOAD "...")` und ruft danach die normale
  Platform-API. Das ist der hostseitige Lisp-LOAD-Beleg; der geraetenahe
  MEGA65-Pfad bleibt bis zu einem echten LISP64-Interpreter-Start ueber
  BASIC65+D81+BLOAD/SYS abgesichert.
- **MEGA65-Bank-4-SAVEFMT-Variante:** `python3 tools/host-lisp/lisp64.py
  lisp/prelude.lsp lisp/lib-platform-mega65-bank4-load.lsp
  lisp/platform-mega65-bank4-savefmt-tests.lsp` → `PASS=13 FAIL=0`. Die Variante
  nutzt kurze, SAVE-Format-freundliche Namen fuer den sichtbaren `$40000`-
  Framebuffer. `make phase5-platform-mega65-bank4-savefmt-d81-check` erzeugt die
  LOAD-Datei, schreibt sie als `m65b4,u` in ein D81, liest sie zurueck und prueft
  bytegenau per `cmp`.
- **MEGA65-Bank-4-Demo-SAVEFMT:** `python3 tools/host-lisp/lisp64.py
  lisp/prelude.lsp lisp/lib-platform-mega65-bank4-load.lsp
  lisp/platform-demo-c64-load.lsp
  lisp/platform-mega65-bank4-demo-savefmt-tests.lsp` → `PASS=7 FAIL=0`. Das
  belegt die LOAD-sichere Rechteck-/Fill-/Dashboard-Kette gegen simuliertes
  Bank-4-RAM. `make phase5-platform-mega65-bank4-demo-savefmt-d81-check` schreibt
  dieselbe Kette als `m65b4dm,u` in ein D81 und liest sie bytegenau zurueck.
- **MEGA65-LISP64-Startpfad:** noch nicht gruen. Details und reproduzierte
  xmega65-Headless-Startvarianten stehen in `docs/mega65-lisp-start-path.md`.
  Es gibt deshalb bewusst noch keinen Make-Target, der `(LOAD 8 "M65B4DM")` auf
  dem MEGA65-LISP64-Interpreter als geraeteseitig bestanden ausweist.
  `make phase5-mega65-lisp64-launcher-artifacts-check` baut jedoch die
  Probe-Artefakte inklusive BOOT-basiertem Copy-Entry-Wrapper und prueft
  Mini-/Bank-4-Demo-D81s per Readback. Der Copy-Entry-Wrapper selbst ist
  geraeteseitig gruen: `make phase5-mega65-lisp64-copy-entry-launcher` startet
  ueber `BOOT "AUTOBOOT.C65"`, kopiert das volle LISP64-Entry-Diagnose-Image
  nach `$0801` und erreicht `OK` plus Xemu-Test-Exit. Staged-Targets belegen
  denselben Pfad inzwischen bis nach `InputLine` und in den Quote-Reader:
  `HR`, `NW`, `CR`, `QB` und `QC` sind gruen. Der aktuelle Laufzeit-Blocker
  liegt nicht mehr nur grob zwischen `hRead4`/`PopAStack_Jmp` und der Rueckkehr
  in `hReadQuoted`: die `QV`-Return-Vektor-Diagnose zeigt, dass der AStack bei
  `$fffc` `$fa4f` statt des erwarteten `hReadQuoted`-Return-Vektors liest. Der
  klassische `$fffe`-AStack ist im BOOT/Copy-C65-Kontext damit kein
  verlaesslicher writable C64-RAM-Stack. `make
  phase5-mega65-map-high-ram-diagnostic` belegt den isolierten Zugriffspfad:
  direktes `$fffc-$ffff` und `$01=$35` lesen weiter ROM-/KERNAL-Vektoren, waehrend
  `MAPHI=$8000` fuer `$e000-$ffff -> bank-0 RAM` den Bereich stabil
  beschreibt und zurueckliest. Derselbe Smoke zeigt jetzt auch, dass ein hartes
  Restore auf `MAPHI=$8300` den vorherigen MAP-State nicht exakt wiederherstellt
  (`e0 00 83 00 00 00` -> `00 00 83 00 00 00`); die Runtime braucht deshalb
  einen echten Save/Restore-Wrapper oder einen Zugriffspfad ohne globalen
  MAP-Flip. Der aktuelle Diagnostic-Smoke validiert `hyppo_get_mapping` plus
  `hyppo_set_mapping` als bytegenauen Save/Restore-Baustein
  (`e0 00 83 00 00 00` -> gleich). Der neue
  `phase5-mega65-flat-high-ram-diagnostic` belegt den alternativen Pfad ohne
  globalen MAP-Flip: per 45GS02-Quad-Indirect-Z-Indexed wird `$0fffa-$0fffd`
  als `6a 95 c3 3c` geschrieben und gelesen; direkte 16-bit-Reads bleiben im
  BOOT/C65-Kontext (`16 fa 4f fa`), MAP bleibt `e0 00 83 00 00 00`. Der neue
  `phase5-mega65-flat-astack-popa-jmp-diagnostic` belegt darauf aufbauend auch
  isoliertes Flat-AStack-Push/Pop plus indirekten Sprung (`FJ`,
  `AStackPtrLo=$fc->$fa->$fc`, Vektor `$182e`). Der erste direkte Runtime-Prototyp
  `MEGA65_C65_STACK_MAP` nutzt fuer Stackzugriffe einen MAP/AUG-Wechsel auf
  bank-0-High-RAM. Die Scratch-Diagnose `QQ` belegt, dass zwei absolute
  RAM-Stores vor dem naechsten High-RAM-Fenster reichen, um den isolierten
  `PopDStack`-Fall zurueckkehren zu lassen. Eine produktive Barriere im globalen
  High-RAM-Map-Pfad bzw. direkt in `PopDStack` regressierte jedoch `QK` und wurde
  nicht uebernommen. Damit sind die BOOT/Copy-Reader-Diagnostics bis `QR`, `QJ`,
  `QK`, `QP` und `QQ` gruen; direkte `QL`/`QM` sowie
  `phase5-mega65-lisp64-copy-stack-map-start-minimal` bleiben Timeout-Reproducer.
  Die spaeteren hREAD-Schnitte grenzen den Rueckweg weiter ein: ein manueller
  Top-Slot-Pop ohne Restore ist gruen (`RO`), derselbe manuelle Pop mit
  direktem `Mega65StackMapRestore` bleibt im echten hREAD-Layout aber ein
  No-Marker-Reproducer (`phase5-mega65-lisp64-copy-hread-manual-pop-restore-diagnostic`).
  Ein Restore-only-Schnitt im selben hREAD-Kontext erreicht dagegen `RR`; der
  nackte `Mega65StackMapRestore`-Aufruf ist damit nicht der Ausloeser. Ebenso
  gruen ist `map+restore` ohne Top-Slot-Read (`RM`). Der kleinere
  `top-read+restore`-Schnitt reproduziert den No-Marker-Timeout bereits ohne
  AStack-Pointer-Fortschritt; im hREAD-Layout reicht also der Top-Slot-Read plus
  Restore aus. `top-read-only` ist dagegen gruen (`RT`, Vektor `$1206`), also
  kehrt der Read selbst zurueck. Die Flat-Gegenprobe
  `phase5-mega65-lisp64-copy-hread-flat-top-read-only-diagnostic` ist ebenfalls
  gruen (`RF`, Vektor `$1206`) und liest denselben echten Top-Slot ohne
  MAP/Restore per Quad-Indirect-Z-Indexed-Zugriff. Der layoutneutrale
  Ersatzschnitt
  `phase5-mega65-lisp64-copy-hread-flat-pop-replace-diagnostic` ist ebenfalls
  gruen (`RP`, `$fa->$fc`, Vektor `$1206`) und belegt denselben Flat-Pfad mit
  AStack-Pointer-Fortschritt ohne MAP/Restore. Der ausgelagerte Runtime-Helfer
  `phase5-mega65-lisp64-copy-hread-flat-helper-after-popa-diagnostic` ist im
  selben hREAD-Kontext gruen (`RH`, `$fa->$f8->$fa`, Vektor `$0f2d`) und nutzt
  `Mega65FlatPushYA2AStack` plus `Mega65FlatPopAStack_Jmp` ohne globale
  MAP-Umschaltung. Darauf aufbauend erreicht
  `phase5-mega65-lisp64-copy-flat-astack-start-minimal` mit
  `MEGA65_C65_ASTACK_FLAT_RUNTIME` den `(POKE 54991 66)`-Xemu-Test-Exit und ist
  die aktuelle Basis fuer den MEGA65-LISP64-Startpfad. Darauf aufbauend sind
  `phase5-mega65-lisp64-copy-flat-astack-load-return` und
  `phase5-mega65-lisp64-copy-flat-astack-load-call` gruen: LOAD kehrt zur REPL
  zurueck, und die geladene Funktion `M65OK` laeuft danach als eigene
  Top-Level-Form. `phase5-mega65-lisp64-copy-flat-astack-load-quote-symbol`
  ist ebenfalls gruen. Nach dem hPOKE-I/O-Mapping-Fix sind auch
  `phase5-mega65-lisp64-copy-flat-astack-eq-number`,
  `phase5-mega65-lisp64-copy-flat-astack-load-eq-number` und
  `phase5-mega65-lisp64-copy-flat-astack-load-eq-literal` gruen. Die
  hEQ-Diagnosen `...heq-entry`, `...heq-compare-return`,
  `...heq-return-true-entry`, `...heq-return-true-push` und
  `...heq-return-popa` sind gruen; der neue `...heq-return-popa`-Gate stoppt am
  echten Eintritt in `PopAStack_Jmp` mit Marker `EQP` und AStack-Pointer `$fa`.
  `...heq-popa-after-pop` ist ebenfalls gruen und stoppt nach einem out-of-line
  `PopAStack2YA` (`EQBA`, `$fa->$fc`, Vektor `$126f`). `...heq-eval-return` ist
  ebenfalls gruen und stoppt direkt nach `JSR CallEval` vor `hPRINT`;
  `...heq-hprint-entry` erreicht auch den Eintritt in `hPRINT`, und
  `...heq-hprint-after-dup` erreicht die Stelle nach `DupDStack`;
  `...heq-hprint-after-printsexpr` erreicht auch die Stelle nach `PrintSExpr`;
  `...heq-hprint-after-printcr` erreicht danach auch die Stelle nach `PrintCR`;
  `...heq-hprint-return` erreicht den REPL-Ruecksprung hinter `CallYA hPRINT`;
  `...eq-repl-second-iteration` erreicht danach den naechsten `IntprLoop1`;
  `...eq-second-read-return` erreicht auch den `hREAD`-Return der zweiten
  Script-Form; `...eq-poke-entry` erreicht den Eintritt in `hPOKE`;
  `...eq-poke-after-args` erreicht den Punkt nach `Pop_Str2ARG_and_Next2ACC`.
  `...eq-poke-after-store` erreicht auch die Stelle nach dem indirekten Store
  `STA (<ACC32),Y`. Der entscheidende Fix ist, dass `hPOKE` im
  `MEGA65_C65_STACK_MAP`-Build vor dem indirekten Store `MapNormalBank` aufruft;
  damit sieht der I/O-Bereich den dynamischen Store auf `$D6CF`.
  Der strenge Mini-LOAD-Wertnutzungs-Schnitt
  `phase5-mega65-lisp64-copy-flat-astack-load-mini` packt `AUTOBOOT.C65` und
  `M65OK,U` auf ein D81, bleibt aber ein Timeout-Reproducer, sobald der Exit vom
  Funktionswert innerhalb von `(COND ((EQ (M65OK) 'M65OK) ...))` abhaengt.
  `phase5-mega65-lisp64-copy-flat-astack-load-cond-t` und
  `phase5-mega65-lisp64-copy-flat-astack-load-cond-eq-number` sind gruen; der
  verbleibende Blocker ist damit enger als `LOAD` oder `COND` allgemein. Die
  Gegenprobe `phase5-mega65-lisp64-copy-flat-astack-cond-quote-symbol` ist
  ebenfalls gruen, nutzt aber direkt den `$D6CF`-Exit und ist deshalb kein
  Screen-RAM-Body-Beweis. Die nachgezogenen Screen-Orakel zeigen:
  Der finale `COND`-Body laeuft im MEGA65-Flat-AStack-Build nun ueber
  `CallEval` und die bestehende AStack-Continuation statt per direktem
  Tail-`JMP hEVAL`. Positiv belegt sind
  `phase5-mega65-lisp64-copy-flat-astack-load-cond-t-eq-body`,
  `phase5-mega65-lisp64-copy-flat-astack-load-cond-t-poke-nontail-screen` und
  `phase5-mega65-lisp64-copy-flat-astack-load-cond-t-poke-screen-tail`:
  `COND T` mit finalem `(EQ 1 1)` sowie mit nicht-finalem und finalem
  `(POKE 1024 65)` kehrt zurueck; die POKE-Varianten schreiben `$41` nach
  `$0400`. Auch
  `phase5-mega65-lisp64-copy-flat-astack-load-cond-quote-symbol-then-poke` ist
  gruen und zeigt, dass ein Quote-Symbol-Praedikat mit einfachem `T`-Body und
  separatem Top-Level-POKE nach LOAD laeuft. Auch
  `phase5-mega65-lisp64-copy-flat-astack-load-cond-quote-symbol-two-t-body`
  ist gruen: ein rein literaler Mehrfach-Body `(T T)` unter demselben
  Quote-Symbol-Praedikat kehrt bis zum Top-Level-Exit zurueck. Der Schnitt ist
  aber enger als "Funktions-Body" und enger als generischer `QUOTE`-Body:
  `phase5-mega65-lisp64-copy-flat-astack-cond-quote-symbol-quote-body` ist
  ohne LOAD gruen fuer `(COND ('M65OK 'M65OK))`, und
  `phase5-mega65-lisp64-copy-flat-astack-load-cond-t-quote-body` ist gruen
  fuer `LOAD` plus `(COND (T 'M65OK))`. Der offene Reproducer braucht damit
  die Kombination aus geladenem/folgendem Kontext, Quote-Symbol-Praedikat und
  `QUOTE`-Body:
  `phase5-mega65-lisp64-copy-flat-astack-load-cond-quote-symbol-quote-body-known-blocker`
  reproduziert `(COND ('M65OK 'M65OK))` nach LOAD ohne `$0400`-Write. Auch
  `phase5-mega65-lisp64-copy-flat-astack-load-cond-quote-symbol-quote-foo-body-known-blocker`
  reproduziert den Abbruch bei `(COND ('M65OK 'FOO))`; gleicher Predicate- und
  Body-Symbolwert ist damit nicht die Ursache. Die weitere reine Script-Gegenprobe
  `phase5-mega65-lisp64-copy-flat-astack-load-cond-quote-symbol-quote-t-body-known-blocker`
  reproduziert den Abbruch auch mit `(COND ('M65OK 'T))`. Zusaetzlich
  reproduziert
  `phase5-mega65-lisp64-copy-flat-astack-load-cond-quote-symbol-quote-t-nontail-known-blocker`
  den Schnitt mit `(COND ('M65OK 'T T))`, also mit nicht-finalem `QUOTE`-Body
  und anschliessendem Top-Level-POKE. Neu trennt
  `phase5-mega65-lisp64-copy-flat-astack-load-cond-quote-symbol-t-quote-t-body-known-blocker`
  den ebenfalls roten Fall `(COND ('M65OK T 'T))`, waehrend
  `phase5-mega65-lisp64-copy-flat-astack-load-cond-quote-symbol-two-quote-t-body`
  fuer `(COND ('M65OK 'T 'T))` gruen ist. Der Body-Wert ist damit nicht
  entscheidend; der Schnitt liegt bei der `COND`-Body-Iteration fuer den
  einzelnen finalen Reader-Quote-Body und fuer gemischte Literal/Reader-Quote-
  Body-Folgen. Wichtig:
  `phase5-mega65-lisp64-copy-flat-astack-load-cond-quote-symbol-explicit-quote-t-body`
  ist fuer `(COND ('M65OK (QUOTE T)))` gruen. Das engt den Fehler von `QUOTE`
  allgemein auf die Reader-Kurzform `'...` in diesem LOAD/Quote-Praedikat-Kontext
  ein. Noch enger:
  `phase5-mega65-lisp64-copy-flat-astack-load-cond-explicit-quote-symbol-quote-t-body`
  ist fuer `(COND ((QUOTE M65OK) 'T))` ebenfalls gruen. Damit kippt nicht schon
  ein Reader-Quote-Body, sondern die Kombination aus Reader-Quote-Praedikat und
  Reader-Quote-Body in derselben Klausel nach LOAD. Reine Literal- und reine
  wiederholte Reader-Quote-Folgen laufen. Das
  zusaetzliche Ziel
  `phase5-mega65-lisp64-copy-flat-astack-load-cond-quote-symbol-quote-body-hprint-entry-known-blocker`
  baut denselben Reproducer mit `TERM_TEST_MEGA65_HPRINT_ENTRY_EXIT=1`; der
  hPRINT-Einstieg wird nicht erreicht, und der Dump bleibt bei `$0400=$20`.
  Noch enger bleiben
  `phase5-mega65-lisp64-copy-flat-astack-load-cond-quote-symbol-quote-body-hlistquote-entry-known-blocker`
  und
  `phase5-mega65-lisp64-copy-flat-astack-load-cond-quote-symbol-quote-body-hcond-final-body-return-known-blocker`
  rot: der QUOTE-Body erreicht `hLISTQUOTE` nicht, und der finale
  `COND`-Body-`CallEval` kehrt nicht zurueck. Die noch frueheren Targets
  `phase5-mega65-lisp64-copy-flat-astack-load-cond-quote-symbol-quote-body-hcond-pred-return-known-blocker`
  und
  `phase5-mega65-lisp64-copy-flat-astack-load-cond-quote-symbol-quote-body-hcond-final-body-call-known-blocker`
  bleiben ebenfalls rot. Diese instrumentierten Marker sind wegen der
  MEGA65-Autoboot-/Layout-Empfindlichkeit nur als Diagnose zu lesen; die
  stabileren Script-Proben zeigen den naechsten technischen Schnitt an der
  Grenze zwischen erfolgreichem Quote-Symbol-Praedikat und `COND`-Body-Iteration:
  `hCOND6` fuer den direkten finalen Reader-Quote-Body, `hCOND7`/`hCOND5` fuer
  den Wechsel zwischen Literal- und Reader-Quote-Bodies sowie die Reader-Expansion
  der Kurzform gegen explizites `(QUOTE ...)`, besonders wenn Praedikat und Body
  beide aus der Kurzform stammen. Quote-,
  Literal-`EQ`- und geladener-Call-Praedikat-Varianten bleiben damit
  klassifizierte Diagnose/Blocker: Quote-Symbol mit nicht-trivialem Body,
  Literal-`EQ`-`screen-tail` und geladener Call-Praedikat-Body sind
  Known-Blocker; der Call-Praedikat-Fall erreicht mit separatem Top-Level-Exit
  das Ende, laesst `$0400` aber unveraendert (`$20`). Das alte
  Negativtarget
  `phase5-mega65-lisp64-copy-flat-astack-load-cond-t-poke-screen-tail-known-blocker`
  ist auf den gruenen Tail-Smoke umgebogen. Das Negativtarget
  `phase5-mega65-lisp64-copy-flat-astack-load-cond-quote-symbol-known-blocker`
  reproduziert den Timeout bei finalem
  `(COND ('M65OK (POKE 54991 66)))` nach LOAD; eine manuelle Gegenprobe mit
  finalem `(POKE 54991 65)` und separatem Top-Level-Exit timeoutet ebenfalls.
  Die bekannten Negativtargets
  `phase5-mega65-lisp64-copy-flat-astack-load-cond-quote-symbol-quote-body-known-blocker`,
  `phase5-mega65-lisp64-copy-flat-astack-load-cond-quote-symbol-quote-foo-body-known-blocker`,
  `phase5-mega65-lisp64-copy-flat-astack-load-cond-quote-symbol-eq-body-known-blocker`,
  `phase5-mega65-lisp64-copy-flat-astack-load-cond-quote-symbol-poke-nontail-known-blocker`,
  `phase5-mega65-lisp64-copy-flat-astack-load-cond-quote-symbol-poke-screen-tail-known-blocker`,
  `phase5-mega65-lisp64-copy-flat-astack-load-cond-quote-foo-poke-screen-tail-known-blocker`,
  `phase5-mega65-lisp64-copy-flat-astack-load-cond-eq-literal-poke-screen-tail-known-blocker`,
  `phase5-mega65-lisp64-copy-flat-astack-load-cond-eq-literal-known-blocker`
  und `phase5-mega65-lisp64-copy-flat-astack-load-eq-call-known-blocker`
  reproduzieren den Quote-Symbol-Body-Schnitt (`QUOTE`, `EQ`, nicht-finaler
  POKE, finaler POKE) ohne `$0400`-Write, denselben Blocker mit frischem `'FOO`
  statt geladenem `M65OK`, den Symbol-/Literal-`EQ`-Timeout nach LOAD
  beziehungsweise den geladenen Funktionswert als `EQ`-Argument; die umgekehrte
  Argumentordnung ist ebenfalls als
  `phase5-mega65-lisp64-copy-flat-astack-load-eq-call-reversed-known-blocker`
  festgehalten. Die expliziten Varianten
  `phase5-mega65-lisp64-copy-flat-astack-load-eq-call-explicit-quote-known-blocker`
  und
  `phase5-mega65-lisp64-copy-flat-astack-load-eq-call-reversed-explicit-quote-known-blocker`
  bleiben rot und enden bei PC `$0000`; der Reader-Quote-Vergleichswert ist
  damit nicht die Ursache. `phase5-mega65-lisp64-copy-flat-astack-load-atom-call-known-blocker`
  zeigt denselben verschachtelten geladenen Funktionswert auch ausserhalb von
  `hEQ` als roten Pfad. Die gruene Kontrollprobe
  `phase5-mega65-lisp64-copy-flat-astack-de-atom-call` definiert dieselbe
  Funktion per `DE` und kann `(ATOM (M65OK))` danach auswerten; der Schnitt ist
  damit kein allgemeiner verschachtelter Funktionsaufruf. Die schaerfere
  Kontrolle
  `phase5-mega65-lisp64-copy-flat-astack-load-rede-atom-call-known-blocker`
  fuehrt erst `LOAD`, dann ein interaktives Re-`DE` und danach `(ATOM (M65OK))`
  aus; sie timeoutet ebenfalls. Die Top-Level-Gegenprobe
  `phase5-mega65-lisp64-copy-flat-astack-load-rede-call` bleibt gruen, also sind
  Re-`DE` und `(M65OK)` nach LOAD nicht allgemein gebrochen. Der verbleibende
  Suchraum liegt beim verschachtelten Funktionswert-Argument nach LOAD/Re-`DE`;
  `phase5-mega65-lisp64-copy-flat-astack-load-atom-quote-symbol` zeigt
  zusaetzlich, dass `hATOM` nach LOAD mit quotiertem Symbol gruen bleibt.
  Neue Override-Diagnosen auf demselben kurzen `LOAD`-Target zeigen: der rote
  `(ATOM (M65OK))`-Pfad erreicht `S1338`, kehrt aus dem verschachtelten
  `CallEval` zurueck, erreicht `hATOM`, `PopD2NodePtr`, `GetNodePtrTypeInfo`
  und in `return_true` den Push von `T`. Der kontrollierte AStack-Top-Slot vor
  dem finalen Pop steht bei `$fffa` auf `$1239`; bytegenau ist das die
  Instruktion nach dem top-level `JSR CallEval`, also die Vorbereitung des
  folgenden `hPRINT`-Aufrufs. Der rote uninstrumentierte Pfad erreicht den
  separaten Eval-Return-Schnitt vor `hPRINT` trotzdem nicht; groessere
  Pop-/hPRINT-Instrumentierungen sind hier layout-sensitiv. Der naechste
  Schnitt liegt damit zwischen `return_true`/finalem `PopAStack_Jmp` und der
  Rueckkehr zum top-level Eval-Return. Der frische uninstrumentierte
  Known-Blocker-Dump zeigt dabei eine Code-Korruption im Eval/Apply-Bereich:
  `$16b0` (`return_true`/`hATOM`-Nahe) ist nach dem Crash mit `$37`
  ueberschrieben. Der gruene `LOAD + (ATOM 'M65OK)`-Kontrollpfad und der rote
  `return_true`-After-Push-Stop lassen denselben Bereich intakt. Die naechste
  Diagnose sollte deshalb eine minimale Code-Page-/Write-Waechterprobe um diese
  Stelle sein, nicht ein weiterer hPRINT-Marker.
  Dieselbe Gegenprobe mit
  hartem MAP-Restore statt Hyppo-Restore bleibt weiterhin ein Reproducer; der
  Effekt ist damit nicht Hyppo-spezifisch. Auch ein inline eingebetteter harter
  MAP-Restore reproduziert; `JSR`/`RTS` um `Mega65StackMapRestore` ist damit
  ebenfalls entlastet.
- **MEGA65-Readiness:** `make phase5-platform-mega65-readiness-check` prueft
  nicht-interaktiv `xmega65`, die lokale Xemu-MEGA65-Datenbasis (`MEGA65.ROM`,
  `CHARROM.M65`, `mega65.img`) und fuehrt die hostseitige MEGA65-Backend-/Platform-
  Suites aus (`PASS=50 FAIL=0`, `PASS=20 FAIL=0`). Das Ziel startet den Emulator
  absichtlich nicht; die geraetenahen Xemu-Laeufe liegen getrennt in den folgenden
  Smoke-Zielen.
- **MEGA65-Aggregat:** `make phase5-platform-mega65-smokes` fuehrt Readiness,
  direkten H640-Smoke, BASIC65-Screen-Oracle, Bank-4-POKE-Smoke, Bank-4-Fill-
  Native-Smoke, Bank-4-Diagonal-Native-Smoke, den D81-Diagonal-LOAD/SYS-Smoke
  und den D81-Clear-LOAD/SYS-Smoke
  sequentiell aus.
- **MEGA65-Xemu-Smoke:** `make phase5-platform-mega65-h640-smoke` baut ein
  eigenstaendiges PRG aus `src/v2/test-scripts/platform-mega65-h640.acme` und
  startet es nicht-interaktiv mit `xmega65 -prgtest`. Der Smoke aktiviert
  VIC-IV/H640/Bitplane 0 mit ROM-kompatiblen Modebits (`$D030=$64`, `$D031=$F0`,
  `$D033=$22` fuer `$2000` im Direktsmoke), schreibt definierte Daten nach `$2000-$5fff`,
  beendet Xemu ueber das Test-Register `$D6CF=$42` und erzeugt PNG plus
  384K-Memory-Dump. `scripts/check-mega65-h640-smoke.py` prueft Screenshot-
  Dimension/Farbsignatur sowie die harte Dump-Signatur (`16384` Bytes `$FF` ab
  `$2000`). Das ist ein direkter Xemu-Lifecycle-/Dump-Smoke; die sichtbare
  Linien-/Palette-Anbindung an diese RAM-Region bleibt der naechste Ausbau. Die
  MEGA65-Referenzen beschreiben BASIC65-`SCREEN`-Grafik separat als Bank-4/5-
  Allokation; der Direktsmoke bleibt daher bewusst ein C65/VIC-III-Bitplane-Pfad
  in den ersten 128 KiB.
- **MEGA65-Screen-Oracle:** `make phase5-platform-mega65-screen-oracle-smoke`
  importiert ein kurzes BASIC65-Programm (`SCREEN 640,200,1`, `SCREEN CLR 0`) und
  prueft per `scripts/check-mega65-screen-oracle.py` die saubere sichtbare
  640×200-Geometrie: blauer Aussenbereich, schwarzes Grafikfenster und keine
  relevante weisse Altstruktur. Das Programm schreibt ausserdem `RGRAPHIC(0,0..10)`
  nach `$3000`; der Checker validiert `[1,1,0,1,1,3,0,0,0,0,0]` und belegt damit
  640×200×1 sowie die BASIC65-Screen-Allokation in Bank-4-Segmenten 0+1. Dieses
  Ziel ist das Referenzbild und die ROM-Zustandsreferenz fuer den naechsten direkten
  H640-Pixel-Smoke.
- **MEGA65-Bank-4-Poke-Smoke:** `make phase5-platform-mega65-screen-bank4-poke-smoke`
  nutzt dieselbe BASIC65-`SCREEN`-Initialisierung, schreibt danach direkt per
  `BANK 4`/`POKE` `16000` Bytes `$FF` ab Bank-4-Offset `$0000` und prueft per
  `scripts/check-mega65-screen-bank4-poke.py`, dass das Grafikfenster sichtbar weiss
  wird und der Dump bei `$40000-$43e7f` exakt diese Bytes enthaelt. Das belegt den
  sichtbaren Speicherpfad fuer die ROM-allozierten 640×200×1-Bitplane-Daten.
- **MEGA65-Bank-4-Native-Smoke:** `make phase5-platform-mega65-screen-bank4-native-smoke`
  ersetzt die BASIC-POKE-Schleife durch einen 49-Byte-45GS02-Helper aus
  `src/v2/test-scripts/platform-mega65-bank4-fill-native.acme`. BASIC65 initialisiert
  nur `SCREEN 640,200,1`, poked den Helper nach `$1800` und ruft `SYS 6144`.
  Der Helper schreibt per Quad-Indirect-Z-Indexed-Adressierung direkt nach `$40000`.
  `scripts/check-mega65-native-data.py` verhindert Drift zwischen ACME-Binaerhelper
  und BASIC-`DATA`; der Bank-4-Screenshot-/Dumpchecker prueft dieselbe sichtbare
  weisse Grafikflaeche.
- **MEGA65-Bank-4-Diagonal-Native-Smoke:**
  `make phase5-platform-mega65-screen-bank4-diagonal-native-smoke` nutzt denselben
  BASIC65-`SCREEN`-/`SYS 6144`-Pfad, aber einen Helper aus
  `src/v2/test-scripts/platform-mega65-bank4-diagonal-native.acme`, der den
  gemeinsamen `bank4_plot_xy`-Baustein aus
  `src/v2/test-scripts/platform-mega65-bank4-plot-helper.inc` nutzt. Dieser
  berechnet `$40000 + y*80 + x/8`, bildet die Pixelmaske und setzt per
  Quad-Indirect-Z-Indexed das sichtbare Bank-4-Pixel. Der Checker validiert
  PNG-Grundfarben, `RGRAPHIC` und alle 16000 Dumpbytes gegen die erwartete
  640×200×1-Diagonale.
- **MEGA65-Bank-4-Diagonal-LOAD/SYS-Smoke:**
  `make phase5-platform-mega65-screen-bank4-diagonal-load-smoke` baut denselben
  45GS02-Helper als PRG mit Load-Adresse `$1800`, schreibt ihn als `M65DIAG` auf
  ein D81-Image und startet ein BASIC65-Programm, das `BLOAD "M65DIAG",P($1800)`
  und danach `SYS 6144` ausfuehrt. Damit ist der sichtbare Bank-4-Pixelpfad nicht
  mehr nur ueber eingebettete BASIC-`DATA`-Bytes belegt.
- **MEGA65-Bank-4-Clear-LOAD/SYS-Smoke:**
  `make phase5-platform-mega65-screen-bank4-clear-load-smoke` baut den vorhandenen
  Fill-Helper und den neuen Clear-Helper als PRGs, schreibt beide in ein D81 und
  startet BASIC65 mit `BLOAD "M65FILL"`/`SYS 6144`, danach
  `BLOAD "M65CLR"`/`SYS 6144`. Der Checker prueft Screenshot-Farben, `RGRAPHIC`-
  Oracle und alle 16000 Bank-4-Framebuffer-Bytes auf `$00`.
- **Geräte-Smoke:** der bestehende direkte Textzellen-POKE-Smoke
  `make phase5-platform-c64-draw-script-test-screenshot` assembliert ein
  `TERM_TEST_SCRIPT_FILE`-Fixture und zeigt per VICE-Screenshot eine Diagonale aus
  Screen-/Color-RAM-Schreibungen (`POKE` nach `$0400` und `$D800`). Das belegt den
  sichtbaren historischen Textzellen-POKE-Pfad.
- **Hi-Res-Geräte-Smoke:** `make phase5-platform-c64-hires-script-test-screenshot`
  assembliert ein `TERM_TEST_SCRIPT_FILE`-Fixture, setzt Bitmap-Modus (`$D011`,
  `$D018`) und zeigt per VICE-Screenshot gefuellte Hi-Res-Zellen aus Bitmapbytes bei
  `$2000` plus Farbzellen bei `$0400`. Das ist der sichtbare Geraetebeleg fuer den
  neuen C64-Plotpfad.
- **Generischer C64-LOAD-Zeichner-Smoke:**
  `make phase5-platform-c64-load-line-script-test-screenshot` laedt eine kurze
  SAVE-Format-Teilmenge aus `lib-platform-c64-load.lsp` und ruft echtes
  `DRAWLINE` ueber Hi-Res-`PLAT-PLOT` auf; `PLOK` im Screenshot belegt, dass die
  geladene generische Zeichnerkette auf dem Geraet zurueckkehrt. Die konkrete
  RAM-Wirkung (`$2000`-Bitmapbyte, `$0400`-Farbbyte) wird hostseitig in
  `platform-c64-load-tests.lsp` gegen simuliertes `PEEK`/`POKE`-RAM geprueft.
- **Portable-Demo-LOAD-Smoke:** `make phase5-platform-demo-load-script-test-screenshot`
  erzeugt ein SAVE-Format-D64 aus `platform-demo.lsp` plus kleinen Platform-Stubs,
  laedt es auf dem C64-LOAD-Pfad und belegt `demo-handle-key`: Ton-Dispatch,
  `load-file`-Dispatch und Dashboard-Dispatch enden sichtbar in `PDLOADOK`.
- **Grafischer Demo-Dashboard-LOAD-Smoke:**
  `make phase5-platform-demo-dashboard-load-script-test-screenshot` laedt die
  C64-LOAD-sichere, bindestrichfreie Dashboard-Sequenz aus
  `platform-demo-c64-load.lsp` plus die volle generische Zeichnerkette aus
  `lib-platform-c64-load.lsp` im SAVE-Format. Das Script zeichnet zunaechst in
  Bitmap-/Screen-RAM (`CLEARBUF`, zeilenweise `BMCLEAR`/`SCLEAR`,
  `DRAWRECTANGLE`, `FILLRECTANGLE`, `DRAWBARS`, `LINEGRAPH`) und schaltet erst
  als letzte Form mit `SHOWHIRES` in den Bitmap-Modus. `PLAT-PLOT` projiziert
  logische Punkte auf sichtbare 8-Pixel-Hi-Res-Segmente; der VICE-Screenshot
  zeigt die Dashboard-Grafik ohne Zeichner-Stubs.
  `scripts/check-c64-load-dashboard-screenshot.py` prueft das erzeugte PNG
  automatisch auf Dimension, aktive Bitmap-Flaeche und helle Dashboard-
  Akzentpixel.

## Nächste Schritte

1. MEGA65-Backend ausbauen: den direkten H640-Smoke an die sichtbare Geometrie
   aus `phase5-platform-mega65-screen-oracle-smoke` angleichen, danach
   Linien-/Palette-Checks statt nur Dump-Signatur.
2. Weiterer C64-Bitmap-Clear nur mit anderem Ansatz: ein vollflaechiger Lisp-Clear ist
   rekursionstiefen-/laufzeitkritisch; sauberer waere ein kleiner nativer oder
   cross-kompilierter Clear-Helper fuer die sichtbare Bitmap-Flaeche.
