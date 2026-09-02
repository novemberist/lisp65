# Speicherbudget-Strategie (Bank 0) — dauerhaft Luft schaffen

Stand: 2026-07-03 (Claude). Grundlage: vermessener Produkt-Build
`build/lisp65-mega65-vm-stdlib.prg.elf`. Motiv: Wir reißen fast jede Session die
Bank-0-Wand, mit langen Debug-Nachläufen. Dieses Papier hält die Analyse + den
beschlossenen Dreifach-Hebel (A/B/E) fest.

## Diagnose (Zahlen, nicht Bauchgefühl)

Bank 0 nutzbar `$2001–$D000` = **45055 B (44 KB)**:

| Bereich | Größe | Anteil |
| --- | --- | --- |
| Code (.text+.data) | 37,9 KB | **86 %** |
| Datenstrukturen (BSS) | 4,6 KB | 10 % |
| Stack-Lücke | 1472 B | — |
| **echte Reserve** (Gap − C-Stack-Bedarf ~1338) | **~134 B** | ~0,3 % |

**.text ist die Wand**, nicht BSS/Heap. Eine neue C-Primitive kostet 200–800 B
`.text` → bei ~134 B Reserve reißt fast jedes C-Feature das Budget. Die
Budget-Kopplung (MAX_SYM/VM_DIR_MAX/GC_ROOTS/VM_CODEBUF/Stack-Gap) ist nur das
Symptom; Ursache ist der zu 86 % volle residente Kern.

.text-Fresser (größte): `vm_run` 6,6 KB · `apply` 4,0 · `eval_env` 3,2 ·
`vm_callprim` 2,9 = **16,7 KB heiße Schleife (unvermeidbar resident)**. Dazu
Boot-Code `eval_init` 1,3 · `vm_load_embedded_stdlib` 1,2 · `md_lit_node` 1,4 =
**~3,9 KB, die nur EINMAL beim Boot laufen** und danach resident totliegen.

BSS-Fresser: `symval/symfn/nameoff` je 664 B (=2 KB, MAX_SYM=332) ·
`dir_off/len/bank` (~1,2 KB, VM_DIR_MAX=244) · `marks` 392 · `heap` 300 (60 Zellen)
· `gc_rootstack` 272 · `repl.buf` 178. Bereits in EXT: Stdlib-Blob (Bank 5),
Heap-Überlauf (Bank 4, 3072 Zellen), Symbol-Namepool (Bank 5).

## Der beschlossene Hebel: A + B + E

### A. Boot-Code-Overlay — ~3,9 KB (Lane K+T) → FEASIBILITY-SPIKE GEMACHT: aufgeschoben
**Spike-Befund (Claude, 2026-07-03): der saubere Overlay-Weg ist BLOCKIERT, das
Low-Hanging-Fruit ist schon geerntet.** Konkret:
- Die Boot-DATEN (Symbolnamen, Metadaten) sind **bereits NICHT resident** — sie
  liegen im EXT-Blob (L65M-Trailer, per DMA gelesen). `LISP65_STDLIB_BOOTDATA` ist
  im Produkt leer; `.lisp65_boot`-Overlay ist hinter `LISP65_STDLIB_BOOT_OVERLAY`
  gegatet und im Produkt AUS (M65VMSTDLIB_LDFLAGS leer). Der frühere Overlay-Versuch
  wurde aufgegeben (→ EXT), weil geladener Inhalt in der Overlay-Region (hoch, nach
  `.noinit`) über **$C000** läge und die etherload-Invariante `prg_file_end < $C000`
  bricht. Genau diese Wand killt auch Boot-CODE im Overlay.
- Was resident BLEIBT, ist Boot-CODE (`md_lit_node` 1,4 KB, `vm_load_embedded_stdlib`
  1,2 KB, `eval_init` 1,3 KB): liest/staged den EXT-Blob, läuft 1×. Reclaim
  erfordert **manuelles Freelist-Einfädeln** der Boot-Code-RAM NACH dem Boot (wie
  `gc_freeze_boot`) + eine DRITTE Heap-Region im HEISSEN `cell_a/b/type`-Accessor
  (Bank-0-Direktzugriff neben hot-Array + EXT-DMA). BSS-Zeroing verhindert den
  sauberen Heap/Code-Overlap. → **intricat, heißer Pfad, HW-Crash-Risiko.**
- **Verdikt: AUFGESCHOBEN.** Lohnt ~3,9 KB, aber als eigenes, gut getestetes
  Sub-Projekt mit Appetit auf Hot-Path-Arbeit — NICHT als Nebenbei-Fix. Erst
  angehen, wenn B nicht mehr reicht (echter neuer Primitiv-Bedarf sprengt Bank 0).

### B. Kern einfrieren — Features als Bytecode-Lisp, nicht C (Trajektorie)
Kosten pro Feature: C-Primitive ~500 B `.text` **in Bank 0** vs. Bytecode-Lisp-Fn
~5 B Directory + ~6 B Symbol **in BSS**, Code im **EXT-Blob (Bank 4/5)**. → **~50×
effizienter pro Feature.** Die Architektur trägt das bereits (Stdlib + IDE SIND
Bytecode-Lisp im EXT-Blob). **Regel:** Neue Features werden Bytecode-Lisp; der
residente C-Kern wächst NUR für echte Primitive (was Lisp nicht kann: DMA, Screen,
GC, Reader-Kern). Ohne diese Disziplin frisst das nächste Feature den A-Gewinn
sofort. Siehe Memory [[scope-discipline]].

Rest-Kopplung: auch Bytecode-Features wachsen die BSS-Arrays (Directory/Symbole)
minimal (~11 B/Fn). Erst wenn diese Arrays Bank 0 sprengen, wird Hebel C nötig.

### E. Headroom-Ziel + Budget-Dashboard (Lane T, Prozess)
Die G1–G5-Gates fangen Wände seit 2026-07-03 beim `make check` ab (das
Whack-a-Mole DAVOR war der Debug-Schmerz — strukturell gelöst). Fehlt: (1) ein
explizites **Reserve-Ziel** (Vorschlag: **≥1 KB Bank 0 frei** nach A), damit wir
nicht am 134-B-Rand operieren; (2) eine Zeile im Footprint-Report „Bank-0 frei +
Kopplungs-Aufschlüsselung", damit ein reißendes Gate sagt „X B drüber, hier die
Posten" statt Geräte-Crash.

Codex-Follow-up (2026-07-04): `make mvp-vm-stdlib-footprint-report` schreibt jetzt
`bank0_dashboard`, `bank0_text_data_bytes`, `bank0_bss_bytes`,
`bank0_reserve_bytes`, `bank0_reserve_target_bytes` und
`bank0_coupling_summary`. Das 1-KB-Ziel ist sichtbar (`target_status`), aber der
harte Zusatzreserve-Gate lag bis zum Dir-Kompaktierungsgewinn bei
`M65VMSTDLIB_MIN_BANK0_RESERVE=0`; der Schalter auf 1024 ist damit vorbereitet,
ohne den heutigen Produkt-Build absichtlich rot zu machen.

Codex-Cap-Follow-up (2026-07-04): Nach dem 1a-Hygiene-Reclaim wurden die taktischen
Produkt-Caps wieder angehoben und gegen das Footprint-Gate getunt. `MAX_SYM=330` und
`VM_DIR_MAX=246` liefern 19 Symbol- und 16 Directory-Slots Headroom bei
`bank0_reserve_bytes=24` (`stack_gap=1474/1450`). Der getestete Zielpunkt `332/248`
war mit 2 B Reserve zu knapp.

Codex-Reserve-Follow-up (2026-07-04): Nach Claudes sicherer Dir-Kompaktierung
(`dir_bank[]`→Einzelwert, `dir_len` `uint16`→`uint8`) wurde die Luft fuer das
Rule-B-LOAD-Projekt gehalten. Nach `symbol-max`/`number->string` und dem IDE-Modeline-
Budget liegt der aktuelle Default bei `VM_DIR_MAX=242`, `REPL_BUF_MAX=112`,
`HIST_MAX=16`, `GC_ROOTS=128`, `stack_gap=2096/1450`, `bank0_reserve_bytes=646`.
Das harte Gate steht auf `M65VMSTDLIB_MIN_BANK0_RESERVE=640` (unter dem 1-KB-Ziel,
aber hoch genug, um versehentliche Cap-/C-Wachstums-Ausgaben vor LOAD zu fangen).

### F. Ladbare Libraries von Disk — die strukturelle Erweiterung von B (NEU 2026-07-04)
**Ermöglicht durch den HW-bewiesenen `(load)`-Leseweg** (siehe
`docs/mega65-file-io-research.md`, Memory [[native-load-solved]]). B zieht Features aus
Bank 0 in den **gebündelten** EXT-Blob (ships mit dem PRG, beim Boot ins EXT-RAM). F geht
einen Schritt weiter: optionale Features werden **Dateien auf Disk**, geladen **on demand**
(`(load "graphics")`). 
- **Gewinn ggü. B:** Was nicht geladen ist, kostet **NICHTS** — nicht im PRG, nicht im
  EXT-RAM, nicht in den BSS-Directory/Symbol-Arrays. Der gebündelte Blob wächst nicht mehr
  mit jedem optionalen Feature; die Gesamt-Library-Größe ist praktisch unbegrenzt (Disk ≫
  EXT-RAM). „Pay-per-use" statt „pay-for-all-bundled". Das schiebt die in B genannte
  Rest-Kopplung (Directory/Symbol-Arrays sprengen irgendwann Bank 0 → Hebel C) nach hinten:
  nur GELADENE Features belegen Slots, nicht alle gebündelten.
- **Ehrliche Grenzen:** (1) F braucht die **Produkt-Integration von LOAD** (Budget/Build,
  Lane T) — bis LOAD in einem lauffähigen Produkt verdrahtet ist, ist F nicht demonstrierbar.
  (2) GELADENE Features belegen weiterhin **permanente** Symbol-/Directory-Slots
  (Symbole werden nie GC't, `MAX_SYM`-Cap — siehe [[lisp65-symbol-constraints]]); F umgeht das
  nicht, es zahlt nur pro geladenem statt pro gebündeltem Feature. (3) Laden = Disk-Read +
  Parse/Eval → langsamer als resident; gut für On-Demand, nicht für heiße Pfade. (4) Braucht
  eine Library-Konvention (Namen, Abhängigkeiten, Quelltext- vs. Bytecode-Form — Letzteres ist
  die Brücke zum Bytecode-v1-Nordstern: vorkompilierten Bytecode statt Quelltext laden).
- **Verhältnis zu B:** F ersetzt B nicht, es ergänzt es. Kern-nahe/häufige Stdlib bleibt
  gebündelt (schneller Boot); optionale/große/selten genutzte Libs wandern auf Disk.

**Weitere LOAD-Türen (Capability, nicht Budget — hier nur als Zeiger):** persistente
Nutzerprogramme (braucht SAVE, vertagt), Stdlib komplett von Disk (Flexibilität/Größe),
Editor/IDE-Öffnen/Speichern. Vollständig in Memory [[native-load-solved]].

## Zurückgestellt (nur im Notfall)
- **C. Symbol/Directory-Arrays → EXT (~3,2 KB): KEIN sicherer Teil-Schnitt (Spike 2026-07-04).**
  Jedes Kandidaten-Array ist heiß: `dir_off/len/bank` via `dir_find(sym)` + Index PRO
  Bytecode-Call (vm.c:580/591); `symval`/`symfn` pro Var-/Fn-Referenz; und `nameoff` ist der
  ABSICHTLICH Bank-0-residente **DMA-freie Längen-Vorfilter** für `intern` — nach EXT verschoben
  kehrt die ~1/3-s-pro-Reader-Token-Bremse zurück (symbol.c:28-31, HW-Messung 2026-07-02). Ein
  Write-Back-Cache für die heißen Arrays ist möglich, frisst aber .text + Rest-DMA-Miss-Perf →
  marginal/riskant. Fazit: C-nach-EXT bringt keinen billigen Gewinn; der Code ist an der
  optimierten Grenze. Hohes Risiko + Perf-Kosten bestätigt. Siehe [[lisp65-symbol-constraints]].
  - **✅ ABER: Dir-KOMPAKTIERUNG statt EXT = sicherer Teil-Gewinn (Claude, `298c012`).** Nicht
    nach EXT verschieben, sondern in Bank 0 schrumpfen: `dir_bank[]` → Einzelwert `dir_bank0`
    (Blob liegt in EINER EXT-Bank, ~20 KB < 64 KB) und `dir_len` `uint16`→`uint8` (größtes
    Code-Objekt 234 B < 256). Guards in `vm_dir_add` (Bank-Wechsel / >255 B → laut abbrechen).
    **-616 B Bank-0 gemessen (stack_gap 1578→2194), KEIN Hot-Path-DMA, `make check` grün +
    HW-VALIDIERT (mvp-vm-stdlib-hw-selftest 11/11 grün am Geraet 2026-07-04).** Reserve nach
    Codex-Caps + Kompaktierung = **658 B**. Das ist
    der eine sichere Schnitt, den der EXT-Weg verdeckt hatte. (`dir_off` bleibt 16-bit/Bank-0.)
- **D. mark-Bitmap → EXT (~400 B):** GC-DMA-Kosten, geringer Gewinn.
- **Shrink vm_run/apply .text:** heiß + handoptimiert, abnehmender Ertrag, Risiko.

## Reihenfolge (REVIDIERT nach A-Spike)
**B ist der eigentliche Hebel gegen die wiederkehrenden Wände** — die Wände kommen
vom `.text`-WACHSTUM (neue C-Features). Hält die Bytecode-Disziplin, wächst `.text`
nicht mehr → keine neuen Wände, auch OHNE den 4-KB-Reclaim. A ist die Reserve für
den Fall, dass wir doch einen echten neuen Primitiv brauchen.
1. **B** (Regel gilt ab sofort) — stoppt das Bluten. Wichtigster Hebel.
2. **E** (Headroom-Ziel + Dashboard, Lane T) — Sichtbarkeit, fängt Wände beim Gate.
3. **A** — AUFGESCHOBEN mit dokumentiertem Befund (s. o.); als Sub-Projekt, wenn nötig.
4. **F** — mittelfristig, ERST nach der LOAD-Produkt-Integration; dann strukturell der
   stärkste Hebel (optionale Features kosten null, bis geladen). Reihenfolge-Abhängigkeit:
   LOAD-Integration (Lane T) → Library-Konvention → optionale Libs von Disk.
