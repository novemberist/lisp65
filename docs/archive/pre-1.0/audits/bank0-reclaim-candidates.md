# Bank-0 Reclaim Candidates

Stand: 2026-07-09, Abschlussnachtrag 2026-07-11. Ziel: konkrete Kandidaten fuer strukturellen Reclaim sammeln,
damit `STACK_GUARD` und die AP4-Mindestreserven nicht weiter gegen ein
taktisches Reservefenster gebaut werden.

Die Rankings und Einzelmessungen unten sind historische AP4-Eingangsdaten. Der
heutige Produktpin steht im Abschnitt „AP4-Abschluss“; alte Werte duerfen nicht
als aktuelle Reserve oder als offene Arbeitsqueue zitiert werden.

## Report

Neues Target:

```sh
make bank0-reclaim-report
make bank0-lifetime-report
```

Outputs:

- `build/bytecode/bank0-reclaim-report.txt`: Groessenranking und physisch
  noch nicht gefaltete Clone-Cluster.
- `build/reports/workbench/bank0-lifetime.{json,txt}`: deterministische,
  ICF-deduplizierte Lifetime-Klassifikation gegen
  `config/bank0-lifetime-workbench.json`.

Das Target baut zuerst den aktuellen Workbench-Kandidaten ueber
`workbench-candidate-footprint-report` und wertet danach dessen natives ELF per
`llvm-size`/`llvm-nm` aus. Die Workbench-Stdlib besitzt seit AP3 einen eigenen
Namespace unter `build/bytecode/profiles/workbench/`. Der Lifetime-Selftest
gehoert zu G0, der echte Report samt Drift-Check zu G2.

## Historischer Snapshot

Quelle: `make bank0-lifetime-report` auf dem kanonischen Workbench-Pin vom
2026-07-09. Das Report-Target misst
`mvp-vm-stdlib-einsuite-core-workbench`; alte Dev-Core-Zahlen sind nur noch
Vergleichswerte.

- `prg_bytes=41096`
- `prg_file_end=0xc087`
- `bank0_text_data_bytes=41058`
- `bank0_bss_bytes=2299`
- `stack_gap_bytes=1662`
- `bank0_reserve_bytes=212`
- `NAMEPOOL=9536`, `MAX_SYM=720`, `SYMPOOL_EXT_OFF=0xc9e0`,
  `VM_DIR_MAX=552`, `GC_ROOTS=128`, `REPL_BUF_MAX=192`,
  `STR_ARENA_SIZE=0x2480`, `DISK_EXT_BASE=0x6900`,
  `DISK_EXT_FILE_MAX=0x9600`

Nachtrag Workbench-Compile-String + IDE-On-Demand: Der Kandidat ist durch
`LISP65_SYMFN_EXT` wieder gruen. Das ist ein produktbezogener MVP-Pin, kein
echter Reclaim: BSS-Druck sinkt, aber Bytecode-CALL-Aufloesung zahlt DMA, weil
kein Symfn-Cache unter das PRG-Ende-Gate passte.
Die wieder aktivierte Mini-REPL-History nutzt keinen separaten Puffer, kostet
aber trotzdem fast die komplette PRG-Ende-Reserve. Der groessere REPL-Buffer
kostet dagegen keinen PRG-Code, sondern 128 B BSS/Stack-Gap gegenueber dem
64-Byte-Pin.

## Groesste native Text-Symbole

| Symbol | Bytes ca. | Einschaetzung |
| --- | ---: | --- |
| `vm_run` | 7295 | Groesster Block und Hotpath; Reclaim hier ist wertvoll, aber riskant. |
| `apply` | 5030 | Groesser als viele Kernelmodule; pruefen, welcher Treewalk-/Bridge-Anteil im Dev-Core noch produktrelevant ist. |
| `vm_callprim` | 2450 | Direkter Kandidat fuer Dispatch-/Leaf-Diaet, gleichzeitig im Scroll-Debugpfad relevant. |
| `lcc_install_obj` | 2070 | Dev-Core-Funktionalitaet; Produkt-/Runtime-Core koennte sie auslagern oder separat bauen. |
| `read_expr_1` | 1403 | Reader bleibt fuer REPL/Load noetig; eher Runtime-Core-Schnitt als Quick-Win. |
| `md_lit_node` | 1388 | Boot-Materialisierung; guter Kandidat fuer Boot-only Overlay/Lifetime-Trennung. |
| `io_disk_lib_staged` | 1210 | Disk-Lib-Kern; Reclaim nur mit I/O-Designentscheidung. |
| `gc_collect` | 1109 | Hot und kritisch; nicht als kurzfristiger Byte-Schneider behandeln. |
| `vm_load_embedded_stdlib` | 1075 | Boot-only; zusammen mit `md_lit_node` ein plausibler Lifetime-Reclaim-Hebel. |

## Groesste BSS-Bloecke

| Symbol | Bytes | Einschaetzung |
| --- | ---: | --- |
| `symfn` | ausgelagert im Workbench-Pin | `LISP65_SYMFN_EXT` spart Bank-0-BSS und ermoeglicht aktuell `MAX_SYM=720`; Hotpath-DMA bleibt Performance-Risiko, Cache/Reclaim spaeter messen. |
| `dir_len` | 512 | 1 B pro `VM_DIR_MAX`; Cap-Senkung kollidiert mit IDE/LCC/FASL. |
| `namelen4` | 288 | Symbol-Lookup-Beschleuniger; Entfernen spart BSS, kostet vermutlich Tipp-/Lookup-Zeit. |
| `gc_rootstack` | 256 | Direktes Runtime-Budget; nicht senken. |
| `heap` | 240 | Bank-0-Hotheap; nicht fuer kurzfristigen Reclaim opfern. |

## Lifetime- und ICF-Befund

`--icf=all` faltet die frueher als Clone-Potenzial gelisteten `cell_*`-Varianten
bereits physisch. Beispielsweise liegen `cell_b`, `cell_b.107` und
`cell_b.255` an derselben Adresse und belegen zusammen nicht 285 B, sondern
einmal 95 B. Beide Reports deduplizieren deshalb nach Section, Adresse und
Groesse; der aktuelle Reclaim-Report findet keinen verbleibenden physischen
Clone-Cluster.

Der Lifetime-Report klassifiziert 75 grosse Allokationen ab 80 B ohne offene
Zuordnung. ICF-deduplizierte Summen:

| Klasse | Bytes | Bedeutung |
| --- | ---: | --- |
| `runtime-hot` | 19091 | VM, GC, Allokation, String- und Symbol-Hotpaths |
| `runtime-cold` | 5348 | I/O, Ausgabe, Directory und Runtime-Lib-Loader |
| `boot-only` | 2206 | theoretisches Reclaim-Potenzial, noch nicht freigegeben |
| `dev-only` | 9945 | nur durch expliziten Runtime-Profil-Split entfernbar |
| `bss-cap` | 2054 | kapazitaetsgetriebene Arrays, kein ehrlicher Reclaim |

Sicher boot-only sind aktuell `vm_load_embedded_stdlib` (1075 B), `eval_init`
(840 B), `defprim` (193 B) und `gc_freeze_boot` (98 B). Dagegen muessen
`md_lit_node`, `vm_lit_keep` und `vm_register_embedded` wegen des
Runtime-`load-lib`-Pfads resident bleiben.

Die vor AP4.2a isolierte `LISP65_STACK_GUARD`-Buildvariante mass 41368 PRG-Bytes,
`prg_file_end=0xc197`, `stack_gap=1392` und `bank0_reserve=-58`. Der Guard
durfte damit nicht in den damaligen Produktpin. Nach Trailer-Reclaim wird die
Guard-Variante erst zusammen mit dem Boot-Overlay neu vermessen.

Nachtrag AP4.5: Die gemeinsame Overlay-/Guard-Variante ist jetzt gruen. Sie
misst 39862 B Resident, 2245 B Overlay, 631 B Boot-Gap und 1427 B Reserve ueber
dem 1450-B-Laufzeitbudget. Der Guard verwendet den Linker-Floor
`__heap_start + 24`; der echte IDE-/VM-Bridge-/GC-/Abort-Lauf besteht ohne
Fehlalarm. Die Werte sind technisch abgenommen, aber bis zur expliziten
Produktpromotion noch kein kanonischer Ship-Pin.

## AP4-Abschluss

Der Abschlusslink verwendet `$c344` als gemeinsame Guard-Produkt-
Overlaybasis. Gemessen sind 1851 B Boot-Gap und 1811 B Post-Boot-Reserve; das
harte 1024-B-Minimum und das 1536-B-Ziel sind damit gruen. Der Attic-Katalog
belegt 38/64 Produktslots. Slot 37 installiert die residente Insel
`$1800..$1fff`; ihr dynamisch dahinter erzeugter Seed-LMA ist build-only und
kein weiterer Produktslot.

Das Inselinventar weist 1108 B unveraenderliche L65M-/Batch-Koordinatoren und
einen 260-B-Rootstack-Annex aus. 680 B bleiben eingefroren frei. Die frueher
genannten 932 B waren nur der Stand vor dem Annex und sind keine aktuelle
Reserve. HW-Math ist mit 519 B bereits in der Baseline verbraucht. Die 385 B
Primitivnamen liegen bereits in `.lisp65_boot.names`; ihre Verlagerung spart
resident exakt 0 B.

AP4 ist implementiert und das Layout eingefroren. Weitere Layoutarbeit ist
keine Fortsetzung dieses Reclaim-Plans, sondern braucht eine neue
Scope-Entscheidung. Commit `5ce25a2` ist sauber als Ship-v5 promotet; die an
Manifest-SHA
`67c5943259ed2bd3d849a33c6f7909bc16962c1c88271baf32dd36a1058085dd`
gebundene verified-only Live-G5-Matrix ist gruen. AP4 ist damit geschlossen.

## Runtime-Core-Prototyp

Der explizite, embedded-only Runtime-Core belegt bei denselben Kern-Caps wie die
Workbench 23079 PRG-Bytes und endet bei `$7a26`. Gemessen sind 20036 B
Stack-Gap und 15940 B Bank-0-Reserve. Das Link-Audit bestaetigt, dass die als
`dev-only` klassifizierten Reader-, REPL-, Eval-, Treewalk-`apply`-, lcc- und
Compilerpfade nicht im ELF liegen. Die Reserve ist damit strukturell durch den
Produktschnitt belegt, nicht durch kleinere Caps erkauft.

Der Wert ist noch kein Runtime-Exportbudget: Der Prototyp enthaelt nur drei
residente Bytecodefunktionen und ein 181-B-Image. Disk-Lib-Loader,
App-Descriptor, Paket und Cold-Boot-Abnahme werden erst nach dem
L65M-Zwei-Pass-Preflight hinzugerechnet. Der Profilpin reserviert schon jetzt
mindestens 8192 B Bank 0 und 8192 B Stack-Gap.

## Historische empfohlene Reihenfolge

Die folgende Liste dokumentiert den Weg zum AP4-Abschluss und ist keine offene
Arbeitsqueue mehr.

1. **Lifetime- und Budgetreport halten.** Neue grosse Symbole und jedes
   Bank-0-Wachstum muessen G2 sichtbar rot machen.
2. **Runtime-Trailer auf Allokatorebene reclaimed.** Der IDE-Lib-Trailer belegt
   nur noch den Load-Peak; nach erfolgreicher Registrierung bleiben 14805 B
   Code und 23396 B EXT-Headroom. Peak und Post-Commit sind getrennt gegatet.
   Offen bleibt der vollstaendige L65M-Preflight vor sichtbaren Mutationen.
3. **Boot-only-Overlay profilgebunden integrieren.** Der Loader-only-Versuch
   blieb mit 678 B Reserve rot. Die umgesetzte vollstaendige Transaktion aus
   `eval_init`, `defprim`, Stdlib-Lader und `gc_freeze_boot` erreicht dagegen
   39524 B Resident, 2257 B Overlay und 1764 B Post-Boot-Reserve. Der 955-B-
   Boot-Gap erfuellt das harte 512-B-Minimum, verfehlt den 1024-B-Zielwert aber
   um 69 B. Deshalb folgen Hardware-Watermark und Reclaim-Stress, bevor diese
   Bytes als Produktreserve gelten. Der Runtime Core kann 3144 B Boot-Code im
   eigenen flachen PRG halten und bleibt mit Dateiende `$81f2` weit unter
   seinem `$b000`-Limit.
4. **Mess-/Diagnosebuild klein halten.** `STACK_GUARD` und Watermarks bleiben
   opt-in, bis Reclaim belastbar ist.
5. **`vm_callprim`-Diaet:** Dispatch/Leafs auf geteilte Checks oder kleinere
   Spezialhelfer pruefen; besonders relevant, weil Scroll-Debug viele
   `CALLPRIM`s sieht.
6. **Runtime-Core-Profil separat definieren:** IDE/LCC/Reader/Save nicht
   alle in einem Produktprofil erzwingen, wenn echte Nutzerprogramme Platz
   brauchen.

Nicht empfohlen als schneller Hebel: `MAX_SYM`, `VM_DIR_MAX`, `GC_ROOTS`,
`HEAP_CELLS` oder `VM_CODEBUF` blind senken. Diese Caps sind mehrfach als
knappe Produktgrenzen aufgefallen. Ausnahme: ein explizit gemessener
Produktpin wie der Workbench-Compile-String-Kandidat darf Caps setzen, wenn
die Headrooms dokumentiert sind und HW-/Footprint-Gates gruen bleiben. Solche
Caps zaehlen aber nicht als Reclaim und duerfen nicht weitere Featurearbeit
finanzieren.
