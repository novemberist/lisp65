# IDE-OOM: Packed-Byte-Strings — Design-Konzept (Vier-Augen mit Codex)

---

## ✅ HW-IDE-Gate BESTANDEN (2026-07-08, echte MEGA65) — mit kritischem Fix

Der Praxistest am Gerät (`/dev/ttyUSB1`, arena-ide-Profil) ist **grün** — nach einem
kritischen HW-Fund + Fix:

- **HW-Fund:** Codex' Device-Arena lag in EXT-**Bank 6** (`$60000`) — die ist auf der
  MEGA65 **nicht bestückt** (Fast-RAM = 384 KB = Banks 0–5). Jeder Arena-Byte-Read lieferte
  `0` → alle Lisp-String-Ops brachen still: `(string->list "ide")` → `(0 0 0)`, `load-lib`
  scannte nach Namen `(0 0 0)` → `nil` → `(edit)` „undefined function: ide". Bank-6 war
  **nie auf HW verifiziert** (nur statischer Footprint-Report). Beweis: Bank-6-`memsave` =
  komplett Null, Bank-5 = echte Blob-Daten.
- **Fix (`fix(strings): Arena-Device-Backing von Bank 6 nach Bank 4`):** Device-Arena in
  die freie Bank-4-Luecke `$42000-$46BFF` (zwischen EXT-Zellen `$40000-$41FFF` und
  Disk-Scratch `$46C00`), zwei 9,5-KB-Fenster. Bank 4 ist durch den EXT-Zell-Heap als RAM
  verifiziert. Host-Arena bleibt 16 KB (ABI-Gate).
- **Verifiziert:** `(string->list "ide")` → `(105 100 101)`; `load-lib "ide"` → `t`;
  `(edit)` öffnet; **40 Zeilen getippt → `mem_oom=0`, `gc_badobj=0`, `gc_runs=537`, Editor
  lebt, kein Bildschirm-Müll** (alte char-listen-IDE crasht bei ~30). Host-Gate + Footprint
  weiter grün. Artefakte: `build/hw/arena-*.png`.
- **Bekannt (Test-Harness, KEIN IDE-Bug):** `m65 -T` tippt schneller als die on-device
  read-key/render-Schleife → verschluckte/verschmolzene Zeichen im Auto-Tipp-Test (die
  *registrierten* Zeichen sind korrekt, der Editor rendert sauber via Arena-Reads). Ein
  Mensch tippt langsam genug.

**Offen:** (1) Bank 4 teilt sich der Arena-Heap mit EXT-Zellen + Disk-Scratch — wenn
`EXT_CELLS` je über 1024 wächst oder die Arena >20 KB braucht, ist **Attic-RAM**
(`$8000000`, via Enhanced-DMA) der saubere Wachstumspfad. (2) Produktentscheid: `arena-ide`
als Default-IDE-Core?

---

## HW-IDE-Gate — Rezept (Arena-IDE-Profil `arena-ide`, no-FASL)

Nachfahrbares Gate-Rezept fuer Regressionstests am echten MEGA65. Ziel: **30–60 Zeilen echten
Lisp-Code tippen + scrollen → kein `out of memory`-Absturz (kein REPL-Fallback), keine
Bildschirmkorruption.** Braucht Gerät + mos-Toolchain (`tools/llvm-mos`) + `tools/m65tools`,
Device `/dev/ttyUSB1`. Footprint-Gate ist bereits grün (`bank0_reserve=630`).

**1. Bauen** (Arena-IDE zuletzt bauen — es regeneriert `build/bytecode/stdlib-p0.ext.bin`
aus der no-FASL-Arena-Suite):
```
make bytecode-p0-pilot-libs-artifacts
make bytecode-p0-ide-lib-d81                       # -> build/bytecode/libs/ide.d81 (IDE-Bytecode; nutzt nur string->list/list->string -> arena-kompatibel, kein FASL)
make mvp-vm-stdlib-einsuite-core-arena-ide          # -> .prg + stdlib-p0.ext.bin (Arena-Suite)
mkdir -p build/hw                                  # Ziel fuer Screenshots/Counters
```

**2. Deployen** (etherload direkt — KEIN `m65 -F` im Normalpfad; IP via Auto-Discovery):
```
# IDE-Disk-Lib auf die SD (resettet Maschine -> BASIC):
tools/m65tools/mega65_ftp -e -i <ip> -y -c "put build/bytecode/libs/ide.d81 IDE.D81"
# Core mit vorgeladenem Arena-Stdlib-Blob starten:
sh scripts/run-on-mega65.sh --mount IDE.D81 \
   --preload-bin 0x050000 build/bytecode/stdlib-p0.ext.bin --run \
   build/lisp65-mega65-vm-stdlib-einsuite-core-arena-ide.prg
```
(`run-on-mega65.sh --dry-run` zeigt die Kommandos ohne HW. IP notfalls `tools/m65tools/etherload --discover`.)

**3. Editor öffnen + testen** (⚠️ echtes `sleep`, dann EIN PNG lesen — keine schnellen
Screenshots als „Takt". `m65 -T` verschluckt Großbuchstaben → **nur lowercase tippen**.
Highlighting ist aktuell temporär aus = uniformer Render; für den OOM-Test irrelevant):
```
sleep 16                                            # Boot-Settle
tools/m65tools/m65 -l /dev/ttyUSB1 --screenshot=build/hw/arena-boot.png
tools/m65tools/m65 -l /dev/ttyUSB1 -T '(edit)~M'    # ggf. 2x (erstes wird verschluckt)
sleep 2
tools/m65tools/m65 -l /dev/ttyUSB1 --screenshot=build/hw/arena-edit-open.png   # PNG MUSS den Editor zeigen, NICHT lisp65> (sonst REPL-Falle)
# ~40 Zeilen echten geklammerten Code tippen (lowercase!), je Zeile mit ~M:
for i in $(seq 1 40); do
  tools/m65tools/m65 -l /dev/ttyUSB1 -T "(defun f$i (x) (+ x 1) (list x x x))~M"
  sleep 0.1                                        # bei verschluckten Zeichen auf 0.2 erhoehen
done
sleep 2
tools/m65tools/m65 -l /dev/ttyUSB1 --screenshot=build/hw/arena-typed40.png
# Scrollen: Cursor rauf/runter über die Fenstergrenze (Zeile 24) und zurück
```

**4. Auswerten** — zwei unabhängige Belege:
- **PNG (`arena-typed40.png`):** Der Editor ist noch da (kein `lisp65>`-Prompt = kein
  OOM-Absturz); Nicht-Leer-Glyphen im normalen Bereich (~20–40 pro Zeile-Region, NICHT
  ~1941 Vollbild-Müll); kein magenta Border.
- **Counter (definitiv):** `mem_oom` muss 0 sein:
  ```
  python3 scripts/hw-jtag-counters.py \
     --elf build/lisp65-mega65-vm-stdlib-einsuite-core-arena-ide.prg.elf \
     --device /dev/ttyUSB1
  # erwartet: mem_oom=0, gc_badobj=0 (gc_runs>0 ist normal)
  ```

**5. Gegenprobe (zeigt den Fix):** derselbe Test auf dem NICHT-Arena-Core
(`make mvp-vm-stdlib-einsuite-core`, gleicher Deploy mit dessen `.prg`/`.ext.bin`) sollte
bei ~30 Zeilen mit `*** out of memory` in die REPL fallen (`mem_oom=1`). Arena hält durch.

**PASS-Kriterium:** 40+ Zeilen getippt + gescrollt, Editor lebt, `mem_oom=0`, kein Müll —
per PNG + Counter. Dann ist der IDE-OOM-Kapazitätsfix am Gerät angekommen; danach Produkt-
entscheid, ob `arena-ide` das Default-IDE-Core ablöst.

---

**Status:** P1/P2/P3 — Codex-Review-Blocker #1–#4 abgearbeitet + host-verifiziert
(opt-in `-DLISP65_STRING_ARENA`, Default byte-identisch). Ergebnis: **~16× weniger
Zellen, Compaction + String-Semantik host-verifiziert** (s. §0). Device-taugliche
Arena-Accessoren, Footprint-Gate und HW-IDE-Gate sind fuer `arena-ide` erledigt
(Bank-4-Fix nach Bank-6-HW-Befund, s. oben). OFFEN: Produktentscheid (`arena-ide`
als Default-IDE-Core?) und spaeterer Wachstumspfad via Attic-RAM, falls Bank 4 zu klein wird.
**Autor:** Claude, 2026-07-08. **Regel:** große Architektur vor Umsetzung mit Codex
abstimmen; messen statt raten.

---

## Codex-Review-Blocker (Stand nach P1)

Codex-Review `c24dfd3` (docs/collaboration.md). Status:

- **#1 `tmp[600]`-Festpuffer (Truncation + Stream-Desync)** ✅ BEHOBEN. Streaming-API
  `str_open`/`str_putc`/`str_close` (kein Festpuffer) in `read_string`, `str_from_charlist`,
  Metadata-Boot-Literal. Bei Arena-Voll: `mem_oom` + sauberes Konsumieren bis zum Quote.
  Host-Beweis: 700-Zeichen-String → Länge 700, Folge-Form parst korrekt (kein Desync).
- **#2 `screen-write-string` nicht arena-aware** ✅ BEHOBEN (`vm.c` CALLPRIM 12 +
  `eval.c` P_SCRWRITE via `str_copy_out`).
- **#3 `eval.c` char-list-Contract** ✅ BEHOBEN: `eval-string` (String+Index-Cursor),
  `save`, `load`, `%fasl-src`, `%fasl-save` (Namen via `STR_NAME_COPY`-Makro),
  `number->string`, `symbol-name`, `string->list`/`list->string`/`string-length`/
  `string-ref` (Treewalk-Prims) — alle flag-gegabelt. Syntax-Check `-Wall -Wextra` clean
  über ein Superset aller Guards (EVAL_PRIMS+FASL+F011_WRITE+SCREEN_WRITE_STRING).
- **#4 ABI/Doku** ✅ `docs/kernel-abi.md`: `T_STR.a=len`, `T_STR.b=arena-offset`,
  `string->list` liefert unter Arena eine **frische** Liste (Gate-Check beweist es).
## Codex-P1-Review-Nachzug (2026-07-08, `a933454`)

Codex verifizierte P1 (Branch gebaut, Gate PASS, `-Wall -Wextra` clean), akzeptierte die
Blocker-Fixes, und nannte 3 Punkte + den Device-Entscheid. Alle host-verifiziert erledigt:

- **Rebase auf aktuellen `main`** ✅ (`878c1a1`; erhält Highlighting-off + Bulk-Safety-Fixes).
- **Arena-OOM ohne Compaction** ✅ BEHOBEN: `str_putc` löst bei Arena-Voll `gc_collect`
  (Compaction) aus und retryt VOR `mem_oom`. Der in-Arbeit-String ist via `str_building`
  markiert und wird bei der Compaction ZULETZT platziert (bleibt am Arena-Ende anhängbar);
  `str_from_charlist` rootet die Quellliste über die Compaction. Host-Beweis: 500 tote
  Wegwerf-Strings in 2048-B-Arena → kein OOM (109 Compactions), `keep` byte-exakt; ein
  400-Byte-String, der MITTEN im Aufbau komprimiert, kommt byte-exakt heraus.
- **Gate-Baseline rot by design** ✅ BEHOBEN: Freshness-Erwartung konditional
  (`#ifdef LISP65_STRING_ARENA` → 97, sonst 88) → BEIDE Profile GATE PASS. `pr()` schreibt
  nur noch auf stdout (kein stderr-Mix).
- **Accessor-API (Codex Device-Vorgabe)** ✅ Der Arena-Byte-Zugriff läuft jetzt durch
  `str_read_byte`/`str_write_byte`/`str_copy_to_alt`/`str_swap_buffers` — die EINZIGE Naht,
  die der Geräte-Port ersetzt (Host-Arrays sind nur die Impl derselben API).

**Codex-Entscheid Device-P2 (übernommen als Zielbild, spaeter HW-korrigiert):** Doppelpuffer
(nicht in-place), kein Bank-0, keine Bank-5/SYMPOOL-Kollision. Der erste Vorschlag
**EXT-Bank 6** war auf echter MEGA65 nicht bestueckt; der gelandete Device-Pfad nutzt deshalb
Bank 4, zwei 9,5-KB-Fenster (`cur=$2000`, `alt=$4600`, `STR_ARENA_SIZE=0x2600`) zwischen
EXT-Zellen und Disk-Scratch. In-place-slide bleibt spaetere Optimierung.

## Codex-P1.1-Review-Nachzug (2026-07-08, `21a21e0`): Fixnum-ABI-Grenze

Codex akzeptierte P1.1 (Rebase sauber, Retry-Probe PASS, `make check` bis Geräte-Full grün),
fand aber einen ABI-Randbug: `T_STR.a`/`b` sind positive Fixnums (max **16383**). Bei
`STR_ARENA_SIZE=16384` wrappte ein 16384-Byte-String die Länge nach `-16384` statt ehrlicher
OOM. BEHOBEN:

- `STR_MAX_BYTES=0x3FFF` gepinnt (`src/mem.c`); `#error` falls `STR_ARENA_SIZE > 16384`.
- `str_putc` cappt die Länge (`(str_top-offset) >= STR_MAX_BYTES` → `mem_oom`), `str_open`
  kompaktiert/OOM wenn `str_top > STR_MAX_BYTES` (leerer String startet nie mit Offset 16384).
- Host-Beweis (frische Arena): 16383-Byte-String → Länge 16383 positiv, `oom=0`;
  16384-Byte-String → Länge auf 16383 gecappt (nie negativ), `oom=1`. Als Dauergate in
  `scripts/string-arena-probe-main.c` (GATE PASS beide Profile).
- `docs/kernel-abi.md` + `reader.c`-Kommentar: „max 16383 Bytes/String, sonst ehrlicher OOM".

Aus Codex-Sicht ist der **Host-P1 damit mergefähig**.

- **OFFEN: Geräte-Port der 4 Accessoren** (Bank-6-DMA) + Footprint-Delta + HW-IDE-Gate.
  Braucht den mos-Toolchain/HW (fehlen im Claude-Worktree) — daher an Codex/T bzw. bis
  Toolchain verfügbar. Die Logik (compact/open/putc/close) bleibt unverändert.

---

## 0. P0-Ergebnis (host-gemessen, 2026-07-08)

Prototyp hinter `-DLISP65_STRING_ARENA` (Byte-Arena + mark-compact) in den C-Kern
gebaut; alle String-Call-Sites flag-gegabelt, Default-Build byte-identisch. Messung
mit `scripts/string-arena-probe-main.c` (echter Kern + einsuite-core-Blob, HEAP=48/
EXT=1024, N-Zeilen-Buffer wie getippt):

| | Baseline (char-listen) | **Arena (packed)** |
|---|---|---|
| Zellen/Zeile (~26 Zeichen) | ~40 | **~2,5** |
| OOM bei | Zeile **35** | **kein OOM bei 200** (502 Zellen frei) |
| Inhalt nach GC (print) | — | **byte-genau** (`keep`, neueste + tiefe Zeile) |

**Compaction korrekt** unter natürlicher GC-Kadenz: lebende Strings werden über die
Arena relociert (Offset in `b` aktualisiert), Inhalt byte-exakt — auch alte/tiefe
Buffer-Zeilen und ein standalone-`keep`-String über 10 GCs. **Regression:** Flag AUS
lässt vm-smoke (18/18), gc-smoke (400 Zyklen, badobj=0), output-smoke, compile-run,
repl-session grün. ⚠️ `GC_STRESS` ist mit dem Treewalk-Host-Harness inkompatibel
(nil/t schon in der Baseline — eigene Rooting-Annahmen); Korrektheit daher per
natürlicher Kadenz + `print_obj` (= Geräteverhalten).

**Geänderte Dateien (alle flag-gegabelt):** `src/mem.{c,h}` (Arena-Storage +
`str_from_bytes`/`str_from_charlist`/`str_len`/`str_byte` + `str_arena_compact` in
`gc_collect` + `str_arena_freeze` in `gc_freeze_boot` + T_STR aus der GC-CONS-
Traversierung), `src/reader.c` (`read_string`), `src/vm.c` (CALLPRIM string->list/
list->string/string-length/string-ref), `src/printer.c` (`print_string_raw`),
`src/vm_embed.c` (Boot-Literal-Strings, C-Array + Metadata-DMA-Variante).

Dies ist der echte Kapazitätsfix für den `out of memory`-Crash der on-device-IDE
(viel Tippen → REPL-Fallback). Getrennt vom gelösten Scroll-Müll (CRAM_WINDOW=1024).

---

## 1. Root Cause (host-gemessen, nicht geraten)

**Strings sind Zeichen-Listen.** Ein String ist eine `T_STR`-Zelle mit `a` = Liste
von Zeichen-Code-Fixnums (`src/reader.c:read_string`, `src/obj.h:55`). **Jedes
Zeichen kostet eine volle 8-Byte-Zelle** (auf EXT: type@0, a@2, b@4). Ein String
von *L* Zeichen = *L*+1 Zellen. Nutzdichte: 30 B Text → 320 B Heap ≈ **10×
Overhead**.

`einsuite-core` (der IDE-Core) hat `HEAP_CELLS=48` + `EXT_CELLS=1024` =
**MAX_CELLS = 1072** (Bank-0-Budget deckelt EXT, s. §5).

**Messung** (`scratchpad/oom_probe.c`: echter C-Kern eval/vm/mem/GC + einsuite-core-
Blob + exaktes Zellbudget; Buffer = Liste ~30-Zeichen-Codezeilen via `setq`,
persistiert wie getippter Inhalt):

```
nach Boot+freeze: 1023 Zellen frei
~40 Zellen pro 30-Zeichen-Zeile
OOM bei Zeile #32
```

Das deckt den Nutzerbefund („~30+ Zeilen → out of memory") **exakt**. Auf echter
HW kippt es **früher/intermittierend**, weil zusätzlich (a) die IDE-Disk-Lib Zellen
belegt und (b) der Full-Redraw Transienten alloziert (`ide-visible-frame-lines`,
`string->list` im Cursor-Render, Syntax-Spans) — feuert ein GC mitten im Render,
sind diese In-Flight-Zellen als Roots gepinnt → Peak über die Grenze.

Es ist **kein Leck und kein GC-Bug** — es ist ein hartes Zell-Kapazitätslimit,
getrieben von der 10×-Overhead-String-Repräsentation.

---

## 2. Zell- und String-Modell heute (Vertrag)

- Zelle = `{ uint8 type; obj a; obj b; }` (EXT: 8 B, davon Byte 1/6/7 Padding).
- `obj` = 16-bit getaggt: Fixnum `(n<<1)|1`, Zeiger `index<<1`, Immediates negativ.
- `T_STR`: `a` = Zeichenliste, `b` = ungenutzt. GC traversiert `a` wie eine CONS-Liste
  (`src/mem.c` 4 Stellen).
- **String-Operationen sind reine char-list-Manipulation.** `string->list` gibt
  `cell_a` **direkt** zurück (die Liste *ist* der Speicher, `src/vm.c:468`);
  `list->string` verpackt eine Liste in eine T_STR-Zelle (`src/vm.c:469`);
  `string-length`/`string-ref` laufen die Liste ab. Die IDE editiert AUSSCHLIESSLICH
  über `string->list` → cons/append → `list->string` (`lib/ide-buffer.lisp`).
- **Strings sind immutable**: jede Editierung erzeugt einen NEUEN String; kein
  in-place-mutate. ← **Schlüsseleigenschaft** für die Arena-GC (§4).

---

## 3. Zwei Repräsentations-Optionen

### Option A — Byte-Arena (Ziel: ~10–30× weniger Zellen) — EMPFOHLEN

Ein String wird EINE `T_STR`-Zelle: `a` = Länge (Fixnum), `b` = Byte-Offset in eine
**contiguous Byte-Arena** im erweiterten RAM (Bank 4, wie Disk-Scratch/Namepool).
Der Text lebt als rohe Bytes in der Arena.

- **Zellkosten: 1 Zelle/String** statt *L*+1. 30-Zeilen-Buffer: 30 Zellen +
  Zeilenlisten-conses statt ~960 Zellen. → der 30-Zeilen-Buffer belegt ~5 % statt
  ~95 % des Heaps.
- Arena-Alloc = Bump-Pointer (Strings immutable → append-only zwischen GCs).
- **GC = mark-compact der Arena** (§4).

### Option B — Chunked in-cell (Ziel: ~2×) — FALLBACK

Neue Datenzellen packen 2 Bytes in `a`, `b` = cdr → String = cdr-Kette aus
Chunk-Zellen (+ 1 Header mit Länge). 30 Zeichen: ~16 statt 31 Zellen.

- Bleibt VOLL im bestehenden Zell+GC-Modell (keine Arena, keine Kompaktierung).
- Nur ~2× — hebt die 30-Zeilen-Grenze auf ~60. Deutlich kleinerer Eingriff, aber
  löst das Problem nur halb.

**Empfehlung:** Option A. Sie ist der einzige Weg zum „echten" Fix und entlastet
sogar das Bank-0-Budget (§5). Option B nur, falls die Arena-Kompaktierung gegen den
rasiermesserdünnen Soft-Stack als zu riskant bewertet wird.

---

## 4. GC der Byte-Arena (der harte Teil — Option A)

Weil Strings **immutable und singulär besessen** sind (jede T_STR-Zelle besitzt
ihren Byte-Bereich exklusiv; kein Aliasing, keine Interior-Pointer von außen),
passt **mark-compact** perfekt und fragmentierungsfrei:

1. Cell-GC läuft wie heute und markiert lebende `T_STR`-Zellen.
2. **Arena-Compaction-Pass** (neu): über alle lebenden T_STR-Zellen iterieren, ihre
   Bytes low→high in eine frische/gleitende Arena kopieren, `b` (Offset) auf den
   neuen Ort setzen. Arena-Bump-Pointer = Ende der kompaktierten Daten.
3. Tote Strings verschwinden implizit (ihre Bytes werden nicht kopiert).

- Kopie ist O(lebende String-Bytes) per GC, in EXT via DMA (dasselbe F018-Muster wie
  ext_disk_stage). Zwischen GCs 0 Zusatzkosten (Bump-Alloc).
- **Kein** neuer Root-Typ, **kein** Interior-Pointer-Scan (Arena wird nur von
  T_STR-`b` referenziert).
- Platz: gleitende In-place-Compaction braucht keine zweite Arena; ein
  Doppelpuffer wäre einfacher, Bank 4 hat Raum (EXT-Zellen enden bei ~$6000,
  Disk-Scratch $7000 — Arena koennte in eine eigene Bank, z. B. Bank 4 oberhalb
  oder eine ungenutzte Bank; TBD mit Codex, s. §7).

---

## 5. Bank-0-Budget (kritisch)

Der Grund, warum einsuite-core auf `EXT_CELLS=1024` gepinnt ist: die Mark-Bitmap
`marks[(MAX_CELLS+7)/8]` liegt in **Bank 0**, und der Stack-Gap ist rasiermesser-
dünn (~1462 ≥ 1450, ~12 B Reserve). Gemessene Skalierung eines naiven EXT-Bumps:

| EXT_CELLS | OOM bei Zeile | Bitmap Bank-0 | Δ Bank-0 |
|---|---|---|---|
| 1024 (heute) | 32 | 134 B | — |
| 2048 | ~62 | 262 B | +128 B |
| 3072 | ~92 | 390 B | +256 B |

Jeder EXT-Bump sprengt das Gate ohne Reclaim. **Option A dreht das um:** weniger
Zellen pro String → `EXT_CELLS` kann sogar SINKEN (Bitmap schrumpft), der
Kapazitätsgewinn kommt aus der Arena (Bank 4, kein Bank-0). Netto-Bank-0-Effekt:
neutral bis positiv (Arena-Bookkeeping = wenige Bytes). Der Compaction-Code kostet
`.text` — das ist die Bank-0-Frage, die am Geräte-Footprint-Gate zu verifizieren
ist (Toolchain fehlt im Claude-Worktree — Codex/Nutzer baut).

---

## 6. Migrationsfläche (Scope)

**C-Kern:**
- `src/reader.c:read_string` — Bytes direkt in die Arena schreiben statt cons-Kette.
- `src/vm.c` CALLPRIM (`src/vm.c:457+`): `string->list` (case 1, gibt heute `cell_a`
  direkt — muss nun eine Fixnum-Liste aus Arena-Bytes **materialisieren**),
  `list->string` (case 2, Liste → Arena-Bytes), `string-length` (case 3, = `a`),
  `string-ref` (case 4, = Arena-Byte[i]), `screen-write-string` (case ~547).
- `src/printer.c:print_string_raw` — Arena-Bytes ausgeben.
- `src/vm_embed.c` (2×) — Boot-Literal-Strings (`LISP65_BC_LIT_STRING`) in die Arena.
- `src/mem.c` (4×) — T_STR NICHT mehr wie CONS traversieren; stattdessen Arena-Byte-
  Bereich beim Compaction-Pass behandeln.
- `src/eval.c` — `eval-string`/`load`/`compile-file` lesen char-für-char aus dem
  String in den Reader (`eval.c:178`); Quelle = Arena-Bytes.
- `src/obj.h:55` — Vertrag `T_STR`: `a`=Länge, `b`=Arena-Offset dokumentieren.

**Lisp (bleibt weitgehend unverändert):** die IDE nutzt `string->list`/`list->string`/
`string-ref`/`string-length` — semantisch identisch. `string->list` alloziert nun
transient eine Fixnum-Liste (kurzlebig, sofort wieder gesammelt); der PERSISTENTE
Buffer bleibt kompakt. Das ist die 10×-Steady-State-Ersparnis: Editieren expandiert
EINE Zeile transient auf char-Zellen, der gespeicherte Buffer ist gepackt.

**Werkzeuge/Oracle:** `tools/host-lisp/*` (Python-Oracle) modelliert Strings evtl.
als Python-Strings — prüfen, ob `string->list`-Semantik (frische Liste) übereinstimmt.

---

## 7. Offene Fragen an Codex

1. **Arena-Ort/-Bank:** eigene Bank vs. Bank 4 oberhalb der EXT-Zellen? Kollision mit
   Disk-Scratch ($7000) und Sympool (Bank 5) ausschliessen. Groesse/Wachstum?
2. **Compaction-Strategie:** gleitend in-place (1 Bank) vs. Doppelpuffer (2 Banks,
   simpler)? DMA-Kosten je GC unter tiefem Render akzeptabel?
3. **`.text`-Kosten der Compaction** gegen den ~12-B-Stack-Gap — passt es ohne
   Feature-Strip? (Geräte-Footprint-Gate.)
4. **Phasenplan:** Option A direkt, oder erst Option B (2×, low-risk) als Zwischen-
   Ship und Option A danach? B beseitigt den Crash bei normalem Editieren evtl. schon
   „gut genug", während A designt wird.
5. **Graceful-OOM als Sicherheitsnetz** (unabhängig): IDE lehnt Edits nahe Ceiling ab
   statt Crash-to-REPL — sinnvoll ZUSÄTZLICH zu A (Restrisiko bei sehr großen Files)?

---

## 8. Vorgeschlagener Phasenplan (nach Codex-OK)

1. **P0 — Host-Prototyp** ✅ ERLEDIGT (§0): `scripts/string-arena-probe-main.c`,
   ~16× Zellersparnis, Compaction host-verifiziert (natürliche Kadenz; GC_STRESS ist
   harness-inkompatibel).
2. **P1 — C-Kern-Umbau** hinter `-DLISP65_STRING_ARENA` ✅ GEBAUT (opt-in, Default
   byte-identisch, Host-Smokes grün). OFFEN vor Ship: (a) Arena-Storage device-tauglich
   (aktuell 2×16 KB Host-Array — auf EXT-RAM/DMA portieren, §4/§7); (b) volle
   `make check`-Runde MIT Flag inkl. Oracle-Semantik `string->list`=frische Liste;
   (c) restliche String-Sites unter `LISP65_EVAL_PRIMS`/`LISP65_FASL`/screen-write
   (eval.c) mitziehen, falls das Zielprofil sie kompiliert.
3. **P2 — Geräte-Footprint-Gate** (Codex/Nutzer): stack_gap/Bank-0/prg-file-end.
4. **P3 — HW-Abnahme**: 60+ Zeilen echter Lisp-Code tippen, Highlight, Scroll — kein
   OOM, kein Müll (PNG-verifiziert, echter Render, NICHT R1).
5. **P4** (optional): Graceful-OOM-Netz + EXT_CELLS neu justieren (evtl. senken).

---

## Anhang: Messwerkzeug

`scratchpad/oom_probe.c` — Host-C-Harness, echter Kern + einsuite-core-Blob
(`build/bytecode/stdlib-p0.c`), exaktes Zellbudget (HEAP=48/EXT=1024). Baut einen
N-Zeilen-Buffer, meldet freie Zellen + OOM je Zeile. Reproduziert OOM@32
deterministisch, misst EXT-Skalierung (2304→72, 3072→92). Kandidat für `scripts/`
als dauerhaftes Kapazitäts-Regressionswerkzeug.
```
cc -std=c99 -O1 -DLISP65_VM -DLISP65_EMBED_STDLIB -DHEAP_CELLS=48 -DEXT_CELLS=1024 \
  -DLISP65_EXT_HEAP -DLISP65_MARK_BITMAP -DLISP65_NURSERY_HYSTERESIS=192 -DMAX_SYM=576 \
  -DNAMEPOOL=8192 -DGC_ROOTS=128 -DLISP65_STDLIB_EXT_METADATA -DVM_DIR_MAX=480 \
  -DVM_CODEBUF=56 -DREPL_BUF_MAX=64 -DLISP65_VM_GLOBAL_PRIMS -Isrc -Ibuild/bytecode \
  oom_probe.c src/{eval,vm,mem,symbol,reader,printer,interrupt,screen,io,vm_embed}.c \
  build/bytecode/stdlib-p0.c -o oom_probe
```
