# Workbench HW Test 2026-07-08

Stand: 2026-07-08. Ziel war ein echter MEGA65-Test des aktuellen
Workbench-MVP-Kandidaten `mvp-vm-stdlib-einsuite-core-workbench`.

## Setup

- Commit: `a9c10fd` fuer den ersten Compile-String-Roundtrip; spaeterer
  Retest auf dem `LISP65_SYMFN_EXT`-Changeset nach `e654cb3`.
- Build-Gate: `make workbench-gate`
- PRG: `build/lisp65-mega65-vm-stdlib-einsuite-core-workbench.prg`
- Blob: `build/bytecode/stdlib-p0.ext.bin`
- MEGA65: `fe80::500c:34ff:fe76:a540%enp35s0`
- JTAG: `/dev/ttyUSB1`
- Kein `m65 -F`; Deploy direkt per Etherload.

## Automatisches Build-Gate

`make workbench-gate` ist mit dem aktuellen Workbench-Pin gruen:

```text
prg_bytes=41143
prg_file_end=0xc0b6
stack_gap_bytes=1728
bank0_reserve_bytes=278
NAMEPOOL=12288
MAX_SYM=640
VM_DIR_MAX=512
GC_ROOTS=128
REPL_BUF_MAX=192
```

Diese automatischen Gate-Werte enthalten die Mini-REPL-History per CRSR-hoch,
den 192-Byte-REPL-Buffer und den Cap-Nachzug fuer die vergroesserte IDE-Lib
inklusive `(dir)`. `make workbench-persistence-gate` prueft zusaetzlich die
IDE-Persistenz-Hostcases, baut `mvp-ship` und laesst den Deploy-Dry-Run laufen.
Die frueheren HW-Interaktionsprotokolle unten stammen teils von vorherigen PRGs;
wo das relevant ist, steht es im jeweiligen Abschnitt.

## REPL- und Compile-String-Roundtrip

Test-D81 `WBTEST.D81` enthielt einen vorallokierten 8-KB-SEQ-Slot `an`.
Deploy:

```sh
sh scripts/run-on-mega65.sh \
  --ip 'fe80::500c:34ff:fe76:a540%enp35s0' \
  --mount WBTEST.D81 \
  --preload-bin 0x050000 build/bytecode/stdlib-p0.ext.bin \
  --run build/lisp65-mega65-vm-stdlib-einsuite-core-workbench.prg
```

JTAG-REPL-Ergebnis:

```lisp
(+ 20 22)                                                     => 42
(defun sq (x) (* x x))                                       => sq
(sq 7)                                                       => 49
(compile-string "(defun a()40)(defun b()(+ (a)2))" "an")     => t
(load-lib "an")                                              => t
(b)                                                          => 42
```

Counter nach dem Compile-/Load-Lib-Roundtrip:

```text
gc_runs=6
gc_badobj=0
mem_oom=0
```

Ergebnis: REPL, lcc-installierter `defun`, `compile-string`, Disk-Save in
vorallokierten Slot, `load-lib` und Ausfuehrung der geladenen Funktion sind auf
echter HW gruen.

## IDE-On-Demand-Test

Zweites D81 `WBIDE.D81` enthielt:

```text
"ide"  seq  ; build/bytecode/libs/ide.ext.bin
"an"   seq  ; vorallokierter 8-KB-Slot
```

Der erste Lauf mit `MAX_SYM=472`/`VM_DIR_MAX=384` zeigte nach Deploy mit
`WBIDE.D81`:

```lisp
(edit)
```

JTAG-Screenshot:

```text
*** too many symbols
```

Counter nach dem IDE-Fehler:

```text
gc_runs=0
gc_badobj=0
mem_oom=0
```

Interpretation: Der Fehler ist kein GC-/OOM-Crash. Der aktuelle Cap-Pin
`MAX_SYM=472` hat nur 39 Boot-Symbol-Headroom; die IDE-Disk-Lib benoetigt beim
On-Demand-Load mehr Symbol-Slots. Damit ist der Compile-String-Teil des
Workbench-Kandidaten HW-gruen, der vollstaendige Workbench-Vertrag mit
`(edit)`/IDE-On-Demand aber noch nicht erfuellt.

## Retest nach `LISP65_SYMFN_EXT`

Fix: Workbench lagert `symfn` mit `-DLISP65_SYMFN_EXT` nach EXT-RAM aus und
pinnt `MAX_SYM=592`, `VM_DIR_MAX=464`. Der RUN/STOP-IDE-Toggle bleibt aus dem
residenten MVP-Pfad; IDE-Start erfolgt per `(edit)`.

Deploy:

```sh
sh scripts/run-on-mega65.sh \
  --ip 'fe80::500c:34ff:fe76:a540%enp35s0' \
  --mount WBIDE.D81 \
  --preload-bin 0x050000 build/bytecode/stdlib-p0.ext.bin \
  --run build/lisp65-mega65-vm-stdlib-einsuite-core-workbench.prg
```

JTAG-REPL-Ergebnis:

```lisp
(+ 20 22)                                                     => 42
(compile-string "(defun a()40)(defun b()(+ (a)2))" "an")     => t
(load-lib "an")                                              => t
(b)                                                          => 42
(edit)                                                       => IDE, "-- scratch -- 563/592"
```

Kurzer IDE-Tipp-Smoke:

```text
(+ 1 2)
-- scratch * -- 563/592
```

Nachtrag: Der spaetere RUN/STOP-Persistenz-Fix speichert den aktiven Buffer vor
jedem blockierenden `read-key` und fuegt der ladbaren IDE-Lib zwei interne
Funktionen hinzu. Diese historische Statuszeile bleibt der belegte HW-Wert vor
diesem Nachtrag; die naechste HW-Messung sollte grob zwei Symbole hoeher liegen.

Counter nach dem IDE-Tipp-Smoke:

```text
gc_runs=9
gc_badobj=0
mem_oom=0
```

Ergebnis: Der IDE-On-Demand-Blocker ist geloest. Die neue offene Frage ist
Performance, weil der aktuelle `symfn`-EXT-Pfad bewusst ohne MRU-/Slot-Cache
gebaut ist; Cache-Varianten sprengten im Test das PRG-Ende-Gate.

## Retest nach Persistenz- und Demo-Slot-Nachzug

Der erste Persistenz-Nachzug vergroesserte die ladbare IDE-Lib auf 152 Eintraege.
Der alte Pin `MAX_SYM=592`/`VM_DIR_MAX=464` war danach nicht mehr ausreichend:

```lisp
(load-lib "ide")                         => nil
```

Ursache: Boot hat 315 Directory-Eintraege, `load-lib` richtet vor Lib-Load auf
8er-Grenzen aus. `align8(315)=320`, plus 152 IDE-Eintraege ergibt 472 benoetigte
Slots. Nach dem spaeteren `(dir)`-Nachzug hatte die IDE-Lib 157 Eintraege; der
damalige Zwischenpin deckte `an` + IDE + Demo-FASL in einer Session:

```text
MAX_SYM=616
VM_DIR_MAX=496
stack_gap_bytes=1762
bank0_reserve_bytes=312
```

Nach diesem Cap-Fix:

```lisp
(+ 20 22)                                                => 42
(compile-string "(defun a()40)(defun b()(+ (a)2))" "an") => t
(load-lib "an")                                         => t
(b)                                                      => 42
(load-lib "ide")                                        => t
(function-kind (quote compile-buffer))                  => bytecode
```

Weitere HW-Befunde nach dem ersten finalen Test:

- Ein Save in nicht vorallokierte Slots wie `tst` liefert korrekt `save failed`.
  Das MVP-D81 schreibt bewusst nur in vorhandene SEQ-Zielslots.
- Ein Save nach `work` gelang, aber der Reload scheiterte zuerst mit
  `*** vm: out of memory`, weil die Lisp-Readerseite die ganze gepaddete 8-KB-
  SEQ-Kette vor dem Trimmen in Cons-Zellen las.
- Nach der effektiven Laengenmessung in `lib/ide-disk.lisp` wird ein gepaddeter
  Save-Slot erst ohne Cons-Zellen gescannt und dann nur bis zur Nutzlaenge
  materialisiert.
- Die auf 177 Eintraege gewachsene `ide`-Lib machte `VM_DIR_MAX=496` zu knapp:
  Boot `315 -> align8=320`, plus 177 IDE-Eintraege ergibt 497. Der aktuelle
  Pin `VM_DIR_MAX=512` deckt danach `align8(497)=504` plus 8 freie Slots ab.
- Mit `MAX_SYM=640`, aber altem 8-KB-Namepool scheiterte der Demo-Compile auf
  HW bei `symbol-count=616/640` mit `too many symbols`; der aktuelle Pin nutzt
  deshalb `NAMEPOOL=12288`.

Finaler Retest nach gepaddetem-Slot-Fix und finalem Cap-/Namepool-Pin:

```lisp
(load-lib "ide")                         => t
(symbol-count)                           => 613
(symbol-max)                             => 640
(load-file-to-buffer "demo" "demo")      => t
(save-buffer-to "work" "demo")           => t
(load-file-to-buffer "work" "copy")      => t
(length (ide-buffer-lines
         (%ide-resume-buffer "copy")))   => 30
(compile-buffer "fasl0" "demo")          => t
(demo-numbers-run)                       => 42
(edit)                                   => IDE, "-- copy -- 617/640"
```

Artefakte: JTAG-Screenshots/Textdumps
`build/hw/workbench-namepool12k-*.png` bzw. `.ansi.txt`. Kein `m65 -F`; Deploy
erfolgte direkt per `mega65_ftp`/`etherload`.

## Nachtrag 2026-07-09

Die obigen Werte sind der damalige 640er-Pin. Der aktuelle Workbench-Pin nach
Editor-UX-Nachzug und HW-Retest ist:

```text
NAMEPOOL=9568
MAX_SYM=720
SYMPOOL_EXT_OFF=0xc9c0
VM_DIR_MAX=552
prg_file_end=0xc04b
stack_gap_bytes=1724
bank0_reserve_bytes=274
```

`make hw-workbench-ux-smoke` ist damit auf echter HW gruen, inklusive
M-x-Pilot (`C-x x` -> `"M-x {find-file}"` im Textscreen), mehrzeiliger
Region/Kill/Copy/Yank, Search/Goto/Repeat und einer separaten frischen
`eval-buffer`-Session. Die Ursachen der
zwischenzeitlichen Ausfaelle waren zusaetzlich zum Symbol-Headroom ein zu
kleines Bank-5-Codefenster fuer die ladbare IDE-Lib und ein zu kleines
Bank-4-Disk-Scratch-Dateifenster. Aktuelles Disk-Fenster:
`DISK_EXT_FILE_MAX=0x9300`, Disk-Scratch ab Bank-4-Offset `$6c00`.
Der 9248er Namepool war nach dem `eval-buffer`-Nachzug ebenfalls zu knapp:
`load-lib "ide"` lief live in `too many symbols`. Der aktuelle Gate prueft
deshalb den kombinierten Stdlib+IDE-Lib-Bedarf:
`runtime_symbols=690/720`, `runtime_namepool=9316/9568`,
`ext_code_headroom=780`.

## Nachtrag 2026-07-09: M4 Directory-Write-Smoke

`make hw-workbench-dir-write-smoke` ist auf echter MEGA65-HW gruen. Ablauf:
Wegwerf-D81 `L65M4.D81` hochladen, Mini-PRG schreibt
`tests/disk/m4-dir-source.lisp` als T45/S8 -> T45/S9, aktualisiert die BAM und
schreibt zuletzt den freien Directory-Slot T40/S4 Entry 1 als `M4SRC`. Danach
wird das D81 zurueckgeholt und hostseitig exakt diff-geprueft.

Live-Ergebnisse:

```text
dir write pass 11/11
d81-dir-write-diff: PASS name=m4src T45/S8->S9 dir@0x61c20 len=276 count@0x61a28 32->30 bitmap@0x61a2a 0xff->0xfc
(load "m4src") => "m4-load-ok"
(m4-dir-run)   => 767
```

Wichtig: Das Oracle nutzt bewusst normales `(load "m4src")`, nicht
`%disk-load-file`, damit der regulaere Directory-Walk auf einer neu angelegten
Datei mitgeprueft ist. Der Harness hat danach die aktuelle Workbench wieder
deployed; ein Nach-Restore-Screenshot zeigte `lisp65>`.

## Minibuffer-Cancel-Retest

Nach Commit `d7bd58c` wurde der Workbench-Kandidat erneut per Etherload
deployed, ohne `m65 -F`. Ziel: verifizieren, dass der Minibuffer abbrechbar
ist, ohne die IDE zu verlassen.

Der m65-`virttype`-Pfad kann rohe Control-Chords/ESC nicht verlaesslich als
MEGA65-Tastaturereignis injizieren. Deshalb wurde der Runtime-Pfad auf echter HW
per REPL-Evaluation geprueft: Minibuffer-State erzeugen und `ide-step` mit den
normalisierten Key-Events ausfuehren.

```lisp
(setq ms (%ide-mini-start s (quote f) "" "" "" nil))      => state mit 1005
(ide-state-message (ide-step ms (list (quote key) 27 nil))) => "cancelled"
(symbol-value (quote %ide-mini))                            => nil

(setq ms (%ide-mini-start s (quote f) "" "" "" nil))      => state mit 1005
(ide-state-message (ide-step ms (list (quote key) 7 nil)))  => "cancelled"
(symbol-value (quote %ide-mini))                            => nil

(%ide-quit-key-p (list (quote key) 27 nil))                 => t
```

Ergebnis: `ESC` und `C-g` brechen den Minibuffer-State ab und raeumen
`%ide-mini`; `ESC` bleibt ausserhalb des Minibuffers weiterhin ein IDE-Quit.
Artefakte: `build/hw/minibuffer-cancel-*.png` bzw. `.ansi.txt`.

## IDE-UX-Retest nach `ca4669d`

Commit `ca4669d` wurde per `scripts/hw-smoke-vm-stdlib.sh --no-build` als
aktueller Ship-Kandidat deployed:

```text
PRG: build/ship/lisp65-mvp-workbench.prg
D81: build/ship/lisp65-mvp-workbench.d81 als L65WB.D81
Blob: build/bytecode/stdlib-p0.ext.bin bei $050000
```

Es wurde kein `m65 -F` verwendet. Der Deploy lief direkt ueber
`mega65_ftp`/`etherload`; der Boot-Screenshot zeigte den erwarteten
`lisp65>`-Prompt.

JTAG-REPL-Ergebnis:

```lisp
(+ 20 22)                              => 42
(load-lib "ide")                       => t
(load-file-to-buffer "demo" "demo")    => t
(save-buffer-to "noslot" "demo")       => nil
(ide-error)                            => "slot missing"
```

Die neuen IDE-UX-Pfade wurden wie beim Minibuffer-Cancel-Retest ueber
normalisierte `ide-step`-Events geprueft, weil `m65 --vtype` rohe Control-Chords
nicht verlaesslich als MEGA65-Tastenereignisse injiziert:

```lisp
(setq s (ide-make-state (ide-make-buffer "demo" (list ""))))  => state
(setq s1 (ide-step s (list (quote key) 24 nil)))              => C-x prefix
(setq s2 (ide-step s1 (list (quote key) 6 nil)))              => C-x C-f
(%ide-mini-status-line)                                       => "Find file: [demo]"

(setq dx (ide-step s (list (quote key) 24 nil)))              => C-x prefix
(setq dd (ide-step dx (list (quote key) 4 nil)))              => C-x C-d
(ide-buffer-name (ide-state-buffer dd))                       => "*directory*"

(%ide-store-buffer (ide-make-buffer "a" (list "aa")))         => t
(%ide-store-buffer (ide-make-buffer "b" (list "bb")))         => t
(setq bs (ide-make-state (%ide-resume-buffer "b")))           => state
(setq bx (ide-step bs (list (quote key) 24 nil)))             => C-x prefix
(setq bm (ide-step bx (list (quote key) 2 nil)))              => C-x C-b
(%ide-mini-status-line)                                       => "Buffer: [a]"
```

Hinweis: Der ASCII-Screenshot rendert die eckigen Klammer-Glyphen als
PETSCII-nahe `{...}`-Zeichen; das ist ein Screenshot-/Charset-Artefakt, nicht
der Lisp-String-Inhalt. Artefakte:
`build/hw/workbench-ux-boot-ca4669d.*`,
`build/hw/workbench-ux-disk-ca4669d.*`,
`build/hw/workbench-ux-events-ca4669d.*`,
`build/hw/workbench-ux-dir-ca4669d.*`,
`build/hw/workbench-ux-buffer-ca4669d.*`.

## Editor-Compile-UX-Retest

Der erste `C-x C-k`-Implementierungsversuch war Host-gruen, aber HW-rot:
`%ide-command-action` hatte 27 Literale. Bei `VM_CODEBUF=56` braucht der
Funktionskopf `7 + 2*27 + 3 = 64` Bytes, weshalb die Geraete-VM beim
`C-x C-k`-Eintritt sauber mit `*** vm: bad bytecode` abbrach.

Fix: Dispatch entflechtet in `%ide-switch-key` und `%ide-compile-key`; danach
hat `%ide-command-action` 18 Literale. Das Workbench-Disk-Lib-Budget-Gate prueft
nun auch den Codepuffer fuer on-demand geladene Disk-Lib-Bytecode-Objekte:

```text
workbench-disk-lib-budget: PASS resident=315 start=320 disk_lib=182
load_used=502 post_align=504 cap=512 headroom=10 post_headroom=8
codebuf=56 codebuf_required=48 codebuf_headroom=8 codebuf_worst=ide-apply-command
```

Retest auf echter HW, ohne `m65 -F`, deployed per `scripts/hw-smoke-vm-stdlib.sh
--no-build`. `m65 --vtype` kann rohe Control-Chords weiterhin nicht direkt
injizieren; deshalb wurde der Editor-Keypfad wie oben ueber normalisierte
`ide-step`-Events ausgefuehrt:

```lisp
(load-lib "ide")                                             => t
(setq cb (ide-make-buffer "demo2"
          (list "(defun cxdemo () 42)")))                    => buffer
(setq cs (ide-make-state cb))                                => state
(setq cx (ide-step cs (list (quote key) 24 nil)))            => C-x prefix
(setq ck (ide-step cx (list (quote key) 11 nil)))            => C-x C-k
(%ide-mini-status-line)                                      => "Compile to: [fasl0]"
(setq cr (ide-step ck (list (quote key) 13 nil)))            => state
(ide-state-message cr)                                       => "compiled"
(cxdemo)                                                     => 42
```

Hinweis: Der ASCII-Screenshot rendert `[fasl0]` wieder als `{fasl0}`. Nach dem
Terminologie-Pin in `docs/ide-api-terminology.md` heisst der aktuelle UI-Prompt
`Compile+load:`; der HW-Retest oben ist der historische Befund vor dieser
Textaenderung. Artefakt: `build/hw/workbench-compile-ux-cxck-fixed.*`.

## TAB-Minibuffer-HW-Retest

Stand: 2026-07-09, Commit `2bb7f07`. Deployment direkt per
`scripts/hw-smoke-vm-stdlib.sh --no-build --ip fe80::500c:34ff:fe76:a540%enp35s0`;
kein `m65 -F`. Vor dem Deploy war das lokale Gate gruen:

```text
workbench-disk-lib-budget: PASS resident=319 start=320 disk_lib=184
load_used=504 post_align=504 cap=512 headroom=8 post_headroom=8
codebuf=56 codebuf_required=48 codebuf_headroom=8 codebuf_worst=ide-apply-command
```

Basis-HW-Check per JTAG-REPL:

```lisp
(+ 20 22)        => 42
(load-lib "ide") => t
```

Der `m65 -T`-Pfad sendet selbst RETURN; ein zusaetzlich uebergebenes `\n`
wird als Text mitgetippt und kann die REPL-Eingabe verfremden. Die belastbaren
TAB-Pruefungen wurden deshalb ohne angehaengtes `\n` und wieder ueber
normalisierte `ide-step`-Events ausgefuehrt:

```lisp
(setq s (ide-make-state (ide-make-buffer "scratch" (list "")))) => state
(setq s1 (ide-step s (list (quote key) 24 nil)))                => C-x prefix
(setq s2 (ide-step s1 (list (quote key) 6 nil)))                => C-x C-f
(setq s3 (ide-step s2 (list (quote key) 9 nil)))                => TAB
(symbol-value (quote %ide-mini))
=> (find-file "Find file: " "IDE" "scratch"
              ("IDE" "AN" "WORK" "OUT" "FASL0" "FASL1" "FASL2" "DEMO" "TMP"))

(%ide-store-buffer (ide-make-buffer "a" (list "aa")))           => t
(%ide-store-buffer (ide-make-buffer "b" (list "bb")))           => t
(setq bs (ide-make-state (%ide-resume-buffer "b")))             => state
(setq bx (ide-step bs (list (quote key) 24 nil)))               => C-x prefix
(setq bm (ide-step bx (list (quote key) 2 nil)))                => C-x C-b
(setq bt (ide-step bm (list (quote key) 9 nil)))                => TAB
(symbol-value (quote %ide-mini))
=> (switch-buffer "Buffer: " "b" "a" ("b" "a"))
```

Damit ist der aktuelle TAB-Pfad auf echter Hardware smoke-geprueft. Artefakte:
`build/hw/workbench-tab-boot.*`, `build/hw/workbench-tab-load-ide.*`,
`build/hw/workbench-tab-cxf-tab.*`, `build/hw/workbench-tab-cxb-tab.*`.

## Automatisierter Workbench-UX-HW-Smoke

Stand: 2026-07-09. Der manuelle TAB-/Directory-/Buffer-Retest ist jetzt als
`scripts/hw-workbench-ux-smoke.sh` reproduzierbar. Das Script deployt die
aktuelle MVP-Workbench ueber `scripts/hw-smoke-vm-stdlib.sh` und prueft danach
per sicherem JTAG-REPL-Helper:

- Core-REPL + `(load-lib "ide")` + `(function-kind 'compile-buffer)` => Marker
  `bytecode`.
- `C-x C-d` ueber normalisierte `ide-step`-Events => Marker `"*directory*"`.
- RETURN auf einer `*directory*`-Zeile => Marker `("demo" "loaded")`.
- `C-x C-f` + `TAB` => Marker `(find-file "Find file: " "IDE" ...`.
- `C-x C-b` + `TAB` => Marker `(switch-buffer "Buffer: " "b" "a" ...`.

Live-Lauf:

```sh
scripts/hw-workbench-ux-smoke.sh \
  --no-build \
  --ip 'fe80::500c:34ff:fe76:a540%enp35s0' \
  --prefix hw-workbench-ux-live
```

Ergebnis des letzten Live-Laufs (`hw-workbench-ux-20260709c`, 2026-07-09):
alle fuenf Phasen PASS, kein `m65 -F`. Der Lauf verwendete:

```sh
scripts/hw-workbench-ux-smoke.sh \
  --no-build \
  --ip 'fe80::500c:34ff:fe76:a540%enp35s0' \
  --prefix hw-workbench-ux-20260709c \
  --form-wait 5
```

Aktueller Live-Retest am 2026-07-09 mit `make hw-workbench-ux-smoke`:
alle automatisierten Phasen PASS, inklusive FASL-Open/Save-Guards,
Navigation/Editierpfade, Minibuffer-History, `mini-edit`/DEL-Backspace
(`"d"`), Search/Goto/Repeat und separater frischer zweiter Etherload-Session
fuer `M-x eval-buffer` mit Marker `("evaluated" 42)`. Auch dieser Lauf
verwendete keinen harten JTAG-Reset (`m65 -F`).

Harness-Lektionen: `directory-open` nutzt lowercase `"demo"` und stille
`progn ... nil`-Setup-Formen, weil lange/uppercase JTAG-Tastatureingaben und
grosse gedruckte Buffer-Zustaende den Markercheck stoeren koennen. `buffer-tab`
setzt vor dem Test `*ide-buffers*` zurueck, damit ein zuvor geladener
Directory-Open-Buffer den erwarteten Buffer-Zyklus nicht verschiebt.

Ein erster ungetakteter Harness-Versuch tippte bereits waehrend des Boots bzw.
waehrend `load-lib` noch arbeitete und erzeugte nur `lisp65> load-` im
Screenshot. Die finale Version wartet deshalb nach Etherload (`--boot-wait`,
default 3s) und zwischen REPL-Formen (`--form-wait`, default 3s). Artefakte:
`build/hw/hw-workbench-ux-live-core.*`,
`build/hw/hw-workbench-ux-live-directory.*`,
`build/hw/hw-workbench-ux-live-directory-open.*`,
`build/hw/hw-workbench-ux-live-find-tab.*`,
`build/hw/hw-workbench-ux-live-buffer-tab.*`.

Aktuelle Artefakte:
`build/hw/hw-workbench-ux-20260709c-core.*`,
`build/hw/hw-workbench-ux-20260709c-directory.*`,
`build/hw/hw-workbench-ux-20260709c-directory-open.*`,
`build/hw/hw-workbench-ux-20260709c-find-tab.*`,
`build/hw/hw-workbench-ux-20260709c-buffer-tab.*`.

## Automatisierter Workbench-BAM-Read-HW-Smoke

Stand: 2026-07-09. `scripts/hw-workbench-bam-read-smoke.sh` deployt die
aktuelle MVP-Workbench per Etherload, nutzt keinen harten JTAG-Reset und liest
danach die 1581-BAM-Sektoren der gemounteten Workbench-D81 read-only ueber die
Lisp-Disk-Prims.

Live-Lauf mit:

```sh
make hw-workbench-bam-read-smoke
```

Ergebnis auf echter MEGA65-HW:

- `(+ 20 22)` => Marker `42`
- T40/S1 via `%disk-read-sector`/`%disk-byte` => Marker `(t 40 2 40 35)`
- T40/S2 via `%disk-read-sector`/`%disk-byte` => Marker `(t 0 255 0 32)`

Damit ist der Host-BAM-Pin der Workbench-D81 auch ueber den echten
F011-Lesepfad bestaetigt. Artefakte:
`build/hw/hw-workbench-bam-read-core-arith.*`,
`build/hw/hw-workbench-bam-read-bam-sector-1.*`,
`build/hw/hw-workbench-bam-read-bam-sector-2.*`.

## Automatisierter Workbench-BAM-Alloc-HW-Smoke

Stand: 2026-07-09. `scripts/hw-workbench-bam-alloc-smoke.sh` ist der erste
destruktive Workbench-D81-Smoke fuer 1581-BAM-Metadaten. Der Test arbeitet
bewusst nur auf einer Wegwerf-Kopie der Ship-D81:
`build/hw/workbench-m2-before.d81` wird als `L65M2.D81` auf die SD-Karte
geladen, danach schreibt ein dediziertes Mini-PRG T45/S8 in der BAM auf belegt,
und das zurueckgeholte Image wird am Host gegen die Ausgangskopie verglichen.

Live-Lauf mit:

```sh
make hw-workbench-bam-alloc-smoke
```

Ergebnis auf echter MEGA65-HW:

- sichtbarer Marker: `bam alloc pass 4/4`
- Host-Differ: `d81-bam-alloc-diff: PASS T45/S8`
- erlaubter D81-Diff exakt:
  `0x61a28 32->31` und `0x61a2a 0xff->0xfe`

Der Harness nutzt fuer den Schreibteil kein JTAG-getipptes Lisp, weil der
virtuelle Tastaturpfad bei laengeren Formen Zeichen verlieren kann. Der
Schreibpfad selbst ist dadurch reproduzierbar: F011 liest T40/S2, patched nur
das Count-/Bitmap-Paar fuer T45/S8, schreibt den BAM-Sektor zurueck und liest
ihn zur Verifikation erneut. `make check` enthaelt nur den Dry-Run und den
Host-Differ-Selftest, keinen Live-Hardware-Schreibtest.

Nachbeobachtung: Der fachliche M2-Test war durch Screenshot und Host-D81-Diff
korrekt gruen, aber der `mega65_ftp get`-Readback liess die Maschine danach in
BASIC stehen. Der Harness restauriert ab dem Nachzug standardmaessig wieder die
aktuelle Workbench; `--no-restore` ist nur fuer explizite Diagnose-Endzustaende.

## Automatisierter Workbench-Chain-Write-HW-Smoke

Stand: 2026-07-09. `scripts/hw-workbench-chain-write-smoke.sh` ist der M3-Pin
fuer eine zweisektorige Quellkette ohne Directory-Eintrag. Der Test arbeitet nur
auf einer Wegwerf-Kopie der Ship-D81: `build/hw/workbench-m3-before.d81` wird
als `L65M3.D81` auf die SD-Karte geladen, danach schreibt ein dediziertes
Mini-PRG die Fixture `tests/disk/m3-chain-source.lisp` nach T45/S8 -> T45/S9
und markiert beide Sektoren in der BAM.

Live-Lauf mit:

```sh
make hw-workbench-chain-write-smoke
```

Ergebnis auf echter MEGA65-HW:

- sichtbarer Marker: `chain write pass 7/7`
- Host-Differ: `d81-chain-write-diff: PASS T45/S8->S9 len=275`
- erlaubter D81-Diff: BAM `0x61a28 32->30`, `0x61a2a 0xff->0xfc`,
  plus exakt die beiden Daten-Sektoren T45/S8 und T45/S9
- Workbench-Oracle gegen dieselbe Wegwerf-D81:
  `(%disk-load-file 45 8)` => `"m3-load-ok"`, `(m3-chain-run)` => `737`

Der Harness restauriert danach wieder die normale Workbench; ein Nachlauf-
Screenshot bestaetigte `lisp65>`. `make check` enthaelt nur den Dry-Run und den
Host-Differ-Selftest, keinen Live-Hardware-Schreibtest.

## Konsequenz

Nachzug: `mvp-ship` ist auf den Workbench-Kandidaten umgezogen. Das Ship-Paket
enthaelt PRG, externes Stdlib-Blob und D81 mit `ide` plus vorallokierten
Compile-Slots. Verbleibende Follow-ups sind Slot-Fehler-UX,
REPL-Mehrzeilenfortsetzung und Beobachtung der `LISP65_SYMFN_EXT`-Performance.
