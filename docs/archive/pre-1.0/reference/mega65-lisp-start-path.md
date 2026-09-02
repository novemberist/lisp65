# MEGA65 LISP64 Startpfad

Stand: 2026-06-30.

## Gesicherte Pfade

- BASIC65 kann D81-PRGs per `BLOAD ...,P($1800)` laden und per `SYS 6144`
  ausfuehren. Belegt durch Diagonal- und Clear-LOAD/SYS-Smokes.
- Der MEGA65/C65-PRGTest-Pfad selbst ist als positiver Kontrollpfad gruen:
  `make phase5-mega65-c65-prgtest-diagnostic` startet dasselbe minimale
  Diagnose-PRG mit `-prgmode 65 -prgtest "SYS 2300"`, erreicht den
  Xemu-Test-Exit und der Dump enthaelt `OK` in Screen-RAM `$0400/$0401`.
- MEGA65-Bank-4-Backend-Code ist hostseitig per Lisp-`LOAD` belegt.
- Die SAVE-Format-Varianten werden als D81 geschrieben, zurueckgelesen und per
  `cmp` geprueft:
  - `phase5-platform-mega65-bank4-savefmt-d81-check`
  - `phase5-platform-mega65-bank4-demo-savefmt-d81-check`
- Die LISP64-Launcher-Probe-Artefakte werden gebaut und die zugehoerigen D81s
  readback-geprueft: `make phase5-mega65-lisp64-launcher-artifacts-check`.
- Der BOOT-basierte LISP64-Copy-Entry-Launcher ist gruen:
  `make phase5-mega65-lisp64-copy-entry-launcher` schreibt einen C65-ML-Wrapper
  als `AUTOBOOT.C65` auf D81, startet ihn ueber `BOOT "AUTOBOOT.C65"`, kopiert
  das volle LISP64-Entry-Diagnose-Image nach `$0801`, springt nach `$08FC` und
  erreicht `OK` plus Xemu-Test-Exit. Das belegt einen pruefbaren
  Full-Image-Startbaustein ausserhalb von xmega65s direktem `-prg`-Pfad.

## Nicht gesicherter Pfad

Ein nicht-interaktiver xmega65-Start von LISP64 als C64-PRG mit anschließendem
REPL-Script-`(LOAD 8 "...")` ist noch nicht gruen. Mehrere Headless-Varianten
bleiben vor einem verwertbaren Screenshot/Dump haengen, inzwischen auch mit
explizitem Test-Exit `(POKE 54991 66)` im REPL-Script:

- `-go64 -8 <d81> -prg <lisp64.prg> -prgmode 64 -prgtest "SYS 2049"`
- `-go64 -8 <d81> -prg <lisp64.prg> -prgmode 64 -prgexit`
- `-go64 -prg <minimal.prg> -prgmode 64 -prgtest "SYS 2300"` mit einem
  C64-BASIC-PRG, dessen BASIC-Zeile ebenfalls `SYS 2300` enthaelt
- `-go64 -autoload -8 <d81>` mit `LISP64,P` als erstem D81-File
- `-8 <d81> -prg <lisp64.prg> -prgmode 64 -prgexit`
- `-go64 -prg <minimal.prg> -prgmode 64 -prgexit`, wobei das Script nur
  `'M65STARTOK` und `(POKE 54991 66)` enthaelt
- `-go64 -prg <minimal.prg> -prgmode 64 -prgtest "RUN"` mit demselben Script
- `-go64 -autoload -8 <d81>` mit demselben Minimal-Script als `LISP64,P`
- `-go64 -importbas <minimal.bas>` mit einem C64-BASIC-Textprogramm, das nur
  `OK` nach `$0400/$0401` und den Xemu-Test-Exit `$D6CF=$42` schreibt

Zusaetzliche Diagnose am 2026-06-29: Der C64-Autostartpfad haengt auch mit einem
minimalen C64-BASIC-PRG, das nur `SYS 2300`, zwei Screen-Bytes (`OK`) und den
Xemu-Test-Exit `$D6CF=$42` ausfuehrt. Der vergleichbare MEGA65/C65-ML-PRG-Pfad
ueber `-prgmode 65 -prgtest "SYS 2300"` ist gruen und wird durch
`phase5-mega65-c65-prgtest-diagnostic` plus Dump-Checker reproduzierbar
abgesichert. Damit ist der aktuelle Headless-Blocker vor LISP64 isoliert:
xmega65s READY-/Autostart-Erkennung im C64-Pfad feuert in dieser lokalen Version
nicht reproduzierbar.
Auch der direkte C64-PRGTest-Aufruf desselben Minimal-PRGs mit
`-go64 -prg ... -prgmode 64 -prgtest "SYS 2300"` erreicht keinen Test-Exit;
`make phase5-mega65-c64-prgtest-sys2300-diagnostic` reproduziert diesen
Timeout mit kontrolliertem Prozess-Cleanup.
Quellencheck in der lokalen xemu-Version (`targets/mega65/mega65.c` und
`targets/mega65/inject.c`): Wenn `-prg` gesetzt ist, laeuft nicht der normale
`configdb.go64`-Zweig. Stattdessen setzt `-prgmode 64` `prg.c64_mode` und xemu
haelt beim Booten intern die MEGA-Taste fuer C64-Mode. Eine Gegenprobe ohne
explizites `-go64` zeigte denselben Timeout. Weitere `-go64`/`-prg`-
Kombinationen sind deshalb kein anderer Startmechanismus, sondern Varianten
derselben blockierten PRG-Injection.

Der gruene C65-PRGTest-Pfad traegt jedoch nicht automatisch einen direkten
LISP64-Kernstart in C65/MEGA65-Modus: `make
phase5-mega65-lisp64-c65-direct-diagnostic` injiziert das minimale LISP64-
Startskript-PRG und startet es mit `-prgmode 65 -prgtest "SYS 2300"`. Dieses
Skript sollte in der REPL nur `'M65STARTOK` und `(POKE 54991 66)` ausfuehren.
Aktueller Befund: Der Lauf erreicht keinen Xemu-Test-Exit und produziert in
dieser Timeout-Situation keinen verwertbaren Dump/Screenshot. Das trennt den
positiven kleinen ML-PRGTest-Kontrollpfad von einem echten LISP64-Start: LISP64
selbst laeuft auf diesem direkten C65-Startpfad noch nicht pruefbar bis zur REPL.
Ein strengerer Full-Image-Probe ist ebenfalls verdrahtet: `make
phase5-mega65-lisp64-c65-entry-diagnostic` baut den normalen LISP64-Kern mit
`TERM_TEST_MEGA65_C65_ENTRY_EXIT`, sodass die Entry-Adresse `$08FC` vor `Start1`
nur `OK` nach Screen-RAM schreiben und ueber `$D6CF=$42` beenden soll. Auch dieser
Pfad erreicht aktuell keinen Test-Exit. Der Blocker liegt damit nicht nur im
minimalen REPL-Skript oder in dessen Lisp-Eingabe, sondern bereits vor bzw. bei der
vollen LISP64-Image-Entry-Ausfuehrung ueber xmega65s C65-PRGTest-Injection.

Gegenprobe am selben Full-Image-Entry: `make
phase5-mega65-lisp64-copy-entry-launcher` vermeidet xmega65s `-prg`-Injection.
Stattdessen startet ein kleiner C65-ML-Wrapper ueber den gruenen
`BOOT "AUTOBOOT.C65"`-Pfad bei `$6000`, enthaelt das volle
`TERM_TEST_MEGA65_C65_ENTRY_EXIT`-Image als Daten, kopiert dessen PRG-Payload
nach `$0801` und springt direkt nach `$08FC`. Dieser Weg ist gruen: der Dump
enthaelt die Entry-Signatur bei `$08FC`, der Screen-State ist `OK`, und
`$D6CF=$42` beendet Xemu. Damit ist der direkte `-prg`-/PRGTest-Pfad als
Startmechanismus der engere Blocker; ein BOOT-basierter Full-Image-Startbaustein
steht.

Weitere Staged-Diagnosen am 2026-06-29 verwenden denselben BOOT/Copy-Wrapper,
aber setzen den Xemu-Test-Exit tiefer in den LISP64-Kern. Gruen sind `Init`
(`IN`), `Init0` (`I0`), `ResetHashTable` (`RH`), `InitFSL` (`FS`),
`ShowACC32` (`SA`), die `NODES FREE`-Ausgabe (`NM`) und mit
`TERM_TEST_KEYS` plus `mega65-lisp64-start-minimal.acme` auch der Ruecksprung
aus `InputLine` (`LI`). Der naechste reproduzierte Blocker ist
`make phase5-mega65-lisp64-copy-after-read-diagnostic`: der erste Testscript-
Input liegt im Puffer (`'M65STARTOK`), aber `CallYA hREAD` erreicht den
nachgeschalteten `RD`-Marker nicht und das Target meldet den bekannten Timeout.
Die feinere Reader-Leiter grenzt diesen Blocker weiter ein: `HR` (`hREAD`
Entry), `NW` (nach erstem `GetNextNoWhiteSpaceChar`), `CR`/`QC` (rekursiver
Symbol-Read des gequoteten `M65STARTOK` nach `CallReadRest`) und `QB` (Quote-
Zweig direkt vor `CallYA hRead1`) sind gruen. `QA` (Rueckkehr aus diesem
rekursiven `CallYA hRead1` nach `hReadQuoted`) timeoutet. Damit liegt der
aktuelle Blocker zwischen dem `hRead4`-Ruecksprung ueber `PopAStack_Jmp` und
der Rueckkehr in `hReadQuoted`, nicht mehr in `InputLine`, der Quote-Erkennung
oder dem eigentlichen Symbol-Scan.

Weitere Eingrenzung am selben Pfad: `make
phase5-mega65-lisp64-copy-quoted-return-vector-diagnostic` haelt direkt vor
`PopAStack_Jmp` in `hRead4` an und liest den AStack-Top-Vektor unter
`MapKernalRamSEI`. Der Marker `QV` ist gruen, aber der gelesene Vektor ist
`$fa4f`; erwartet waere das Label nach dem rekursiven `CallYA hRead1`
(`$0ff2` in diesem Build). Der AStack-Zeiger steht dabei bei `$fffc`.
Damit ist der `QA`-Timeout nicht mehr nur als Kontrollflussproblem beschrieben:
im MEGA65/C65-BOOT/Copy-Kontext liefert der klassische LISP64-AStack bei
`$fffe` keinen beschreibbaren C64-RAM-Return-Vektor, sondern einen Wert aus dem
ROM-/KERNAL-Bereich. Ein schneller Gegenversuch mit `KERNAL_RAM_REPL=1` korrigiert
das nicht; provisorische Low-/Mid-RAM-Stackfenster (`$c000` bzw. `$a000-$bfff`)
waren ebenfalls nicht gruen und bleiben deshalb nicht als Runtime-Konfiguration
im Build. Der naechste belastbare Fix muss also die MEGA65/C65-Memory-Map fuer
einen writable Return-Stack gezielt klaeren oder den Startpfad in echten C64-RAM
bringen.

Diese Memory-Map-Klaerung ist jetzt als isolierter ML-Smoke verdrahtet:
`make phase5-mega65-map-high-ram-diagnostic` startet ein kleines
`AUTOBOOT.C65` ueber denselben gruenen `BOOT "AUTOBOOT.C65"`-Pfad, aber ohne
LISP64. Befund: direkte Zugriffe auf `$fffc-$ffff` und ein reines
`$01=$35`/`$36`-C64-Banking lesen weiter ROM-/KERNAL-Vektoren (`4f fa 23 fa` im
Dump). Ein explizites `MAPHI=$8000` fuer `$e000-$ffff -> bank-0 RAM` schreibt und
liest dagegen stabil `66 99 aa 55`; nach Restore auf `MAPHI=$8300` erscheinen
wieder die ROM-/KERNAL-Vektoren. Damit ist der noetige Schreibpfad fuer einen
MEGA65/C65-AStack nicht geraten, sondern als isolierte CPU-Memory-Map-Operation
belegt. Die ergaenzte MAP-State-Telemetrie zeigt aber auch, dass ein hartes
Restore auf `MAPHI=$8300` den urspruenglichen MAP-Zustand nicht exakt
wiederherstellt: initial liest der Smoke `e0 00 83 00 00 00`, nach dem Restore
`00 00 83 00 00 00`. Der eigentliche LISP64-Fix muss den MAP-Wechsel deshalb
entweder mit exaktem Save/Restore des vorherigen MAP-States kapseln oder einen
Zugriffspfad ohne globalen MAP-Flip waehlen; keine KERNAL-/I/O-Routine und kein
Interrupt darf waehrend des bank-0-High-RAM-Fensters laufen.

Der Zugriffspfad ohne globalen MAP-Flip ist inzwischen isoliert belegt:
`make phase5-mega65-flat-high-ram-diagnostic` nutzt die 45GS02-Adressierung
`[basepage],Z` mit einem 28-bit-Zielpointer auf `$0fffa`. Der Smoke schreibt und
liest `6a 95 c3 3c` aus bank-0-High-RAM zurueck, waehrend direkte 16-bit-Reads
weiter den BOOT/C65-Kontext (`16 fa 4f fa`) sehen und der MAP-State unveraendert
`e0 00 83 00 00 00` bleibt. Damit ist der naechste Runtime-Fixpfad klarer: fuer
MEGA65/C65 sollte AStack-Push/Pop nach Moeglichkeit per Quad-Indirect-Z-Indexed
auf den linearen bank-0-Stack zugreifen statt pro Zugriff ein High-RAM-MAP-Fenster
zu oeffnen und wieder zu restaurieren.

Dieser bevorzugte Pfad ist jetzt auch als AStack-Semantikprobe gruen:
`phase5-mega65-flat-astack-popa-jmp-diagnostic` spiegelt den MAP-basierten
`PopAStack_Jmp`-Harness, nutzt aber fuer Push/Pop ausschliesslich
Quad-Indirect-Z-Indexed-Zugriffe auf `$0fffa/$0fffb`. Der Gate prueft
`AStackPtrLo=$fc->$fa->$fc`, den gepoppten Zielvektor (`$182e` in diesem Build)
und den `FJ`-Marker aus dem indirekten Sprungziel. Damit sind die nackte
Flat-High-RAM-AStack-Semantik und der indirekte Sprung entlastet; offen ist
weiter die Integration in den echten LISP64-hREAD-/REPL-Kontext.

Der naechste isolierte Schritt ist ebenfalls gruen: derselbe Smoke restauriert
den beim Start per `hyppo_get_mapping` gesicherten sechs Byte langen MAP-State
anschliessend per `hyppo_set_mapping` (`$76`). Der Dump zeigt danach
`map_initial=e0 00 83 00 00 00` und
`map_restored=e0 00 83 00 00 00`. Damit ist ein exakter Save/Restore-Baustein
fuer den LISP64-AStack-Fix belegt; offen ist noch die Integration an den
Push-/Pop-Stellen ohne Aufruf von KERNAL-/I/O-Code im umgemappten Fenster.

Diese Integration ist als erster bedingter Runtime-Prototyp vorhanden:
`MEGA65_C65_STACK_MAP` kapselt DStack-/AStack-Zugriffe ueber einen direkten
MAP/AUG-Wechsel auf bank-0-High-RAM und restauriert danach zunaechst den
BOOT/C65-MAP-State (`MAPLO=$e000`, `MAPHI=$8300`). Mit diesem Define sind die
Copy-Diagnostics `phase5-mega65-lisp64-copy-after-hread-quoted-recurse-diagnostic`
(`QR`) und `phase5-mega65-lisp64-copy-before-hread-quoted-final-cons-diagnostic`
(`QJ`) gruen. Die nachgeschaltete Diagnose
`phase5-mega65-lisp64-copy-after-hread-quoted-final-cons-move-diagnostic` (`QK`)
ist ebenfalls gruen und belegt, dass der erste `hCONS`-Schritt
`MoveW2ToNode_SetW2ToW2NextPtr` zurueckkehrt. Die Pre/Post-Diagnose
`phase5-mega65-lisp64-copy-after-hread-quoted-final-cons-pop-prepost-diagnostic`
(`QP`) zeigte danach, dass `PopDStack` nach zwei sichtbaren Screen-Stores
zurueckkehren kann. Die engere Scratch-Diagnose
`phase5-mega65-lisp64-copy-after-hread-quoted-final-cons-pop-scratch-diagnostic`
(`QQ`) belegt, dass zwei absolute RAM-Stores (`lBUF`, `lBUF+1`) vor dem
naechsten MAP/AUG-High-RAM-Fenster reichen; ein einzelner Store bzw. ein
Zero-Page-Store reichte nicht. Ein Versuch, diese Barriere produktiv in den
globalen `Mega65StackMapHighRam`-Pfad bzw. direkt in `PopDStack` zu heben,
regressierte jedoch den frueheren `QK`-Grenzpunkt und wurde nicht uebernommen.
Eine Gegenprobe mit denselben zwei Stores direkt nach dem finalen
`hCONS`-Move timeoutete auf `QL`; die Store-Barriere ist also nicht einfach an
diese Stelle verschiebbar. Die naechste Eingrenzung setzt deshalb nur ein
neutrales 10-Byte-NOP-Pad in `hCONS` unter
`TERM_TEST_MEGA65_HCONS_LAYOUT_PAD`. Mit diesem Define sind
`phase5-mega65-lisp64-copy-after-hread-quoted-final-cons-cdr-pop-hcons-layout-diagnostic`
(`QL`) und
`phase5-mega65-lisp64-copy-after-hread-quoted-final-cons-pop-dstack-hcons-layout-diagnostic`
(`QM`) gruen. Damit ist belegt, dass die direkten finalen Grenzpunkte stark
code-layout-sensitiv sind, nicht dass eine ausgefuehrte Store-Barriere an
dieser Stelle produktionsreif ist. Die direkten finalen Grenzpunkte
`phase5-mega65-lisp64-copy-after-hread-quoted-final-cons-cdr-pop-diagnostic`
(`QL`) und
`phase5-mega65-lisp64-copy-after-hread-quoted-final-cons-pop-dstack-diagnostic`
(`QM`) timeouteten ohne Layout-Pad weiter.

Der naechste produktionsnaehere Schritt ist `MEGA65_C65_STACK_MAP_HYPPO_RESTORE`:
Der Restore-Pfad nutzt nun einen page-ausgerichteten sechs Byte langen
MAP-Snapshot im PRG und ruft `hyppo_set_mapping` mit explizitem `X=0` auf. Ein
frueherer Test mit festem `$6200`-Puffer war nur diagnostisch brauchbar, weil
`$6200` im vollen LISP64-Build Code enthaelt. Mit dem reservierten Snapshot
sind die direkten `QL`-/`QM`-Make-Gates ohne Layout-Pad gruen. Ein Versuch, ein
`NOP ; EOM` direkt nach `Mega65StackMapHighRam` einzufuegen, regressierte
dagegen `QK` und wurde verworfen. Der volle Hyppo-Restore-Copy-Minimal-Build
erreicht trotzdem noch keinen abschliessenden `(POKE 54991 66)`-Test-Exit; der
normale `phase5-mega65-lisp64-copy-stack-map-start-minimal` bleibt deshalb ein
bekannter Timeout-Reproducer.

Die naechste Reader-Eingrenzung ist jetzt hinter dem finalen Quote-Cons:
`phase5-mega65-lisp64-copy-hread-quoted-final-hcons-before-popa-diagnostic`
(`QH`) stoppt im echten finalen `hCONS` kurz vor `PopAStack_Jmp`,
`phase5-mega65-lisp64-copy-hread-quoted-final-hcons-after-popa-diagnostic`
(`QN`) springt ueber eine bekannte AStack-Fortsetzung aus diesem finalen
`hCONS` heraus, und
`phase5-mega65-lisp64-copy-hread-after-hread1-diagnostic` (`R1`) erreicht den
Ruecksprungpunkt in `hREAD` nach `CallYA hRead1`. Damit ist der Quote-Reader
inklusive finalem `hCONS` und internem `hRead1`-Return gruen; offen bleibt der
normale Rueckweg von `hREAD` in die REPL-Fortsetzung bzw. der unmittelbar
anschliessende Eval-Pfad.

Die hREAD-Ruecksprungstelle ist nun weiter getrennt: Ein zusaetzliches Label
direkt nach `CallYA hREAD` markiert den erwarteten REPL-Returnpunkt.
`phase5-mega65-lisp64-copy-hread-after-popa-diagnostic` (`RP`) pusht direkt vor
dem finalen `hREAD`-`PopAStack_Jmp` eine bekannte Fortsetzung und ist gruen;
`hREAD` kann also an dieser Stelle ueber den AStack springen. Die
produktionsnaehere Gegenprobe
`phase5-mega65-lisp64-copy-hread-return-vector-diagnostic` poppt dagegen den
echten AStack-Top-Vektor nach `R1` und bleibt ein bekannter Timeout-Reproducer.
Damit liegt der Blocker nicht mehr beim nackten `hREAD`-Pop-Mechanismus,
sondern beim realen AStack-Top-Zustand fuer den Ruecksprung in die REPL.

Eine nicht-invasive Snapshot-Gegenprobe ist gruen:
`phase5-mega65-lisp64-copy-hread-astack-ptr-diagnostic` (`RS`) haelt direkt
nach `R1`, ohne den echten AStack-Top-Vektor zu poppen. Der Dump zeigt
`AStackPtrLo=$fa`. Nach der Rueckkehr aus dem internen `CallYA hRead1` waere
fuer den normalen Rueckweg eher der aeussere hREAD-/REPL-Return-Frame oben zu
erwarten; `$fa` spricht deshalb fuer mindestens einen zusaetzlichen realen
AStack-Frame an dieser Stelle. Eine groessere Snapshot-Variante, die zusaetzlich
mehrere AStack-High-Bytes auslesen sollte, timeoutete wieder. Auch dieser Punkt
bleibt also layout-sensitiv. Der kontrollierte Push/Pop-Vergleich um `$fa` ist
jetzt gruen:
`phase5-mega65-lisp64-copy-hread-astack-pushpop-diagnostic` (`RU`) pusht nach
`R1` einen bekannten Vektor, poppt ihn sofort wieder und prueft im Dump
`AStackPtrLo=$fa->$f8->$fa` sowie den unveraenderten bekannten Vektor
(`$0ed4` in diesem Build). Damit funktionieren AStack-Pointer-Arithmetik,
High-RAM-MAP und Hyppo-Restore an dieser Stelle fuer einen kontrollierten
obersten Frame.
Ein zusaetzlicher Skip-Frame-Read bestaetigt die erste Variante:
`phase5-mega65-lisp64-copy-hread-skip-frame-diagnostic` (`RY` als erwarteter
Reproducer) liest nach `R1` mit `AStackPtrLo=$fa` den naechsten Slot bei `$fc`
unter High-RAM-MAP. Dort steht stabil `$0000`, waehrend der erwartete
hREAD-/REPL-Return in diesem Build `$122e` waere. Der Return liegt also nicht
einfach einen Frame tiefer. Ein direkter Top-Frame-Read hatte den echten Slot
bei `$fa` mit demselben MAP-Muster wie der Skip-Frame-Read gelesen und dort den
erwarteten hREAD-/REPL-Return gefunden; im aktuellen Rebuild ist
`phase5-mega65-lisp64-copy-hread-top-frame-diagnostic` (`RZ`) jedoch nicht mehr
als stabiler gruenes Gate reproduzierbar und timeoutet ohne `RZ`/`RA`-Marker.
Damit bleibt dieser Punkt layout-/rebuild-sensitiv. Eine weitere Gegenprobe
`phase5-mega65-lisp64-copy-hread-manual-pop-diagnostic` (`RO`) liest denselben
Top-Slot und schreibt den AStack-Pointer manuell von `$fa` auf `$fc` fort, ohne
`PopAStack2YA` oder den indirekten Ruecksprung zu benutzen. Auch dieser Lauf ist
gruen (`$123b` als erwarteter Return in diesem Diagnose-Build). Damit ist der
Pointer-Fortschritt selbst nicht der Ausloeser; der naechste Schnitt muss den
echten `PopAStack2YA`-Pfad, insbesondere MAP-Restore/Register-Erhalt gegen den
anschliessenden indirekten Sprung, zerlegen.
`phase5-mega65-lisp64-copy-hread-manual-pop-restore-diagnostic` zerlegt diesen
Schnitt weiter: derselbe manuelle Top-Slot-Read und Pointer-Fortschritt plus ein
direktes `Mega65StackMapRestore` erreicht im echten hREAD-Layout den
Post-Restore-Marker nicht. Der Gate akzeptiert diesen No-Marker-Timeout mit der
aktuellen Dump-Signatur (`20 2a ...`, beobachteter Vektor `$1309`). Damit liegt
der produktionsnahe Reproducer bereits beim Restore-tragenden hREAD-Kontext,
nicht erst bei der PHA/PLA-Registerrettung des Inline-PopA-Schnitts.
Eine kleinere Gegenprobe entlastet `Mega65StackMapRestore` allein:
`phase5-mega65-lisp64-copy-hread-restore-only-diagnostic` setzt nach `R1` nur
einen Vor-Marker, ruft `Mega65StackMapRestore` und erreicht danach `RR` mit
unveraendertem AStack-Zustand (`AStackPtrLo=$fa`, High `$ff`). Der Blocker liegt
damit nicht im nackten Restore-Aufruf. Auch der naechste Schnitt ist gruen:
`phase5-mega65-lisp64-copy-hread-map-restore-diagnostic` aktiviert nach `R1`
das High-RAM-Fenster und restauriert sofort wieder; `RM` zeigt erneut
unveraenderten AStack-Zustand (`$fa`/`$ff`). Der naechste Schnitt
`phase5-mega65-lisp64-copy-hread-top-read-restore-diagnostic` liest danach nur
den echten Top-Slot unter High-RAM-Mapping und restauriert direkt, ohne den
AStack-Pointer fortzuschreiben. Dieser Lauf reproduziert denselben
No-Marker-Timeout wie `manual-pop-restore` (`20 2a ...`, beobachteter Vektor
`$1309`). Damit ist der Top-Slot-Read plus Restore im hREAD-Layout ausreichend;
der Pointer-Fortschritt ist fuer den Reproducer nicht erforderlich. Die direkte
Gegenprobe ohne Restore ist gruen:
`phase5-mega65-lisp64-copy-hread-top-read-only-diagnostic` erreicht `RT`, laesst
`AStackPtrLo` bei `$fa` und liest den Top-Slot-Vektor `$1206`. Der echte Read
kehrt also zurueck; der Bruch entsteht erst beim anschliessenden Restore. Die
Flat-Gegenprobe im selben hREAD-Kontext ist ebenfalls gruen:
`phase5-mega65-lisp64-copy-hread-flat-top-read-only-diagnostic` liest denselben
Top-Slot per 45GS02-Quad-Indirect-Z-Indexed-Zugriff ohne MAP/Restore, erreicht
`RF`, laesst `AStackPtrLo` ebenfalls bei `$fa` und beobachtet denselben Vektor
`$1206`. Damit ist nicht nur der isolierte Flat-High-RAM-Zugriff, sondern auch
der produktionsnahe Flat-Read nach `CallYA hRead1` entlastet. Ein direkter
Folgeversuch, daraus einen zusaetzlichen inline Flat-Pop-Gate mit
Pointer-Fortschritt `$fa->$fc` zu machen, wurde nicht gelandet: selbst eine
minimalisierte Variante timeoutete vor dem Marker mit der bekannten
No-Marker-Signatur (`20 2a ...`). Der layoutneutrale Ersatzschnitt im
bestehenden `RF`-Slot ist dagegen gruen:
`phase5-mega65-lisp64-copy-hread-flat-pop-replace-diagnostic` nutzt dieselbe
Blockposition und ersetzt die letzte 5-Byte-Pointer-Beobachtung durch
`INC AStackPtrLo; INC AStackPtrLo; NOP`. Der Lauf erreicht `RP`, liest weiter
den Vektor `$1206` ohne MAP/Restore und belegt den Pointer-Fortschritt
`$fa->$fc` im echten hREAD-Kontext. Ein groesserer Inline-Folgegate im finalen
`hREAD`-Returnslot bleibt dagegen ein Reproducer:
`phase5-mega65-lisp64-copy-hread-flat-after-popa-diagnostic` versucht
Flat-Push, Flat-Pop und indirekten Jump auf eine bekannte Fortsetzung, erreicht
aber keinen `RJ`-Marker und zeigt wieder die No-Marker-Signatur (`20 2a ...`).
Der ausgelagerte Runtime-Schnitt ist dagegen gruen:
`phase5-mega65-lisp64-copy-hread-flat-helper-after-popa-diagnostic` ruft
`Mega65FlatPushYA2AStack` und `Mega65FlatPopAStack_Jmp` im echten
`hREAD`-Kontext auf, erreicht `RH`, prueft den Pointerlauf `$fa->$f8->$fa` und
springt ueber den gepoppten Vektor (`$0f2d` in diesem Build) in die bekannte
Fortsetzung. Damit ist der naechste Integrationsschritt ein eng gegateter
Ersatz des echten `PopAStack_Jmp`-/AStack-Runtimepfads, nicht ein weiterer
breiter Inline-Block im finalen `hREAD`-Slot.

Dieser Integrationsschritt ist jetzt als Minimalstart gruen:
`phase5-mega65-lisp64-copy-flat-astack-start-minimal` ersetzt den normalen
AStack-Runtimepfad per `MEGA65_C65_ASTACK_FLAT_RUNTIME` durch die Flat-Helper,
laeuft ueber den BOOT/Copy-Wrapper und erreicht im minimalen REPL-Script den
`(POKE 54991 66)`-Xemu-Test-Exit. Der historische
`phase5-mega65-lisp64-copy-stack-map-start-minimal` bleibt als Stack-MAP-
Timeout-Reproducer erhalten; die gruen belastbare Startbasis ist der Flat-
AStack-Runtimepfad.
Auch die
Gegenprobe ohne `MEGA65_C65_STACK_MAP_HYPPO_RESTORE` bleibt ein Reproducer:
`phase5-mega65-lisp64-copy-hread-top-read-hard-restore-diagnostic` nutzt den
alten harten MAP-Restore und erreicht ebenfalls keinen Post-Restore-Marker
(`20 2a ...`). Der Blocker ist damit nicht Hyppo-spezifisch, sondern sitzt am
Rueckweg nach einem echten Top-Slot-Read unter High-RAM-MAP. Der naechste
Schnitt schliesst auch den Subroutine-Rueckweg aus:
`phase5-mega65-lisp64-copy-hread-top-read-inline-hard-restore-diagnostic` fuehrt
denselben harten MAP-Restore direkt inline aus und reproduziert weiterhin den
No-Marker-Timeout. Damit ist nicht `JSR`/`RTS` um `Mega65StackMapRestore` der
Bruch, sondern die Restore-Operation selbst nach dem Top-Slot-Read.
Der erste Restore-Schnitt ist selbst schon ein Reproducer:
`phase5-mega65-lisp64-copy-hread-popa-restore-diagnostic` fuegt nach `R1` einen
minimalen Inline-Pop mit `Mega65StackMapRestore` ein. Dieser Build erreicht den
Post-`R1`-Marker nicht mehr und wird als No-Marker-Timeout akzeptiert. Das
bestaetigt die Layout-Sensitivitaet des Restore-tragenden hREAD-Pfads; ein
erfolgreicher Restore-/Register-Nachweis muss ausserhalb dieses hREAD-Layouts
isoliert werden. Dieser kleinere Schnitt ist jetzt gruen:
`phase5-mega65-stack-map-popa-restore-diagnostic` ist ein natives MEGA65-PRG,
das nur MAP high-RAM, HYPPO-Restore und einen AStack-Push/PopA nachbildet. Der
Gate prueft `AStackPtrLo=$fc->$fa->$fc` plus den gepoppten Ruecksprungvektor
(`$183c` in diesem Build). Damit sind MAP/Restore und A/Y-Erhalt im isolierten
PopA-Pfad entlastet; offen bleibt die Full-LISP-Layoutgrenze beziehungsweise der
echte `PopAStack_Jmp`-/indirekte Sprungpfad.

Der direkte isolierte Anschluss ist ebenfalls gruen:
`phase5-mega65-stack-map-popa-jmp-diagnostic` nutzt denselben MAP-High-RAM- und
Hyppo-Restore-Pfad, poppt den AStack-Vektor, schreibt ihn in einen Zero-Page-
Jump-Vektor und springt per indirektem `JMP` zum Ziel. Der Gate prueft
`AStackPtrLo=$fc->$fa->$fc`, den gepoppten Zielvektor (`$1831` in diesem Build)
und den `PJ`-Marker aus dem indirekten Sprungziel. Damit ist auch der isolierte
`PopAStack_Jmp`-Baustein entlastet; der verbleibende Blocker liegt im
Full-LISP-hREAD-Layout/Kontext oder unmittelbar im Rueckweg nach dem echten
REPL-Return, nicht im nackten MAP/Restore/indirekten Sprung-Mechanismus.

Die Flat-Gegenprobe desselben Semantikschnitts ist ebenfalls gruen:
`phase5-mega65-flat-astack-popa-jmp-diagnostic` ersetzt MAP/Restore durch
45GS02-Quad-Indirect-Z-Indexed-Zugriffe auf den linearen bank-0-AStack. Der Gate
prueft denselben Pointerverlauf, den gepoppten Zielvektor (`$182e` in diesem
Build) und den `FJ`-Marker aus dem indirekten Sprungziel. Damit ist der naechste
produktive Versuch enger: nicht mehr das Speicherzugriffsprinzip, sondern dessen
Register-/Zero-Page-/Layout-Vertraeglichkeit im echten LISP64-Runtime-Code muss
gegatet werden.

Die direkte produktionsnahe Gegenprobe bleibt dagegen ein Timeout:
`phase5-mega65-lisp64-copy-stack-map-after-read-diagnostic` baut denselben
`TERM_TEST_MEGA65_AFTER_READ_EXIT`-Marker wie der historische `copy-after-read`-
Schnitt, aber mit `MEGA65_C65_STACK_MAP` und
`MEGA65_C65_STACK_MAP_HYPPO_RESTORE`. Der Lauf erreicht den `RD`-Marker nach
`CallYA hREAD` nicht und reproduziert den bekannten Timeout mit Prozess-Cleanup.
Damit ist der normale hREAD-Ruecksprung im Full-LISP-Kontext weiter offen, obwohl
der isolierte `PopAStack_Jmp`-Mechanismus gruen ist.

Ein kurzer `QL`-Pad-Sweep zeigt, dass der Effekt nicht monoton ist: Pads
1-7, 9, 13, 14 und 16 timeouteten, Pads 8 und 11 beendeten xmega65 mit
Status 1 ohne `QL`-Marker, und Pads 10, 12 und 15 erreichten `QL`. Die
Symboladressen fuer den direkten `QL`-Build waren dabei:

| Pad | `TermTest...Hang` | `PopD2NextPtr` | `NextPtrNextToNodePtr` | Ergebnis |
| --- | --- | --- | --- | --- |
| 0 | `$1004` | `$11a7` | `$1244` | Timeout |
| 8 | `$100c` | `$11af` | `$124c` | xmega65 Status 1, PC `$1252`, kein `QL` |
| 10 | `$100e` | `$11b1` | `$124e` | `QL` |
| 11 | `$100f` | `$11b2` | `$124f` | xmega65 Status 1, kein `QL` |
| 12 | `$1010` | `$11b3` | `$1250` | `QL` |
| 15 | `$1013` | `$11b6` | `$1253` | `QL` |

Eine direkte BASIC-Text-Injektion in den C64-Modus ist ebenfalls kein
Workaround: `make phase5-mega65-go64-importbas-diagnostic` startet xmega65 mit
`-go64 -importbas src/v2/test-scripts/mega65-go64-importbas-diagnostic.bas`.
Dieses minimale C64-BASIC-Programm sollte `OK` in Screen-RAM schreiben und per
`$D6CF=$42` beenden. In dieser lokalen xmega65-/ROM-Kombination erreicht der
Lauf weder Test-Exit noch verwertbaren Dump/Screenshot; das Target reproduziert
den Timeout mit kontrolliertem Prozess-Cleanup.

Referenzbefund: Das MEGA65 Book dokumentiert `C64MODE` als `JMP $FF53`. Dieser
KERNAL-Einstieg setzt die GO64-Memory-Map/VIC-Modi und springt in die GO64-
Startroutine, kehrt aber nicht zurueck. Der BASIC-Abschnitt zu `GO 64` weist
ausserdem darauf hin, dass Programme im Speicher beim Moduswechsel verloren gehen.
Ein einfacher MEGA65-ML-Stub, der nur `JMP $FF53` ausfuehrt, ist deshalb noch kein
LISP64-Launcher: Er muesste nach dem GO64-Reset erneut laden oder einen belegten
preload-/cartridge-aehnlichen Uebergang nutzen.
Ein zusaetzlicher Test mit xmega65s `-prgtest file@addr`-Vorladung eines
minimalen C64-PRGs nach `$0801` plus anschließendem MEGA65-ML-Stub `JMP $FF53`
hing ebenfalls ohne verwertbaren Dump. Damit ist auch "vorladen, dann C64MODE"
aktuell kein gruener Headless-Pfad.

Zusaetzliche Diagnose am 2026-06-29: Ein C65-Launcher, der ueber den gruenen
`-prgmode 65 -prgtest "SYS 6144"`-Pfad startet, ein minimales C64-BASIC-PRG nach
`$0801` kopiert, die C64-BASIC-Pointer setzt, den KERNAL-Keyboard-Buffer mit
`RUN`+RETURN fuellt und dann per `JMP $FF53` in `C64MODE` springt, haengt
ebenfalls ohne Xemu-Test-Exit. `make phase5-mega65-c64mode-keybuf-launcher`
reproduziert diesen Befund als erwarteten Blocker und beendet das Make-Target
ohne haengenden Emulatorprozess. Damit ist auch der einfache
"C64-Payload vorladen, RUN per Typeahead, dann C64MODE"-Uebergang kein gruener
Launcher-Pfad.

Eine Variante desselben Schnitts mit dem dokumentierten MEGA65-KERNAL-Einstieg
`ADDKEY` (`$FF4A`; `$FF4D` ist laut MEGA65 Book `SPIN_SPOUT`) statt direkter
`$0277/$C6`-Keyboard-Buffer-Schreibzugriffe haengt ebenfalls ohne
Xemu-Test-Exit. `make
phase5-mega65-c64mode-addkey-launcher` kopiert denselben Minimal-Payload,
queued `RUN`+RETURN ueber `ADDKEY` und springt danach nach `C64MODE`; der
Timeout-Dump zeigt einen ausgefuehrten C65-Starter und C64-Payload-Spuren im
`$0801`-Bereich, aber keinen `OK`-Screen-State. Damit ist auch die
KERNAL-Soft-Keyboard-Uebergabe kein gruener Headless-Launcher-Pfad.

Zusaetzliche BOOT-Gegenprobe am 2026-06-29: `make
phase5-mega65-c64mode-addkey-boot-command` schreibt denselben ADDKEY-Launcher
als `AUTOBOOT.C65` auf D81 und startet ihn ueber den gruenen BASIC65-Befehl
`BOOT "AUTOBOOT.C65"`. Dieser Weg vermeidet xmega65s `-prgtest`-Starter und
nutzt den bereits belegten D81-BOOT-Pfad. Befund: Der Launcher wird geladen und
ausgefuehrt; der Dump zeigt den C65-Starter bei `$1800` und den C64-ML-Payload
bei `$0810`. Nach `C64MODE` bleibt der Bildschirm jedoch leer (`$0400/$0401`
Spaces), `$0801/$0802` sind null statt eines lauffaehigen BASIC-Line-Pointers,
und es gibt keinen Xemu-Test-Exit. Damit ist auch "BOOT -> C65-Launcher ->
C64MODE/ADDKEY/RUN" kein gruener LISP64-Launcher-Ersatz.

Eine normale C64-CRT-Datei mit `CBM80`-Autostart wurde als schneller
cartridge-aehnlicher Ersatzpfad getestet. xmega65s `-cart` lehnt dieses Format in
dieser Version explizit als `Non-MEGA65 CRT file` ab; der naechste
Cartridge-Versuch muesste daher das separate, im MEGA65 Book nur als spaeter zu
dokumentierendes Protokoll fuer MEGA65-Cartridges verwenden.

Naechster isolierter Versuch: Das MEGA65 Book dokumentiert `RESET_RUN` (`JSR
$FF32`) mit `A=2` als KERNAL-Warmboot, der das BASIC-Programm im Speicher ab
`$2001` ausfuehrt. `make phase5-mega65-reset-run-diagnostic` startet bewusst
nicht ueber xmega65s `-prgtest`-READY-Hook, sondern importiert ein kleines
BASIC65-Starterprogramm, das einen Diagnose-PRG von D81 nach `$1800` laedt und
`SYS 6144` ausfuehrt. Der Diagnose-PRG kopiert dann ein minimales BASIC-Programm
nach `$2001`, ruft `RESET_RUN` mit `A=2` auf und prueft bei Erfolg `OK` plus
Xemu-Test-Exit. Dieser Test ist bewusst noch kein LISP64-Launcher, sondern nur
ein Proof fuer "C65-Starter kann ein Programm im Speicher headless neu starten".
Als engere Kontrolle nutzt `make phase5-mega65-reset-run-basic-diagnostic` ein
importiertes BASIC65-Programm selbst: erster Lauf setzt ein RAM-Flag und ruft
`RESET_RUN A=2`, der erwartete zweite Lauf schreibt `OK` und beendet xmega65.
Falls `RESET_RUN` in dieser ROM-/xmega65-Kombination stattdessen zum Aufrufer
zurueckkehrt, schreibt der Test `RT` und beendet ebenfalls kontrolliert.
Aktueller Befund: Die BASIC-Kontrolle schreibt `RT`; `RESET_RUN A=2` kehrt also
in dieser lokalen ROM-/xmega65-Kombination zurueck, statt den erwarteten
Warmboot-RUN auszufuehren. Der D81/PRG-Test kopiert seinen Payload korrekt nach
`$2001/$2010`, erreicht aber keinen `OK`-Exit. Damit ist `RESET_RUN A=2` aktuell
kein gruener Launcher-Ersatz.

AUTOBOOT/BOOT-Diagnose: Das MEGA65-Handbuch beschreibt `AUTOBOOT.C65` als
bootfaehige Datei und `BOOT filename` als PRG-Load mit Start an der Load-Adresse.
`make phase5-mega65-autoboot-ml-diagnostic` schreibt deshalb ein minimales
MEGA65-ML-PRG als `AUTOBOOT.C65` auf D81 und startet xmega65 nur mit `-8`.
`make phase5-mega65-autoboot-boot-command-diagnostic` importiert zusaetzlich ein
BASIC65-Programm, das explizit `BOOT "AUTOBOOT.C65"` ausfuehrt. Beide Wege sind
als Diagnose gedacht und behaupten noch keinen LISP64-Start. Aktueller Befund:
der nackte `-8`-Start bootet die D81 nicht automatisch bis zum Test-Exit, aber
der explizite `BOOT "AUTOBOOT.C65"`-Pfad ist gruen: xmega65 laedt das
MEGA65-ML-PRG von D81, springt an dessen Load-Adresse `$1800`, schreibt `OK` und
erreicht `$D6CF=$42`.

## Fuenfstufige Probe-Matrix

Die fuenf naechsten Probe-Punkte sind jetzt als getrennte Artefakte vorbereitet:

| Stufe | Script/Fixture | Zweck | Status |
| --- | --- | --- | --- |
| 1 | `mega65-lisp64-start-minimal.acme` | LISP64 ohne D81/LOAD starten, Marker ausgeben, Test-Exit | blockiert vor verwertbarem Exit |
| 2 | `mega65-lisp64-start-d81.acme` + `phase5-mega65-lisp64-start-empty.d81` | Drive-8-D81 mounten, aber kein Lisp-LOAD | Artefakte gruen; Geraetestart durch Stufe 1 blockiert |
| 3 | `mega65-lisp64-load-mini.acme` + `phase5-mega65-lisp64-mini-savefmt.d81` | minimale SAVEFMT-Funktion `M65OK` laden und ausfuehren | Artefakte/Readback gruen; `phase5-mega65-lisp64-copy-flat-astack-load-return` beweist LOAD-Rueckkehr zur REPL, `phase5-mega65-lisp64-copy-flat-astack-load-call` beweist den anschliessenden Top-Level-Aufruf `(M65OK)`, `phase5-mega65-lisp64-copy-flat-astack-load-quote-symbol` beweist Quote nach LOAD; `phase5-mega65-lisp64-copy-flat-astack-eq-number`, `phase5-mega65-lisp64-copy-flat-astack-load-eq-number` und `phase5-mega65-lisp64-copy-flat-astack-load-eq-literal` sind nach dem hPOKE-I/O-Mapping-Fix gruen; der strenge `phase5-mega65-lisp64-copy-flat-astack-load-mini` bleibt Timeout-Reproducer am Funktionswert/COND-Schnitt |
| 4 | `mega65-lisp64-load-bank4-demo.acme` + `phase5-platform-mega65-bank4-demo-savefmt-smoke.d81` | `M65B4DM` laden und `DEMODASH` ausfuehren | Artefakte/Readback gruen; Geraetestart durch Stufe 1 blockiert |
| 5a | `mega65-c64-autostart-diagnostic.acme` | Positiver MEGA65/C65-PRGTest-Kontrollpfad mit demselben Minimal-PRG | gruen; `make phase5-mega65-c65-prgtest-diagnostic` prueft Dump-Signatur `OK` |
| 5a1 | voller LISP64-Kern mit `TERM_TEST_MEGA65_C65_ENTRY_EXIT` direkt per `-prgmode 65 -prgtest` | Entry-Adresse `$08FC` soll vor `Start1` nur `OK` schreiben und per `$D6CF=$42` beenden | bekannter direkter `-prg`-/PRGTest-Full-Image-Entry-Blocker; `make phase5-mega65-lisp64-c65-entry-diagnostic` reproduziert Timeout + Cleanup |
| 5a1b | `mega65-lisp64-copy-entry-launcher.acme` + D81 `AUTOBOOT.C65` | BOOT startet C65-Wrapper, Wrapper kopiert volles LISP64-Entry-Diagnose-Image nach `$0801` und springt nach `$08FC` | gruen; `make phase5-mega65-lisp64-copy-entry-launcher` prueft `OK`, Entry-Signatur und Xemu-Test-Exit |
| 5a1c | BOOT/Copy-Wrapper + staged Init-Marker | Tieferen LISP64-Start ohne REPL-Eingabe pruefen | gruen bis `NM`; Targets `phase5-mega65-lisp64-copy-init-entry-diagnostic`, `copy-after-init0`, `copy-after-reset-hash`, `copy-after-initfsl`, `copy-after-showacc32`, `copy-after-nodes-msg` |
| 5a1d | BOOT/Copy-Wrapper + `TERM_TEST_KEYS` + `mega65-lisp64-start-minimal.acme` | REPL-Scriptpfad gegen `InputLine`/`READ` eingrenzen | `copy-after-inputline`, `HR`, `NW`, `CR`, `QB` und `QC` gruen; mit `MEGA65_C65_STACK_MAP` jetzt auch `QR`, `QJ`, `QK`, `QP` und `QQ` gruen; direkte `QL`/`QM` sind mit `MEGA65_C65_STACK_MAP_HYPPO_RESTORE` und reserviertem MAP-Snapshot ohne Layout-Pad gruen; `phase5-mega65-lisp64-copy-stack-map-start-minimal` reproduziert weiter den Stack-MAP-Full-Minimal-Timeout; `phase5-mega65-lisp64-copy-flat-astack-start-minimal` erreicht mit `MEGA65_C65_ASTACK_FLAT_RUNTIME` den `(POKE 54991 66)`-Test-Exit |
| 5a1e | BOOT/Copy-Wrapper + `QV`-Return-Vektor-Diagnose | AStack-Top direkt vor `PopAStack_Jmp` lesen | gruenes Diagnose-Exit; AStack `$fffc` liest `$fa4f` statt erwartetem `hReadQuoted`-Return `$0ff2`, also kein valider C64-RAM-Return-Vektor bei `$fffe` |
| 5a1f | `mega65-map-high-ram-diagnostic.acme` | `$fffc-$ffff` im C65/BOOT-Kontext direkt, per `$01`, per MAPHI und per Hyppo-Save/Restore testen | gruen; direkt/`$01=$35` lesen ROM-Vektoren, `MAPHI=$8000` schreibt/liest bank-0-RAM korrekt; harter Restore war nicht exakt, `hyppo_set_mapping` restauriert `e0 00 83 00 00 00` bytegenau |
| 5a1f2 | `mega65-flat-high-ram-diagnostic.acme` | bank-0-High-RAM ohne globalen MAP-Flip per 45GS02-Quad-Indirect-Z-Indexed lesen/schreiben | gruen; `make phase5-mega65-flat-high-ram-diagnostic` schreibt/liest `$0fffa-$0fffd` als `6a 95 c3 3c`, direkte 16-bit-Reads bleiben im BOOT/C65-Kontext (`16 fa 4f fa`), MAP bleibt `e0 00 83 00 00 00` |
| 5a1f3 | `mega65-flat-astack-popa-jmp-diagnostic.acme` | isolierten Flat-High-RAM-AStack-Push/Pop plus echten indirekten Sprung pruefen | gruen; `make phase5-mega65-flat-astack-popa-jmp-diagnostic` prueft `AStackPtrLo=$fc->$fa->$fc`, Vektor `$182e` und `FJ` aus dem indirekten Ziel |
| 5a1g | `mega65-stack-map-popa-jmp-diagnostic.acme` | isolierten MAP-High-RAM-AStack-Pop plus echten indirekten Sprung pruefen | gruen; `make phase5-mega65-stack-map-popa-jmp-diagnostic` prueft `AStackPtrLo=$fc->$fa->$fc`, Vektor `$1831` und `PJ` aus dem indirekten Ziel |
| 5a1h | BOOT/Copy-Wrapper + `TERM_TEST_MEGA65_AFTER_READ_EXIT` + Stack-MAP/Hyppo-Restore | echten normalen `CallYA hREAD`-Ruecksprung bis zum REPL-Returnmarker `RD` pruefen | bekannter Timeout-Reproducer; `make phase5-mega65-lisp64-copy-stack-map-after-read-diagnostic` erreicht keinen `RD`-Marker |
| 5a1i | BOOT/Copy-Wrapper + hREAD-Restore-only / map-restore / top-read-only / flat-top-read-only / flat-pop-replace / flat-after-popa / flat-helper-after-popa / top-read-restore / top-read-hard-restore / inline-hard-restore / manual-pop-restore | Restore im echten hREAD-Kontext gegen High-RAM-Map, Flat-Read, Top-Slot-Read und Pointer-Fortschritt trennen | `phase5-mega65-lisp64-copy-hread-restore-only-diagnostic` (`RR`), `phase5-mega65-lisp64-copy-hread-map-restore-diagnostic` (`RM`), `phase5-mega65-lisp64-copy-hread-top-read-only-diagnostic` (`RT`, Vektor `$1206`), `phase5-mega65-lisp64-copy-hread-flat-top-read-only-diagnostic` (`RF`, Vektor `$1206`), `phase5-mega65-lisp64-copy-hread-flat-pop-replace-diagnostic` (`RP`, `$fa->$fc`, Vektor `$1206`) und `phase5-mega65-lisp64-copy-hread-flat-helper-after-popa-diagnostic` (`RH`, `$fa->$f8->$fa`, Vektor `$0f2d`) sind gruen; `phase5-mega65-lisp64-copy-hread-flat-after-popa-diagnostic` ist ein akzeptierter No-Marker-Reproducer fuer einen groesseren Inline-Flat-Push/Pop/Jmp-Gate; `phase5-mega65-lisp64-copy-hread-top-read-restore-diagnostic`, `phase5-mega65-lisp64-copy-hread-top-read-hard-restore-diagnostic`, `phase5-mega65-lisp64-copy-hread-top-read-inline-hard-restore-diagnostic` und `phase5-mega65-lisp64-copy-hread-manual-pop-restore-diagnostic` bleiben No-Marker-Reproducer, also reicht Top-Slot-Read plus Restore bereits aus und der Effekt ist weder Hyppo- noch JSR/RTS-spezifisch |
| 5a2 | `mega65-lisp64-start-minimal.acme` | Direktstart des minimalen LISP64-REPL-Skripts ueber den C65-PRGTest-Pfad | bekannter LISP64-C65-Direktstart-Blocker; `make phase5-mega65-lisp64-c65-direct-diagnostic` reproduziert Timeout + Cleanup |
| 5b | `mega65-c64-autostart-diagnostic.acme` | Minimalen C64-Autostart ohne LISP64 pruefen | bekannter xmega65-C64-Autostart-Blocker; `make phase5-mega65-c64-autostart-diagnostic` reproduziert ihn |
| 5b1 | `mega65-c64-autostart-diagnostic.acme` | Minimalen C64-PRGTest mit `-go64 -prgmode 64 -prgtest "SYS 2300"` pruefen | bekannter xmega65-C64-PRGTest-Blocker; `make phase5-mega65-c64-prgtest-sys2300-diagnostic` reproduziert Timeout + Cleanup |
| 5b2 | `mega65-go64-importbas-diagnostic.bas` | Minimalen C64-BASIC-Text per `-go64 -importbas` ausfuehren | bekannter xmega65-C64-ImportBAS-Blocker; `make phase5-mega65-go64-importbas-diagnostic` reproduziert Timeout + Cleanup |
| 5c | `mega65-c64mode-keybuf-launcher.acme` | C65-Launcher kopiert C64-PRG, seedet `RUN`+RETURN direkt und springt nach `C64MODE` | bekannter C64MODE-/Typeahead-Blocker; `make phase5-mega65-c64mode-keybuf-launcher` reproduziert ihn |
| 5d | `mega65-c64mode-addkey-launcher.acme` | C65-Launcher kopiert C64-PRG, queued `RUN`+RETURN per `ADDKEY` und springt nach `C64MODE` | bekannter C64MODE-/ADDKEY-Blocker; `make phase5-mega65-c64mode-addkey-launcher` reproduziert ihn |
| 5e | normales C64-CRT mit `CBM80` | Cartridge-aehnlicher C64-Autostart ueber xmega65 `-cart` | xmega65 lehnt das Format als `Non-MEGA65 CRT file` ab; kein C64-CRT-Pfad in dieser Tool-Version |
| 5f | `mega65-reset-run-diagnostic.acme` | C65-Launcher kopiert BASIC-Programm nach `$2001`, ruft `RESET_RUN A=2` und laesst es per Warmboot laufen | bekannter RESET_RUN-Blocker; Payload liegt bei `$2001/$2010`, aber kein `OK`-Exit |
| 5g | `mega65-reset-run-basic-diagnostic.bas` | BASIC65-Programm ruft `RESET_RUN A=2` und prueft per RAM-Flag den zweiten RUN nach Warmboot | bekannter RESET_RUN-Blocker; Test schreibt `RT`, weil `RESET_RUN` zum Aufrufer zurueckkehrt |
| 5h | `mega65-autoboot-ml-diagnostic.acme` | D81 enthaelt MEGA65-ML-PRG als `AUTOBOOT.C65`; xmega65 startet nur mit `-8` | bekannter AUTOBOOT-Blocker; kein Test-Exit ohne explizites BOOT |
| 5i | `mega65-autoboot-boot-command.bas` | importiertes BASIC65 ruft `BOOT "AUTOBOOT.C65"` fuer dasselbe ML-PRG auf | gruen; `make phase5-mega65-autoboot-boot-command-diagnostic` prueft `OK` + Xemu-Test-Exit |
| 5j | `mega65-autoboot-boot-command.bas` + ADDKEY-Launcher als `AUTOBOOT.C65` | gruener BOOT-Starter startet C65-Launcher, der nach `C64MODE` per `ADDKEY` `RUN` ausloesen soll | bekannter C64MODE-/ADDKEY-Blocker bleibt; `make phase5-mega65-c64mode-addkey-boot-command` zeigt C65-Starter und Payload-Spuren, aber keinen `OK`-Exit |
| 6 | dedizierter Launcher | Ersatz fuer xmega65-PRG-Autostart, falls Stufe 1 haengt | offen |

Damit gibt es aktuell noch keinen Make-Target, der behauptet, die MEGA65-SAVEFMT-
Bank-4-Bibliothek werde auf dem Geraet von LISP64 selbst geladen. Der belegte
geraetenahe Pfad bleibt BASIC65+D81+BLOAD/SYS fuer native Helper; der belegte
Lisp-Startpfad ist jetzt der BOOT/Copy-Minimalstart mit Flat-AStack-Runtime.
Der erste echte LISP64-LOAD-Geraeteschnitt ist jetzt aufgeteilt:
`phase5-mega65-lisp64-copy-flat-astack-load-return` kommt bis zum D81 mit
`AUTOBOOT.C65` und `M65OK,U` und erreicht nach `(LOAD 8 "M65OK")` den
Test-Exit. `phase5-mega65-lisp64-copy-flat-astack-load-call` erreicht den Exit
auch nach einem separaten Top-Level-`(M65OK)`, und
`phase5-mega65-lisp64-copy-flat-astack-load-quote-symbol` erreicht den Exit
nach einem separaten Top-Level-`'M65OK`. Die EQ-Gegenproben
`phase5-mega65-lisp64-copy-flat-astack-eq-number`,
`phase5-mega65-lisp64-copy-flat-astack-load-eq-number` und
`phase5-mega65-lisp64-copy-flat-astack-load-eq-literal` sind nach dem
hPOKE-I/O-Mapping-Fix gruen. Der strenge
`phase5-mega65-lisp64-copy-flat-astack-load-mini` bleibt ein akzeptierter
Timeout-Reproducer am kombinierten Funktionswert/COND-Schnitt. Die neuen
Kontrolltargets `phase5-mega65-lisp64-copy-flat-astack-load-cond-t` und
`phase5-mega65-lisp64-copy-flat-astack-load-cond-eq-number` sind gruen; damit
sind `LOAD`, `COND` und numerisches `EQ` in dieser Kombination entlastet. Die
Gegenprobe `phase5-mega65-lisp64-copy-flat-astack-cond-quote-symbol` ist
ebenfalls gruen, nutzt aber direkt den `$D6CF`-Exit und ist deshalb kein
Screen-RAM-Body-Beweis. Der finale `COND`-Body laeuft im
MEGA65-Flat-AStack-Build nun ueber `CallEval` und die bestehende
AStack-Continuation statt per direktem Tail-`JMP hEVAL`. Positiv belegt sind
damit
`phase5-mega65-lisp64-copy-flat-astack-load-cond-t-eq-body`,
`phase5-mega65-lisp64-copy-flat-astack-load-cond-t-poke-nontail-screen` und
`phase5-mega65-lisp64-copy-flat-astack-load-cond-t-poke-screen-tail`:
`COND T` mit finalem `(EQ 1 1)` sowie mit nicht-finalem und finalem
`(POKE 1024 65)` kehrt zurueck; die POKE-Varianten schreiben `$41` nach
`$0400`. Auch
`phase5-mega65-lisp64-copy-flat-astack-load-cond-quote-symbol-then-poke` ist
gruen und zeigt, dass ein Quote-Symbol-Praedikat mit einfachem `T`-Body und
separatem Top-Level-POKE nach LOAD laeuft. Auch
`phase5-mega65-lisp64-copy-flat-astack-load-cond-quote-symbol-two-t-body` ist
gruen; ein rein literaler Mehrfach-Body `(T T)` unter demselben Quote-Praedikat
kehrt bis zum Top-Level-Exit zurueck. Der offene Schnitt ist aber kein
generischer `QUOTE`-Body und auch nicht generisch `LOAD` plus `QUOTE`-Body:
`phase5-mega65-lisp64-copy-flat-astack-cond-quote-symbol-quote-body` ist ohne
LOAD gruen fuer `(COND ('M65OK 'M65OK))`, und
`phase5-mega65-lisp64-copy-flat-astack-load-cond-t-quote-body` ist gruen fuer
`LOAD` plus `(COND (T 'M65OK))`. Der Reproducer braucht die Kombination aus
geladenem/folgendem Kontext, Quote-Symbol-Praedikat und `QUOTE`-Body:
`phase5-mega65-lisp64-copy-flat-astack-load-cond-quote-symbol-quote-body-known-blocker`
reproduziert `(COND ('M65OK 'M65OK))` nach LOAD ohne `$0400`-Write. Auch
`phase5-mega65-lisp64-copy-flat-astack-load-cond-quote-symbol-quote-foo-body-known-blocker`
reproduziert den Abbruch bei `(COND ('M65OK 'FOO))`; der Blocker haengt damit
nicht daran, dass Praedikat und Body dasselbe Symbol zitieren. Die weitere
reine Script-Gegenprobe
`phase5-mega65-lisp64-copy-flat-astack-load-cond-quote-symbol-quote-t-body-known-blocker`
reproduziert den Abbruch auch bei `(COND ('M65OK 'T))`. Die neue reine
Script-Probe
`phase5-mega65-lisp64-copy-flat-astack-load-cond-quote-symbol-quote-t-nontail-known-blocker`
reproduziert denselben Schnitt mit `(COND ('M65OK 'T T))`: ein nicht-finaler
`QUOTE`-Body schreibt nicht bis zum anschliessenden Top-Level-POKE durch.
Zusaetzlich reproduziert
`phase5-mega65-lisp64-copy-flat-astack-load-cond-quote-symbol-t-quote-t-body-known-blocker`
den roten Fall `(COND ('M65OK T 'T))`, waehrend
`phase5-mega65-lisp64-copy-flat-astack-load-cond-quote-symbol-two-quote-t-body`
fuer `(COND ('M65OK 'T 'T))` gruen ist. Zusammen mit dem gruenen
`(COND ('M65OK T T))` ist der Schnitt damit nicht der Body-Wert, sondern die
`COND`-Body-Iteration fuer den einzelnen finalen Reader-Quote-Body und fuer
gemischte Literal/Reader-Quote-Body-Folgen. Wichtig:
`phase5-mega65-lisp64-copy-flat-astack-load-cond-quote-symbol-explicit-quote-t-body`
ist fuer `(COND ('M65OK (QUOTE T)))` gruen. Damit ist der Fehler enger als
`QUOTE` allgemein und sitzt an der Reader-Kurzform `'...` in diesem
LOAD/Quote-Praedikat-Kontext. Noch enger:
`phase5-mega65-lisp64-copy-flat-astack-load-cond-explicit-quote-symbol-quote-t-body`
ist fuer `(COND ((QUOTE M65OK) 'T))` ebenfalls gruen. Damit kippt nicht schon
ein Reader-Quote-Body, sondern die Kombination aus Reader-Quote-Praedikat und
Reader-Quote-Body in derselben Klausel nach LOAD. Reine Literal- und reine
wiederholte Reader-Quote-Folgen laufen. Der neue
`phase5-mega65-lisp64-copy-flat-astack-load-cond-quote-symbol-quote-body-hprint-entry-known-blocker`
kompiliert denselben Reproducer mit `TERM_TEST_MEGA65_HPRINT_ENTRY_EXIT=1`; der
hPRINT-Einstieg wird nicht erreicht, und der Dump bleibt bei `$0400=$20`. Der
Abbruch liegt damit vor der Top-Level-Ausgabe. Die beiden engeren Targets
`phase5-mega65-lisp64-copy-flat-astack-load-cond-quote-symbol-quote-body-hlistquote-entry-known-blocker`
und
`phase5-mega65-lisp64-copy-flat-astack-load-cond-quote-symbol-quote-body-hcond-final-body-return-known-blocker`
bleiben ebenfalls rot: der QUOTE-Body erreicht `hLISTQUOTE` nicht, und der
finale `COND`-Body-`CallEval` kehrt nicht zurueck. Noch frueher bleiben
`phase5-mega65-lisp64-copy-flat-astack-load-cond-quote-symbol-quote-body-hcond-pred-return-known-blocker`
und
`phase5-mega65-lisp64-copy-flat-astack-load-cond-quote-symbol-quote-body-hcond-final-body-call-known-blocker`
rot. Diese instrumentierten Marker bleiben diagnostisch nuetzlich, sind wegen
der MEGA65-Autoboot-/Layout-Empfindlichkeit aber vorsichtiger zu lesen als die
reinen Script-Proben. Der naechste enge Schnitt ist damit die Grenze zwischen
erfolgreichem Quote-Symbol-Praedikat und `COND`-Body-Iteration: `hCOND6` fuer
den direkten finalen Reader-Quote-Body, `hCOND7`/`hCOND5` fuer den Wechsel
zwischen Literal- und Reader-Quote-Bodies sowie die Reader-Expansion der
Kurzform gegen explizites `(QUOTE ...)`, besonders wenn Praedikat und Body beide
aus der Kurzform stammen. Die
separaten-Exit-Kontrollen zu Quote-, Literal-`EQ`- und geladenem
Call-Praedikat bleiben damit als Diagnose/Blocker stehen: Quote-Symbol mit
nicht-trivialem Body,
Literal-`EQ`-`screen-tail` und geladener Call-Praedikat-Body sind
Known-Blocker; der Call-Praedikat-Fall erreicht den separaten Exit, laesst
`$0400` aber bei `$20`.
Das alte Negativtarget
`phase5-mega65-lisp64-copy-flat-astack-load-cond-t-poke-screen-tail-known-blocker`
ist auf den gruenen Tail-Smoke umgebogen. Das Negativtarget
`phase5-mega65-lisp64-copy-flat-astack-load-cond-quote-symbol-known-blocker`
reproduziert dagegen den Timeout bei finalem
`(COND ('M65OK (POKE 54991 66)))` nach LOAD. Eine manuelle Gegenprobe mit
finalem `(POKE 54991 65)` und separatem Top-Level-Exit timeoutet ebenfalls. Die
bekannten Negativtargets
`phase5-mega65-lisp64-copy-flat-astack-load-cond-quote-symbol-quote-body-known-blocker`,
`phase5-mega65-lisp64-copy-flat-astack-load-cond-quote-symbol-quote-foo-body-known-blocker`,
`phase5-mega65-lisp64-copy-flat-astack-load-cond-quote-symbol-eq-body-known-blocker`,
`phase5-mega65-lisp64-copy-flat-astack-load-cond-quote-symbol-poke-nontail-known-blocker`,
`phase5-mega65-lisp64-copy-flat-astack-load-cond-quote-symbol-poke-screen-tail-known-blocker`,
`phase5-mega65-lisp64-copy-flat-astack-load-cond-quote-foo-poke-screen-tail-known-blocker`,
`phase5-mega65-lisp64-copy-flat-astack-load-cond-eq-literal-poke-screen-tail-known-blocker`,
`phase5-mega65-lisp64-copy-flat-astack-load-cond-eq-literal-known-blocker` und
`phase5-mega65-lisp64-copy-flat-astack-load-eq-call-known-blocker` reproduzieren
den Quote-Symbol-Body-Schnitt (`QUOTE`, `EQ`, nicht-finaler POKE, finaler POKE)
ohne `$0400`-Write, denselben Blocker mit frischem `'FOO` statt geladenem
`M65OK`, den verbleibenden Timeout bei Literal-`EQ` nach LOAD beziehungsweise
bei einem geladenen Funktionswert als `EQ`-Argument; die umgekehrte
Argumentordnung ist mit
`phase5-mega65-lisp64-copy-flat-astack-load-eq-call-reversed-known-blocker`
ebenfalls ein Reproducer. Die expliziten Vergleichswert-Varianten
`phase5-mega65-lisp64-copy-flat-astack-load-eq-call-explicit-quote-known-blocker`
und
`phase5-mega65-lisp64-copy-flat-astack-load-eq-call-reversed-explicit-quote-known-blocker`
enden ebenfalls rot bei PC `$0000`; Reader-Quote auf dem Vergleichswert ist
damit nicht die Ursache. `phase5-mega65-lisp64-copy-flat-astack-load-atom-call-known-blocker`
reproduziert denselben verschachtelten geladenen Funktionswert als `ATOM`-
Argument, also ausserhalb von `hEQ`. Die Kontrollprobe
`phase5-mega65-lisp64-copy-flat-astack-de-atom-call` ist dagegen gruen:
interaktiv per `DE` definierter `M65OK` kann als `(ATOM (M65OK))` ausgewertet
werden. Der rote Pfad haengt damit an LOAD-/SAVEFMT-geladenen Definitionen, nicht
an verschachtelten Funktionsaufrufen allgemein. Die nachgeschaerfte Probe
`phase5-mega65-lisp64-copy-flat-astack-load-rede-atom-call-known-blocker`
laedt `M65OK`, definiert `M65OK` danach interaktiv neu und timeoutet trotzdem
bei `(ATOM (M65OK))`. `phase5-mega65-lisp64-copy-flat-astack-load-rede-call`
ist dagegen gruen: derselbe LOAD/Re-`DE`-Vorlauf kann `(M65OK)` als Top-Level-
Aufruf ausfuehren. LOAD hinterlaesst also offenbar Runtime-/Stack-Zustand, der
erst die verschachtelte Funktionswert-Auswertung belastet. `hATOM` selbst ist
nach LOAD nicht der Bruch: `phase5-mega65-lisp64-copy-flat-astack-load-atom-quote-symbol`
wertet `(ATOM 'M65OK)` gruen aus.
Die anschliessenden Override-Diagnosen auf dem bestehenden
`phase5-mega65-lisp64-copy-flat-astack-load-eq-number`-Pfad schneiden den roten
`(ATOM (M65OK))`-Fall weiter: der `S1338`-Argumentpfad erreicht das
verschachtelte `CallEval`, kehrt daraus zurueck, pusht das finale NIL fuer
`hCONS`, erreicht `hATOM`, poppt das ausgewertete Argument vom DStack, bestimmt
dessen Typ und erreicht in `return_true` den Push von `T`. Der kontrollierte
`return_true`-After-Push-Dump zeigt den AStack-Top-Slot bei `$fffa` als `$1239`.
Bytegenau liegt dort in diesem Build nicht ein stale `hREAD`-Return, sondern
die Instruktion direkt nach dem top-level `JSR CallEval`, also die Vorbereitung
des folgenden `hPRINT`-Aufrufs. Der rote uninstrumentierte Pfad erreicht den
separaten Eval-Return-Schnitt vor `hPRINT` trotzdem nicht, und groessere
Pop-/hPRINT-Instrumentierungen in diesem Bereich sind layout-sensitiv. Der
naechste Schnitt liegt damit zwischen `return_true`/finalem `PopAStack_Jmp` und
der Rueckkehr zum top-level Eval-Return, nicht mehr bei `hATOM`, `hCONS` oder
dem verschachtelten `(M65OK)`-Aufruf selbst. Ein frischer uninstrumentierter
Reproducer-Dump zeigt zusaetzlich, dass der Codebereich um
`return_true`/`hATOM` (`$16b0` in diesem Build) nach dem Crash mit `$37`
ueberschrieben ist, waehrend der gruene `LOAD + (ATOM 'M65OK)`-Kontrollpfad und
der rote `return_true`-After-Push-Stop denselben Bereich intakt lassen. Die
Korruption passiert also nach dem erfolgreichen `T`-Push und vor bzw. waehrend
der Rueckkehr zum top-level Eval-Return. Ein erneuter roter Dump zeigt dabei ein
wiederholtes `$37`-Muster bereits in Zero Page; die Flat-AStack-Routinen und die
`AStackPtrHi*`-Selbstmodifikationsbytes bleiben dagegen intakt. Zwei direkte
Fix-Hypothesen sind negativ getestet und wieder verworfen: Flat-AStack-Far-
Pointer `$44-$47` sichern/restaurieren sowie harter MAP-Restore statt
Hyppo-`set_mapping` machen bereits den gruenen `LOAD + (ATOM 'M65OK)`-
Kontrollpfad zum Timeout. Die naechste Diagnose sollte deshalb eine minimale
Code-Page-/Write-Waechterprobe um diesen Eval/Apply-Bereich sein, nicht ein
weiterer hPRINT-Marker.
Die hEQ-Diagnoseleiter trennt diesen Blocker weiter:
`phase5-mega65-lisp64-copy-flat-astack-heq-entry-diagnostic`,
`phase5-mega65-lisp64-copy-flat-astack-heq-compare-return-diagnostic`,
`phase5-mega65-lisp64-copy-flat-astack-heq-return-true-entry-diagnostic` und
`phase5-mega65-lisp64-copy-flat-astack-heq-return-true-push-diagnostic` sind
gruen. Der neue
`phase5-mega65-lisp64-copy-flat-astack-heq-return-popa-diagnostic` ist ebenfalls
gruen und stoppt am echten Eintritt in `PopAStack_Jmp` (`EQP`, AStack-Pointer
`$fa`). Der neue
`phase5-mega65-lisp64-copy-flat-astack-heq-popa-after-pop-diagnostic` ist
ebenfalls gruen und stoppt nach einem out-of-line `PopAStack2YA` im echten
hEQ-Rueckweg (`EQBA`, `$fa->$fc`, Vektor `$126f`). `(EQ 1 1)` erreicht also
`hEQ`, `Compare` kehrt mit True-Zweig zurueck, der lokale Push von `T` kehrt
zurueck, der echte `return_true`-Pfad springt bis `PopAStack_Jmp`, und der echte
AStack-Pop liefert einen plausiblen Ruecksprungvektor. Der neue
`phase5-mega65-lisp64-copy-flat-astack-heq-eval-return-diagnostic` ist ebenfalls
gruen und stoppt direkt nach `JSR CallEval` vor `hPRINT`. Der echte indirekte
Sprung nach `$126f` und die Rueckkehr aus `CallEval` funktionieren damit
ebenfalls. Der neue
`phase5-mega65-lisp64-copy-flat-astack-heq-hprint-entry-diagnostic` erreicht
auch den Eintritt in `hPRINT`. Der neue
`phase5-mega65-lisp64-copy-flat-astack-heq-hprint-after-dup-diagnostic` erreicht
zusaetzlich die Stelle nach `DupDStack` in `hPRINT`. Der neue
`phase5-mega65-lisp64-copy-flat-astack-heq-hprint-after-printsexpr-diagnostic`
erreicht auch die Stelle nach `PrintSExpr`. Der neue
`phase5-mega65-lisp64-copy-flat-astack-heq-hprint-after-printcr-diagnostic`
erreicht danach auch die Stelle nach `PrintCR`. Der neue
`phase5-mega65-lisp64-copy-flat-astack-heq-hprint-return-diagnostic` erreicht
anschliessend den REPL-Ruecksprung hinter `CallYA hPRINT`. Der neue
`phase5-mega65-lisp64-copy-flat-astack-eq-repl-second-iteration-diagnostic`
erreicht danach den naechsten `IntprLoop1`. Der neue
`phase5-mega65-lisp64-copy-flat-astack-eq-second-read-return-diagnostic`
erreicht auch den `hREAD`-Return der zweiten Script-Form. Die hPOKE-Diagnosen
haben danach gezeigt: `ACC32=$0000d6cf` und `ARG32=$00000042` sind korrekt,
aber der indirekte Store loeste ohne explizite I/O-Sicht keinen Xemu-Test-Exit
aus. `hPOKE` ruft im `MEGA65_C65_STACK_MAP`-Build vor dem indirekten Store nun
`MapNormalBank`; damit sind `phase5-mega65-lisp64-copy-flat-astack-eq-number`,
`phase5-mega65-lisp64-copy-flat-astack-load-eq-number` und
`phase5-mega65-lisp64-copy-flat-astack-load-eq-literal` gruen.

## Naechster technischer Schnitt

Der naechste echte Fortschritt ist der strenge Mini-LOAD-Wertnutzungs-Schnitt
auf Basis des gruenen BOOT/Copy-Starts mit Flat-AStack-Runtime:

- das Flat-AStack-Gate als MEGA65-Startvariante stabil halten,
- eine minimale Code-Page-/Write-Waechterprobe um den nach dem finalen
  `return_true` korrumpierten Eval/Apply-Bereich (`$16b0` in diesem Build)
  schneiden, ohne den layout-sensitiven hPRINT-Bereich zu verschieben,
- beim Quote-Symbol-Zweig konkret vor der Top-Level-Ausgabe weiter schneiden:
  Quote-Symbol-Predicate-Evaluation nach LOAD bis zum Rueckweg nach
  `hCOND3TestDone`, danach erst Body-Eval/Dispatch, Rueckweg von `hLISTQUOTE`
  nach `hCOND` und die `hPOKE`-/`$D6CF`-Tail-Varianten pruefen; Quote-Praedikat,
  finaler `EQ`-Body, nicht-finaler `hPOKE`-Body und finaler `hPOKE`-Tail auf
  normale RAM-Adresse sind inzwischen gruen,
- danach ein D81 mit minimalen LISP64-/IDE-Libraries packen und einen
  MEGA65-Geraete-Smoke fuer den ersten strengen `(LOAD 8 ...)`-Schnitt in den
  gruenen Build aufnehmen.
